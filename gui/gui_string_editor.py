# gui/gui_string_editor.py
"""
String Search/Editor Tool - Find, edit, and repurpose strings in game files
"""

import dearpygui.dearpygui as dpg
import os
from typing import List, Optional, Tuple
from tkinter import messagebox
from classes.project_data.project_data import ProjectData
from classes.injection_targets.binary_patch import BinaryPatch

class GameString:
    """Represents a string found in a game file"""
    def __init__(self, file_offset: int, text: str, length: int, encoding: str = "ascii"):
        self.file_offset = file_offset
        self.text = text
        self.length = length  # Including null terminator
        self.encoding = encoding
        self.memory_address: Optional[int] = None
        self.section: Optional[str] = None
        self.is_printf_debug = False  # True if contains printf format specifiers, paths, or error keywords
        self.format_spec_count = 0  # Number of printf format specifiers

def _is_printf_debug_string(text: str) -> tuple[bool, int]:
    """
    Check if a string is likely a printf format string, file path, or error message.
    Returns (is_debug, format_spec_count) where format_spec_count is number of printf format specifiers.
    """
    import re

    text_lower = text.lower()

    # Count printf format specifiers (%s, %d, %x, %c, %f, %p, %u, %i, %n, %ld, %lld, etc.)
    # Match patterns like: %s, %d, %5d, %.2f, %08x, %ld, %lld, %p, etc.
    printf_pattern = r'%[-+ 0#]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|l|ll|j|z|t|L)?[sdioxXufFeEgGaAcpn%]'
    format_specs = re.findall(printf_pattern, text)
    format_count = len([f for f in format_specs if f != '%%'])  # Exclude literal %

    # Check for file paths (/, \, or file extensions)
    has_file_path = ('/' in text or '\\' in text or
                     '.c' in text_lower or '.cpp' in text_lower or '.h' in text_lower or
                     '.cc' in text_lower or '.cxx' in text_lower or '.hpp' in text_lower)

    # Check for error/debug keywords
    debug_keywords = ['error', 'fail', 'warning', 'assert', 'debug', 'printf', 'log',
                      'exception', 'fatal', 'panic', 'abort', 'trace', 'interrupt', 'timeout']
    has_debug_keyword = any(keyword in text_lower for keyword in debug_keywords)

    # It's a printf/debug string if it has ANY of these characteristics
    is_debug = format_count > 0 or has_file_path or has_debug_keyword

    return is_debug, format_count

