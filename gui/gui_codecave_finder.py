# gui/gui_codecave_finder.py
"""
Codecave Finder Tool - Searches for empty space (null bytes) in game files
"""

import dearpygui.dearpygui as dpg
import os
from typing import List, Optional
from gui import gui_messagebox as messagebox
from classes.project_data.project_data import ProjectData
from classes.injection_targets.code_cave import Codecave
from dpg.widget_themes import SetLastItemsTheme

class CodecaveCandidate:
    """Represents a potential codecave location"""
    def __init__(self, file_offset: int, size: int, memory_address: Optional[int] = None):
        self.file_offset = file_offset
        self.size = size
        self.memory_address = memory_address

class DebugStringGroup:
    """Represents a continuous group of debug strings"""
    def __init__(self, start_offset: int, end_offset: int, string_count: int, strings: List[dict]):
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.size = end_offset - start_offset
        self.string_count = string_count
        self.strings = strings  # List of dicts with 'offset', 'text', 'length'
        self.memory_address: Optional[int] = None

        self.printf_debug_count = 0   # Number of strings in group that look like debug strings
        self.is_printf_debug = False  # True if group contains any debug/printf strings

        self.total_format_specs = 0      # Total number of printf-like format specifiers in the group
        self.debug_keyword_count = 0     # Number of strings with error/debug keywords
        self.debug_score = 0             # Weighted score used for sorting

def _is_printf_debug_string(text: str) -> tuple[bool, int, bool]:
    """
    Check if a string is likely a printf format string or an error/debug/log message.
    Returns (is_debug, format_spec_count, has_debug_keyword).

    NOTE: We deliberately do NOT treat file paths as debug strings anymore.
    """
    import re

    text_lower = text.lower()

    # Match patterns like: %s, %d, %5d, %.2f, %08x, %ld, %lld, %p, etc.
    printf_pattern = r'%[-+ 0#]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|l|ll|j|z|t|L)?[sdioxXufFeEgGaAcpn%]'
    format_specs = re.findall(printf_pattern, text)
    format_count = len([f for f in format_specs if f != '%%'])  # Exclude literal %%

    # Check for error/debug keywords
    debug_keywords = [
        'error', 'fail', 'warning', 'assert', 'debug', 'printf', 'log',
        'exception', 'fatal', 'panic', 'abort', 'trace', 'interrupt', 'timeout'
    ]
    has_debug_keyword = any(keyword in text_lower for keyword in debug_keywords)

    # It's a debug-ish string if it has printf format specifiers OR debug keywords
    is_debug = (format_count > 0) or has_debug_keyword

    return is_debug, format_count, has_debug_keyword

def show_codecave_finder_window(sender, app_data, current_project_data: ProjectData):
    """Show the codecave finder tool window"""

    # Delete existing window if it exists
    if dpg.does_item_exist("codecave_finder_window"):
        dpg.delete_item("codecave_finder_window")

    current_build = current_project_data.GetCurrentBuildVersion()

    # Get available game files
    game_files = current_build.GetInjectionFiles()

    if not game_files:
        messagebox.showinfo("No Files", "No game files available.\n\nPlease add game files first in the 'Game Files To Inject Into' tab.")
        return

    # Calculate centered position for 1024x768 viewport
    window_width = 915
    window_height = 700
    viewport_width = 1024
    viewport_height = 768
    pos_x = (viewport_width - window_width) // 2 - 10
    pos_y = (viewport_height - window_height) // 2 - 15

    # Create window
    with dpg.window(
        label="Codecave Finder",
        tag="codecave_finder_window",
        width=window_width,
        height=window_height,
        pos=[pos_x, pos_y],
        modal=False,
        no_close=False,
        no_move = True
    ):
        dpg.add_text("Find Codecaves in Game Files", color=(100, 150, 255))
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Tab bar for different finder types
        # Main tab bar for codecave finder
    # Tab bar for different finder types
        with dpg.tab_bar(tag="codecave_finder_tab_bar"):
            # Padding Finder tab (original functionality)
            with dpg.tab(label="Padding Finder", tag="padding_finder_tab"):
                _create_padding_finder_tab(current_project_data, game_files)

            # Debug String Finder tab (new functionality)
            with dpg.tab(label="Debug String Finder", tag="debug_string_finder_tab"):
                _create_debug_string_finder_tab(current_project_data, game_files)

