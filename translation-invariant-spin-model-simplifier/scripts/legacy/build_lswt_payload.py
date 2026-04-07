#!/usr/bin/env python3
import sys

from lswt import build_lswt_payload as _impl

if __name__ != "__main__":
    sys.modules[__name__] = _impl
else:
    raise SystemExit(_impl.main())