def show_string_editor_window(sender, app_data, current_project_data: ProjectData):
    """Show the string editor tool window"""

    # Delete existing window if it exists
    if dpg.does_item_exist("string_editor_window"):
        dpg.delete_item("string_editor_window")

    current_build = current_project_data.GetCurrentBuildVersion()

    # Get available game files
    game_files = current_build.GetInjectionFiles()

    if not game_files:
        messagebox.showinfo("No Files", "No game files available.\n\nPlease add game files first in the 'Game Files To Inject Into' tab.")
        return

    with dpg.window(
        label="String Search & Editor",
        tag="string_editor_window",
        width=1200,
        height=800,
        pos=[100, 100],
        modal=False,
        no_close=False
    ):
        dpg.add_text("String Search & Editor", color=(100, 200, 255))
        dpg.add_text("Find and edit strings in game files, or convert debug strings to codecaves",
                    color=(150, 150, 150))
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # File selection
        with dpg.group(horizontal=True):
            dpg.add_text("Target File:", color=(200, 200, 200))
            dpg.add_combo(
                tag="string_editor_file_combo",
                width=300,
                callback=lambda: _on_file_changed(current_project_data)
            )
            dpg.add_button(
                label="Scan for Strings",
                callback=lambda: _on_scan_strings_clicked(current_project_data),
                width=150,
                height=30
            )

        dpg.add_spacer(height=5)

        # Scan options
        with dpg.group(horizontal=True):
            dpg.add_text("Min Length:", color=(180, 180, 180))
            dpg.add_input_int(
                tag="string_editor_min_length",
                default_value=4,
                width=80,
                min_value=1,
                max_value=1000,
                min_clamped=True
            )
            dpg.add_spacer(width=20)
            dpg.add_checkbox(
                label="Include Unicode (UTF-16)",
                tag="string_editor_include_unicode",
                default_value=False
            )
            dpg.add_spacer(width=20)
            dpg.add_text("", tag="string_editor_status", color=(150, 150, 150))

        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Search/Filter bar
        with dpg.group(horizontal=True):
            dpg.add_text("Filter:", color=(200, 200, 200))
            dpg.add_input_text(
                tag="string_editor_filter",
                width=300,
                hint="Type to filter strings...",
                callback=lambda: _on_filter_changed()
            )
            dpg.add_spacer(width=20)
            dpg.add_checkbox(
                label="Printf/Debug only",
                tag="string_editor_filter_printf",
                default_value=False,
                callback=lambda: _on_filter_changed()
            )
            dpg.add_spacer(width=20)
            dpg.add_text("Sort by:", color=(200, 200, 200))
            dpg.add_combo(
                tag="string_editor_sort_mode",
                items=["Printf/Debug First", "Offset", "Alphabetical", "Size (Largest)", "Size (Smallest)"],
                default_value="Printf/Debug First",
                width=150,
                callback=lambda: _on_sort_changed()
            )
            dpg.add_spacer(width=20)
            dpg.add_text("", tag="string_editor_count", color=(100, 200, 100))

        dpg.add_spacer(height=5)

        # Results table
        with dpg.table(
            tag="string_editor_results_table",
            header_row=True,
            resizable=True,
            policy=dpg.mvTable_SizingStretchProp,
            borders_innerH=True,
            borders_outerH=True,
            borders_innerV=True,
            borders_outerV=True,
            scrollY=True,
            scrollX=True,
            height=500
        ):
            # Columns
            dpg.add_table_column(label="#", width_fixed=True, init_width_or_weight=50)
            dpg.add_table_column(label="Printf?", width_fixed=True, init_width_or_weight=70)
            dpg.add_table_column(label="String", width_fixed=False, init_width_or_weight=400)
            dpg.add_table_column(label="Size", width_fixed=True, init_width_or_weight=80)
            dpg.add_table_column(label="File Offset", width_fixed=True, init_width_or_weight=120)
            dpg.add_table_column(label="Memory Addr", width_fixed=True, init_width_or_weight=150)
            dpg.add_table_column(label="Section", width_fixed=True, init_width_or_weight=100)
            dpg.add_table_column(label="Actions", width_fixed=True, init_width_or_weight=300)

        dpg.add_spacer(height=10)
        dpg.add_separator()

        # Info text
        with dpg.group(horizontal=False):
            dpg.add_text("Tips:", color=(100, 200, 255))
            dpg.add_text("  • Edit: Modify string text and save as binary patch", color=(150, 150, 150))
            dpg.add_text("  • Convert to Codecave: Use debug string list as free space", color=(150, 150, 150))
            dpg.add_text("  • WARNING: Converting strings to codecaves may break functionality!",
                        color=(200, 100, 0))

    # Populate file dropdown
    _populate_file_dropdown(current_project_data)

# ==================== Internal Functions ====================

# Global storage for scanned strings
_scanned_strings: List[GameString] = []
_filtered_strings: List[GameString] = []
_current_file_path: str = ""
_current_project_data: Optional[ProjectData] = None

def reset_string_editor_state():
    """Reset gui_string_editor global state when project closes"""
    global _current_project_data, _filtered_strings, _current_file_path
    _current_project_data = None
    _filtered_strings = []
    _current_file_path = ""

def _populate_file_dropdown(current_project_data: ProjectData):
    """Populate the file dropdown with available files"""
    current_build = current_project_data.GetCurrentBuildVersion()
    main_exe = current_build.GetMainExecutable()

    # Get all files from the project
    project_folder = current_project_data.GetProjectFolder()
    source_folder = current_build.GetSourcePath()

    files = []

    # Add main executable
    if main_exe:
        files.append(main_exe)

    # Scan for common file types in source folder
    if source_folder and os.path.isdir(source_folder):
        for root, dirs, filenames in os.walk(source_folder):
            for filename in filenames:
                # Skip small files and known binaries
                if filename.lower().endswith(('.exe', '.dll', '.bin', '.iso', '.dol', '.elf')):
                    rel_path = os.path.relpath(os.path.join(root, filename), source_folder)
                    if rel_path not in files:
                        files.append(rel_path)

    if not files:
        files = ["No files found"]

    dpg.configure_item("string_editor_file_combo", items=files, default_value=files[0] if files else "")

