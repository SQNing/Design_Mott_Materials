#!/usr/bin/env python3
import sys

from classical import lt_solver as _impl

if __name__ != "__main__":
    sys.modules[__name__] = _impl
