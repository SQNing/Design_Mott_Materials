# CPN Workflow Readiness Checklist

Use this short checklist before treating a pseudospin-orbital `CP^(N-1)` workflow result as analysis-ready.

1. Confirm which classical method actually produced the final branch.
2. If the method is `cpn-generalized-lt`, check `solver_role` before trusting it as final.
3. Check whether magnetic-supercell refinement ran, and whether it was accepted.
4. If refinement was accepted, check which backend supplied the accepted energy comparison.
5. Compare branches using `energy/site`, not total energy.
6. If the case is a schedule-based local-ray route, review `max_linear_size` before imitating `sun-gswt-cpn` promotion behavior.
7. If the result still depends on a diagnostic-only GLT branch, treat it as a lower bound or seed rather than a final classical answer.