def _on_file_changed(current_project_data: ProjectData):
    """Handle file selection change"""
    global _scanned_strings, _filtered_strings
    _scanned_strings = []
    _filtered_strings = []

    # Clear table
    children = dpg.get_item_children("string_editor_results_table", slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

    dpg.set_value("string_editor_status", "Select file and click 'Scan for Strings'")
    dpg.set_value("string_editor_count", "")

def _on_scan_strings_clicked(current_project_data: ProjectData):
    """Scan selected file for strings"""
    global _scanned_strings, _filtered_strings, _current_file_path, _current_project_data

    _current_project_data = current_project_data

    filename = dpg.get_value("string_editor_file_combo")
    min_length = dpg.get_value("string_editor_min_length")
    include_unicode = dpg.get_value("string_editor_include_unicode")

    if not filename or filename == "No files found":
        messagebox.showerror("No File", "Please select a file to scan")
        return

    # Find file path (same method as codecave finder)
    current_build = current_project_data.GetCurrentBuildVersion()
    file_path = current_build.FindFileInGameFolder(filename)

    if not file_path or not os.path.exists(file_path):
        messagebox.showerror("File Not Found", f"Could not find file: {filename}")
        dpg.set_value("string_editor_status", "File not found")
        return

    _current_file_path = file_path

    dpg.set_value("string_editor_status", "Scanning...")
    dpg.set_value("string_editor_count", "")

    # Scan for strings
    try:
        print(f"Starting scan of {file_path} with min_length={min_length}, include_unicode={include_unicode}")
        _scanned_strings = _scan_file_for_strings(file_path, min_length, include_unicode)
        print(f"Scan complete, found {len(_scanned_strings)} strings")

        if not _scanned_strings:
            dpg.set_value("string_editor_status", "No strings found")
            dpg.set_value("string_editor_count", "")
            messagebox.showinfo("No Strings",
                f"No strings found longer than {min_length} characters.\n\n"
                "Try lowering the minimum length.")
            return

        # Calculate memory addresses
        print("Calculating memory addresses...")
        _calculate_memory_addresses(_scanned_strings, filename, current_project_data)
        print("Memory addresses calculated")

        # Sort strings: Printf/debug strings first (by format spec count), then by length
        print("Sorting strings...")
        _scanned_strings.sort(key=lambda s: (s.format_spec_count, len(s.text)), reverse=True)
        print("Sorting complete")

        # Initial display (no filter)
        _filtered_strings = _scanned_strings.copy()
        print(f"Displaying {len(_filtered_strings)} strings...")
        _display_strings(_filtered_strings)
        print("Display complete")

        dpg.set_value("string_editor_status", f"Scan complete")

        # Update count with display limit warning if needed
        if len(_scanned_strings) > 500:
            dpg.set_value("string_editor_count", f"Found {len(_scanned_strings)} string(s) (showing first 500, use filter)")
        else:
            dpg.set_value("string_editor_count", f"Found {len(_scanned_strings)} string(s)")

    except Exception as e:
        import traceback
        dpg.set_value("string_editor_status", "Scan failed")
        messagebox.showerror("Scan Error", f"Error scanning file:\n\n{str(e)}\n\n{traceback.format_exc()}")

def _scan_file_for_strings(file_path: str, min_length: int, include_unicode: bool) -> List[GameString]:
    """
    Scan a binary file for null-terminated ASCII (and optionally UTF-16) strings.
    Returns list of found strings with their offsets.
    Fast state machine similar to codecave finder.
    """
    strings = []

    with open(file_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)

    # Scan for ASCII null-terminated strings
    current_string = []
    string_start = None

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
            # NULL TERMINATOR - only save string if we found a null byte
            if current_string and len(current_string) >= min_length:
                try:
                    text = bytes(current_string).decode('ascii', errors='ignore')
                    # Length includes null terminator
                    game_string = GameString(string_start, text, len(current_string) + 1, "ascii")
                    # Categorize the string
                    is_debug, format_count = _is_printf_debug_string(text)
                    game_string.is_printf_debug = is_debug
                    game_string.format_spec_count = format_count
                    strings.append(game_string)
                except:
                    pass

            current_string = []
            string_start = None
            i += 1
        else:
            # Non-null, non-printable byte - reset without saving
            current_string = []
            string_start = None
            i += 1

    # Don't save final string if not null-terminated

    # Scan for UTF-16 LE null-terminated strings if requested
    if include_unicode:
        current_string = []
        string_start = None

        i = 0
        while i < file_size - 1:
            # UTF-16 LE: printable char followed by 0x00
            byte1 = file_data[i]
            byte2 = file_data[i + 1]

            if 32 <= byte1 <= 126 and byte2 == 0:
                if string_start is None:
                    string_start = i
                current_string.append(byte1)
                current_string.append(byte2)
                i += 2
            elif byte1 == 0 and byte2 == 0:
                # Double null terminator for UTF-16
                if current_string and len(current_string) // 2 >= min_length:
                    try:
                        text = bytes(current_string).decode('utf-16-le', errors='ignore')
                        game_string = GameString(string_start, text, len(current_string) + 2, "utf-16")
                        # Categorize the string
                        is_debug, format_count = _is_printf_debug_string(text)
                        game_string.is_printf_debug = is_debug
                        game_string.format_spec_count = format_count
                        strings.append(game_string)
                    except:
                        pass

                current_string = []
                string_start = None
                i += 2
            else:
                # Not a valid UTF-16 sequence - reset
                current_string = []
                string_start = None
                i += 1

    return strings

def _calculate_memory_addresses(strings: List[GameString], filename: str, current_project_data: ProjectData):
    """Calculate memory addresses for strings using section maps"""
    current_build = current_project_data.GetCurrentBuildVersion()

    # Check if section map exists
    has_section_map = filename in current_build.section_maps

    if has_section_map:
        sections = current_build.section_maps[filename]

        for string in strings:
            # Find which section this file offset belongs to
            for section in sections:
                # Calculate if this file offset is within this section's file range
                section_file_start = section.file_offset
                section_file_end = section.file_offset + section.size

                if section_file_start <= string.file_offset < section_file_end:
                    # Calculate memory address
                    offset_within_section = string.file_offset - section.file_offset
                    string.memory_address = section.mem_start + offset_within_section

                    # Get section info (type/name)
                    section_info = current_build.GetSectionInfoForAddress(filename, string.memory_address)
                    if section_info:
                        string.section = section_info['type']
                    break
    else:
        # Fallback: Use file offset
        file_offset_str = current_build.GetInjectionFileOffset(filename)

        if file_offset_str:
            try:
                file_offset = int(file_offset_str, 16)

                for string in strings:
                    # Memory address = file offset in file + base RAM offset
                    string.memory_address = string.file_offset + file_offset

            except ValueError:
                print(f"Warning: Could not parse file offset: {file_offset_str}")

def _display_strings(strings: List[GameString]):
    """Display strings in the table"""
    # Clear previous results
    children = dpg.get_item_children("string_editor_results_table", slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

    # Limit display to prevent UI freeze (max 500 rows)
    MAX_DISPLAY = 500
    display_strings = strings[:MAX_DISPLAY]

    if len(strings) > MAX_DISPLAY:
        print(f"Warning: Displaying first {MAX_DISPLAY} of {len(strings)} strings. Use filter to narrow results.")

    # Display strings
    for idx, string in enumerate(display_strings, 1):
        with dpg.table_row(parent="string_editor_results_table"):
            # Index
            dpg.add_text(f"{idx}")

            # Printf/Debug indicator with color coding
            if string.is_printf_debug:
                if string.format_spec_count > 0:
                    dpg.add_text(f"Yes ({string.format_spec_count})", color=(255, 200, 100))
                else:
                    dpg.add_text("Yes", color=(255, 200, 100))
            else:
                dpg.add_text("No", color=(150, 150, 150))

            # String text (truncate if too long)
            display_text = string.text
            if len(display_text) > 60:
                display_text = display_text[:60] + "..."

            # Escape special characters for display
            display_text = display_text.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')

            dpg.add_text(display_text, color=(200, 200, 200))

            # Size
            dpg.add_text(f"{string.length}")

            # File offset
            dpg.add_text(f"0x{string.file_offset:X}", color=(150, 200, 255))

            # Memory address
            if string.memory_address is not None:
                platform = _current_project_data.GetCurrentBuildVersion().GetPlatform()
                if platform in ["PS1", "N64", "Gamecube", "Wii"]:
                    mem_str = f"0x80{string.memory_address:06X}"
                else:
                    mem_str = f"0x{string.memory_address:08X}"
                dpg.add_text(mem_str, color=(150, 255, 150))
            else:
                dpg.add_text("N/A", color=(150, 150, 150))

            # Section
            if string.section:
                dpg.add_text(string.section.upper(), color=(200, 150, 255))
            else:
                dpg.add_text("N/A", color=(150, 150, 150))

            # Action buttons
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Edit",
                    callback=_on_edit_string_clicked,
                    user_data=string,
                    small=True,
                    width=70
                )
                dpg.add_button(
                    label="Convert to Codecave",
                    callback=_on_convert_to_codecave_clicked,
                    user_data=string,
                    small=True,
                    width=140
                )

def _on_filter_changed():
    """Handle filter text change"""
    global _filtered_strings

    if not _scanned_strings:
        return

    filter_text = dpg.get_value("string_editor_filter").lower()
    filter_printf = dpg.get_value("string_editor_filter_printf") if dpg.does_item_exist("string_editor_filter_printf") else False

    # Apply text filter
    if not filter_text:
        _filtered_strings = _scanned_strings.copy()
    else:
        _filtered_strings = [s for s in _scanned_strings if filter_text in s.text.lower()]

    # Apply printf/debug filter
    if filter_printf:
        _filtered_strings = [s for s in _filtered_strings if s.is_printf_debug]

    # Apply current sort
    _on_sort_changed()

    dpg.set_value("string_editor_count",
                 f"Showing {len(_filtered_strings)} of {len(_scanned_strings)} string(s)")

def _on_sort_changed():
    """Handle sort mode change"""
    global _filtered_strings

    if not _filtered_strings:
        return

    sort_mode = dpg.get_value("string_editor_sort_mode")

    if sort_mode == "Printf/Debug First":
        # Sort by printf/debug first (by format spec count), then by length
        _filtered_strings.sort(key=lambda s: (s.format_spec_count, len(s.text)), reverse=True)
    elif sort_mode == "Offset":
        _filtered_strings.sort(key=lambda s: s.file_offset)
    elif sort_mode == "Alphabetical":
        _filtered_strings.sort(key=lambda s: s.text.lower())
    elif sort_mode == "Size (Largest)":
        _filtered_strings.sort(key=lambda s: s.length, reverse=True)
    elif sort_mode == "Size (Smallest)":
        _filtered_strings.sort(key=lambda s: s.length)

    _display_strings(_filtered_strings)

def _on_edit_string_clicked(sender, app_data, user_data):
    """Open string editor dialog"""
    string: GameString = user_data

    # Create unique window tag
    window_tag = f"string_edit_dialog_{string.file_offset}"

    # Delete existing window if it exists
    if dpg.does_item_exist(window_tag):
        dpg.delete_item(window_tag)

    with dpg.window(
        label=f"Edit String at 0x{string.file_offset:X}",
        tag=window_tag,
        width=600,
        height=400,
        pos=[400, 200],
        modal=True,
        no_close=False
    ):
        dpg.add_text("Edit String", color=(100, 200, 255))
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Original string info
        dpg.add_text(f"File Offset: 0x{string.file_offset:X}", color=(150, 150, 150))
        dpg.add_text(f"Original Length: {string.length} bytes (including null terminator)",
                    color=(150, 150, 150))
        dpg.add_spacer(height=10)

        dpg.add_text("Original String:", color=(200, 200, 200))
        dpg.add_input_text(
            tag=f"{window_tag}_original",
            default_value=string.text,
            width=-1,
            multiline=True,
            height=80,
            readonly=True
        )

        dpg.add_spacer(height=10)
        dpg.add_text("New String:", color=(200, 200, 200))
        dpg.add_input_text(
            tag=f"{window_tag}_new",
            default_value=string.text,
            width=-1,
            multiline=True,
            height=80,
            hint="Enter new string text..."
        )

        dpg.add_spacer(height=10)
        dpg.add_text("", tag=f"{window_tag}_warning", color=(200, 100, 0))

        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Action buttons
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Save as Binary Patch",
                callback=_on_save_string_patch,
                user_data=(string, window_tag),
                width=180,
                height=35
            )
            dpg.add_spacer(width=10)
            dpg.add_button(
                label="Cancel",
                callback=lambda: dpg.delete_item(window_tag),
                width=100,
                height=35
            )

        dpg.add_spacer(height=10)

        dpg.add_text("Note: New string must fit within original length!",
                    color=(150, 150, 150))
        dpg.add_text("Longer strings will be truncated. Shorter strings will be null-padded.",
                    color=(150, 150, 150))

