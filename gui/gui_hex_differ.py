import dearpygui.dearpygui as dpg
from classes.project_data.project_data import ProjectData
from services.visual_patcher_service import VisualPatcherService, PatchRegion
from typing import List, Optional
from functions.verbose_print import verbose_print

# Color scheme for hex viewer
COLOR_ORIGINAL = (180, 180, 180, 255)  # Gray for unmodified bytes
COLOR_PATCHED = (180, 180, 180, 255)   # Gray for unmodified bytes
COLOR_CAVE_SIZE = (255, 255, 100, 255)  # Yellow for the entire cave size region (both views)
COLOR_ACTUAL_CHANGE = (255, 100, 100, 255)  # Red for bytes that actually changed (patched view only)
COLOR_ADDRESS = (150, 150, 200, 255)   # Blue-ish for addresses
COLOR_ASCII = (200, 200, 150, 255)     # Yellow-ish for ASCII

BYTES_PER_ROW = 16  # Standard hex viewer width

class VisualPatcherState:
    def __init__(self):
        self.file_name: str = ""
        self.original_data: Optional[bytearray] = None
        self.patched_data: Optional[bytearray] = None
        self.patch_regions: List[PatchRegion] = []
        self.selected_patch_index: int = -1  # -1 means show all patches
        self.syncing_scroll: bool = False  # Flag to prevent infinite scroll loops

_state = VisualPatcherState()

def show_visual_patcher_window(sender, app_data, project_data: ProjectData):
    WINDOW_TAG = "visual_patcher_window"
    
    if dpg.does_item_exist(WINDOW_TAG):
        dpg.show_item(WINDOW_TAG)
        return

    # Calculate centered position for 1024x768 viewport
    window_width = 1000
    window_height = 706
    viewport_width = 1024
    viewport_height = 768
    pos_x = (viewport_width - window_width) // 2 - 8
    pos_y = (viewport_height - window_height) // 2 - 12

    with dpg.window(
        label="Hex Diff Viewer",
        tag=WINDOW_TAG,
        width=window_width,
        height=window_height,
        pos=(pos_x, pos_y),
        on_close=lambda: dpg.delete_item(WINDOW_TAG)
    ):
        
        current_build = project_data.GetCurrentBuildVersion()
        injection_files = current_build.GetInjectionFiles()
        
        # Top toolbar
        with dpg.group(horizontal=True):
            dpg.add_text("File:")
            dpg.add_combo(
                items=injection_files, 
                tag=f"{WINDOW_TAG}_file_combo",
                default_value=current_build.GetMainExecutable() or (injection_files[0] if injection_files else ""),
                width=200,
                callback=lambda s, d: _on_file_changed(project_data)
            )
            dpg.add_button(
                label="Load", 
                tag=f"{WINDOW_TAG}_load_button",
                callback=lambda: _load_file(project_data)
            )
            
            dpg.add_spacer(width=20)
            dpg.add_text("Modification:")
            dpg.add_combo(
                items=[],
                tag=f"{WINDOW_TAG}_patch_combo",
                default_value="",
                width=250,
                callback=lambda s, d: _on_patch_selection_changed()
            )
        
        dpg.add_separator()
        
        # Info bar
        with dpg.group(horizontal=True, tag=f"{WINDOW_TAG}_info_bar"):
            dpg.add_text("", tag=f"{WINDOW_TAG}_info_text")
        
        dpg.add_separator()
        
        # Main content area with side-by-side hex viewers
        with dpg.group(horizontal=True):
            # Left side - Original
            with dpg.child_window(
                width=490,
                height=550,
                tag=f"{WINDOW_TAG}_original_child"
            ):
                dpg.add_text("Original File", color=COLOR_ADDRESS)
                dpg.add_separator()
                with dpg.child_window(tag=f"{WINDOW_TAG}_original_hex", border=False):
                    dpg.add_text("Load a file to view hex data...", tag=f"{WINDOW_TAG}_original_placeholder")

            dpg.add_spacer(width=2)

            # Right side - Patched
            with dpg.child_window(
                width=490,
                height=550,
                tag=f"{WINDOW_TAG}_patched_child"
            ):
                dpg.add_text("Patched File", color=COLOR_ADDRESS)
                dpg.add_separator()
                with dpg.child_window(tag=f"{WINDOW_TAG}_patched_hex", border=False):
                    dpg.add_text("Load a file to view hex data...", tag=f"{WINDOW_TAG}_patched_placeholder")
    
    # Set up scroll synchronization using a global mouse wheel handler
    with dpg.handler_registry():
        dpg.add_mouse_wheel_handler(callback=_on_mouse_wheel_scroll)

