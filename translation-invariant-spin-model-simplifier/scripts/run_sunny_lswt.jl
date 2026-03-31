#!/usr/bin/env julia

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

emit_payload(
    Dict(
        "status" => "error",
        "backend" => Dict("name" => "Sunny.jl"),
        "linear_spin_wave" => Dict(),
        "error" => Dict(
            "code" => "backend-not-yet-implemented",
            "message" => "Sunny execution scaffold is present, but full LSWT model construction is not implemented yet",
        ),
    ),
)
