#!/usr/bin/env julia

const SCRIPT_DIR = dirname(@__FILE__)
const LOCAL_DEPOT = normpath(joinpath(SCRIPT_DIR, "..", ".julia-depot"))
const LOCAL_PROJECT = normpath(joinpath(SCRIPT_DIR, "..", "..", ".julia-env-v09"))

try
    if isdir(LOCAL_DEPOT)
        empty!(DEPOT_PATH)
        push!(DEPOT_PATH, LOCAL_DEPOT)
    end
    @eval using Pkg
    if isfile(joinpath(LOCAL_PROJECT, "Project.toml"))
        Pkg.activate(LOCAL_PROJECT; io=devnull)
    end
catch
end

function emit_without_json3(status::String, code::String, message::String)
    escaped = replace(message, "\"" => "\\\"")
    println("{\"status\":\"$(status)\",\"backend\":{\"name\":\"Sunny.jl\"},\"linear_spin_wave\":{},\"error\":{\"code\":\"$(code)\",\"message\":\"$(escaped)\"}}")
end

try
    @eval using JSON3
catch
    emit_without_json3("error", "missing-json3-package", "JSON3.jl is required to parse Sunny LSWT payloads")
    exit(0)
end

function emit_payload(payload)
    println(JSON3.write(payload))
end

function error_payload(code::String, message::String)
    return Dict(
        "status" => "error",
        "backend" => Dict("name" => "Sunny.jl"),
        "linear_spin_wave" => Dict(),
        "error" => Dict("code" => code, "message" => message),
    )
end

function to_float_matrix(rows)
    matrix_rows = [Float64.(collect(row)) for row in rows]
    return reduce(vcat, (reshape(row, 1, :) for row in matrix_rows))
end

function to_float_vector(values)
    return Float64.(collect(values))
end

function build_crystal(payload)
    latvecs = to_float_matrix(payload.lattice_vectors)
    positions = [to_float_vector(position) for position in payload.positions]
    types = ["site$(index)" for index in 1:length(positions)]
    return Sunny.Crystal(latvecs, positions; types=types)
end

function build_system(crystal, payload)
    infos = [
        Int(moment.site) + 1 => Sunny.Moment(
            ;
            s=Float64(moment.spin),
            g=Float64(moment.g),
        )
        for moment in payload.moments
    ]
    supercell_shape = haskey(payload, :supercell_shape) && !isempty(payload.supercell_shape) ? Tuple(Int.(collect(payload.supercell_shape))) : (1, 1, 1)
    sys = Sunny.System(crystal, infos, :dipole; dims=supercell_shape)
    for bond in payload.bonds
        matrix = to_float_matrix(bond.exchange_matrix)
        offset = NTuple{3, Int}(Tuple(Int.(collect(bond.vector))))
        Sunny.set_exchange!(sys, matrix, Sunny.Bond(Int(bond.source) + 1, Int(bond.target) + 1, offset))
    end
    if haskey(payload, :supercell_reference_frames) && !isempty(payload.supercell_reference_frames)
        for frame in payload.supercell_reference_frames
            cell = Int.(collect(frame.cell))
            Sunny.set_dipole!(
                sys,
                to_float_vector(frame.direction),
                (cell[1] + 1, cell[2] + 1, cell[3] + 1, Int(frame.site) + 1),
            )
        end
    else
        for frame in payload.reference_frames
            Sunny.set_dipole!(sys, to_float_vector(frame.direction), (1, 1, 1, Int(frame.site) + 1))
        end
    end
    return sys
end

function build_spin_wave_theory(sys)
    try
        return Sunny.SpinWaveTheory(sys; measure=nothing)
    catch
        return Sunny.SpinWaveTheory(sys)
    end
end

function select_q_points(payload)
    q_path = haskey(payload, :q_path) ? payload.q_path : []
    q_grid = haskey(payload, :q_grid) ? payload.q_grid : []
    source = !isempty(q_path) ? q_path : q_grid
    if isempty(source)
        source = [[0.0, 0.0, 0.0]]
    end
    return [to_float_vector(point) for point in source]
end

function bands_at_q(bands, index::Int, q_count::Int)
    if isa(bands, Number)
        return [Float64(bands)]
    end
    if isa(bands, AbstractVector)
        value = bands[index]
        return isa(value, Number) ? [Float64(value)] : Float64.(vec(value))
    end
    if size(bands, 1) == q_count && size(bands, 2) != q_count
        value = bands[index, :]
    elseif size(bands, 2) == q_count && size(bands, 1) != q_count
        value = bands[:, index]
    else
        value = bands[index, :]
    end
    return isa(value, Number) ? [Float64(value)] : Float64.(vec(value))
end

function dispersion_payload(q_points, bands)
    entries = []
    for (index, q_point) in enumerate(q_points)
        band_values = bands_at_q(bands, index, length(q_points))
        push!(
            entries,
            Dict(
                "q" => q_point,
                "bands" => band_values,
                "omega" => isempty(band_values) ? 0.0 : minimum(band_values),
            ),
        )
    end
    omegas = [entry["omega"] for entry in entries]
    return Dict(
        "dispersion" => entries,
        "density_of_states" => Dict(
            "omega_min" => minimum(omegas),
            "omega_max" => maximum(omegas),
            "count" => length(omegas),
        ),
    )
end

if length(ARGS) < 1
    emit_payload(error_payload("missing-input", "Path to LSWT payload JSON is required"))
    exit(0)
end

payload = try
    JSON3.read(read(ARGS[1], String))
catch exc
    emit_payload(error_payload("invalid-input-json", sprint(showerror, exc)))
    exit(0)
end

try
    @eval using Sunny
catch
    emit_payload(error_payload("missing-sunny-package", "Sunny.jl is not available in the active Julia environment"))
    exit(0)
end

bonds = haskey(payload, :bonds) ? payload.bonds : []
reference_frames = haskey(payload, :reference_frames) ? payload.reference_frames : []
if isempty(bonds) || isempty(reference_frames)
    emit_payload(error_payload("invalid-lswt-payload", "Sunny LSWT payload must include bonds and reference frames"))
    exit(0)
end

try
    crystal = build_crystal(payload)
    sys = build_system(crystal, payload)
    swt = build_spin_wave_theory(sys)
    q_points = select_q_points(payload)
    bands = Sunny.dispersion(swt, q_points)
    emit_payload(
        Dict(
            "status" => "ok",
            "backend" => Dict("name" => "Sunny.jl"),
            "linear_spin_wave" => dispersion_payload(q_points, bands),
        ),
    )
catch exc
    emit_payload(error_payload("backend-execution-failed", sprint(showerror, exc)))
end