def _on_mouse_wheel_scroll(sender, app_data):
    if _state.syncing_scroll:
        return
    
    WINDOW_TAG = "visual_patcher_window"
    original_hex_tag = f"{WINDOW_TAG}_original_hex"
    patched_hex_tag = f"{WINDOW_TAG}_patched_hex"
    
    # Check if the window exists
    if not dpg.does_item_exist(WINDOW_TAG):
        return
    
    # Check if both hex containers exist
    if not dpg.does_item_exist(original_hex_tag) or not dpg.does_item_exist(patched_hex_tag):
        return
    
    # Check if mouse is hovering over either hex viewer
    is_over_original = dpg.is_item_hovered(original_hex_tag)
    is_over_patched = dpg.is_item_hovered(patched_hex_tag)
    
    if not (is_over_original or is_over_patched):
        return
    
    try:
        _state.syncing_scroll = True
        
        # Get the scroll position from whichever one was scrolled
        if is_over_original:
            scroll_y = dpg.get_y_scroll(original_hex_tag)
            dpg.set_y_scroll(patched_hex_tag, scroll_y)
        else:  # is_over_patched
            scroll_y = dpg.get_y_scroll(patched_hex_tag)
            dpg.set_y_scroll(original_hex_tag, scroll_y)
    except Exception as e:
        print(f"Scroll sync error: {e}")
    finally:
        _state.syncing_scroll = False

def _on_file_changed(project_data: ProjectData):
    _load_file(project_data)

def _on_patch_selection_changed():
    WINDOW_TAG = "visual_patcher_window"
    patch_name = dpg.get_value(f"{WINDOW_TAG}_patch_combo")
    
    if not patch_name:
        return
    
    # Find the index of the selected patch
    _state.selected_patch_index = -1
    for i, region in enumerate(_state.patch_regions):
        if region.name == patch_name:
            _state.selected_patch_index = i
            break
    
    # Refresh the hex view with new highlighting
    if _state.original_data is not None:
        _render_hex_view()

def _load_file(project_data: ProjectData):
    WINDOW_TAG = "visual_patcher_window"
    file_name = dpg.get_value(f"{WINDOW_TAG}_file_combo")

    if not file_name:
        _update_info_text("Error: No file selected.")
        return

    _update_info_text(f"Loading '{file_name}'...")

    # Run the service
    service = VisualPatcherService(project_data)
    original_data, patched_data, patch_regions = service.generate_diff(file_name)

    if original_data is None:
        _update_info_text(f"Error: Could not load file '{file_name}'.")
        return
        
    if not patch_regions:
        _update_info_text(f"File '{file_name}' loaded. No patches target this file.")
        return

    # Update state
    _state.file_name = file_name
    _state.original_data = original_data
    _state.patched_data = patched_data
    _state.patch_regions = patch_regions
    _state.selected_patch_index = 0  # Automatically select first patch
    
    # Update patch combo box
    patch_names = [region.name for region in patch_regions]
    dpg.configure_item(f"{WINDOW_TAG}_patch_combo", items=patch_names, default_value=patch_names[0])
    
    # Update info text
    total_patched_bytes = sum(region.size for region in patch_regions)
    _update_info_text(
        f"Loaded '{file_name}' ({len(original_data):,} bytes) | "
        f"{len(patch_regions)} patch(es) | "
        f"{total_patched_bytes:,} bytes modified"
    )
    
    _render_hex_view()

def _update_info_text(text: str):
    WINDOW_TAG = "visual_patcher_window"
    dpg.set_value(f"{WINDOW_TAG}_info_text", text)

