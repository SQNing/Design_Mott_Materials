#!/usr/bin/env python3

from input import natural_language_parser as _impl

globals().update({name: value for name, value in vars(_impl).items() if not name.startswith("__")})