def _on_save_string_patch(sender, app_data, user_data):
    """Save string edit as a binary patch"""
    string: GameString = user_data[0]
    window_tag = user_data[1]

    new_text = dpg.get_value(f"{window_tag}_new")

    # Encode new string
    try:
        if string.encoding == "utf-16":
            new_bytes = new_text.encode('utf-16-le')
        else:
            new_bytes = new_text.encode('ascii')
    except Exception as e:
        dpg.set_value(f"{window_tag}_warning", f"Error: Invalid characters for {string.encoding}")
        return

    # Check length (must fit in original space)
    max_length = string.length - 1  # -1 for null terminator

    if len(new_bytes) > max_length:
        dpg.set_value(f"{window_tag}_warning",
                     f"Warning: String too long ({len(new_bytes)} > {max_length}). Will be truncated.")
        new_bytes = new_bytes[:max_length]

    # Pad with nulls to fill original space
    new_bytes += b'\x00' * (string.length - len(new_bytes))

    # Create binary patch
    filename = dpg.get_value("string_editor_file_combo")

    # Create a unique name for this patch
    safe_text = new_text[:30].replace(' ', '_').replace('\n', '_')
    patch_name = f"string_edit_{safe_text}_at_0x{string.file_offset:X}"

    # Create a .bin file with the hex data
    project_folder = _current_project_data.GetProjectFolder()
    bin_folder = os.path.join(project_folder, "bin_patches")
    os.makedirs(bin_folder, exist_ok=True)

    bin_file_path = os.path.join(bin_folder, f"{patch_name}.bin")

    # Write the binary data to file
    with open(bin_file_path, 'wb') as f:
        f.write(new_bytes)

    # Create BinaryPatch object
    binary_patch = BinaryPatch()
    binary_patch.SetName(patch_name)
    binary_patch.SetInjectionFile(filename)

    # Calculate memory address if available
    if string.memory_address is not None:
        platform = _current_project_data.GetCurrentBuildVersion().GetPlatform()
        if platform in ["PS1", "N64", "Gamecube", "Wii"]:
            mem_addr_str = f"0x80{string.memory_address:06X}"
        else:
            mem_addr_str = f"0x{string.memory_address:08X}"
        binary_patch.SetMemoryAddress(mem_addr_str)
    else:
        # Fallback: use file offset as placeholder
        binary_patch.SetMemoryAddress(f"0x{string.file_offset:X}")

    binary_patch.SetInjectionFileAddress(f"0x{string.file_offset:X}")
    binary_patch.SetAutoCalculateInjectionFileAddress(False)
    binary_patch.SetSize(f"0x{len(new_bytes):X}")

    # Add the bin file to the patch
    binary_patch.AddBinaryFile(bin_file_path)

    # Add to project
    _current_project_data.GetCurrentBuildVersion().AddBinaryPatch(binary_patch)
    _current_project_data.SaveToFile()

    dpg.delete_item(window_tag)

    messagebox.showinfo("Patch Created",
        f"String patch created successfully!\n\n"
        f"Patch Name: {patch_name}\n"
        f"File: {filename}\n"
        f"Offset: 0x{string.file_offset:X}\n"
        f"Binary file: {os.path.basename(bin_file_path)}\n\n"
        f"The patch will be applied when you rebuild.")