def _render_hex_view():
    WINDOW_TAG = "visual_patcher_window"
    
    if _state.original_data is None or _state.patched_data is None:
        return
    
    _clear_hex_container(f"{WINDOW_TAG}_original_hex")
    _clear_hex_container(f"{WINDOW_TAG}_patched_hex")
    
    # Determine which regions to highlight and what range to show
    if _state.selected_patch_index >= 0 and _state.selected_patch_index < len(_state.patch_regions):
        # Show the selected patch region with context
        region = _state.patch_regions[_state.selected_patch_index]
        
        # Use allocated_size if available, otherwise fall back to patch size
        display_size = region.allocated_size if hasattr(region, 'allocated_size') else region.size
        
        # Align to row boundaries
        start_offset = (region.offset // BYTES_PER_ROW) * BYTES_PER_ROW
        end_offset = ((region.offset + display_size + BYTES_PER_ROW - 1) // BYTES_PER_ROW) * BYTES_PER_ROW
        
        # Show some context before and after (5 rows = 80 bytes)
        context_rows = 5
        start_offset = max(0, start_offset - (context_rows * BYTES_PER_ROW))
        end_offset = min(len(_state.original_data), end_offset + (context_rows * BYTES_PER_ROW))
        
        highlight_regions = [region]
    else:
        # Show first 50 rows if no valid patch selected
        start_offset = 0
        end_offset = min(len(_state.original_data), 50 * BYTES_PER_ROW)
        highlight_regions = []
    
    verbose_print(f"Rendering hex view from {start_offset:X} to {end_offset:X}")
    verbose_print(f"Original data size: {len(_state.original_data)}, Patched data size: {len(_state.patched_data)}")
    
    # Render original hex view
    _render_hex_data(
        f"{WINDOW_TAG}_original_hex",
        _state.original_data,
        start_offset,
        end_offset,
        highlight_regions,
        is_patched_view=False
    )
    
    # Render patched hex view
    _render_hex_data(
        f"{WINDOW_TAG}_patched_hex",
        _state.patched_data,
        start_offset,
        end_offset,
        highlight_regions,
        is_patched_view=True
    )

def _clear_hex_container(container_tag: str):
    if dpg.does_item_exist(container_tag):
        children = dpg.get_item_children(container_tag, slot=1)
        if children:
            for child in children:
                if dpg.does_item_exist(child):
                    dpg.delete_item(child)

def _render_hex_data(
    container_tag: str,
    data: bytearray,
    start_offset: int,
    end_offset: int,
    highlight_regions: List[PatchRegion],
    is_patched_view: bool
):  
    #print(f"_render_hex_data called: container={container_tag}, is_patched={is_patched_view}, start={start_offset:X}, end={end_offset:X}")
    
    # Check if container exists
    if not dpg.does_item_exist(container_tag):
        print(f"Error: Container {container_tag} does not exist!")
        return
    
    # Build a map of bytes in the cave size region (yellow in both views)
    cave_size_bytes = set()
    # Build a map of bytes that are part of the patch data (red in patched view only)
    actually_changed_bytes = set()
    
    for region in highlight_regions:
        # Use the allocated_size (from GetSize()) for yellow highlighting
        allocated_size = region.allocated_size if hasattr(region, 'allocated_size') else region.size
        
        # Yellow highlight for entire allocated cave size in both views (if size > 0)
        if allocated_size and allocated_size > 0:
            for offset in range(region.offset, region.offset + allocated_size):
                cave_size_bytes.add(offset)
        
        # Red highlight for bytes changed within the actual patch data (patched view only)
        # This should always show, even if allocated_size is 0
        if is_patched_view and region.size > 0:
            # Mark all bytes in the patch data range (region.size) as red
            for i in range(region.size):
                offset = region.offset + i
                actually_changed_bytes.add(offset)
    
    #print(f"Cave size bytes: {len(cave_size_bytes)}, Actually changed bytes: {len(actually_changed_bytes)}")
    
    current_offset = start_offset
    row_count = 0
    
    with dpg.group(parent=container_tag):
        while current_offset < end_offset and current_offset < len(data):
            # Calculate how many bytes to show in this row
            bytes_in_row = min(BYTES_PER_ROW, len(data) - current_offset, end_offset - current_offset)
            
            with dpg.group(horizontal=True, horizontal_spacing=0):
                # Address column
                dpg.add_text(f"{current_offset:08X}: ", color=COLOR_ADDRESS)

                # Build grouped hex bytes by color for efficiency
                i = 0
                while i < bytes_in_row:
                    byte_offset = current_offset + i
                    byte_value = data[byte_offset]

                    # Determine color
                    if byte_offset in actually_changed_bytes:
                        color = COLOR_ACTUAL_CHANGE
                    elif byte_offset in cave_size_bytes:
                        color = COLOR_CAVE_SIZE
                    elif is_patched_view:
                        color = COLOR_PATCHED
                    else:
                        color = COLOR_ORIGINAL

                    # Group consecutive bytes with same color
                    hex_bytes = [f"{byte_value:02X}"]
                    j = i + 1
                    while j < bytes_in_row:
                        next_offset = current_offset + j
                        # Check if next byte has same color
                        if next_offset in actually_changed_bytes:
                            next_color = COLOR_ACTUAL_CHANGE
                        elif next_offset in cave_size_bytes:
                            next_color = COLOR_CAVE_SIZE
                        elif is_patched_view:
                            next_color = COLOR_PATCHED
                        else:
                            next_color = COLOR_ORIGINAL

                        if next_color == color:
                            hex_bytes.append(f"{data[next_offset]:02X}")
                            j += 1
                        else:
                            break

                    # Join bytes with spaces
                    # Each byte in hex_bytes becomes "XX " except we don't want trailing space in the segment
                    hex_parts = []
                    for k, byte_hex in enumerate(hex_bytes):
                        if k < len(hex_bytes) - 1:
                            hex_parts.append(f"{byte_hex} ")
                        else:
                            # Last byte in this colored segment
                            if j < bytes_in_row:
                                # More bytes follow in this row (different color), add space
                                hex_parts.append(f"{byte_hex} ")
                            else:
                                # Last byte in row, no trailing space
                                hex_parts.append(byte_hex)

                    hex_string = "".join(hex_parts)
                    dpg.add_text(hex_string, color=color)

                    i = j

                # Padding for incomplete rows (if needed)
                if bytes_in_row < BYTES_PER_ROW:
                    padding_count = BYTES_PER_ROW - bytes_in_row
                    padding_str = "   " * padding_count
                    dpg.add_text(padding_str, color=COLOR_ORIGINAL)
            
            current_offset += BYTES_PER_ROW
            row_count += 1
    
    verbose_print(f"Rendered {row_count} rows for {container_tag}")