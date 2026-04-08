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
    println("{\"status\":\"$(status)\",\"backend\":{\"name\":\"Sunny.jl\",\"mode\":\"SUN\"},\"payload_kind\":\"sun_gswt_prototype\",\"error\":{\"code\":\"$(code)\",\"message\":\"$(escaped)\"}}")
end

try
    @eval using JSON3
catch
    emit_without_json3("error", "missing-json3-package", "JSON3.jl is required to parse Sunny SUN-GSWT payloads")
    exit(0)
end

function emit_payload(payload)
    println(JSON3.write(payload))
end

function error_payload(code::String, message::String)
    return Dict(
        "status" => "error",
        "backend" => Dict("name" => "Sunny.jl", "mode" => "SUN"),
        "payload_kind" => "sun_gswt_prototype",
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

function build_crystal(payload)
    latvecs = to_float_matrix(payload.lattice_vectors)
    positions = [to_float_vector(position) for position in payload.positions]
    types = ["site$(index)" for index in 1:length(positions)]
    return Sunny.Crystal(latvecs, positions; types=types)
end

function build_system(payload)
    positions = haskey(payload, :positions) ? payload.positions : []
    if length(positions) != 1
        error("SUN-GSWT prototype backend currently supports exactly one local unit per crystallographic cell")
    end

    local_dimension = Int(payload.local_dimension)
    spin_quantum_number = 0.5 * Float64(local_dimension - 1)
    supercell_shape = haskey(payload, :supercell_shape) && !isempty(payload.supercell_shape) ? Tuple(Int.(collect(payload.supercell_shape))) : (1, 1, 1)

    crystal = build_crystal(payload)
    infos = [Sunny.SpinInfo(1; S=spin_quantum_number, g=2.0)]
    sys = Sunny.System(crystal, supercell_shape, infos, :SUN)

    for bond in payload.pair_couplings
        matrix = to_complex_matrix(bond.pair_matrix)
        offset = NTuple{3, Int}(Tuple(Int.(collect(bond.R))))
        # Keep the effective two-site operator in its full matrix form instead
        # of forcing a bilinear/biquadratic projection before symmetry checks.
        Sunny.set_pair_coupling!(sys, matrix, Sunny.Bond(1, 1, offset); extract_parts=false)
    end

    for ray in payload.initial_local_rays
        cell = Int.(collect(ray.cell))
        if length(cell) != 3
            error("Each local ray must include a three-component cell index")
        end
        amplitudes = ComplexF64[deserialize_complex(value) for value in collect(ray.vector)]
        Sunny.set_coherent!(sys, amplitudes, (cell[1] + 1, cell[2] + 1, cell[3] + 1, 1))
    end

    return sys
end

function select_q_points(payload)
    source = haskey(payload, :q_path) ? payload.q_path : []
    if isempty(source)
        source = [[0.0, 0.0, 0.0]]
    end
    return [to_float_vector(point) for point in source]
end

function bands_at_q(bands, index::Int)
    if isa(bands, Number)
        return [Float64(real(bands))]
    end
    if isa(bands, AbstractVector)
        value = bands[index]
        return isa(value, Number) ? [Float64(real(value))] : Float64.(real.(vec(value)))
    end
    value = bands[index, :]
    return isa(value, Number) ? [Float64(real(value))] : Float64.(real.(vec(value)))
end

function dispersion_payload(q_points, bands)
    entries = []
    for (index, q_point) in enumerate(q_points)
        band_values = bands_at_q(bands, index)
        push!(
            entries,
            Dict(
                "q" => q_point,
                "bands" => band_values,
                "omega" => isempty(band_values) ? 0.0 : minimum(band_values),
            ),
        )
    end
    return entries
end

function build_spin_wave_theory(sys)
    try
        return Sunny.SpinWaveTheory(sys; measure=nothing)
    catch
        return Sunny.SpinWaveTheory(sys)
    end
end

if length(ARGS) < 1
    emit_payload(error_payload("missing-input", "Path to SUN-GSWT payload JSON is required"))
    exit(0)
end

payload = try
    JSON3.read(read(ARGS[1], String))
catch exc
    emit_payload(error_payload("invalid-input-json", sprint(showerror, exc)))
    exit(0)
end

if !haskey(payload, :pair_couplings) || isempty(payload.pair_couplings)
    emit_payload(error_payload("invalid-gswt-payload", "SUN-GSWT payload must include pair couplings"))
    exit(0)
end
if !haskey(payload, :initial_local_rays) || isempty(payload.initial_local_rays)
    emit_payload(error_payload("invalid-gswt-payload", "SUN-GSWT payload must include initial local rays"))
    exit(0)
end

try
    @eval using Sunny
catch
    emit_payload(error_payload("missing-sunny-package", "Sunny.jl is not available in the active Julia environment"))
    exit(0)
end

try
    sys = build_system(payload)
    swt = build_spin_wave_theory(sys)
    q_points = select_q_points(payload)
    bands = Sunny.dispersion(swt, q_points)
    emit_payload(
        Dict(
            "status" => "ok",
            "backend" => Dict("name" => "Sunny.jl", "mode" => "SUN"),
            "payload_kind" => "sun_gswt_prototype",
            "dispersion" => dispersion_payload(q_points, bands),
            "path" => haskey(payload, :path) ? payload.path : Dict("labels" => ["Q0"], "node_indices" => [0]),
        ),
    )
catch exc
    emit_payload(error_payload("backend-execution-failed", sprint(showerror, exc)))
end
