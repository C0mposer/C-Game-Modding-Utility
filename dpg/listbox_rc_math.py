import dearpygui.dearpygui as dpg

# --- Configuration & Data Mapping ---
# Dictionary to store the data associated with each listbox tag
LISTBOX_DATA = {}
# Estimate/Test this based on your theme/font size
LISTBOX_ITEM_HEIGHT = 18 

# --- Core Logic Function ---
def calculate_clicked_index(listbox_tag):
    """Calculates the 0-based index of the listbox item under the mouse cursor."""
    
    # 1. Get Listbox and Mouse Positions
    listbox_pos = dpg.get_item_rect_min(listbox_tag)
    mouse_pos = dpg.get_mouse_pos(local=False) # Viewport coordinates

    # 2. Calculate Vertical Offset
    y_offset = mouse_pos[1] - listbox_pos[1]
    
    # 3. Check Bounds (Vertical)
    listbox_height = dpg.get_item_rect_size(listbox_tag)[1]
    if y_offset < 0 or y_offset > listbox_height:
        return -1 # Clicked outside the visible list area

    # 4. Calculate Index
    item_index = int(y_offset // LISTBOX_ITEM_HEIGHT)
    
    # 5. Validate Index against data length
    if listbox_tag in LISTBOX_DATA and 0 <= item_index < len(LISTBOX_DATA[listbox_tag]):
        return item_index
    else:
        # Clicked on empty space past the last item
        return -1

# --- Generalized Handler ---
def generic_listbox_right_click_handler(sender, app_data, user_data):
    """
    Generic callback for ALL listboxes.
    'sender' is the tag of the listbox that was clicked.
    """
    listbox_tag = sender
    item_index = calculate_clicked_index(listbox_tag)
    
    # Get mouse position for the popup
    mouse_pos = dpg.get_mouse_pos(local=False)

    if item_index != -1:
        # Success: An item was highlighted/clicked
        clicked_item = LISTBOX_DATA[listbox_tag][item_index]
        
        print(f"[{listbox_tag}] Right-clicked item index: {item_index}")
        print(f"[{listbox_tag}] Item value: {clicked_item}")

        # --- Show and Configure Popup ---
        popup_tag = "generic_popup" # Assume a single, reusable popup
        
        # Update popup content
        dpg.set_value("popup_text_tag", f"Actions for: **{clicked_item}**")
        
        # Position and show the popup
        dpg.set_item_pos(popup_tag, mouse_pos)
        dpg.show_item(popup_tag)
        
    else:
        # Failure: Clicked outside an item
        print(f"[{listbox_tag}] Right-clicked non-item area.")
        dpg.hide_item("generic_popup")