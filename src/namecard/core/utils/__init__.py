"""
Core utilities for namecard processing
"""

from .phone_utils import (
    normalize_phone,
    parse_phone_info,
    is_valid_phone,
    format_phone_display,
    PHONENUMBERS_AVAILABLE,
)

__all__ = [
    "normalize_phone",
    "parse_phone_info",
    "is_valid_phone", 
    "format_phone_display",
    "PHONENUMBERS_AVAILABLE",
]
