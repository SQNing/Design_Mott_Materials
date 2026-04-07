# Fallback Rules

- If the user does not choose among simplification candidates and timed continuation is supported, use the recommended candidate after the configured timeout.
- If the model cannot be mapped to spin operators, ask whether to project or truncate; if the user stays silent beyond the configured projection timeout and timed continuation is supported, apply the default combined heuristic.
- If a requested solver is outside implemented scope or required dependencies are missing, ask whether to install dependencies or relax assumptions instead of silently proceeding.