def _create_padding_finder_tab(current_project_data: ProjectData, game_files: List[str]):
    """Create the padding finder tab (original codecave finder)"""
    dpg.add_text("Find Padding Byte Regions", color=(100, 200, 255))
    dpg.add_text("Scan for continuous groups of padding (0x00) bytes to repurpose as codecaves",
                color=(150, 150, 150))
    dpg.add_spacer(height=10)

    # File selection
    dpg.add_text("Select File to Scan:")
    dpg.add_combo(
        items=game_files,
        default_value=game_files[0] if game_files else "",
        tag="codecave_finder_file_combo",
        width=400,
        callback=_on_file_selected,
        user_data=current_project_data
    )

    dpg.add_spacer(height=5)

    # Minimum size filter
    with dpg.group(horizontal=True):
        dpg.add_text("Minimum Size (bytes):")
        dpg.add_input_int(
            tag="codecave_finder_min_size",
            default_value=150,
            width=100,
            min_value=4,
            min_clamped=True
        )
        dpg.add_text("(Only show codecaves larger than this)")

    dpg.add_spacer(height=10)

    # Scan button
    with dpg.group(horizontal=True):
        dpg.add_button(
            label="Scan for Padding",
            callback=_on_scan_clicked,
            user_data=current_project_data,
            width=200,
            height=30
        )
        dpg.add_text("", tag="codecave_finder_status", color=(150, 150, 150))

    dpg.add_separator()
    dpg.add_spacer(height=10)

    # Results section
    dpg.add_text("Found Codecaves:", color=(100, 200, 255))
    dpg.add_text("(Sorted by size, largest first)", color=(150, 150, 150))
    dpg.add_spacer(height=5)

    # Results table
    with dpg.table(
        tag="codecave_finder_results_table",
        header_row=True,
        borders_innerH=True,
        borders_outerH=True,
        borders_innerV=True,
        borders_outerV=True,
        row_background=True,
        scrollY=True,
        height=200
    ):
        # Columns
        dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=40)
        dpg.add_table_column(label="Size (bytes)", width_fixed=True, init_width_or_weight=100)
        dpg.add_table_column(label="Size (hex)", width_fixed=True, init_width_or_weight=100)
        dpg.add_table_column(label="File Offset", width_fixed=True, init_width_or_weight=120)
        dpg.add_table_column(label="Memory Address", width_fixed=True, init_width_or_weight=150)
        dpg.add_table_column(label="Section", width_fixed=True, init_width_or_weight=100)
        dpg.add_table_column(label="Actions", width_fixed=True, init_width_or_weight=200)

    dpg.add_spacer(height=10)
    dpg.add_separator()

    # Info text
    with dpg.group(horizontal=False):
        dpg.add_text("How to Use:", color=(255, 200, 100))
        dpg.add_text("1. Select the game file you want to scan")
        dpg.add_text("2. Set minimum size (default 150 bytes)")
        dpg.add_text("3. Click 'Scan for Codecaves'")
        dpg.add_text("4. Review results and click 'Add as Codecave' for any you want to use")
        dpg.add_spacer(height=5)
        dpg.add_text("WARNING:",
                    color=(200, 0, 0))
        dpg.add_text("This is not a perfect solution. A sequence of 0x00 bytes in a game file isn't always the best way to find a codecave:")
        dpg.add_text("1. It could be written to/read from in memory. Ensure that the memory region isn't being used with the built-in Verfication Tools, or manually in a memory viewer")
        dpg.add_text("2. The section of 0x00 bytes in the file may not be loaded into memory at all. Ensure that it is")
        dpg.add_text("")
        dpg.add_text("Note: Memory addresses are calculated from file offset using section maps or file offset",
                    color=(150, 150, 150))

def _create_debug_string_finder_tab(current_project_data: ProjectData, game_files: List[str]):
    """Create the debug string finder tab"""
    dpg.add_text("Find Debug String Regions", color=(100, 200, 255))
    dpg.add_text("Scan for continuous groups of debug strings that can be repurposed as codecaves",
                color=(150, 150, 150))
    dpg.add_spacer(height=5)

    # File selection
    dpg.add_text("Select File to Scan:")
    dpg.add_combo(
        items=game_files,
        default_value=game_files[0] if game_files else "",
        tag="debug_string_finder_file_combo",
        width=400
    )

    dpg.add_spacer(height=5)

    # # Filter options
    # with dpg.group(horizontal=True):
    #     dpg.add_checkbox(
    #         label="Show only Printf/Debug strings (format specifiers, paths, errors)",
    #         tag="debug_string_filter_printf",
    #         default_value=False,
    #         callback=lambda: _on_debug_string_filter_changed(current_project_data)
    #     )

    # dpg.add_spacer(height=10)

    # Scan button
    with dpg.group(horizontal=True):
        dpg.add_button(
            label="Scan for Debug Strings",
            callback=_on_debug_string_scan_clicked,
            user_data=current_project_data,
            width=200,
            height=30
        )
        dpg.add_text("", tag="debug_string_finder_status", color=(150, 150, 150))

    dpg.add_separator()
    dpg.add_spacer(height=10)

    # Results section
    dpg.add_text("Found Debug String Groups:", color=(100, 200, 255))
    dpg.add_text("(Sorted by printf/debug strings first, then by size)", color=(150, 150, 150))
    dpg.add_spacer(height=5)

    # Results table
    with dpg.table(
        tag="debug_string_finder_results_table",
        header_row=True,
        borders_innerH=True,
        borders_outerH=True,
        borders_innerV=True,
        borders_outerV=True,
        row_background=True,
        scrollY=True,
        height=200
    ):
        # Columns
        dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=20)
        dpg.add_table_column(label="Debug", width_fixed=True, init_width_or_weight=50)
        dpg.add_table_column(label="Amt", width_fixed=True, init_width_or_weight=30)
        dpg.add_table_column(label="Hex Size", width_fixed=True, init_width_or_weight=60)
        dpg.add_table_column(label="File Offset", width_fixed=True, init_width_or_weight=90)
        dpg.add_table_column(label="Memory Address", width_fixed=True, init_width_or_weight=90)
        dpg.add_table_column(label="First String Preview", width_fixed=True, init_width_or_weight=200)
        dpg.add_table_column(label="Actions", width_fixed=True, init_width_or_weight=250)

    dpg.add_spacer(height=10)
    dpg.add_separator()

    # Info text
    with dpg.group(horizontal=False):
        dpg.add_text("How to Use:", color=(255, 200, 100))
        dpg.add_text("1. Select the game file you want to scan")
        dpg.add_text("2. Click 'Scan for Debug Strings'")
        dpg.add_text("3. Review the largest continuous string regions")
        dpg.add_text("4. Click 'View Strings' to see all strings in a group. Ensure they are infact debug/error strings.")
        dpg.add_text("5. Click 'Add as Cave' to use that region of debug strings as a codecave")
        dpg.add_text("Tip: Look for strings that contain printf format specifiers: \"%d, %s, %c\", or error keywords: \"Error, Warning, Failed, Debug\"")
        #dpg.add_text("Tip: Look for strings that contain function names: \"OSSystemReset(): Failed because...\"")
        dpg.add_spacer(height=5)
        dpg.add_text("WARNING:", color=(200, 0, 0))
        dpg.add_text("Some strings may look like debug strings, but are actually needed for functionality! Ensure you properly test them.")

