"""Helpers for reproducing the official Sunny.jl FeI2 SU(3) example."""

OFFICIAL_FEI2_WEBSITE_PAGE_URL = (
    "https://sunnysuite.github.io/Sunny.jl/stable/examples/03_LSWT_SU3_FeI2.html"
)
OFFICIAL_FEI2_WEBSITE_SCRIPT_URL = (
    "https://sunnysuite.github.io/Sunny.jl/stable/assets/scripts/03_LSWT_SU3_FeI2.jl"
)

OFFICIAL_FEI2_TARGET_Q = [0.0, -0.25, 0.25]
OFFICIAL_FEI2_RESHAPE_MATRIX = [[1, 0, 0], [0, 1, -2], [0, 1, 2]]
OFFICIAL_FEI2_Q_PATH = [
    [0.0, 0.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.5, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0],
]
OFFICIAL_FEI2_DOMAIN_ROTATIONS = [
    ([0.0, 0.0, 1.0], 0.0),
    ([0.0, 0.0, 1.0], 2.0943951023931953),
    ([0.0, 0.0, 1.0], 4.1887902047863905),
]


def render_fei2_official_sunny_julia():
    return r"""#!/usr/bin/env julia
using Sunny, JSON3

function capture_stdout(f)
    path, io = mktemp()
    close(io)
    open(path, "w") do stream
        redirect_stdout(stream) do
            f()
        end
    end
    text = read(path, String)
    rm(path; force=true)
    return text
end

function serialize_scalar(value)
    if value isa Complex
        return Dict("real" => Float64(real(value)), "imag" => Float64(imag(value)))
    end
    if value isa Integer
        return Int(value)
    end
    if value isa AbstractFloat
        return Float64(value)
    end
    return value
end

function serialize_numeric_array(values; limit=8)
    flat = collect(Iterators.flatten(values))
    sample = [serialize_scalar(value) for value in Iterators.take(flat, limit)]
    return Dict{String, Any}(
        "size" => collect(size(values)),
        "sample" => sample,
    )
end

function serialize_real_matrix(matrix)
    return [[Float64(matrix[row, col]) for col in 1:size(matrix, 2)] for row in 1:size(matrix, 1)]
end

function serialize_complex_matrix(matrix)
    return [[serialize_scalar(matrix[row, col]) for col in 1:size(matrix, 2)] for row in 1:size(matrix, 1)]
end

function serialize_crystal(cryst)
    return Dict{String, Any}(
        "lattice_vectors" => [[serialize_scalar(value) for value in vector] for vector in eachcol(cryst.latvecs)],
        "positions" => [[serialize_scalar(value) for value in position] for position in eachcol(cryst.positions)],
        "types" => [string(value) for value in cryst.types],
    )
end

function maybe_summarize_property(container, name::Symbol)
    if !hasproperty(container, name)
        return nothing
    end
    value = getproperty(container, name)
    if value isa Number
        return serialize_scalar(value)
    end
    if value isa AbstractArray{<:Number}
        return serialize_numeric_array(value)
    end
    if value isa AbstractArray
        return Dict{String, Any}("size" => collect(size(value)), "type" => string(typeof(value)))
    end
    if value isa AbstractVector
        return Dict{String, Any}("length" => length(value), "type" => string(typeof(value)))
    end
    return string(typeof(value))
end

function summarize_result(result)
    summary = Dict{String, Any}("type" => string(typeof(result)))
    for name in (
        :disp,
        :data,
        :intensities,
        :energies,
        :qs,
        :qpts,
        :positions,
        :xticks,
        :xtick_labels,
    )
        value = maybe_summarize_property(result, name)
        if value !== nothing
            summary[string(name)] = value
        end
    end
    return summary
end

function serialize_local_rays(sys)
    shape = Int.(collect(sys.dims))
    rays = Any[]
    for x in 1:shape[1], y in 1:shape[2], z in 1:shape[3], site in 1:size(sys.coherents, 4)
        vector = sys.coherents[x, y, z, site]
        push!(
            rays,
            Dict{String, Any}(
                "cell" => [x - 1, y - 1, z - 1],
                "site" => site - 1,
                "vector" => [serialize_scalar(value) for value in vector],
            ),
        )
    end
    return Dict{String, Any}(
        "shape" => shape,
        "site_count" => Int(size(sys.coherents, 4)),
        "local_rays" => rays,
    )
end

function serialize_sun_gswt_payload(sys)
    pair_couplings = Any[]
    onsite_terms = Any[]
    for (site_index, interaction) in enumerate(sys.interactions_union)
        onsite_matrix = Matrix(interaction.onsite)
        push!(
            onsite_terms,
            Dict(
                "site" => site_index - 1,
                "matrix" => serialize_complex_matrix(onsite_matrix),
            ),
        )
        for pair in interaction.pair
            pair.isculled && continue
            push!(
                pair_couplings,
                Dict(
                    "source" => Int(getfield(pair.bond, :i)) - 1,
                    "target" => Int(getfield(pair.bond, :j)) - 1,
                    "R" => Int.(collect(getfield(pair.bond, :n))),
                    "exchange_matrix" => serialize_real_matrix(Matrix(pair.bilin)),
                ),
            )
        end
    end

    return Dict{String, Any}(
        "payload_version" => 2,
        "backend" => "Sunny.jl",
        "mode" => "SUN",
        "payload_kind" => "sun_gswt_prototype",
        "local_dimension" => 3,
        "orbital_count" => 1,
        "basis_order" => "orbital_major_spin_minor",
        "pair_basis_order" => "site_i_major_site_j_minor",
        "local_basis_labels" => ["state-0", "state-1", "state-2"],
        "lattice_vectors" => serialize_crystal(sys.crystal)["lattice_vectors"],
        "positions" => serialize_crystal(sys.crystal)["positions"],
        "pair_couplings" => pair_couplings,
        "onsite_terms" => onsite_terms,
        "initial_local_rays" => serialize_local_rays(sys)["local_rays"],
        "supercell_shape" => Int.(collect(sys.dims)),
        "classical_reference" => Dict(
            "state_kind" => "local_rays",
            "manifold" => "CP^(N-1)",
            "frame_construction" => "first-column-is-reference-ray",
            "realization_kind" => "explicit-periodic-local-rays",
            "backend_periodicity" => "supercell_shape",
        ),
        "q_path_coordinates" => "crystallographic_reciprocal_basis",
        "q_path_reference_lattice_vectors" => serialize_crystal(orig_crystal(sys))["lattice_vectors"],
        "q_path" => [[0.0,0.0,0.0], [1.0,0.0,0.0], [0.0,1.0,0.0], [1/2,0.0,0.0], [0.0,1.0,0.0], [0.0,0.0,0.0]],
        "q_path_sampling_count" => 500,
        "path" => Dict("labels" => ["G", "M1", "M2", "K", "M2", "G"], "node_indices" => [0, 1, 2, 3, 4, 5]),
    )
end

units = Units(:meV, :angstrom)
a = b = 4.05012
c = 6.75214
latvecs = lattice_vectors(a, b, c, 90, 90, 120)
positions = [[0, 0, 0], [1/3, 2/3, 1/4], [2/3, 1/3, 3/4]]
types = ["Fe", "I", "I"]
cryst = Crystal(latvecs, positions; types)
cryst = subcrystal(cryst, "Fe")

sys = System(cryst, [1 => Moment(s=1, g=2)], :SUN; seed=2)

J1pm   = -0.236
J1pmpm = -0.161
J1zpm  = -0.261
J2pm   = 0.026
J3pm   = 0.166
J′0pm  = 0.037
J′1pm  = 0.013
J′2apm = 0.068

J1zz   = -0.236
J2zz   = 0.113
J3zz   = 0.211
J′0zz  = -0.036
J′1zz  = 0.051
J′2azz = 0.073

J1xx = J1pm + J1pmpm
J1yy = J1pm - J1pmpm
J1yz = J1zpm

set_exchange!(sys, [J1xx   0.0    0.0;
                    0.0    J1yy   J1yz;
                    0.0    J1yz   J1zz], Bond(1,1,[1,0,0]))
set_exchange!(sys, [J2pm   0.0    0.0;
                    0.0    J2pm   0.0;
                    0.0    0.0    J2zz], Bond(1,1,[1,2,0]))
set_exchange!(sys, [J3pm   0.0    0.0;
                    0.0    J3pm   0.0;
                    0.0    0.0    J3zz], Bond(1,1,[2,0,0]))
set_exchange!(sys, [J′0pm  0.0    0.0;
                    0.0    J′0pm  0.0;
                    0.0    0.0    J′0zz], Bond(1,1,[0,0,1]))
set_exchange!(sys, [J′1pm  0.0    0.0;
                    0.0    J′1pm  0.0;
                    0.0    0.0    J′1zz], Bond(1,1,[1,0,1]))
set_exchange!(sys, [J′2apm 0.0    0.0;
                    0.0    J′2apm 0.0;
                    0.0    0.0    J′2azz], Bond(1,1,[1,2,1]))

D = 2.165
set_onsite_coupling!(sys, S -> -D*S[3]^2, 1)

sys = resize_supercell(sys, (4, 4, 4))
randomize_spins!(sys)
minimize_energy!(sys)

wrapped_intensities_text = capture_stdout(() -> print_wrapped_intensities(sys))
suggested_supercell_text = capture_stdout(() -> suggest_magnetic_supercell([[0, -1/4, 1/4]]))

sys_min = reshape_supercell(sys, [1 0 0; 0 1 -2; 0 1 2])
randomize_spins!(sys_min)
minimize_energy!(sys_min)

swt = SpinWaveTheory(sys_min; measure=ssf_perp(sys_min))

qs = [[0,0,0], [1,0,0], [0,1,0], [1/2,0,0], [0,1,0], [0,0,0]]
path = q_space_path(cryst, qs, 500)
res_bands = intensities_bands(swt, path)

kernel = lorentzian(fwhm=0.3)
energies = range(0, 10, 300)
rotations = [([0,0,1], n*(2π/3)) for n in 0:2]
weights = [1, 1, 1]
res_domain = domain_average(cryst, path; rotations, weights) do path_rotated
    intensities(swt, path_rotated; energies, kernel)
end

result = Dict(
    "status" => "ok",
    "sunny_version" => string(pkgversion(Sunny)),
    "website_reference" => Dict(
        "page_url" => "https://sunnysuite.github.io/Sunny.jl/stable/examples/03_LSWT_SU3_FeI2.html",
        "script_url" => "https://sunnysuite.github.io/Sunny.jl/stable/assets/scripts/03_LSWT_SU3_FeI2.jl",
    ),
    "target_q" => [0.0, -0.25, 0.25],
    "reshape_matrix" => [[1, 0, 0], [0, 1, -2], [0, 1, 2]],
    "path_qs" => [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.5, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]],
    "chemical_supercell" => [4, 4, 4],
    "chemical_energy_per_site" => Float64(energy_per_site(sys)),
    "reshaped_energy_per_site" => Float64(energy_per_site(sys_min)),
    "chemical_dims" => Int.(collect(sys.dims)),
    "reshaped_dims" => Int.(collect(sys_min.dims)),
    "chemical_crystal" => serialize_crystal(sys.crystal),
    "reshaped_crystal" => serialize_crystal(sys_min.crystal),
    "wrapped_intensities_text" => wrapped_intensities_text,
    "suggested_supercell_text" => suggested_supercell_text,
    "chemical_local_rays" => serialize_local_rays(sys),
    "reshaped_local_rays" => serialize_local_rays(sys_min),
    "reshaped_sun_gswt_payload" => serialize_sun_gswt_payload(sys_min),
    "bands_summary" => summarize_result(res_bands),
    "domain_average_summary" => summarize_result(res_domain),
)

write(ARGS[1], JSON3.write(result))
println(JSON3.write(result))
"""
