#!/usr/bin/env python3
import sys

from classical import classical_solver_driver as _impl

if __name__ != "__main__":
    sys.modules[__name__] = _impl
else:
    raise SystemExit(_impl.main())
