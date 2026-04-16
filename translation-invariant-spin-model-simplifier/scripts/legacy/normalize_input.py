#!/usr/bin/env python3

from input import normalize_input as _normalize_input_function
from input.normalize_input import *  # noqa: F401,F403

# Preserve the historical module-level name even though `input.normalize_input`
# now also exports a function via the package root.
normalize_input = _normalize_input_function


if __name__ == "__main__":
    raise SystemExit(main())