def _on_file_selected(sender, app_data, current_project_data: ProjectData):
    """Handle file selection change"""
    # Clear previous results
    if dpg.does_item_exist("codecave_finder_results_table"):
        # Clear table contents
        children = dpg.get_item_children("codecave_finder_results_table", slot=1)
        if children:
            for child in children:
                dpg.delete_item(child)

    dpg.set_value("codecave_finder_status", "")

def _on_scan_clicked(sender, app_data, current_project_data: ProjectData):
    """Scan selected file for codecaves"""

    filename = dpg.get_value("codecave_finder_file_combo")
    min_size = dpg.get_value("codecave_finder_min_size")

    if not filename:
        messagebox.showerror("No File", "Please select a file to scan")
        return

    # Find file path
    current_build = current_project_data.GetCurrentBuildVersion()
    file_path = current_build.FindFileInGameFolder(filename)

    if not file_path or not os.path.exists(file_path):
        dpg.set_value("codecave_finder_status", "File not found")
        messagebox.showerror("File Not Found", f"Could not find file: {filename}")
        return

    # Scan for codecaves
    try:
        candidates = _scan_file_for_codecaves(file_path, min_size)

        if not candidates:
            dpg.set_value("codecave_finder_status", "No codecaves found")
            messagebox.showinfo("No Results",
                f"No empty space found larger than {min_size} bytes.\n\n"
                "Try lowering the minimum size.")
            return

        # Calculate memory addresses
        _calculate_memory_addresses(candidates, filename, current_project_data)

        # Display results
        _display_results(candidates, filename, current_project_data, file_path)

        dpg.set_value("codecave_finder_status", f"Found {len(candidates)} padding group(s)")

    except Exception as e:
        import traceback
        dpg.set_value("codecave_finder_status", "Scan failed")
        messagebox.showerror("Scan Error", f"Error scanning file:\n\n{str(e)}\n\n{traceback.format_exc()}")

def _scan_file_for_codecaves(file_path: str, min_size: int) -> List[CodecaveCandidate]:
    """
    Scan a file for contiguous blocks of null bytes (0x00).
    Returns list of candidates sorted by size (largest first).
    """
    candidates = []

    with open(file_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)

    # Track current run of null bytes
    run_start = None
    run_length = 0

    for i in range(file_size):
        byte = file_data[i]

        if byte == 0x00:
            # Start or continue a run
            if run_start is None:
                run_start = i
                run_length = 1
            else:
                run_length += 1
        else:
            # End of run
            if run_start is not None and run_length >= min_size:
                candidates.append(CodecaveCandidate(run_start, run_length))

            run_start = None
            run_length = 0

    # Check final run
    if run_start is not None and run_length >= min_size:
        candidates.append(CodecaveCandidate(run_start, run_length))

    # Sort by size (largest first)
    candidates.sort(key=lambda c: c.size, reverse=True)

    return candidates

def _calculate_memory_addresses(candidates: List[CodecaveCandidate],
                                filename: str,
                                current_project_data: ProjectData):
    """
    Calculate memory addresses for each codecave candidate.
    Uses section maps if available, otherwise falls back to file offset.
    """
    current_build = current_project_data.GetCurrentBuildVersion()

    # Check if section map exists
    has_section_map = filename in current_build.section_maps

    if has_section_map:
        sections = current_build.section_maps[filename]

        for candidate in candidates:
            # Find which section this file offset belongs to
            for section in sections:
                section_file_start = section.file_offset
                section_file_end = section.file_offset + section.size

                if section_file_start <= candidate.file_offset < section_file_end:
                    # Calculate memory address
                    offset_within_section = candidate.file_offset - section.file_offset
                    candidate.memory_address = section.mem_start + offset_within_section
                    break
    else:
        # Fallback: Use file offset
        file_offset_str = current_build.GetInjectionFileOffset(filename)

        if file_offset_str:
            try:
                file_offset = int(file_offset_str, 16)

                for candidate in candidates:
                    # Memory address = file offset in file + base RAM offset
                    candidate.memory_address = candidate.file_offset + file_offset

            except ValueError:
                print(f"Warning: Could not parse file offset: {file_offset_str}")

def _display_results(candidates: List[CodecaveCandidate],
                     filename: str,
                     current_project_data: ProjectData,
                     file_path: str):
    """Display scan results in the table"""

    # Clear previous results
    children = dpg.get_item_children("codecave_finder_results_table", slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Display results
    for idx, candidate in enumerate(candidates, 1):
        with dpg.table_row(parent="codecave_finder_results_table"):
            # Index
            dpg.add_text(f"{idx}")

            # Size (bytes)
            dpg.add_text(f"{candidate.size}")

            # Size (hex)
            dpg.add_text(f"0x{candidate.size:X}")

            # File offset
            dpg.add_text(f"0x{candidate.file_offset:X}", color=(150, 200, 255))

            # Memory address
            if candidate.memory_address is not None:
                if platform in ["PS1", "N64", "Gamecube", "Wii"]:
                    mem_addr_str = f"0x80{candidate.memory_address:06X}"
                else:
                    mem_addr_str = f"0x{candidate.memory_address:08X}"
                dpg.add_text(mem_addr_str, color=(150, 255, 150))
            else:
                dpg.add_text("Unknown", color=(150, 150, 150))

            # Section type (if available)
            if candidate.memory_address is not None:
                section_info = current_build.GetSectionInfoForAddress(filename, candidate.memory_address)
                if section_info:
                    section_type = section_info['type'].upper()
                    dpg.add_text(section_type, color=(150, 200, 255))
                else:
                    dpg.add_text("N/A", color=(150, 150, 150))
            else:
                dpg.add_text("No map", color=(150, 150, 150))

            # Action buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="View Hex",
                    callback=_on_view_hex_clicked,
                    user_data=(candidate, filename, current_project_data, file_path),
                    small=True,
                    width=80
                )
                dpg.add_button(
                    label="Add as Codecave",
                    callback=_on_add_codecave_clicked,
                    user_data=(candidate, filename, current_project_data),
                    small=True,
                    width=110
                )
                dpg.bind_item_theme(dpg.last_item(), "add_as_cave_theme")

