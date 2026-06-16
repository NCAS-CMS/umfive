"""Core parser/decoder modules (transport-agnostic)."""

from .filetype import detect_file_type
from .interpret import (
    get_extra_data_offset_and_length,
    get_type,
    get_num_data_words,
)
from .models import FileTypeInfo, RecordInfo

from .scanner import scan_ff_headers, scan_pp_headers
from .variables import build_data_variable_index

__all__ = [
    "FileTypeInfo",
    "RecordInfo",
    "detect_file_type",
    "get_type",
    "get_num_data_words",
    "get_extra_data_offset_and_length",
    "scan_pp_headers",
    "scan_ff_headers",
    "build_variable_index",
]
