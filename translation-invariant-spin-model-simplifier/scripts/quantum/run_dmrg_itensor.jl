# DMRG driver (ITensor) for spinforge-opsum/v1 payloads.
#
# Usage: julia run_dmrg_itensor.jl payload.json
# Stdout: one JSON document (results). Progress goes to stderr.

using ITensors
using ITensorMPS
using JSON3
using LinearAlgebra
using Printf

# ---------------------------------------------------------------------------
# Generic spin-S site type with optional Sz conservation (QN("Sz", 2m)).

function ITensors.space(::SiteType"SpinS"; dim::Int, conserve_qns::Bool=false)
    if conserve_qns
        return [QN("Sz", q) => 1 for q in (dim - 1):-2:-(dim - 1)]
    end
    return dim
end

# Operator matrices in the descending-m basis matching ITensors.space above.
# Defined with the (OpName, SiteType, Index) signature: this is the first
# dispatch form tried by ITensors.SiteTypes (the (; dim) keyword form is
# never called with dim bound, verified against ITensors v0.9).

function _sz_matrix(dim::Int)
    s = (dim - 1) / 2
    return diagm(collect(s:-1.0:-s))
end

function _sp_matrix(dim::Int)
    s = (dim - 1) / 2
    mat = zeros(dim, dim)
    for m in (-s):(s - 1)
        # |m+1><m|: row = index of m+1, col = index of m
        mat[round(Int, s - m), round(Int, s - m + 1)] = sqrt(s * (s + 1) - m * (m + 1))
    end
    return mat
end

function _sm_matrix(dim::Int)
    s = (dim - 1) / 2
    mat = zeros(dim, dim)
    for m in (-s + 1):s
        mat[round(Int, s - m + 2), round(Int, s - m + 1)] = sqrt(s * (s + 1) - m * (m - 1))
    end
    return mat
end

ITensors.op(::OpName"Sz", ::SiteType"SpinS", s::Index) = op(_sz_matrix(dim(s)), s)
ITensors.op(::OpName"S+", ::SiteType"SpinS", s::Index) = op(_sp_matrix(dim(s)), s)
ITensors.op(::OpName"S-", ::SiteType"SpinS", s::Index) = op(_sm_matrix(dim(s)), s)
ITensors.op(::OpName"Sx", t::SiteType"SpinS", s::Index) =
    (op(OpName"S+"(), t, s) + op(OpName"S-"(), t, s)) / 2
ITensors.op(::OpName"Sy", t::SiteType"SpinS", s::Index) =
    (op(OpName"S+"(), t, s) - op(OpName"S-"(), t, s)) / 2im

# ---------------------------------------------------------------------------

function bond_entropy!(psi, b, nsite)
    if b < 1 || b >= nsite
        return 0.0
    end
    orthogonalize!(psi, b)
    li = linkind(psi, b - 1)
    si = siteind(psi, b)
    inds_l = isnothing(li) ? (si,) : (li, si)
    _, S, _ = svd(psi[b], inds_l)
    entropy = 0.0
    for n in 1:ITensors.dim(S, 1)
        p = S[n, n]^2
        p > 1e-15 && (entropy -= p * log(p))
    end
    return entropy
end