def _on_convert_to_codecave_clicked(sender, app_data, user_data):
    """Convert debug string list to codecave"""
    string: GameString = user_data

    # Create dialog
    window_tag = f"codecave_convert_dialog_{string.file_offset}"

    if dpg.does_item_exist(window_tag):
        dpg.delete_item(window_tag)

    with dpg.window(
        label=f"Convert Debug Strings to Codecave",
        tag=window_tag,
        width=700,
        height=500,
        pos=[350, 150],
        modal=True,
        no_close=False
    ):
        dpg.add_text("Convert Debug String List to Codecave", color=(100, 200, 255))
        dpg.add_separator()
        dpg.add_spacer(height=10)

        dpg.add_text("Selected String:", color=(200, 200, 200))
        dpg.add_text(f"  \"{string.text}\"", color=(150, 255, 150))
        dpg.add_text(f"  Offset: 0x{string.file_offset:X}", color=(150, 150, 150))

        dpg.add_spacer(height=10)

        dpg.add_text("This will scan bidirectionally from this string to find contiguous debug strings.",
                    color=(200, 200, 200))
        dpg.add_text("The region will be marked as available for code injection.",
                    color=(200, 200, 200))

        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Preview area
        dpg.add_text("Preview:", tag=f"{window_tag}_preview_label", color=(180, 180, 180))
        with dpg.child_window(tag=f"{window_tag}_preview", height=250, border=True):
            dpg.add_text("Scanning...", color=(150, 150, 150))

        dpg.add_spacer(height=10)

        # Action buttons
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Add as Codecave",
                callback=_on_confirm_codecave_conversion,
                user_data=(string, window_tag),
                width=180,
                height=35,
                tag=f"{window_tag}_convert_btn"
            )
            dpg.add_spacer(width=10)
            dpg.add_button(
                label="Cancel",
                callback=lambda: dpg.delete_item(window_tag),
                width=100,
                height=35
            )

        dpg.add_spacer(height=10)

        dpg.add_text("WARNING: This will mark the region for code injection and may break debug functionality!",
                    color=(200, 0, 0))

    # Auto-scan on dialog open
    _auto_scan_debug_strings_on_open(string, window_tag)