def _on_view_hex_clicked(sender, app_data, user_data):
    """Show hex viewer for a codecave candidate"""
    candidate, filename, current_project_data, file_path = user_data

    # Create unique window tag
    window_tag = f"hex_viewer_{candidate.file_offset}"

    # Delete existing window if it exists
    if dpg.does_item_exist(window_tag):
        dpg.delete_item(window_tag)

    # Read file data
    with open(file_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)

    # Calculate context range (show 0x100 bytes before and after)
    context_before = 0x100
    context_after = 0x100

    start_offset = max(0, candidate.file_offset - context_before)
    end_offset = min(file_size, candidate.file_offset + candidate.size + context_after)

    # Extract data region
    data_region = file_data[start_offset:end_offset]

    # Calculate codecave boundaries within the displayed region
    codecave_start_in_region = candidate.file_offset - start_offset
    codecave_end_in_region = codecave_start_in_region + candidate.size

    # Create hex viewer window
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Format memory address for title
    if candidate.memory_address is not None:
        if platform in ["PS1", "N64", "Gamecube", "Wii"]:
            mem_addr_str = f"0x80{candidate.memory_address:06X}"
        else:
            mem_addr_str = f"0x{candidate.memory_address:08X}"
    else:
        mem_addr_str = "Unknown"

    

    with dpg.window(
        label=f"Hex Viewer - Codecave at 0x{candidate.file_offset:X}",
        tag=window_tag,
        width=900,
        height=700,
        pos=[50, 10],
        modal=False,
        no_close=False,
        no_move = True
    ):
        # Header info
        dpg.add_text(f"File: {filename}", color=(100, 200, 255))
        dpg.add_text(f"File Offset: 0x{candidate.file_offset:X} | Memory Address: {mem_addr_str} | Size: 0x{candidate.size:X} ({candidate.size} bytes)",
                    color=(150, 200, 150))
        dpg.add_text(f"Showing bytes from 0x{start_offset:X} to 0x{end_offset:X}",
                    color=(150, 150, 150))
        dpg.add_separator()
        dpg.add_spacer(height=5)

        # Legend
        with dpg.group(horizontal=True):
            dpg.add_text("Legend:", color=(180, 180, 180))
            dpg.add_text("  0x00", color=(50, 200, 50))
            dpg.add_text("= Codecave Region (0x00)", color=(150, 150, 150))
            dpg.add_text("  0x00", color=(200, 200, 200))
            dpg.add_text("= Context Bytes", color=(150, 150, 150))

        dpg.add_spacer(height=5)
        dpg.add_separator()
        dpg.add_spacer(height=5)

        # Hex dump container with scrolling
        with dpg.child_window(height=550, border=True):
            _create_hex_dump(data_region, start_offset, codecave_start_in_region, codecave_end_in_region)

def _create_hex_dump(data: bytes, base_offset: int, codecave_start: int, codecave_end: int):
    """Create a formatted hex dump with color coding"""
    bytes_per_row = 16

    for row_start in range(0, len(data), bytes_per_row):
        row_data = data[row_start:row_start + bytes_per_row]
        actual_offset = base_offset + row_start

        with dpg.group(horizontal=True):
            # Offset column
            dpg.add_text(f"{actual_offset:08X}:", color=(100, 150, 255))
            dpg.add_spacer(width=10)

            # Hex bytes
            hex_group = dpg.add_group(horizontal=True)
            with dpg.group(horizontal=True, parent=hex_group):
                for i, byte in enumerate(row_data):
                    byte_pos_in_region = row_start + i

                    # Determine color based on whether this byte is in the codecave
                    if codecave_start <= byte_pos_in_region < codecave_end:
                        # Inside codecave region - bright green
                        color = (50, 200, 50)
                    else:
                        # Outside codecave - normal gray
                        color = (200, 200, 200)

                    dpg.add_text(f"{byte:02X}", color=color)

                    # Add spacing every 4 bytes for readability
                    if (i + 1) % 4 == 0 and i + 1 < len(row_data):
                        dpg.add_text(" ", color=(100, 100, 100))

            dpg.add_spacer(width=20)

            # ASCII representation
            ascii_str = ""
            for i, byte in enumerate(row_data):
                if 32 <= byte <= 126:  # Printable ASCII
                    ascii_str += chr(byte)
                else:
                    ascii_str += "."

            # Color the ASCII section
            byte_pos_in_region = row_start
            if codecave_start <= byte_pos_in_region < codecave_end:
                ascii_color = (50, 200, 50)
            else:
                ascii_color = (150, 150, 150)

            dpg.add_text(f"| {ascii_str}", color=ascii_color)