function main()
    payload = JSON3.read(read(ARGS[1], String))
    nsite = payload.site_count
    dim = payload.local_dim
    conserve = get(payload, :conserve_sz, false)

    params = payload.parameters
    nsweeps = Int(get(params, :nsweeps, 12))
    maxdim_final = Int(get(params, :maxdim, 200))
    cutoff = Float64(get(params, :cutoff, 1e-12))
    # Noise defaults to 0: ITensor's noisy eigensolver produces non
    # block-diagonal effective operators for QN-conserving MPS (eigen
    # failure, verified 2026-11-22); plain sweeps converge to machine
    # precision on the validated systems without it.
    noise = Float64(get(params, :noise, 0.0))
    e_tol = Float64(get(params, :energy_tol, 1e-10))
    var_tol = Float64(get(params, :variance_tol, 1e-8))
    trunc_tol = Float64(get(params, :truncation_tol, 1e-10))
    want_obs = get(params, :observables, true)

    sites = siteinds("SpinS", nsite; dim=dim, conserve_qns=conserve)

    os = OpSum()
    for bond in payload.bonds
        i = Int(bond.source) + 1
        j = Int(bond.target) + 1
        for term in bond.terms
            op_a, op_b, coefficient = term
            os += Float64(coefficient), String(op_a), i, String(op_b), j
        end
    end
    H = MPO(os, sites)

    if conserve
        # Neel product state: total Sz ~ 0 for even N (valid QN sector).
        states = [isodd(i) ? 1 : dim for i in 1:nsite]
        psi = MPS(sites, states)
    else
        psi = randomMPS(ComplexF64, sites, 4)
    end

    # maxdim ramp: geometric growth to maxdim_final (guarded for tiny maxdim
    # and single-sweep starved runs: log(10) > log(maxdim) is invalid).
    ramp_start = min(10, maxdim_final)
    ramp = unique(round.(Int, exp.(range(log(ramp_start), log(maxdim_final),
                                         length=min(nsweeps, 6)))))
    noise_sched = [k <= nsweeps - 3 ? noise : 0.0 for k in 1:nsweeps]

    energies = Float64[]
    maxdims = Int[]
    energy = NaN
    for k in 1:nsweeps
        sw = Sweeps(1)
        setmaxdim!(sw, ramp[min(k, length(ramp))])
        setcutoff!(sw, cutoff)
        setnoise!(sw, noise_sched[k])
        energy, psi = dmrg(H, psi, sw; outputlevel=0)
        push!(energies, energy)
        push!(maxdims, maxlinkdim(psi))
        @printf(stderr, "sweep %d: E = %.12f  maxlinkdim = %d\n", k, energy, maxdims[end])
    end

    # JSON3 cannot serialize NaN/Inf: starved runs (single sweep) legitimately
    # produce Inf deltas and possibly NaN variance; map to null (parsed as
    # None by the Python driver, which treats missing criteria as not
    # converged).
    _json_safe(x::Real) = isfinite(x) ? x : nothing
    _json_safe(x::AbstractVector) = [_json_safe(v) for v in x]
    _json_safe(x) = x

    variance = real(inner(H, psi, H, psi)) - energy^2
    delta_e = length(energies) > 1 ? abs(energies[end] - energies[end - 1]) : Inf
    psi_trunc = truncate(psi; cutoff=cutoff)
    trunc_discard = 1.0 - abs(inner(psi, psi_trunc))
    converged = (variance < var_tol) && (delta_e < e_tol) && (trunc_discard < trunc_tol)

    entropies = Float64[]
    sz_sz = nothing
    dot = nothing
    if want_obs
        entropies = [bond_entropy!(copy(psi), b, nsite) for b in 1:(nsite - 1)]
        sz = correlation_matrix(psi, "Sz", "Sz")
        pm = correlation_matrix(psi, "S+", "S-")
        full = real.(sz) .+ 0.5 .* real.(pm .+ permutedims(pm))
        sz_sz = vec(real.(sz))
        dot = vec(full)
    end

    result = Dict(
        "status" => "ok",
        "energy" => _json_safe(energy),
        "energy_per_site" => _json_safe(energy / nsite),
        "converged" => converged,
        "diagnostics" => Dict(
            "sweep_energies" => _json_safe(energies),
            "sweep_maxlinkdim" => maxdims,
            "variance" => _json_safe(variance),
            "delta_e_last_sweep" => _json_safe(delta_e),
            "truncation_discard" => _json_safe(trunc_discard),
            "criteria" => Dict("energy_tol" => e_tol, "variance_tol" => var_tol,
                               "truncation_tol" => trunc_tol),
        ),
        "entanglement" => Dict("bond_entropies" => entropies),
        "correlations" => Dict("sz_sz" => sz_sz, "dot" => dot,
                               "layout" => "row-major site x site in MPS order"),
    )
    println(stdout, JSON3.write(result))
end

main()