# Storage for preview scan results
_debug_string_scan_result = None

def _auto_scan_debug_strings_on_open(string: GameString, window_tag: str):
    """Automatically scan debug string region when dialog opens"""
    global _debug_string_scan_result

    # Default values for scanning
    max_strings = 50  # Max strings to scan
    max_gap = 16      # Stop at gaps larger than 16 bytes

    # Scan file for contiguous strings
    try:
        result = _scan_debug_string_region(_current_file_path, string.file_offset, max_strings, max_gap)
        _debug_string_scan_result = result

        # Display preview
        _display_debug_string_preview(result, window_tag)

    except Exception as e:
        import traceback
        messagebox.showerror("Scan Error", f"Error scanning debug strings:\n\n{str(e)}\n\n{traceback.format_exc()}")

def _scan_debug_string_region(file_path: str, start_offset: int, max_strings: int, max_gap: int) -> dict:
    """
    Scan file for contiguous debug strings bidirectionally from the starting offset.
    Scans both forward and backward to find all connected strings.
    Returns dict with region info.
    """
    with open(file_path, 'rb') as f:
        file_data = f.read()

    file_size = len(file_data)

    # Helper function to scan for a single string in a direction
    def scan_single_string(start_pos, direction='forward'):
        """Scan for one null-terminated string from start_pos"""
        string_start = None
        string_bytes = []

        if direction == 'forward':
            scan_range = range(start_pos, min(start_pos + 1000, file_size))
        else:  # backward
            scan_range = range(start_pos, max(0, start_pos - 1000), -1)

        for i in scan_range:
            byte = file_data[i]

            if (32 <= byte <= 126) or byte in [9, 10, 13]:
                if string_start is None:
                    string_start = i
                string_bytes.append(byte)
            elif byte == 0:
                if string_bytes:
                    try:
                        # For backward scan, reverse the bytes
                        if direction == 'backward':
                            string_bytes.reverse()
                            string_start = i + 1

                        text = bytes(string_bytes).decode('ascii', errors='ignore')
                        string_length = len(string_bytes) + 1
                        return {
                            'offset': string_start,
                            'text': text,
                            'length': string_length,
                            'end_pos': string_start + string_length if direction == 'forward' else i
                        }
                    except:
                        pass
                return None
            else:
                # Non-printable, non-null
                return None

        return None

    # Scan forward from start_offset
    forward_strings = []
    current_offset = start_offset

    for _ in range(max_strings):
        if current_offset >= file_size:
            break

        string_info = scan_single_string(current_offset, 'forward')
        if string_info:
            forward_strings.append(string_info)
            current_offset = string_info['end_pos']

            # Check gap after this string
            gap_size = 0
            for j in range(current_offset, min(current_offset + max_gap + 1, file_size)):
                if file_data[j] == 0:
                    gap_size += 1
                else:
                    break

            if gap_size > max_gap:
                break

            current_offset += gap_size
        else:
            break

    # Scan backward from start_offset
    backward_strings = []
    current_offset = start_offset - 1

    for _ in range(max_strings):
        if current_offset < 0:
            break

        # Skip backward over nulls to find previous string
        while current_offset >= 0 and file_data[current_offset] == 0:
            current_offset -= 1

        if current_offset < 0:
            break

        string_info = scan_single_string(current_offset, 'backward')
        if string_info:
            backward_strings.append(string_info)
            current_offset = string_info['end_pos'] - 1

            # Check gap before this string
            gap_size = 0
            for j in range(current_offset, max(current_offset - max_gap - 1, -1), -1):
                if file_data[j] == 0:
                    gap_size += 1
                else:
                    break

            if gap_size > max_gap:
                break

            current_offset -= gap_size
        else:
            break

    # Combine and sort all strings by offset
    backward_strings.reverse()  # Reverse to get proper order
    found_strings = backward_strings + forward_strings

    # Remove duplicates and sort by offset
    unique_strings = {s['offset']: s for s in found_strings}.values()
    found_strings = sorted(unique_strings, key=lambda s: s['offset'])

    # Calculate total region
    if found_strings:
        region_start = found_strings[0]['offset']
        last_string = found_strings[-1]
        region_end = last_string['offset'] + last_string['length']
        region_size = region_end - region_start
    else:
        region_start = start_offset
        region_end = start_offset
        region_size = 0

    return {
        'strings': found_strings,
        'region_start': region_start,
        'region_end': region_end,
        'region_size': region_size,
        'string_count': len(found_strings)
    }

