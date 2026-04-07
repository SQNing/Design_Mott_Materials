#!/usr/bin/env python3

from input import parse_lattice_description as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})


if __name__ == "__main__":
    raise SystemExit(main())