def _on_add_codecave_clicked(sender, app_data, user_data):
    """Add a codecave candidate as an actual codecave"""
    candidate, filename, current_project_data = user_data
    current_build = current_project_data.GetCurrentBuildVersion()

    # Get platform to determine alignment requirements
    platform = current_build.GetPlatform()

    # Get alignment requirement for codecaves
    from functions.alignment_validator import get_platform_alignment
    alignment = get_platform_alignment(platform, "codecave")

    # Calculate aligned file offset and adjust size
    original_file_offset = candidate.file_offset
    original_size = candidate.size

    # Round file offset UP to nearest alignment boundary
    aligned_file_offset = ((original_file_offset + alignment - 1) // alignment) * alignment

    # Calculate how many bytes we lost to alignment
    alignment_offset = aligned_file_offset - original_file_offset

    # Adjust size to account for alignment (reduce size by alignment offset)
    adjusted_size = original_size - alignment_offset

    # If adjusted size is too small, warn user
    if adjusted_size < 16:  # Minimum reasonable codecave size
        messagebox.showwarning("Alignment Issue",
            f"After applying {alignment}-byte alignment for {platform}, "
            f"this codecave would be too small ({adjusted_size} bytes).\n\n"
            "Please select a larger codecave.")
        return

    # Calculate aligned memory address if available
    aligned_memory_address = None
    if candidate.memory_address is not None:
        # Apply same alignment offset to memory address
        aligned_memory_address = candidate.memory_address + alignment_offset

    # Generate a unique name
    existing_names = current_build.GetCodeCaveNames()
    base_name = "FoundCodecave"
    counter = 1
    codecave_name = base_name

    while codecave_name in existing_names:
        codecave_name = f"{base_name}_{counter}"
        counter += 1

    # Check if this is the first codecave
    is_first_codecave = len(existing_names) == 0

    # Create codecave
    new_codecave = Codecave()
    new_codecave.SetName(codecave_name)
    new_codecave.SetInjectionFile(filename)
    new_codecave.SetSize(f"{adjusted_size:X}")

    # Set memory address (if available)
    if aligned_memory_address is not None:
        if platform in ["PS1", "N64", "Gamecube", "Wii"]:
            mem_addr_hex = f"80{aligned_memory_address:06X}"
        else:
            mem_addr_hex = f"{aligned_memory_address:X}"

        new_codecave.SetMemoryAddress(mem_addr_hex)

    # Set file address (the aligned file offset)
    new_codecave.SetInjectionFileAddress(f"{aligned_file_offset:X}")
    new_codecave.SetAutoCalculateInjectionFileAddress(False)  # We already calculated it

    # If this is the first codecave, automatically add main.c
    if is_first_codecave:
        import os
        project_folder = current_project_data.GetProjectFolder()
        main_c_path = os.path.join(project_folder, "src", "main.c")

        if os.path.exists(main_c_path):
            new_codecave.AddCodeFile(main_c_path)
            print(f"  Automatically added main.c to first codecave")

        # For PS2, also create and add syscalls.s
        if platform == "PS2":
            syscalls_s_path = os.path.join(project_folder, "asm", "syscalls.s")

            # Create syscalls.s if it doesn't exist
            if not os.path.exists(syscalls_s_path):
                os.makedirs(os.path.dirname(syscalls_s_path), exist_ok=True)
                with open(syscalls_s_path, "w") as syscalls_file:
                    syscalls_file.write(""".set noreorder
.global _print
.type _print, @function
_print:
    li $v1, 0x75
    syscall
    jr $ra
    nop


""")
                print(f"  Created: asm/syscalls.s")

            # Add syscalls.s to the codecave
            if os.path.exists(syscalls_s_path):
                new_codecave.AddCodeFile(syscalls_s_path)
                print(f"  Automatically added syscalls.s to first codecave")

    # Add to project
    current_build.AddCodeCave(new_codecave)

    print(f"Added codecave: {codecave_name}")
    print(f"  File: {filename}")
    print(f"  Platform: {platform} ({alignment}-byte alignment)")
    if alignment_offset > 0:
        print(f"  Alignment adjustment: +{alignment_offset} bytes")
    print(f"  Size: 0x{adjusted_size:X} bytes ({adjusted_size} bytes)")
    print(f"  File offset: 0x{aligned_file_offset:X}")
    if aligned_memory_address:
        print(f"  Memory address: 0x{aligned_memory_address:X}")

    # Update GUI
    from gui.gui_c_injection import UpdateCodecavesListbox, callback_codecave_selected
    UpdateCodecavesListbox(current_project_data)

    # Switch to the Modifications tab (outer tab bar)
    if dpg.does_item_exist("main_tab_bar"):
        dpg.set_value("main_tab_bar", "Modifications")

    # Switch to the C & C++ Injection tab (inner tab bar)
    if dpg.does_item_exist("modifications_tab_bar"):
        dpg.set_value("modifications_tab_bar", "C & C++ Injection")

    # Select the newly added codecave in the listbox
    if dpg.does_item_exist("codecaves_listbox"):
        dpg.set_value("codecaves_listbox", codecave_name)
        # Trigger the selection callback to load the codecave details
        callback_codecave_selected("codecaves_listbox", codecave_name, current_project_data)

    # Trigger auto-save
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    # Show success message with alignment info
    memory_str = f"0x{aligned_memory_address:X}" if aligned_memory_address is not None else "Unknown"

    alignment_msg = ""
    if alignment_offset > 0:
        alignment_msg = f"\n\nAlignment: Adjusted by +{alignment_offset} bytes for {alignment}-byte boundary"

    messagebox.showinfo("Codecave Added",
        f"Codecave added successfully!\n\n"
        f"Size: 0x{adjusted_size:X} bytes\n")

    # Close the codecave finder window
    if dpg.does_item_exist("codecave_finder_window"):
        dpg.delete_item("codecave_finder_window")

# ==================== Debug String Finder Functions ====================

# Global storage for debug string scan results
_debug_string_groups: List[DebugStringGroup] = []
_debug_string_filename: str = ""
_debug_string_file_path: str = ""
_debug_string_project_data: Optional[ProjectData] = None

def reset_codecave_finder_state():
    """Reset gui_codecave_finder global state when project closes"""
    global _debug_string_project_data, _debug_string_filename, _debug_string_file_path, _debug_string_groups
    _debug_string_project_data = None
    _debug_string_filename = ""
    _debug_string_file_path = ""
    _debug_string_groups = []

def _on_debug_string_filter_changed(current_project_data: ProjectData):
    """Handle filter checkbox change"""
    global _debug_string_groups, _debug_string_filename, _debug_string_file_path, _debug_string_project_data

    if not _debug_string_groups:
        return

    # Re-display with filter applied
    _display_debug_string_results(_debug_string_groups, _debug_string_filename,
                                   _debug_string_project_data, _debug_string_file_path)

def _on_debug_string_scan_clicked(sender, app_data, current_project_data: ProjectData):
    """Scan selected file for debug string groups"""
    global _debug_string_groups, _debug_string_filename, _debug_string_file_path, _debug_string_project_data

    filename = dpg.get_value("debug_string_finder_file_combo")

    if not filename:
        messagebox.showerror("No File", "Please select a file to scan")
        return

    # Find file path
    current_build = current_project_data.GetCurrentBuildVersion()
    file_path = current_build.FindFileInGameFolder(filename)

    if not file_path or not os.path.exists(file_path):
        dpg.set_value("debug_string_finder_status", "File not found")
        messagebox.showerror("File Not Found", f"Could not find file: {filename}")
        return

    dpg.set_value("debug_string_finder_status", "Scanning...")

    # Scan for debug string groups
    try:
        groups = _scan_file_for_debug_string_groups(file_path)

        if not groups:
            dpg.set_value("debug_string_finder_status", "No debug string groups found")
            messagebox.showinfo("No Results",
                "No continuous debug string regions found.\n\n"
                "The file may not contain debug strings.")
            return

        # Calculate memory addresses for groups
        _calculate_debug_string_memory_addresses(groups, filename, current_project_data)

        # Store results globally for filtering
        _debug_string_groups = groups
        _debug_string_filename = filename
        _debug_string_file_path = file_path
        _debug_string_project_data = current_project_data

        # Display results
        _display_debug_string_results(groups, filename, current_project_data, file_path)

        dpg.set_value("debug_string_finder_status", f"Found {len(groups)} debug string group(s)")

    except Exception as e:
        import traceback
        dpg.set_value("debug_string_finder_status", "Scan failed")
        messagebox.showerror("Scan Error", f"Error scanning file:\n\n{str(e)}\n\n{traceback.format_exc()}")

def _scan_file_for_debug_string_groups(file_path: str) -> List[DebugStringGroup]:
    """
    Scan a file for continuous groups of null-terminated strings.
    Returns list of groups sorted by:
      1. Whether they contain at least one debug/printf-style string
      2. Size (largest first)
    """
    with open(file_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)

    # First, find all individual strings
    all_strings = []
    current_string = []
    string_start = None
    min_length = 4  # Minimum string length to consider

    i = 0
    while i < file_size:
        byte = file_data[i]

        # Printable ASCII range (plus common whitespace)
        if (32 <= byte <= 126) or byte in [9, 10, 13]:  # Tab, LF, CR
            if string_start is None:
                string_start = i
            current_string.append(byte)
            i += 1
        elif byte == 0x00:
            # NULL TERMINATOR
            if current_string and len(current_string) >= min_length:
                try:
                    text = bytes(current_string).decode('ascii', errors='ignore')
                    all_strings.append({
                        'offset': string_start,
                        'text': text,
                        'length': len(current_string) + 1,  # Include null terminator
                        'end_pos': i + 1
                    })
                except Exception:
                    pass

            current_string = []
            string_start = None
            i += 1
        else:
            # Non-printable, non-null
            current_string = []
            string_start = None
            i += 1

    # Now group contiguous strings together
    if not all_strings:
        return []

    groups: List[DebugStringGroup] = []
    current_group_strings = [all_strings[0]]
    max_gap = 16  # Maximum gap between strings to still consider them part of the same group
                  # This gap includes all null bytes (0x00) between strings

    for i in range(1, len(all_strings)):
        prev_string = all_strings[i - 1]
        curr_string = all_strings[i]

        # Check gap between this string and previous (includes all null padding bytes)
        gap = curr_string['offset'] - prev_string['end_pos']

        if gap <= max_gap:
            # Part of same group
            current_group_strings.append(curr_string)
        else:
            # Start new group (but first save current group if it has multiple strings)
            if len(current_group_strings) >= 2:  # Only save groups with 2+ strings
                first_string = current_group_strings[0]
                last_string = current_group_strings[-1]
                groups.append(DebugStringGroup(
                    start_offset=first_string['offset'],
                    end_offset=last_string['end_pos'],
                    string_count=len(current_group_strings),
                    strings=current_group_strings.copy()
                ))

            current_group_strings = [curr_string]

    # Don't forget the last group
    if len(current_group_strings) >= 2:
        first_string = current_group_strings[0]
        last_string = current_group_strings[-1]
        groups.append(DebugStringGroup(
            start_offset=first_string['offset'],
            end_offset=last_string['end_pos'],
            string_count=len(current_group_strings),
            strings=current_group_strings.copy()
        ))

    # Categorize each group and compute some stats
    for group in groups:
        total_format_specs = 0
        printf_debug_count = 0      # number of debug-ish strings
        debug_keyword_count = 0
        debug_score = 0

        for string in group.strings:
            is_debug, format_count, has_keyword = _is_printf_debug_string(string['text'])

            if is_debug:
                printf_debug_count += 1
                total_format_specs += format_count
                if has_keyword:
                    debug_keyword_count += 1

                # Basic scoring
                per_string_score = 1
                per_string_score += format_count * 2
                if has_keyword:
                    per_string_score += 3
                debug_score += per_string_score

        group.printf_debug_count = printf_debug_count
        group.total_format_specs = total_format_specs
        group.debug_keyword_count = debug_keyword_count
        group.debug_score = debug_score

        # "Has at least one debug string" flag
        group.is_printf_debug = printf_debug_count > 0

    # Sort by:
    # Has at least one debug string
    # Size (largest first)
    groups.sort(
        key=lambda g: (g.printf_debug_count > 0, g.size),
        reverse=True
    )

    return groups



def _calculate_debug_string_memory_addresses(groups: List[DebugStringGroup], filename: str, current_project_data: ProjectData):
    current_build = current_project_data.GetCurrentBuildVersion()

    # Check if section map exists
    has_section_map = filename in current_build.section_maps

    if has_section_map:
        sections = current_build.section_maps[filename]

        # Find which section this file offset belongs to
        for group in groups:
            for section in sections:
                section_file_start = section.file_offset
                section_file_end = section.file_offset + section.size

                if section_file_start <= group.start_offset < section_file_end:
                    # Calculate memory address
                    offset_within_section = group.start_offset - section.file_offset
                    group.memory_address = section.mem_start + offset_within_section
                    break
    else:
        # Fallback: Use file offset
        file_offset_str = current_build.GetInjectionFileOffset(filename)

        if file_offset_str:
            try:
                file_offset = int(file_offset_str, 16)

                for group in groups:
                    # Memory address = file offset in file + base RAM offset
                    group.memory_address = group.start_offset + file_offset

            except ValueError:
                print(f"Warning: Could not parse file offset: {file_offset_str}")

def _display_debug_string_results(groups: List[DebugStringGroup], filename: str, current_project_data: ProjectData, file_path: str):
    """Display debug string group results in the table"""

    # Clear previous results
    children = dpg.get_item_children("debug_string_finder_results_table", slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Apply filter if checked
    filter_printf = dpg.get_value("debug_string_filter_printf") if dpg.does_item_exist("debug_string_filter_printf") else False

    if filter_printf:
        filtered_groups = [g for g in groups if g.is_printf_debug]
    else:
        filtered_groups = groups

    # Display results
    for idx, group in enumerate(filtered_groups, 1):
        with dpg.table_row(parent="debug_string_finder_results_table"):
            # Index
            dpg.add_text(f"{idx}")

            # Printf/Debug count with color coding
            if group.printf_debug_count > 0:
                dpg.add_text(f"{group.printf_debug_count}/{group.string_count}", color=(255, 200, 100))
            else:
                dpg.add_text(f"0/{group.string_count}", color=(150, 150, 150))

            # String count
            dpg.add_text(f"{group.string_count}")

            # Total size (hex only to match padding finder)
            dpg.add_text(f"0x{group.size:X}")

            # File offset
            dpg.add_text(f"0x{group.start_offset:X}", color=(150, 200, 255))

            # Memory address
            if group.memory_address is not None:
                if platform in ["PS1", "N64", "Gamecube", "Wii"]:
                    mem_addr_str = f"0x80{group.memory_address:06X}"
                else:
                    mem_addr_str = f"0x{group.memory_address:08X}"
                dpg.add_text(mem_addr_str, color=(150, 255, 150))
            else:
                dpg.add_text("Unknown", color=(150, 150, 150))

            # First string preview
            first_string_text = group.strings[0]['text']
            if len(first_string_text) > 30:
                first_string_text = first_string_text[:30] + "..."
            dpg.add_text(f'"{first_string_text}"', color=(200, 200, 150))

            # Action buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="View Hex",
                    callback=_on_view_debug_string_hex_clicked,
                    user_data=(group, filename, current_project_data, file_path),
                    small=True,
                    width=70
                )
                dpg.add_button(
                    label="View Strings",
                    callback=_on_view_debug_strings_clicked,
                    user_data=(group, filename, current_project_data),
                    small=True,
                    width=85
                )
                dpg.add_button(
                    label="Add as Cave",
                    callback=_on_add_debug_string_codecave_clicked,
                    user_data=(group, filename, current_project_data),
                    small=True,
                    width=200
                    
                )
                dpg.bind_item_theme(dpg.last_item(), "add_as_cave_theme")
                
def _on_view_debug_string_hex_clicked(sender, app_data, user_data):
    """Show hex viewer for a debug string group"""
    group, filename, current_project_data, file_path = user_data

    # Create unique window tag
    window_tag = f"debug_string_hex_viewer_{group.start_offset}"

    # Delete existing window if it exists
    if dpg.does_item_exist(window_tag):
        dpg.delete_item(window_tag)

    # Read file data
    with open(file_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)

    # Calculate context range (show 0x100 bytes before and after)
    context_before = 0x100
    context_after = 0x100

    start_offset = max(0, group.start_offset - context_before)
    end_offset = min(file_size, group.end_offset + context_after)

    # Extract data region
    data_region = file_data[start_offset:end_offset]

    # Calculate debug string group boundaries within the displayed region
    group_start_in_region = group.start_offset - start_offset
    group_end_in_region = group_start_in_region + group.size

    # Create hex viewer window
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Format memory address for title
    if group.memory_address is not None:
        if platform in ["PS1", "N64", "Gamecube", "Wii"]:
            mem_addr_str = f"0x80{group.memory_address:06X}"
        else:
            mem_addr_str = f"0x{group.memory_address:08X}"
    else:
        mem_addr_str = "Unknown"

    with dpg.window(
        label=f"Hex Viewer - Debug Strings at 0x{group.start_offset:X}",
        tag=window_tag,
        width=900,
        height=700,
        pos=[50, 10],
        modal=False,
        no_close=False,
        no_move = True
    ):
        # Header info
        dpg.add_text(f"File: {filename}", color=(100, 200, 255))
        dpg.add_text(f"File Offset: 0x{group.start_offset:X} | Memory Address: {mem_addr_str} | Size: 0x{group.size:X} ({group.size} bytes)",
                    color=(150, 200, 150))
        dpg.add_text(f"String Count: {group.string_count} | Showing bytes from 0x{start_offset:X} to 0x{end_offset:X}",
                    color=(150, 150, 150))
        dpg.add_separator()
        dpg.add_spacer(height=5)

        # Legend
        with dpg.group(horizontal=True):
            dpg.add_text("Legend:", color=(180, 180, 180))
            dpg.add_text("  0x00", color=(50, 200, 50))
            dpg.add_text("= Debug String Region", color=(150, 150, 150))
            dpg.add_text("  0x00", color=(200, 200, 200))
            dpg.add_text("= Context Bytes", color=(150, 150, 150))

        dpg.add_spacer(height=5)
        dpg.add_separator()
        dpg.add_spacer(height=5)

        # Hex dump container with scrolling
        with dpg.child_window(height=550, border=True):
            _create_hex_dump(data_region, start_offset, group_start_in_region, group_end_in_region)

def _on_view_debug_strings_clicked(sender, app_data, user_data):
    """Show all strings in a debug string group"""
    group, filename, current_project_data = user_data

    # Create unique window tag
    window_tag = f"debug_strings_viewer_{group.start_offset}"

    # Delete existing window if it exists
    if dpg.does_item_exist(window_tag):
        dpg.delete_item(window_tag)

    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Format memory address
    if group.memory_address is not None:
        if platform in ["PS1", "N64", "Gamecube", "Wii"]:
            mem_addr_str = f"0x80{group.memory_address:06X}"
        else:
            mem_addr_str = f"0x{group.memory_address:08X}"
    else:
        mem_addr_str = "Unknown"

    with dpg.window(
        label=f"Debug String Group - {group.string_count} Strings",
        tag=window_tag,
        width=850,
        height=600,
        pos=[75, 80],
        modal=False,
        no_close=False,
        no_move = True
    ):
        # Header info
        dpg.add_text(f"File: {filename}", color=(100, 200, 255))
        dpg.add_text(f"File Offset: 0x{group.start_offset:X} - 0x{group.end_offset:X}",
                    color=(150, 200, 150))
        dpg.add_text(f"Memory Address: {mem_addr_str} | Size: {group.size} bytes (0x{group.size:X})",
                    color=(150, 200, 150))
        dpg.add_text(f"String Count: {group.string_count}", color=(200, 200, 100))

        dpg.add_separator()
        dpg.add_spacer(height=5)

        # String list
        with dpg.child_window(height=450, border=True):
            for idx, string in enumerate(group.strings, 1):
                display_text = string['text'].replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')

                dpg.add_text(
                    f"{idx}. [0x{string['offset']:X}] ({string['length']} bytes) \"{display_text}\"",
                    color=(200, 200, 200),
                    wrap=750
                )

def _on_add_debug_string_codecave_clicked(sender, app_data, user_data):
    """Add a debug string group as a codecave"""
    group, filename, current_project_data = user_data

    # Confirm with user
    response = messagebox.askyesno(
        "Add Debug String Codecave",
        f"Add this debug string region as codecave?\n\n"
        f"Region: 0x{group.start_offset:X} - 0x{group.end_offset:X}\n"
        f"Size: {group.size} bytes\n\n"
        f"Continue?"
    )

    if not response:
        return

    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Generate a unique codecave name
    existing_names = current_build.GetCodeCaveNames()
    counter = 0
    codecave_name = f"debug_strings_{counter}"

    while codecave_name in existing_names:
        counter += 1
        codecave_name = f"debug_strings_{counter}"

    # Check if this is the first codecave
    is_first_codecave = len(existing_names) == 0

    # Create codecave
    new_codecave = Codecave()
    new_codecave.SetName(codecave_name)
    new_codecave.SetInjectionFile(filename)
    new_codecave.SetSize(f"{group.size:X}")

    # Set memory address (if available)
    if group.memory_address is not None:
        if platform in ["PS1", "N64", "Gamecube", "Wii"]:
            mem_addr_hex = f"80{group.memory_address:06X}"
        else:
            mem_addr_hex = f"{group.memory_address:X}"

        new_codecave.SetMemoryAddress(mem_addr_hex)

    # Set file address
    new_codecave.SetInjectionFileAddress(f"{group.start_offset:X}")
    new_codecave.SetAutoCalculateInjectionFileAddress(False)

    # If this is the first codecave, automatically add main.c
    if is_first_codecave:
        import os
        project_folder = current_project_data.GetProjectFolder()
        main_c_path = os.path.join(project_folder, "src", "main.c")

        if os.path.exists(main_c_path):
            new_codecave.AddCodeFile(main_c_path)
            print(f"  Automatically added main.c to first codecave")

        # For PS2, also create and add syscalls.s
        if platform == "PS2":
            syscalls_s_path = os.path.join(project_folder, "asm", "syscalls.s")

            # Create syscalls.s if it doesn't exist
            if not os.path.exists(syscalls_s_path):
                os.makedirs(os.path.dirname(syscalls_s_path), exist_ok=True)
                with open(syscalls_s_path, "w") as syscalls_file:
                    syscalls_file.write(""".set noreorder
.global _print
.type _print, @function
_print:
    li $v1, 0x75
    syscall
    jr $ra
    nop


""")
                print(f"  Created: asm/syscalls.s")

            # Add syscalls.s to the codecave
            if os.path.exists(syscalls_s_path):
                new_codecave.AddCodeFile(syscalls_s_path)
                print(f"  Automatically added syscalls.s to first codecave")

    # Add to project
    current_build.AddCodeCave(new_codecave)

    print(f"Added debug string codecave: {codecave_name}")
    print(f"  File: {filename}")
    print(f"  String count: {group.string_count}")
    print(f"  Size: 0x{group.size:X} bytes ({group.size} bytes)")
    print(f"  File offset: 0x{group.start_offset:X}")
    if group.memory_address:
        print(f"  Memory address: 0x{group.memory_address:X}")

    # Update GUI
    from gui.gui_c_injection import UpdateCodecavesListbox, callback_codecave_selected
    UpdateCodecavesListbox(current_project_data)

    # Switch to the Modifications tab
    if dpg.does_item_exist("main_tab_bar"):
        dpg.set_value("main_tab_bar", "Modifications")

    # Switch to the C & C++ Injection tab
    if dpg.does_item_exist("modifications_tab_bar"):
        dpg.set_value("modifications_tab_bar", "C & C++ Injection")

    # Select the newly added codecave
    if dpg.does_item_exist("codecaves_listbox"):
        dpg.set_value("codecaves_listbox", codecave_name)
        callback_codecave_selected("codecaves_listbox", codecave_name, current_project_data)

    # Trigger auto-save
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    messagebox.showinfo("Codecave Added",
        f"Debug strings region added as codecave!\n\n"
        f"Size: {group.size} bytes\n")

    # Close the codecave finder window
    if dpg.does_item_exist("codecave_finder_window"):
        dpg.delete_item("codecave_finder_window")
