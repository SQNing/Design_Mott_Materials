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
    println("{\"status\":\"$(status)\",\"backend\":{\"name\":\"Sunny.jl\",\"mode\":\"SUN\"},\"payload_kind\":\"sunny_sun_thermodynamics\",\"error\":{\"code\":\"$(code)\",\"message\":\"$(escaped)\"}}")
end

try
    @eval using JSON3
catch
    emit_without_json3("error", "missing-json3-package", "JSON3.jl is required to parse Sunny SUN thermodynamics payloads")
    exit(0)
end

function emit_payload(payload)
    println(JSON3.write(payload))
end

function progress_log(message)
    println(stderr, message)
    flush(stderr)
end

function error_payload(code::String, message::String)
    return Dict(
        "status" => "error",
        "backend" => Dict("name" => "Sunny.jl", "mode" => "SUN"),
        "payload_kind" => "sunny_sun_thermodynamics",
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

function build_crystal(model)
    latvecs = to_float_matrix(model.lattice_vectors)
    positions = [to_float_vector(position) for position in model.positions]
    types = ["site$(index)" for index in 1:length(positions)]
    # The hr-style payload already enumerates the bond list explicitly. Build a
    # P1 crystal so Sunny does not reimpose space-group symmetry and overwrite
    # distinct directional couplings during set_pair_coupling!.
    return Sunny.Crystal(latvecs, positions, 1; types=types)
end

function build_system(model, supercell_shape, seed)
    positions = haskey(model, :positions) ? model.positions : []
    if length(positions) != 1
        error("SUN thermodynamics prototype backend currently supports exactly one local unit per crystallographic cell")
    end

    local_dimension = Int(model.local_dimension)
    spin_quantum_number = 0.5 * Float64(local_dimension - 1)
    crystal = build_crystal(model)
    infos = [1 => Sunny.Moment(; s=spin_quantum_number, g=2.0)]
    sys = Sunny.System(crystal, infos, :SUN; dims=supercell_shape, seed=seed)

    for bond in model.bond_tensors
        matrix = to_complex_matrix(bond.pair_matrix)
        offset = NTuple{3, Int}(Tuple(Int.(collect(bond.R))))
        # Keep the projected two-site operator in its full matrix form rather
        # than imposing a bilinear/biquadratic or SU(N)-symmetric reduction
        # before pseudospin-orbital :SUN thermodynamics.
        Sunny.set_pair_coupling!(sys, matrix, Sunny.Bond(1, 1, offset); extract_parts=false)
    end

    return sys
end

function set_initial_state!(sys, state)
    for ray in state.local_rays
        cell = Int.(collect(ray.cell))
        amplitudes = ComplexF64[deserialize_complex(value) for value in collect(ray.vector)]
        Sunny.set_coherent!(sys, amplitudes, (cell[1] + 1, cell[2] + 1, cell[3] + 1, 1))
    end
end

function normalize_direction(payload)
    direction = haskey(payload, :field_direction) ? Float64.(collect(payload.field_direction)) : [0.0, 0.0, 1.0]
    norm = sqrt(sum(value * value for value in direction))
    norm <= 1e-12 && return [0.0, 0.0, 1.0]
    return [value / norm for value in direction]
end

function magnetization_per_site(sys, direction)
    total = 0.0
    nsites = length(Sunny.eachsite(sys))
    for site in Sunny.eachsite(sys)
        total += sum(direction[axis] * sys.dipoles[site][axis] for axis in 1:3)
    end
    return total / nsites
end

function mean_and_stderr(values)
    n = length(values)
    if n == 0
        return 0.0, 0.0, 0.0
    end
    μ = sum(values) / n
    if n == 1
        return μ, 0.0, 0.0
    end
    var = sum((value - μ)^2 for value in values) / n
    stderr = sqrt(var / n)
    return μ, stderr, var
end

function temperature_grid_from_samples(temperatures, energy_samples, magnetization_samples)
    grid = Any[]
    observables = Dict(
        "energy" => Float64[],
        "magnetization" => Float64[],
        "specific_heat" => Float64[],
        "susceptibility" => Float64[],
    )
    uncertainties = Dict(
        "energy" => Float64[],
        "magnetization" => Float64[],
        "specific_heat" => Float64[],
        "susceptibility" => Float64[],
    )

    for (index, temperature) in enumerate(temperatures)
        energies = energy_samples[index]
        magnetizations = magnetization_samples[index]
        mean_energy, energy_stderr, energy_variance = mean_and_stderr(energies)
        mean_mag, mag_stderr, mag_variance = mean_and_stderr(magnetizations)
        β = 1.0 / temperature
        specific_heat = β^2 * energy_variance
        susceptibility = β * mag_variance

        push!(grid, Dict(
            "temperature" => temperature,
            "energy" => mean_energy,
            "magnetization" => mean_mag,
            "specific_heat" => specific_heat,
            "susceptibility" => susceptibility,
            "energy_stderr" => energy_stderr,
            "magnetization_stderr" => mag_stderr,
            "specific_heat_stderr" => 0.0,
            "susceptibility_stderr" => 0.0,
        ))
        push!(observables["energy"], mean_energy)
        push!(observables["magnetization"], mean_mag)
        push!(observables["specific_heat"], specific_heat)
        push!(observables["susceptibility"], susceptibility)
        push!(uncertainties["energy"], energy_stderr)
        push!(uncertainties["magnetization"], mag_stderr)
        push!(uncertainties["specific_heat"], 0.0)
        push!(uncertainties["susceptibility"], 0.0)
    end

    return Dict(
        "grid" => grid,
        "observables" => observables,
        "uncertainties" => uncertainties,
        "reference" => Dict("normalization" => "per_spin"),
    )
end

function resolve_proposal(payload)
    proposal = String(get(payload, :proposal, "delta"))
    if proposal == "uniform"
        return proposal, Sunny.propose_uniform
    end
    if proposal == "flip"
        return proposal, Sunny.propose_flip
    end
    scale = Float64(get(payload, :proposal_scale, 0.2))
    return "delta", Sunny.propose_delta(scale)
end

function progress_interval(total_steps)
    return max(1, Int(cld(max(1, Int(total_steps)), 10)))
end

function run_local_sampler_backend(sys, payload)
    temperatures = Float64.(collect(payload.temperatures))
    sweeps = Int(get(payload, :sweeps, 100))
    burn_in = Int(get(payload, :burn_in, 50))
    measurement_interval = max(1, Int(get(payload, :measurement_interval, 1)))
    direction = normalize_direction(payload)
    proposal_name, proposal_fn = resolve_proposal(payload)

    energy_samples = [Float64[] for _ in temperatures]
    magnetization_samples = [Float64[] for _ in temperatures]
    sweep_progress_interval = progress_interval(sweeps)

    progress_log(
        "[sunny-thermo] backend=local-sampler temperatures=$(temperatures) sweeps=$(sweeps) burn_in=$(burn_in)"
    )

    for (index, temperature) in enumerate(temperatures)
        progress_log("[sunny-thermo] local-sampler temperature $(index)/$(length(temperatures)) = $(temperature)")
        sampler = Sunny.LocalSampler(; kT=temperature, nsweeps=1.0, propose=proposal_fn)
        for _ in 1:burn_in
            Sunny.step!(sys, sampler)
        end
        for sweep in 1:sweeps
            Sunny.step!(sys, sampler)
            if sweep % measurement_interval == 0
                push!(energy_samples[index], Sunny.energy_per_site(sys))
                push!(magnetization_samples[index], magnetization_per_site(sys, direction))
            end
            if sweep == sweeps || sweep % sweep_progress_interval == 0
                progress_log(
                    "[sunny-thermo] local-sampler T=$(temperature) sweep $(sweep)/$(sweeps) samples=$(length(energy_samples[index]))"
                )
            end
        end
    end

    normalized = temperature_grid_from_samples(temperatures, energy_samples, magnetization_samples)
    normalized["method"] = "sunny-local-sampler"
    normalized["sampling"] = Dict(
        "seed" => Int(get(payload, :seed, 0)),
        "proposal" => proposal_name,
        "sweeps" => sweeps,
        "burn_in" => burn_in,
        "measurement_interval" => measurement_interval,
    )
    return normalized
end

function run_parallel_tempering_backend(sys, payload)
    temperatures = Float64.(collect(payload.pt_temperatures))
    sweeps = Int(get(payload, :sweeps, 100))
    burn_in = Int(get(payload, :burn_in, 50))
    measurement_interval = max(1, Int(get(payload, :measurement_interval, 1)))
    exchange_interval = max(1, Int(get(payload, :pt_exchange_interval, 1)))
    direction = normalize_direction(payload)
    proposal_name, proposal_fn = resolve_proposal(payload)
    sweep_progress_interval = progress_interval(sweeps)

    progress_log(
        "[sunny-thermo] backend=parallel-tempering temperatures=$(temperatures) sweeps=$(sweeps) burn_in=$(burn_in) exchange_interval=$(exchange_interval)"
    )

    template_sampler = Sunny.LocalSampler(; kT=temperatures[1], nsweeps=1.0, propose=proposal_fn)
    pt = Sunny.ParallelTempering(sys, template_sampler, temperatures)
    if burn_in > 0
        progress_log("[sunny-thermo] parallel-tempering burn-in start")
        Sunny.step_ensemble!(pt, burn_in, exchange_interval)
        progress_log("[sunny-thermo] parallel-tempering burn-in complete")
    end

    energy_samples = [Float64[] for _ in temperatures]
    magnetization_samples = [Float64[] for _ in temperatures]
    for sweep in 1:sweeps
        Sunny.step_ensemble!(pt, measurement_interval, exchange_interval)
        for rank in 1:length(temperatures)
            current_sys = pt.systems[pt.system_ids[rank]]
            push!(energy_samples[rank], Sunny.energy_per_site(current_sys))
            push!(magnetization_samples[rank], magnetization_per_site(current_sys, direction))
        end
        if sweep == sweeps || sweep % sweep_progress_interval == 0
            progress_log("[sunny-thermo] parallel-tempering sweep $(sweep)/$(sweeps)")
        end
    end

    normalized = temperature_grid_from_samples(temperatures, energy_samples, magnetization_samples)
    exchange_stats = [
        Dict(
            "rank" => rank,
            "accepted" => pt.n_accept[rank],
            "attempted" => pt.n_exch[rank],
            "acceptance_rate" => pt.n_exch[rank] == 0 ? 0.0 : pt.n_accept[rank] / pt.n_exch[rank],
        )
        for rank in 1:length(pt.n_accept)
    ]
    normalized["method"] = "sunny-parallel-tempering"
    normalized["sampling"] = Dict(
        "seed" => Int(get(payload, :seed, 0)),
        "proposal" => proposal_name,
        "sweeps" => sweeps,
        "burn_in" => burn_in,
        "measurement_interval" => measurement_interval,
        "exchange_interval" => exchange_interval,
        "exchange_statistics" => exchange_stats,
    )
    return normalized
end

function free_energy_and_entropy(energies, ln_g, temperatures)
    free_energy = Float64[]
    entropy = Float64[]
    for temperature in temperatures
        weights = exp.(ln_g .- energies ./ temperature)
        Z = sum(weights)
        push!(free_energy, -temperature * log(Z))
        mean_energy = sum(energies .* weights) / Z
        push!(entropy, (mean_energy - free_energy[end]) / temperature)
    end
    return free_energy, entropy
end

function wang_landau_outputs(energies, ln_g, temperatures)
    mean_energy = Sunny.ensemble_average(energies, ln_g, energies, temperatures)
    mean_energy_sq = Sunny.ensemble_average(energies, ln_g, energies .^ 2, temperatures)
    specific_heat = ((mean_energy_sq .- mean_energy .^ 2) ./ (temperatures .^ 2))
    free_energy, entropy = free_energy_and_entropy(energies, ln_g, temperatures)

    grid = Any[]
    for index in eachindex(temperatures)
        push!(grid, Dict(
            "temperature" => temperatures[index],
            "energy" => mean_energy[index],
            "magnetization" => 0.0,
            "specific_heat" => specific_heat[index],
            "susceptibility" => 0.0,
            "free_energy" => free_energy[index],
            "entropy" => entropy[index],
        ))
    end

    thermodynamics_result = Dict(
        "method" => "sunny-wang-landau",
        "grid" => grid,
        "observables" => Dict(
            "energy" => mean_energy,
            "magnetization" => fill(0.0, length(temperatures)),
            "specific_heat" => specific_heat,
            "susceptibility" => fill(0.0, length(temperatures)),
            "free_energy" => free_energy,
            "entropy" => entropy,
        ),
        "uncertainties" => Dict(
            "energy" => fill(0.0, length(temperatures)),
            "magnetization" => fill(0.0, length(temperatures)),
            "specific_heat" => fill(0.0, length(temperatures)),
            "susceptibility" => fill(0.0, length(temperatures)),
            "free_energy" => fill(0.0, length(temperatures)),
            "entropy" => fill(0.0, length(temperatures)),
        ),
        "reference" => Dict("normalization" => "per_spin", "free_energy_reference" => "relative_dos_normalization"),
    )
    dos_result = Dict{String, Any}(
        "energy_bins" => energies,
        "log_density_of_states" => ln_g,
    )
    return thermodynamics_result, dos_result
end

function run_wang_landau_backend(sys, payload)
    temperatures = Float64.(collect(payload.temperatures))
    proposal_name, proposal_fn = resolve_proposal(payload)
    bounds = Tuple(Float64.(collect(payload.wl_bounds)))
    bin_size = Float64(payload.wl_bin_size)
    sweeps = Int(get(payload, :wl_sweeps, 100))
    ln_f = Float64(get(payload, :wl_ln_f, 1.0))
    windows = Int(get(payload, :wl_windows, 1))
    overlap = Float64(get(payload, :wl_overlap, 0.25))

    progress_log(
        "[sunny-thermo] backend=wang-landau temperatures=$(temperatures) sweeps=$(sweeps) windows=$(windows) bin_size=$(bin_size)"
    )

    if windows > 1
        window_ranges = Sunny.get_windows(bounds, windows, overlap)
        pwl = Sunny.ParallelWangLandau(; sys=sys, bin_size=bin_size, propose=proposal_fn, windows=window_ranges, ln_f=ln_f)
        progress_log("[sunny-thermo] parallel Wang-Landau start")
        Sunny.step_ensemble!(pwl, sweeps, 1)
        progress_log("[sunny-thermo] parallel Wang-Landau complete")
        energies_by_window = [Sunny.get_keys(sampler.ln_g) for sampler in pwl.samplers]
        ln_g_by_window = [Sunny.get_vals(sampler.ln_g) for sampler in pwl.samplers]
        energies, ln_g = Sunny.merge(energies_by_window, ln_g_by_window)
        thermodynamics_result, dos_result = wang_landau_outputs(energies, ln_g, temperatures)
        thermodynamics_result["sampling"] = Dict(
            "seed" => Int(get(payload, :seed, 0)),
            "proposal" => proposal_name,
            "windows" => windows,
            "ln_f" => ln_f,
            "sweeps" => sweeps,
        )
        dos_result["windows"] = [collect(window) for window in window_ranges]
        return thermodynamics_result, dos_result
    end

    wl = Sunny.WangLandau(; sys=sys, bin_size=bin_size, bounds=bounds, propose=proposal_fn, ln_f=ln_f)
    progress_log("[sunny-thermo] Wang-Landau start")
    Sunny.step_ensemble!(wl, sweeps)
    progress_log("[sunny-thermo] Wang-Landau complete")
    energies = Sunny.get_keys(wl.ln_g)
    ln_g = Sunny.get_vals(wl.ln_g)
    thermodynamics_result, dos_result = wang_landau_outputs(energies, ln_g .- minimum(ln_g), temperatures)
    thermodynamics_result["sampling"] = Dict(
        "seed" => Int(get(payload, :seed, 0)),
        "proposal" => proposal_name,
        "windows" => 1,
        "ln_f" => ln_f,
        "sweeps" => sweeps,
    )
    dos_result["windows"] = [collect(bounds)]
    return thermodynamics_result, dos_result
end

if length(ARGS) < 1
    emit_payload(error_payload("missing-input", "Path to SUN thermodynamics payload JSON is required"))
    exit(0)
end

payload = try
    JSON3.read(read(ARGS[1], String))
catch exc
    emit_payload(error_payload("invalid-input-json", sprint(showerror, exc)))
    exit(0)
end

if !haskey(payload, :model)
    emit_payload(error_payload("invalid-thermodynamics-payload", "SUN thermodynamics payload must include a `model` object"))
    exit(0)
end
if !haskey(payload, :initial_state)
    emit_payload(error_payload("invalid-thermodynamics-payload", "SUN thermodynamics payload must include an `initial_state` object"))
    exit(0)
end

backend_method = String(get(payload, :backend_method, ""))
if isempty(backend_method)
    emit_payload(error_payload("invalid-thermodynamics-payload", "SUN thermodynamics payload must include `backend_method`"))
    exit(0)
end

try
    @eval using Sunny
catch
    emit_payload(error_payload("missing-sunny-package", "Sunny.jl is not available in the active Julia environment"))
    exit(0)
end

try
    model = payload.model
    if get(model, :classical_manifold, nothing) != "CP^(N-1)"
        error("SUN thermodynamics payload expects a CP^(N-1) model")
    end

    supercell_shape = haskey(payload, :supercell_shape) && !isempty(payload.supercell_shape) ? Tuple(Int.(collect(payload.supercell_shape))) : (1, 1, 1)
    seed = Int(get(payload, :seed, 0))
    progress_log(
        "[sunny-thermo] building system backend=$(backend_method) seed=$(seed) supercell=$(collect(supercell_shape))"
    )
    sys = build_system(model, supercell_shape, seed)
    set_initial_state!(sys, payload.initial_state)
    progress_log("[sunny-thermo] initial state applied")

    thermodynamics_result = nothing
    dos_result = nothing
    if backend_method == "sunny-local-sampler"
        thermodynamics_result = run_local_sampler_backend(sys, payload)
    elseif backend_method == "sunny-parallel-tempering"
        thermodynamics_result = run_parallel_tempering_backend(sys, payload)
    elseif backend_method == "sunny-wang-landau"
        thermodynamics_result, dos_result = run_wang_landau_backend(sys, payload)
    else
        error("Unsupported SUNNY thermodynamics backend: $(backend_method)")
    end

    thermodynamics_result["backend"] = Dict("name" => "Sunny.jl", "mode" => "SUN", "sampler" => backend_method)

    response = Dict(
        "status" => "ok",
        "backend" => Dict("name" => "Sunny.jl", "mode" => "SUN", "sampler" => backend_method),
        "payload_kind" => "sunny_sun_thermodynamics",
        "thermodynamics_result" => thermodynamics_result,
    )
    if !isnothing(dos_result)
        response["dos_result"] = dos_result
    end
    emit_payload(response)
catch exc
    emit_payload(error_payload("backend-execution-failed", sprint(showerror, exc)))
end
