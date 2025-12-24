# functions/helper_funcs.py
"""
DEPRECATED: This module is being phased out in favor of focused modules.

For backward compatibility, this module re-exports functions from:
- functions.file_utils - File path operations
- functions.validators - Validation functions
- functions.ui_utils - UI helper functions

New code should import directly from the specific modules.
"""

# Re-export all functions from focused modules for backward compatibility
from functions.file_utils import (
    get_file_extension,
    get_filename_from_path,
    GetFileExtension,
    GetFileNameFromPath
)

from functions.validators import (
    is_valid_code_file,
    is_valid_asm_file,
    IsAValidCodeFile,
    IsAValidASMFile
)

from functions.ui_utils import (
    get_all_listbox_items,
    sanitize_name_no_spaces,
    GetAllListboxItems,
    SanitizeNameNoSpaces
)

__all__ = [
    # snake_case (new style)
    'get_file_extension',
    'get_filename_from_path',
    'is_valid_code_file',
    'is_valid_asm_file',
    'get_all_listbox_items',
    'sanitize_name_no_spaces',
    # PascalCase (backward compatibility)
    'GetFileExtension',
    'GetFileNameFromPath',
    'IsAValidCodeFile',
    'IsAValidASMFile',
    'GetAllListboxItems',
    'SanitizeNameNoSpaces',
]
