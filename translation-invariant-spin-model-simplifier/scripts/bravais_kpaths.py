#!/usr/bin/env python3

from common import bravais_kpaths as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
