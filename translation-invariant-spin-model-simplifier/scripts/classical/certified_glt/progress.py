#!/usr/bin/env python3

import sys


class ProgressReporter:
    def __init__(self, stream=None):
        self._stream = stream if stream is not None else sys.stdout

    def emit(
        self,
        *,
        stage,
        processed=None,
        queued=None,
        lower_bound=None,
        upper_bound=None,
        depth=None,
        reason=None,
        **extra_fields,
    ):
        tokens = [f"[certified-glt] stage={stage}"]
        if processed is not None:
            tokens.append(f"processed={int(processed)}")
        if queued is not None:
            tokens.append(f"queued={int(queued)}")
        if lower_bound is not None:
            tokens.append(f"lower={float(lower_bound):.6g}")
        if upper_bound is not None:
            tokens.append(f"upper={float(upper_bound):.6g}")
        if lower_bound is not None and upper_bound is not None:
            tokens.append(f"gap={float(upper_bound) - float(lower_bound):.6g}")
        if depth is not None:
            tokens.append(f"depth={int(depth)}")
        if reason is not None:
            tokens.append(f"reason={reason}")
        for key in sorted(extra_fields):
            value = extra_fields[key]
            if value is None:
                continue
            tokens.append(f"{key}={value}")
        self._stream.write(" ".join(tokens) + "\n")
        self._stream.flush()
