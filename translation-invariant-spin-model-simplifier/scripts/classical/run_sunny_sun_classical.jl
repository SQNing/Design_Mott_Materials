#!/usr/bin/env julia

const SCRIPT_DIR = dirname(@__FILE__)
const LOCAL_DEPOT = normpath(joinpath(SCRIPT_DIR, "..", ".julia-depot"))
const LOCAL_PROJECT = normpath(joinpath(SCRIPT_DIR, "..", ".julia-env-v06"))

try
    if isdir(LOCAL_DEPOT)
        empty!(DEPOT_PATH)
        push!(DEPOT_PATH, LOCAL_DEPOT)
    end
    @eval using Pkg
    if isdir(LOCAL_PROJECT)
        Pkg.activate(LOCAL_PROJECT; io=devnull)
    end
catch
end

function emit_without_json3(status::String, code::String, message::String)
    escaped = replace(message, "\"" => "\\\"")
    println("{\"status\":\"$(status)\",\"backend\":{\"name\":\"Sunny.jl\",\"mode\":\"SUN\"},\"payload_kind\":\"sunny_sun_classical\",\"error\":{\"code\":\"$(code)\",\"message\":\"$(escaped)\"}}")
end

try
    @eval using JSON3
catch
    emit_without_json3("error", "missing-json3-package", "JSON3.jl is required to parse Sunny SUN classical payloads")
    exit(0)
end

function emit_payload(payload)
    println(JSON3.write(payload))
end

function error_payload(code::String, message::String)
    return Dict(
        "status" => "error",
        "backend" => Dict("name" => "Sunny.jl", "mode" => "SUN"),
        "payload_kind" => "sunny_sun_classical",
        "error" => Dict("code" => code, "message" => message),
    )
end

function to_float_vector(values)
    return Float64.(collect(values))
end

function to_float_matrix(rows)
    matrix_rows = [Float64.(collect(row)) for row in rows]
    return reduce(vcat, (reshape(row, 1, :) for row in matrix_rows))
end

function deserialize_complex(value)
    if haskey(value, :real) || haskey(value, :imag)
        return ComplexF64(Float64(get(value, :real, 0.0)), Float64(get(value, :imag, 0.0)))
    end
    return ComplexF64(value)
end

function to_complex_matrix(rows)
    matrix_rows = [[deserialize_complex(value) for value in collect(row)] for row in rows]
    return reduce(vcat, (reshape(row, 1, :) for row in matrix_rows))
end

function serialize_complex(value)
    return Dict("real" => Float64(real(value)), "imag" => Float64(imag(value)))
end

function serialize_vector(values)
    return [serialize_complex(value) for value in values]
end

function build_crystal(model)
    latvecs = to_float_matrix(model.lattice_vectors)
    positions = [to_float_vector(position) for position in model.positions]
    types = ["site$(index)" for index in 1:length(positions)]
    return Sunny.Crystal(latvecs, positions; types=types)
end

function build_system(model, supercell_shape, seed)
    positions = haskey(model, :positions) ? model.positions : []
    if length(positions) != 1
        error("SUN classical prototype backend currently supports exactly one local unit per crystallographic cell")
    end

    local_dimension = Int(model.local_dimension)
    spin_quantum_number = 0.5 * Float64(local_dimension - 1)
    crystal = build_crystal(model)
    infos = [Sunny.SpinInfo(1; S=spin_quantum_number, g=2.0)]
    sys = Sunny.System(crystal, supercell_shape, infos, :SUN; seed=seed)

    for bond in model.bond_tensors
        matrix = to_complex_matrix(bond.pair_matrix)
        offset = NTuple{3, Int}(Tuple(Int.(collect(bond.R))))
        # Keep the effective two-site operator in its full matrix form instead
        # of forcing a bilinear/biquadratic projection before classical minimization.
        Sunny.set_pair_coupling!(sys, matrix, Sunny.Bond(1, 1, offset); extract_parts=false)
    end

    return sys
end

function set_initial_state!(sys, rays)
    for ray in rays
        cell = Int.(collect(ray.cell))
        if length(cell) != 3
            error("Each local ray must include a three-component cell index")
        end
        amplitudes = ComplexF64[deserialize_complex(value) for value in collect(ray.vector)]
        Sunny.set_coherent!(sys, amplitudes, (cell[1] + 1, cell[2] + 1, cell[3] + 1, 1))
    end
end

function serialize_state(sys)
    shape = Int.(collect(sys.latsize))
    rays = Any[]
    for x in 1:shape[1], y in 1:shape[2], z in 1:shape[3]
        amplitudes = sys.coherents[x, y, z, 1]
        push!(
            rays,
            Dict(
                "cell" => [x - 1, y - 1, z - 1],
                "vector" => serialize_vector(amplitudes),
            ),
        )
    end
    return Dict("shape" => shape, "local_rays" => rays)
end

if length(ARGS) < 1
    emit_payload(error_payload("missing-input", "Path to SUN classical payload JSON is required"))
    exit(0)
end

payload = try
    JSON3.read(read(ARGS[1], String))
catch exc
    emit_payload(error_payload("invalid-input-json", sprint(showerror, exc)))
    exit(0)
end

if !haskey(payload, :model)
    emit_payload(error_payload("invalid-classical-payload", "SUN classical payload must include a `model` object"))
    exit(0)
end

model = payload.model
if get(model, :classical_manifold, nothing) != "CP^(N-1)"
    emit_payload(error_payload("invalid-classical-payload", "SUN classical payload expects a CP^(N-1) model"))
    exit(0)
end

try
    @eval using Sunny
catch
    emit_payload(error_payload("missing-sunny-package", "Sunny.jl is not available in the active Julia environment"))
    exit(0)
end

try
    supercell_shape = haskey(payload, :supercell_shape) && !isempty(payload.supercell_shape) ? Tuple(Int.(collect(payload.supercell_shape))) : (1, 1, 1)
    starts = max(1, Int(get(payload, :starts, 1)))
    seed = Int(get(payload, :seed, 0))
    initial_local_rays = haskey(payload, :initial_local_rays) ? payload.initial_local_rays : []

    best_energy = Inf
    best_state = nothing

    for start_index in 1:starts
        sys = build_system(model, supercell_shape, seed + start_index - 1)
        if start_index == 1 && !isempty(initial_local_rays)
            set_initial_state!(sys, initial_local_rays)
        else
            Sunny.randomize_spins!(sys)
        end
        Sunny.minimize_energy!(sys)
        trial_energy = Sunny.energy_per_site(sys)
        if trial_energy < best_energy
            best_energy = trial_energy
            best_state = serialize_state(sys)
        end
    end

    emit_payload(
        Dict(
            "status" => "ok",
            "backend" => Dict("name" => "Sunny.jl", "mode" => "SUN", "solver" => "minimize_energy!"),
            "payload_kind" => "sunny_sun_classical",
            "method" => "sunny-cpn-minimize",
            "energy" => best_energy,
            "supercell_shape" => collect(supercell_shape),
            "local_rays" => best_state["local_rays"],
            "starts" => starts,
            "seed" => seed,
        ),
    )
catch exc
    emit_payload(error_payload("backend-execution-failed", sprint(showerror, exc)))
end
