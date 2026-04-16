# Stage-layer package for input normalization and parsing.

from .document_input_protocol import build_intermediate_record, detect_input_kind, land_intermediate_record
from .normalize_input import normalize_freeform_text, normalize_input
