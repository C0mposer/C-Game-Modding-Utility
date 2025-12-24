# functions/validators.py
"""Validation functions for files and data"""

from functions.file_utils import get_file_extension


def is_valid_code_file(file_path: str) -> bool:
    """
    Check if a file is a valid code file (C, C++, or assembly).

    Args:
        file_path: Path to the file

    Returns:
        True if the file has a valid code extension
    """
    file_extension = get_file_extension(file_path)
    return file_extension in ("c", "cpp", "asm", "s")


def is_valid_asm_file(file_path: str) -> bool:
    """
    Check if a file is a valid assembly file.

    Args:
        file_path: Path to the file

    Returns:
        True if the file has a valid assembly extension
    """
    file_extension = get_file_extension(file_path)
    return file_extension in ("s", "asm")


# Backward compatibility aliases (PascalCase)
IsAValidCodeFile = is_valid_code_file
IsAValidASMFile = is_valid_asm_file
