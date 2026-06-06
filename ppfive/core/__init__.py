"""Core parser/decoder modules (transport-agnostic)."""

from .filetype import detect_file_type
from .header import read_header
from .interpret import get_extra_data_offset_and_length, get_type_and_num_words
from .models import FileTypeInfo, RecordInfo
from .references import materialize_reference_dict
from .scanner import scan_ff_headers, scan_pp_headers
from .variables import build_variable_index

__all__ = [
    "FileTypeInfo",
    "RecordInfo",
    "detect_file_type",
    "read_header",
    "get_type_and_num_words",
    "get_extra_data_offset_and_length",
    "materialize_reference_dict",
    "scan_pp_headers",
    "scan_ff_headers",
    "build_variable_index",
]
