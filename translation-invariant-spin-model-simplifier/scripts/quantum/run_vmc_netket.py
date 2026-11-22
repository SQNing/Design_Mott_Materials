#!/usr/bin/env python3
"""netket VMC worker for spinforge-opsum/v1 payloads (stage E).

Executed by the dedicated netket interpreter (``.venv-netket``), never by the
project python: JAX/netket live only in that venv. Reads the OpSum JSON,
builds the spin Hamiltonian exactly (no lattice shortcuts), optimizes a
Jastrow or RBM ansatz with stochastic reconfiguration, and prints one JSON
result document to stdout. Progress goes to stderr.

Usage: python run_vmc_netket.py payload.json
"""

import json
import sys

import numpy as np


def _spin_matrices(spin):
    d = int(round(2 * spin + 1))
    m = np.arange(d) - spin
    sz = np.diag(m)
    sp = np.zeros((d, d))
    for i in range(d - 1):
        mi = m[i]
        sp[i + 1, i] = np.sqrt(spin * (spin + 1) - mi * (mi + 1))
    sm = sp.T
    return {"Sx": (sp + sm) / 2.0, "Sy": (sp - sm) / 2.0j, "Sz": sz}


def build_hamiltonian(nk, spec):
    hilbert = nk.hilbert.Spin(s=spec["spin"] - 0.0, N=spec["site_count"],
                              total_sz=0.0 if spec.get("conserve_sz") else None)
    mats = _spin_matrices(spec["spin"])
    # Unique edges with one bond-operator per edge (per-color GraphOperator).
    edges = []
    bond_ops = []
    seen = set()
    for bond in spec["bonds"]:
        i, j = bond["source"], bond["target"]
        if (i, j) in seen:
            raise ValueError("duplicate bond in opsum spec")
        seen.add((i, j))
        op = None
        for op_a, op_b, coefficient in bond["terms"]:
            term = coefficient * np.kron(mats[op_a], mats[op_b])
            op = term if op is None else op + term
        edges.append([i, j])
        bond_ops.append(np.asarray(op, dtype=complex))
    # Sy.Sy-like terms are real in the Sz basis; drop the imaginary dtype when
    # nothing actually uses it so real ansatze (Jastrow/RBM float) apply.
    is_real = all(np.allclose(op.imag, 0.0) for op in bond_ops)
    dtype = float if is_real else complex
    if is_real:
        bond_ops = [op.real for op in bond_ops]
    # LocalOperator sum: GraphOperator coloring silently mis-assigns bond
    # operators when edges share the default color 0 (verified against dense
    # references), so we never use it for the Hamiltonian.
    ha = nk.operator.LocalOperator(hilbert, dtype=dtype)
    for (i, j), op in zip(edges, bond_ops):
        ha += nk.operator.LocalOperator(hilbert, op, [i, j])
    return hilbert, ha, dtype


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        spec = json.load(handle)
    params = spec["parameters"]
    import netket as nk

    hilbert, ha, dtype = build_hamiltonian(nk, spec)
    n = spec["site_count"]

    # Complex parameters are mandatory: antiferromagnetic sign structure
    # (Marshall) is learnable with complex weights, while a positive ansatz
    # falls into zero-variance excited-state traps (verified on the N=8
    # chain: real Jastrow/RBM pin to E=-1.0, an eigenvalue, instead of
    # E0=-3.651). Complex costs ~2x parameters and is harmless for
    # stoquastic models, so we use it unconditionally.
    ansatz = params.get("ansatz", "rbm")
    if ansatz == "jastrow":
        model = nk.models.Jastrow(param_dtype=complex)
    elif ansatz == "rbm":
        model = nk.models.RBM(alpha=int(params.get("rbm_alpha", 2)),
                              param_dtype=complex)
    else:
        raise ValueError("unknown ansatz: %s" % ansatz)

    # Exact enumeration beats Metropolis whenever the Hilbert space is small
    # enough (test/cross-validation scales): exact gradients, no chain
    # freezing. Above the threshold fall back to Metropolis.
    sampler_choice = params.get("sampler", "auto")
    exact_threshold = int(params.get("exact_threshold", 20000))
    use_exact = (sampler_choice == "exact"
                 or (sampler_choice == "auto"
                     and hilbert.n_states <= exact_threshold))
    if use_exact:
        sampler = nk.sampler.ExactSampler(hilbert)
    elif spec.get("conserve_sz"):
        sampler = nk.sampler.MetropolisExchange(hilbert, graph=nk.graph.Graph(
            edges=[[b["source"], b["target"]] for b in spec["bonds"]]),
            n_chains=int(params.get("n_chains", 16)))
    else:
        sampler = nk.sampler.MetropolisLocal(hilbert,
                                             n_chains=int(params.get("n_chains", 16)))
    vstate = nk.vqs.MCState(sampler, model,
                            n_samples=int(params.get("n_samples", 2048)),
                            seed=int(params.get("seed", 0)))

    optimizer = nk.optimizer.Sgd(learning_rate=float(params.get("learning_rate", 0.02)))
    sr = nk.optimizer.SR(diag_shift=float(params.get("sr_diag_shift", 0.01)))
    driver = nk.driver.VMC(ha, optimizer, variational_state=vstate,
                           preconditioner=sr)

    n_iter = int(params.get("n_iter", 300))
    energies = []

    def log_energy(step, logged, driver):
        if step % max(1, n_iter // 30) == 0 or step == n_iter - 1:
            stats = None
            if isinstance(logged, dict):
                stats = logged.get("energy") or logged.get("Energy")
            if stats is None:
                stats = getattr(driver, "energy", None)
            if stats is None:
                stats = vstate.expect(ha)
            energies.append(float(np.real(stats.mean)))
            print("iter %d: E = %.10f" % (step, energies[-1]), file=sys.stderr)
        return True

    driver.run(n_iter, callback=log_energy)

    stats = vstate.expect(ha)
    energy = float(np.real(stats.mean))
    variance = float(np.real(stats.variance))
    # R-hat style split check: re-estimate with a fresh batch of samples and
    # compare — a cheap under-optimization detector, honest by construction.
    vstate.n_samples = int(params.get("final_samples", 8192))
    final = vstate.expect(ha)
    final_energy = float(np.real(final.mean))
    final_variance = float(np.real(final.variance))
    energy_err = float(np.real(final.error_of_mean))

    var_tol = float(params.get("variance_tol", 1e-6 * n))
    converged = (final_variance < var_tol)

    observables = None
    if params.get("observables", True) and n <= int(params.get("max_corr_sites", 64)):
        mats = _spin_matrices(spec["spin"])
        dot = np.zeros((n, n))
        ops = []
        pairs = []
        for i in range(n):
            for j in range(n):
                op = None
                for a in ("Sx", "Sy", "Sz"):
                    term = np.kron(mats[a], mats[a])
                    op = term if op is None else op + term
                ops.append(np.asarray(op, dtype=complex))
                pairs.append([i, j])
        graph = nk.graph.Graph(edges=pairs)
        corr_op = nk.operator.GraphOperator(hilbert, graph=graph,
                                            bond_ops=ops, dtype=complex)
        # GraphOperator with many edge colors measures each pair separately
        # only via its matrix; instead measure the full operator sum once is
        # wrong here — netket evaluates the whole operator. Fall back to a
        # grouped measurement: sum over j for each i is still one number.
        # We therefore measure the full N x N matrix via local estimators of
        # individual pair operators built lazily.
        corr = np.zeros((n, n))
        for i in range(n):
            for j in range(i, n):
                single = nk.operator.LocalOperator(
                    hilbert, ops[i * n + j], [i, j], dtype=complex)
                value = float(np.real(vstate.expect(single).mean))
                corr[i, j] = corr[j, i] = value
        observables = {"correlation_dot_flat": corr.ravel().tolist(),
                       "correlation_layout": "row-major site x site (system order)"}

    result = {
        "status": "ok",
        "energy": final_energy,
        "energy_per_site": final_energy / n,
        "energy_stderr": energy_err,
        "variance": final_variance,
        "energy_trajectory": energies,
        "converged": converged,
        "ansatz": ansatz,
        "sampler": "exact" if use_exact else "metropolis",
        "n_parameters": int(vstate.n_parameters),
        "samples": int(params.get("final_samples", 8192)),
        "acceptance": None,
        "observables": observables,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
