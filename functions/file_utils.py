# functions/file_utils.py
"""File path utility functions"""


def get_file_extension(file_path: str) -> str:
    """
    Get the file extension from a file path.

    Args:
        file_path: Path to the file

    Returns:
        File extension without the dot (e.g., "txt", "py")
    """
    return file_path.split(".")[-1]


def get_filename_from_path(file_path: str) -> str:
    """
    Extract just the filename from a full file path.
    Handles both forward slashes and backslashes.

    Args:
        file_path: Full path to the file

    Returns:
        Just the filename with extension
    """
    s = file_path.split("/")[-1]
    return s.split("\\")[-1]


# Backward compatibility aliases (PascalCase)
GetFileExtension = get_file_extension
GetFileNameFromPath = get_filename_from_path
