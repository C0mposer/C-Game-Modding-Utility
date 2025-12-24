# functions/ui_utils.py
"""UI utility functions for DearPyGui and other UI operations"""

import re
import dearpygui.dearpygui as dpg


def get_all_listbox_items(user_data):
    """
    Get all items from a DearPyGui listbox.

    Args:
        user_data: The listbox ID

    Returns:
        List of all items in the listbox
    """
    listbox_id = user_data
    config = dpg.get_item_configuration(listbox_id)
    all_items = config.get('items', [])
    print("All items in the listbox:", all_items)
    return all_items


def sanitize_name_no_spaces(name: str) -> str:
    """
    Sanitize a name by collapsing whitespace into underscores.

    Args:
        name: The name to sanitize

    Returns:
        Sanitized name with underscores instead of whitespace
    """
    if not isinstance(name, str):
        return name
    # Collapse any whitespace (space, tab, newline) into a single underscore
    sanitized = re.sub(r"\s+", "_", name.strip())
    return sanitized


# Backward compatibility aliases (PascalCase)
GetAllListboxItems = get_all_listbox_items
SanitizeNameNoSpaces = sanitize_name_no_spaces
