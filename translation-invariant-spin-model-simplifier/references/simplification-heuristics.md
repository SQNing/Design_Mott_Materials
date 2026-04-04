# Simplification Heuristics

Apply the combined default simplification in this order:

- merge symmetry-equivalent terms without changing operator content
- prune terms whose magnitude is small compared with the dominant retained coupling
- map the retained operator content onto a named template such as Heisenberg or XXZ when the pattern is recognized

Always emit 2-3 candidates, not one.
Always mark one candidate as the recommendation.
Always list dropped or merged terms explicitly.
