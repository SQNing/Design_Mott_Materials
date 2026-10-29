# Fallback Rules

- The default readable view keeps the complete Hamiltonian. A display preference
  can use that default without waiting; no small term is removed from computation.
- A missing physical convention remains needs_input. Silence and elapsed time
  never authorize projection, truncation, symmetry repair or another physical model.
- If a requested solver cannot handle every term, preserve the model and report
  unsupported with the term families and arities. Do not drop terms to continue.
- Probe dependencies before asking about them. If an explicitly requested backend
  is unavailable, report its blocker. A different backend may be suggested with
  its scope; do not label it as execution of the requested backend.
- Once the numerical budget is exhausted, keep the evidence and assess partial or
  inconclusive. Reports read saved evidence and never launch missing calculations.
