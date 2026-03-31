# Classical Methods

Expose these methods:

- `luttinger-tisza`
- `variational`
- `annealing`

Recommendation rules:

- recommend `luttinger-tisza` for single-sublattice bilinear Heisenberg or XXZ models when its assumptions hold
- otherwise recommend `variational`
- use `annealing` for frustrated or badly conditioned landscapes

If the user does not reply within ten minutes and timed continuation is supported, choose the recommendation automatically.
