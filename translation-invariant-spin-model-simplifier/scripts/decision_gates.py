#!/usr/bin/env python3
import sys

from classical import decision_gates as _impl

if __name__ != "__main__":
    sys.modules[__name__] = _impl
