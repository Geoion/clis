"""Output formatting modules for CLIS."""

from clis.output.formatter import OutputFormatter

# Lazy import to avoid circular dependencies
def get_error_display():
    from clis.output.error_display import ErrorDisplay
    return ErrorDisplay

__all__ = [
    "OutputFormatter",
    "get_error_display",
]
