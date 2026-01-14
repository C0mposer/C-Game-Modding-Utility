import re
import dearpygui.dearpygui as dpg


def get_all_listbox_items(user_data):
    listbox_id = user_data
    config = dpg.get_item_configuration(listbox_id)
    all_items = config.get('items', [])
    print("All items in the listbox:", all_items)
    return all_items


def sanitize_name_no_spaces(name: str) -> str:
    if not isinstance(name, str):
        return name
    # Collapse any whitespace (space, tab, newline) into a single underscore
    sanitized = re.sub(r"\s+", "_", name.strip())
    return sanitized


# Backward compatibility aliases (PascalCase)
GetAllListboxItems = get_all_listbox_items
SanitizeNameNoSpaces = sanitize_name_no_spaces