def _display_debug_string_preview(result: dict, window_tag: str):
    """Display preview of debug string region"""
    # Clear preview window
    children = dpg.get_item_children(f"{window_tag}_preview", slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

    # Update label
    dpg.set_value(f"{window_tag}_preview_label",
                 f"Preview: Found {result['string_count']} string(s), Total Size: {result['region_size']} bytes (0x{result['region_size']:X})")

    # Display strings
    with dpg.group(parent=f"{window_tag}_preview"):
        for idx, string in enumerate(result['strings'], 1):
            text = string['text']
            if len(text) > 80:
                text = text[:80] + "..."

            display_text = text.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')

            dpg.add_text(
                f"{idx}. [0x{string['offset']:X}] ({string['length']} bytes) \"{display_text}\"",
                color=(200, 200, 200)
            )

def _on_confirm_codecave_conversion(sender, app_data, user_data):
    """Confirm and add debug string region as codecave"""
    global _debug_string_scan_result

    string: GameString = user_data[0]
    window_tag = user_data[1]

    if not _debug_string_scan_result:
        messagebox.showerror("Error", "Error: No scan result available")
        return

    result = _debug_string_scan_result

    if result['string_count'] == 0:
        messagebox.showerror("Error", "No strings found in this region")
        return

    # Confirm with user
    response = messagebox.askyesno(
        "Add Codecave",
        f"Add {result['string_count']} debug string(s) region as codecave?\n\n"
        f"Region: 0x{result['region_start']:X} - 0x{result['region_end']:X}\n"
        f"Size: {result['region_size']} bytes (0x{result['region_size']:X})\n\n"
        f"This will mark the region as available for code injection.\n\n"
        f"Continue?"
    )

    if not response:
        return

    filename = dpg.get_value("string_editor_file_combo")
    current_build = _current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Generate a unique codecave name (without address for linker script compatibility)
    existing_names = current_build.GetCodeCaveNames()
    counter = 0
    codecave_name = f"debug_strings_{counter}"

    while codecave_name in existing_names:
        counter += 1
        codecave_name = f"debug_strings_{counter}"

    # Add as codecave
    from classes.injection_targets.code_cave import Codecave

    new_codecave = Codecave()
    new_codecave.SetName(codecave_name)
    new_codecave.SetInjectionFile(filename)
    new_codecave.SetSize(f"{result['region_size']:X}")

    # Set memory address (if available)
    if string.memory_address is not None:
        if platform in ["PS1", "N64", "Gamecube", "Wii"]:
            mem_addr_hex = f"80{string.memory_address:06X}"
        else:
            mem_addr_hex = f"{string.memory_address:X}"

        new_codecave.SetMemoryAddress(mem_addr_hex)

    # Set file address
    new_codecave.SetInjectionFileAddress(f"{result['region_start']:X}")
    new_codecave.SetAutoCalculateInjectionFileAddress(False)

    # Add to project
    current_build.AddCodeCave(new_codecave)

    # Close the debug string window
    dpg.delete_item(window_tag)

    # Switch to the Modifications tab
    if dpg.does_item_exist("main_tab_bar"):
        dpg.set_value("main_tab_bar", "Modifications")

    # Switch to the C & C++ Injection tab (inner tab bar)
    if dpg.does_item_exist("modifications_tab_bar"):
        dpg.set_value("modifications_tab_bar", "C & C++ Injection")

    # Update the codecave listbox
    from gui.gui_c_injection import UpdateCodecavesListbox, callback_codecave_selected
    UpdateCodecavesListbox(_current_project_data)

    # Select the newly added codecave in the listbox
    if dpg.does_item_exist("codecaves_listbox"):
        dpg.set_value("codecaves_listbox", codecave_name)
        # Trigger the selection callback to load the codecave details
        callback_codecave_selected("codecaves_listbox", codecave_name, _current_project_data)

    # Trigger auto-save
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    messagebox.showinfo("Codecave Added",
        f"Debug strings region added as codecave!\n\n"
        f"Codecave Name: {codecave_name}\n"
        f"Size: {result['region_size']} bytes (0x{result['region_size']:X})\n"
        f"File: {filename}\n"
        f"Offset: 0x{result['region_start']:X}\n\n"
        f"You can now add C/C++ source files to this codecave\n"
        f"in the 'C & C++ Injection' tab.")

    # Refresh display if needed
    _on_scan_strings_clicked(_current_project_data)
