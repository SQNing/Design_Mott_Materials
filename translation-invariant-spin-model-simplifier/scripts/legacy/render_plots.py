#!/usr/bin/env python3

from output import render_plots as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})


if __name__ == "__main__":
    raise SystemExit(main())
