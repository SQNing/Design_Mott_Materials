#!/usr/bin/env python3
import sys

from cli import write_results_bundle as _impl

if __name__ != "__main__":
    sys.modules[__name__] = _impl
else:
    raise SystemExit(_impl.main())
