# Stage-layer package for input normalization and parsing.

from .agent_fallback import (
    apply_agent_inferred_patch,
    build_agent_inferred,
    render_recognized_items,
)
from .document_input_protocol import build_intermediate_record, detect_input_kind, land_intermediate_record
from .normalize_input import normalize_freeform_text, normalize_input
