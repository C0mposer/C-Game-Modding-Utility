"""
Emulator Tools - Runtime memory analysis and verification
"""

import dearpygui.dearpygui as dpg
import os
import threading
from typing import List, Optional, Dict
from tkinter import messagebox
from classes.project_data.project_data import ProjectData
from services.emulator_service import EmulatorService
from services.emulator_connection_manager import get_emulator_manager
from gui.gui_loading_indicator import LoadingIndicator
from services.project_serializer import ProjectSerializer

# Wrapper functions to maintain compatibility while using centralized manager
def _get_or_establish_connection(emulator_name: str, emu_service: EmulatorService):
    """Wrapper that uses the centralized manager"""
    manager = get_emulator_manager()
    # Ensure manager has project data
    if hasattr(emu_service, 'project_data'):
        manager.set_project_data(emu_service.project_data)
    return manager.get_or_establish_connection(emulator_name)

# Wrapper class to maintain compatibility with existing _emulator_connection references
class _EmulatorConnectionWrapper:
    """Wrapper that delegates to the centralized manager's connection"""
    @property
    def is_valid(self):
        conn = get_emulator_manager().get_current_connection()
        return conn.is_valid if conn else False

    @property
    def main_ram(self):
        conn = get_emulator_manager().get_current_connection()
        return conn.main_ram if conn else None

    @property
    def handle(self):
        conn = get_emulator_manager().get_current_connection()
        return conn.handle if conn else None

    @property
    def emu_info(self):
        conn = get_emulator_manager().get_current_connection()
        return conn.emu_info if conn else None

    def validate(self):
        conn = get_emulator_manager().get_current_connection()
        return conn.validate() if conn else False

_emulator_connection = _EmulatorConnectionWrapper()

# Module-level callback for emulator scans
def _on_emulators_scanned_callback(available: list):
    """Update UI when emulators are scanned from other windows"""
    print(f"[EmulatorTools] _on_emulators_scanned_callback called with: {available}")

    # Update UI directly - DearPyGUI is thread-safe for these operations
    if dpg.does_item_exist("emu_tools_emulator_combo"):
        print(f"[EmulatorTools] Updating UI with emulators: {available}")
        if available:
            dpg.configure_item("emu_tools_emulator_combo", items=available)
            current_value = dpg.get_value("emu_tools_emulator_combo")
            if current_value == "No emulators running" or current_value not in available:
                dpg.set_value("emu_tools_emulator_combo", available[0])
            dpg.configure_item("emu_tools_connect_button", enabled=True)
            dpg.set_value("emu_tools_connection_status", f"Found {len(available)} running emulator(s). Click Connect.")
            dpg.configure_item("emu_tools_connection_status", color=(255, 200, 100))
        else:
            dpg.configure_item("emu_tools_emulator_combo", items=["No emulators running"])
            dpg.set_value("emu_tools_emulator_combo", "No emulators running")
            dpg.configure_item("emu_tools_connect_button", enabled=False)
            dpg.set_value("emu_tools_connection_status", "No compatible emulators detected")
            dpg.configure_item("emu_tools_connection_status", color=(255, 100, 100))
    else:
        print(f"[EmulatorTools] Window doesn't exist, skipping UI update")

def show_emulator_tools_window(sender, app_data, current_project_data: ProjectData):
    """Show the emulator tools window"""

    # Delete existing window if it exists
    if dpg.does_item_exist("emulator_tools_window"):
        dpg.delete_item("emulator_tools_window")

    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    window_width = 1000
    window_height = 706
    viewport_width = 1024
    viewport_height = 768
    pos_x = (viewport_width - window_width) // 2 - 8
    pos_y = (viewport_height - window_height) // 2 - 12
    with dpg.window(
        label="Verification Tools",
        tag="emulator_tools_window",
        width=window_width,
        height=window_height,
        pos=[pos_x, pos_y],
        modal=False,
        no_close=False
    ):
        dpg.add_text("Emulator Runtime Analysis & Verification", color=(100, 200, 255))
        dpg.add_text(f"Platform: {platform}", color=(150, 150, 150))
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Emulator connection section
        with dpg.group():
            dpg.add_text("Emulator Connection", color=(100, 200, 255))
            dpg.add_spacer(height=5)

            with dpg.group(horizontal=True):
                dpg.add_text("Select Emulator:", color=(200, 200, 200))
                dpg.add_combo(
                    tag="emu_tools_emulator_combo",
                    items=[],
                    default_value="No emulators running",
                    width=250,
                    callback=lambda: _on_emulator_selected(current_project_data)
                )
                dpg.add_button(
                    label="Refresh",
                    callback=lambda: _refresh_emulator_list(current_project_data),
                    width=100
                )
                dpg.add_button(
                    label="Connect",
                    tag="emu_tools_connect_button",
                    callback=lambda: _connect_to_emulator(current_project_data),
                    width=100,
                    enabled=False
                )

            dpg.add_spacer(height=5)
            with dpg.group(horizontal=True):
                dpg.add_text("Status:", color=(200, 200, 200))
                dpg.add_text("Not connected", tag="emu_tools_connection_status", color=(255, 100, 100))

        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Tab bar for different tools
        with dpg.tab_bar():
            # Codecave Verification tab
            with dpg.tab(label="Codecave Verification"):
                _create_codecave_verification_tab(current_project_data)

            # Memory Verification tab
            with dpg.tab(label="Offset Verification"):
                _create_memory_verification_tab(current_project_data)

    # Initialize manager with project data
    manager = get_emulator_manager()
    manager.set_project_data(current_project_data)

    # Register callback once (manager handles duplicate prevention)
    # Callback checks if window exists before updating UI
    manager.register_scan_callback(_on_emulators_scanned_callback)

    # Check if we have an existing connection
    connection = manager.get_current_connection()
    if connection:
        # Restore connection state in UI
        dpg.set_value("emu_tools_connection_status", f"Connected to {connection.emulator_name}")
        dpg.configure_item("emu_tools_connection_status", color=(100, 255, 100))

        # Update combo with cached emulators
        if manager.available_emulators:
            dpg.configure_item("emu_tools_emulator_combo", items=manager.available_emulators, default_value=connection.emulator_name)
            dpg.configure_item("emu_tools_connect_button", enabled=True)
    elif manager.available_emulators:
        # Use cached scan results from manager (scanned from another window)
        dpg.configure_item("emu_tools_emulator_combo", items=manager.available_emulators, default_value=manager.available_emulators[0])
        dpg.set_value("emu_tools_connection_status", f"Found {len(manager.available_emulators)} running emulator(s). Click Connect.")
        dpg.configure_item("emu_tools_connection_status", color=(255, 200, 100))
        dpg.configure_item("emu_tools_connect_button", enabled=True)
        _on_emulator_selected(current_project_data)
    else:
        # No cached results - show ready state, user must click Refresh
        dpg.configure_item("emu_tools_emulator_combo", items=["Click Refresh to scan"], default_value="Click Refresh to scan")
        dpg.set_value("emu_tools_connection_status", "Click Refresh to scan for emulators")
        dpg.configure_item("emu_tools_connection_status", color=(200, 200, 200))
        dpg.configure_item("emu_tools_connect_button", enabled=False)

def _create_codecave_verification_tab(current_project_data: ProjectData):
    """Create the codecave verification tab"""
    dpg.add_text("Monitor Codecave Memory Regions", color=(100, 200, 255))
    dpg.add_text("Continuously monitors codecave memory to detect any writes during gameplay",
                color=(150, 150, 150))
    dpg.add_spacer(height=10)

    with dpg.group(horizontal=True):
        dpg.add_button(
            label="Start Monitoring",
            tag="codecave_monitor_start_btn",
            callback=lambda: _start_codecave_monitoring(current_project_data),
            width=150,
            height=30
        )
        dpg.add_button(
            label="Stop Monitoring",
            tag="codecave_monitor_stop_btn",
            callback=_stop_codecave_monitoring,
            width=150,
            height=30,
            enabled=False,
            show=False
        )
        dpg.add_button(
            label="Fill with Test Bytes",
            tag="codecave_fill_pattern_btn",
            callback=lambda: _fill_codecaves_with_pattern(current_project_data),
            width=150,
            height=30
        )
        dpg.add_text("Not monitoring", tag="codecave_monitor_status", color=(150, 150, 150))

    dpg.add_spacer(height=10)
    dpg.add_separator()
    dpg.add_spacer(height=5)

    # Results table
    dpg.add_text("Codecave Verification Results:", color=(100, 200, 255))
    dpg.add_spacer(height=5)

    with dpg.table(
        tag="codecave_verification_table",
        header_row=True,
        borders_innerH=True,
        borders_outerH=True,
        borders_innerV=True,
        borders_outerV=True,
        row_background=True,
        scrollY=True,
        height=150
    ):
        dpg.add_table_column(label="Codecave Name", width_fixed=True, init_width_or_weight=150)
        dpg.add_table_column(label="Memory Address", width_fixed=True, init_width_or_weight=120)
        dpg.add_table_column(label="Size", width_fixed=True, init_width_or_weight=100)
        dpg.add_table_column(label="Status", width_fixed=True, init_width_or_weight=120)
        dpg.add_table_column(label="Details", width_fixed=False, init_width_or_weight=300)

    dpg.add_spacer(height=10)

    # Info text
    with dpg.group(horizontal=False):
        dpg.add_text("How to Use:", color=(255, 200, 100))
        dpg.add_text("  1. Connect to emulator using the Connect button above", color=(150, 150, 150))
        dpg.add_text("  2. Click 'Start Monitoring' to begin watching all codecaves", color=(150, 150, 150))
        dpg.add_text("  3. Play your game - monitoring will alert if any codecave is written to", color=(150, 150, 150))
        dpg.add_text("  4. If a codecave shows changes, it may not be safe to use", color=(150, 150, 150))
        dpg.add_text("  5. You can press \"Fill with Test Bytes\", to ensure changing the codecave data is safe", color=(150, 150, 150))

def _create_memory_verification_tab(current_project_data: ProjectData):
    """Create the memory verification tab"""
    dpg.add_text("Offset Mapping Tool", color=(100, 200, 255))
    dpg.add_text("Find file offsets from memory or verify existing configurations",
                color=(150, 150, 150))
    dpg.add_spacer(height=10)

    # Item selector and search direction on same row
    with dpg.group(horizontal=True):
        # Left side: Item selector
        with dpg.group(horizontal=False):
            dpg.add_text("Select Item:")
            with dpg.group(horizontal=True):
                dpg.add_combo(
                    tag="memory_verify_type_combo",
                    items=["Codecave", "Hook", "Manual Memory Address"],
                    default_value="Codecave",
                    width=200,
                    callback=lambda: _on_verify_type_changed(current_project_data)
                )
                dpg.add_combo(
                    tag="memory_verify_item_combo",
                    items=[],
                    default_value="No items",
                    width=300
                )

        dpg.add_spacer(width=20)

        # Right side: Search direction
        with dpg.group(horizontal=False):
            dpg.add_text("Search Direction:")
            dpg.add_radio_button(
                tag="memory_verify_mode_radio",
                items=["Memory to File (Find File Offset)", "File to Memory (Verify Config)"],
                default_value="Memory to File (Find File Offset)",
                callback=lambda: _on_verify_mode_changed(current_project_data)
            )

    dpg.add_spacer(height=10)

    # Manual memory address input (shown when "Manual Memory Address" is selected in Memory→File mode)
    with dpg.group(tag="manual_memory_address_group", show=False, horizontal=True):
        dpg.add_input_text(
            tag="memory_address_input",
            hint="0x80123456",
            width=200
        )
        dpg.add_input_text(
            tag="memory_size_input",
            hint="Size (bytes)",
            default_value="32",
            width=150
        )

    # Manual file offset input (shown when "Manual File Offset" is selected in File→Memory mode)
    with dpg.group(tag="manual_file_offset_group", show=False, horizontal=True):
        dpg.add_combo(
            tag="manual_file_combo",
            items=["Select game file"],
            default_value="Select game file",
            width=200
        )
        dpg.add_input_text(
            tag="file_offset_input",
            hint="0x1234",
            width=150
        )
        dpg.add_input_text(
            tag="file_size_input",
            hint="Size (bytes)",
            default_value="32",
            width=150
        )


    # Verify/Search button (label changes based on mode)
    dpg.add_button(
        tag="offset_search_button",
        label="Verify / Find File Offset",
        callback=lambda: _perform_offset_search(current_project_data),
        width=200,
        height=30,
        show=True,
        enabled=True
    )

    dpg.add_spacer(height=10)
    dpg.add_separator()
    dpg.add_spacer(height=10)

    # Results display
    dpg.add_text("Verification Results:", color=(100, 200, 255))
    dpg.add_spacer(height=5)

    with dpg.child_window(height=150, border=True, tag="memory_verify_results"):
        dpg.add_text("No verification performed yet.", color=(150, 150, 150))

    dpg.add_spacer(height=10)

    # Info text
    with dpg.group(horizontal=False):
        dpg.add_text("How to Use:", color=(255, 200, 100))
        dpg.add_text("  1. Connect to running emulator with game loaded", color=(150, 150, 150))
        dpg.add_text("  2. Select item type and specific item", color=(150, 150, 150))
        dpg.add_text("  3. Click 'Verify' to compare file data with memory", color=(150, 150, 150))
        dpg.add_text("  4. If data doesn't match, memory will automatically be searched for correct location",
                    color=(150, 150, 150))

    # Initialize item combo with Codecaves (default selection)
    _on_verify_type_changed(current_project_data)

# ==================== Internal Functions ====================

def _on_verify_mode_changed(current_project_data: ProjectData):
    """Update button label and combo items based on search direction"""
    mode = dpg.get_value("memory_verify_mode_radio")

    if mode == "Memory to File (Find File Offset)":
        dpg.configure_item("offset_search_button", label="Verify / Find File Offset", show=True)
        # Update combo items for Memory→File mode
        dpg.configure_item("memory_verify_type_combo", items=["Codecave", "Hook", "Manual Memory Address"])
    else:  # "File to Memory (Verify Config)"
        dpg.configure_item("offset_search_button", label="Verify / Find Memory Offset", show=True)
        # Update combo items for File→Memory mode
        dpg.configure_item("memory_verify_type_combo", items=["Codecave", "Hook", "Manual File Offset"])

    # Reset to first option and update UI
    dpg.set_value("memory_verify_type_combo", dpg.get_item_configuration("memory_verify_type_combo")["items"][0])
    _on_verify_type_changed(current_project_data)

def _perform_offset_search(current_project_data: ProjectData):
    """Unified search function that routes based on mode and item type"""
    mode = dpg.get_value("memory_verify_mode_radio")
    item_type = dpg.get_value("memory_verify_type_combo")

    # Route to appropriate handler
    if item_type == "Manual Memory Address":
        # Manual memory address: Read from memory, search in file
        _find_file_offset_from_memory(current_project_data)
    elif item_type == "Manual File Offset":
        # Manual file offset: Read from file, search in memory
        _find_memory_offset_from_file(current_project_data)
    elif mode == "Memory to File (Find File Offset)":
        # Memory → File: Read from configured item's memory address, search/verify in file
        _find_file_from_configured_memory(current_project_data)
    else:  # "File to Memory (Verify Config)"
        # File → Memory: Read from configured item's file offset, search/verify in memory
        _verify_memory_mapping(current_project_data)

def _find_file_from_configured_memory(current_project_data: ProjectData):
    """Verify memory→file mapping for configured item, then search if mismatch"""
    emulator_name = dpg.get_value("emu_tools_emulator_combo")
    if emulator_name == "No emulators running":
        messagebox.showerror("No Emulator", "Please connect to a running emulator first")
        return

    if not _emulator_connection.is_valid:
        messagebox.showerror("Not Connected", "Please click Connect button first")
        return

    item_type = dpg.get_value("memory_verify_type_combo")
    item_name = dpg.get_value("memory_verify_item_combo")

    if item_name == "No items":
        messagebox.showerror("No Item", "Please select an item")
        return

    LoadingIndicator.show("Reading item configuration...")

    def verify_thread():
        try:
            current_build = current_project_data.GetCurrentBuildVersion()
            memory_address = None
            file_offset_str = None
            game_file = None
            size = 32

            # Get item configuration
            if item_type == "Codecave":
                codecaves = current_build.GetCodeCaves()
                codecave = next((cc for cc in codecaves if cc.GetName() == item_name), None)
                if not codecave:
                    LoadingIndicator.hide()
                    dpg.delete_item("memory_verify_results", children_only=True)
                    _add_verify_result(f"Could not find codecave: {item_name}", (255, 100, 100))
                    return

                memory_address = codecave.GetMemoryAddress()
                file_offset_str = codecave.GetInjectionFileAddress()
                size = min(codecave.GetSizeAsInt(), 256)
                game_files = current_build.GetInjectionFiles()
                game_file = game_files[0] if game_files else None

            elif item_type == "Hook":
                hooks = current_build.GetHooks()
                hook = next((h for h in hooks if h.GetName() == item_name), None)
                if not hook:
                    LoadingIndicator.hide()
                    dpg.delete_item("memory_verify_results", children_only=True)
                    _add_verify_result(f"Could not find hook: {item_name}", (255, 100, 100))
                    return

                memory_address = hook.GetMemoryAddress()
                file_offset_str = hook.GetInjectionFileAddress()
                game_file = hook.GetInjectionFile()
                size = 32

            if not memory_address:
                LoadingIndicator.hide()
                dpg.delete_item("memory_verify_results", children_only=True)
                _add_verify_result(f"{item_type} is missing memory address", (255, 100, 100))
                return

            # Read memory data
            LoadingIndicator.update_message(f"Reading {size} bytes from memory...")
            emu_service = EmulatorService(current_project_data)
            offset = int(memory_address.removeprefix("0x").removeprefix("80"), 16)
            target_address = _emulator_connection.main_ram + offset
            memory_data = emu_service._read_memory(_emulator_connection.handle, target_address, size)

            if memory_data is None:
                LoadingIndicator.hide()
                dpg.delete_item("memory_verify_results", children_only=True)
                _add_verify_result("ERROR: Could not read memory", (255, 100, 100))
                return

            dpg.delete_item("memory_verify_results", children_only=True)
            _add_verify_result(f"Verifying {item_type}: {item_name}", (255, 200, 100))
            _add_verify_result(f"Memory Address: {memory_address}", (200, 200, 200))
            _add_verify_result(f"Data Size: {size} bytes", (200, 200, 200))

            hex_preview = ' '.join(f'{b:02X}' for b in memory_data[:min(32, len(memory_data))])
            if len(memory_data) > 32:
                hex_preview += "..."
            _add_verify_result(f"Memory Data: {hex_preview}", (200, 200, 200))
            _add_verify_result("", (255, 255, 255))

            # Check if file offset is configured - if so, VERIFY first
            if file_offset_str and game_file:
                file_offset = int(file_offset_str, 16)
                game_file_path = current_build.FindFileInGameFolder(game_file)

                if os.path.exists(game_file_path):
                    LoadingIndicator.update_message("Verifying against configured file offset...")

                    with open(game_file_path, 'rb') as f:
                        f.seek(file_offset)
                        expected_file_data = f.read(size)

                    _add_verify_result(f"Configured File: {game_file}", (200, 200, 200))
                    _add_verify_result(f"Configured File Offset: 0x{file_offset:X}", (200, 200, 200))

                    hex_preview = ' '.join(f'{b:02X}' for b in expected_file_data[:min(32, len(expected_file_data))])
                    if len(expected_file_data) > 32:
                        hex_preview += "..."
                    _add_verify_result(f"File Data:   {hex_preview}", (200, 200, 200))
                    _add_verify_result("", (255, 255, 255))

                    # Compare
                    if memory_data == expected_file_data:
                        LoadingIndicator.hide()
                        _add_verify_result("VERIFICATION SUCCESSFUL", (100, 255, 100))
                        _add_verify_result("Memory data matches configured file offset!", (100, 255, 100))
                        return  # Success! No need to search

                    else:
                        _add_verify_result("VERIFICATION FAILED", (255, 200, 100))
                        _add_verify_result("Memory data does NOT match configured file offset", (255, 200, 100))
                        _add_verify_result("", (255, 255, 255))

            # Verification failed or not configured - search for correct offset
            LoadingIndicator.update_message("Searching for pattern in game files...")

            game_files = current_build.GetInjectionFiles()
            if not game_files:
                LoadingIndicator.hide()
                _add_verify_result("No game files configured", (255, 100, 100))
                return

            found_offsets = []
            for search_file in game_files:
                game_file_path = current_build.FindFileInGameFolder(search_file)
                if not os.path.exists(game_file_path):
                    continue

                with open(game_file_path, 'rb') as f:
                    file_data = f.read()
                    pos = 0
                    while True:
                        pos = file_data.find(memory_data, pos)
                        if pos == -1:
                            break
                        found_offsets.append((search_file, pos))
                        pos += 1

            LoadingIndicator.hide()

            if not found_offsets:
                _add_verify_result("Pattern not found in any game file", (255, 100, 100))
                _add_verify_result("This memory region may contain runtime-generated data", (255, 100, 100))
            elif len(found_offsets) == 1:
                file_name, file_offset = found_offsets[0]
                _add_verify_result("FOUND CORRECT OFFSET!", (100, 255, 100))
                _add_verify_result(f"File: {file_name}", (100, 255, 100))
                _add_verify_result(f"Correct File Offset: 0x{file_offset:X}", (100, 255, 100))
                _add_verify_result("", (255, 255, 255))

                # Ask user if they want to update
                response = messagebox.askyesno(
                    "Update File Offset?",
                    f"Would you like to update the {item_type.lower()} with the correct file offset?\n\n"
                    f"{item_type}: {item_name}\n"
                    f"File: {file_name}\n"
                    f"New File Offset: 0x{file_offset:X}"
                )

                if response:
                    try:
                        if item_type == "Codecave":
                            codecave.SetInjectionFile(file_name)
                            codecave.SetInjectionFileAddress(f"{file_offset:X}")
                            _add_verify_result("Updated codecave file offset!", (100, 255, 100))
                        elif item_type == "Hook":
                            hook.SetInjectionFile(file_name)
                            hook.SetInjectionFileAddress(f"{file_offset:X}")
                            _add_verify_result("Updated hook file offset!", (100, 255, 100))

                        # Save the project file
                        ProjectSerializer.save_project(current_project_data)
                        _add_verify_result("Project configuration saved", (100, 255, 100))
                    except Exception as e:
                        _add_verify_result(f"Error: Could not update: {e}", (255, 100, 100))
                else:
                    _add_verify_result("Update cancelled by user", (200, 200, 200))
            else:
                _add_verify_result(f"Found {len(found_offsets)} potential matches:", (255, 200, 100))
                for i, (file_name, file_offset) in enumerate(found_offsets[:10]):
                    _add_verify_result(f"  Match {i+1}: {file_name} at 0x{file_offset:X}", (200, 200, 200))
                if len(found_offsets) > 10:
                    _add_verify_result(f"  ... and {len(found_offsets) - 10} more", (200, 200, 200))
                _add_verify_result("", (255, 255, 255))
                _add_verify_result("Multiple matches - try verifying with a larger pattern size", (255, 200, 100))

        except Exception as e:
            import traceback
            LoadingIndicator.hide()
            dpg.delete_item("memory_verify_results", children_only=True)
            _add_verify_result(f"ERROR: {str(e)}", (255, 100, 100))
            messagebox.showerror("Error", f"Error during verification:\n\n{str(e)}")

    threading.Thread(target=verify_thread, daemon=True).start()

def _find_memory_offset_from_file(current_project_data: ProjectData):
    """Find memory offset by reading from file offset and searching in memory"""
    emulator_name = dpg.get_value("emu_tools_emulator_combo")
    if emulator_name == "No emulators running":
        messagebox.showerror("No Emulator", "Please connect to a running emulator first")
        return

    # Check if connected
    if not _emulator_connection.is_valid:
        messagebox.showerror("Not Connected", "Please click Connect button first")
        return

    # Get user input
    selected_file = dpg.get_value("manual_file_combo").strip()
    file_offset_str = dpg.get_value("file_offset_input").strip()
    size_str = dpg.get_value("file_size_input").strip()

    if not selected_file or selected_file == "No files":
        messagebox.showerror("Invalid Input", "Please select a game file")
        return

    if not file_offset_str:
        messagebox.showerror("Invalid Input", "Please enter a file offset (e.g., 0x1234)")
        return

    try:
        # Parse file offset
        if file_offset_str.startswith("0x"):
            file_offset = int(file_offset_str, 16)
        else:
            file_offset = int(file_offset_str, 16)

        # Parse size
        size = int(size_str) if size_str else 32

        if size < 4 or size > 1024:
            messagebox.showerror("Invalid Size", "Size must be between 4 and 1024 bytes")
            return

    except ValueError:
        messagebox.showerror("Invalid Input", "Invalid file offset or size format")
        return

    # Show loading indicator with cancel button
    LoadingIndicator.show("Reading from game file...", allow_cancel=True)

    def search_thread():
        try:
            current_build = current_project_data.GetCurrentBuildVersion()
            game_file_path = current_build.FindFileInGameFolder(selected_file)

            if not os.path.exists(game_file_path):
                LoadingIndicator.hide()
                dpg.delete_item("memory_verify_results", children_only=True)
                _add_verify_result("ERROR: Game file not found", (255, 100, 100))
                messagebox.showerror("Error", f"Game file not found: {game_file_path}")
                return

            # Read file data
            with open(game_file_path, 'rb') as f:
                f.seek(file_offset)
                file_data = f.read(size)

            if len(file_data) < size:
                LoadingIndicator.hide()
                dpg.delete_item("memory_verify_results", children_only=True)
                _add_verify_result("ERROR: Could not read enough bytes from file", (255, 100, 100))
                return

            # Search for this pattern in memory
            LoadingIndicator.update_message("Searching for pattern in memory...")
            emu_service = EmulatorService(current_project_data)

            # If pattern is small, expand it with surrounding context
            search_pattern = file_data
            pattern_offset_in_search = 0

            MIN_SEARCH_SIZE = 32
            if len(file_data) < MIN_SEARCH_SIZE:
                context_size = (MIN_SEARCH_SIZE - len(file_data)) // 2
                try:
                    with open(game_file_path, 'rb') as f:
                        bytes_before_offset = max(0, file_offset - context_size)
                        f.seek(bytes_before_offset)
                        bytes_before = f.read(file_offset - bytes_before_offset)

                        f.seek(file_offset + len(file_data))
                        bytes_after = f.read(context_size)

                        search_pattern = bytes_before + file_data + bytes_after
                        pattern_offset_in_search = len(bytes_before)
                except Exception:
                    pass  # Use original pattern if expansion fails

            matches = _search_memory(emu_service, _emulator_connection.handle, _emulator_connection.main_ram,
                                    search_pattern, _emulator_connection.emu_info)

            LoadingIndicator.hide()
            dpg.delete_item("memory_verify_results", children_only=True)

            # Display results
            _add_verify_result(f"File Offset Search: 0x{file_offset:X}", (255, 200, 100))
            _add_verify_result(f"File: {selected_file}", (200, 200, 200))
            _add_verify_result(f"Pattern Size: {size} bytes", (200, 200, 200))

            hex_preview = ' '.join(f'{b:02X}' for b in file_data[:min(32, len(file_data))])
            if len(file_data) > 32:
                hex_preview += "..."
            _add_verify_result(f"File Data: {hex_preview}", (200, 200, 200))
            _add_verify_result("", (255, 255, 255))

            if matches is None:
                _add_verify_result("Search cancelled by user", (255, 200, 100))
            elif not matches:
                _add_verify_result("Pattern not found in memory", (255, 100, 100))
                _add_verify_result("The game may not have loaded this data yet", (255, 100, 100))
            elif len(matches) == 1:
                found_address = matches[0] + pattern_offset_in_search
                corrected_offset = found_address - _emulator_connection.main_ram
                corrected_memory_addr = f"0x80{corrected_offset:06X}"

                _add_verify_result("FOUND!", (100, 255, 100))
                _add_verify_result(f"Memory Address: {corrected_memory_addr}", (100, 255, 100))
                #_add_verify_result(f"RAM Address: 0x{found_address:X}", (100, 255, 100))
            else:
                _add_verify_result(f"Found {len(matches)} matches:", (255, 200, 100))
                for i, found_address_raw in enumerate(matches[:10]):
                    found_address = found_address_raw + pattern_offset_in_search
                    corrected_offset = found_address - _emulator_connection.main_ram
                    corrected_memory_addr = f"0x80{corrected_offset:06X}"
                    _add_verify_result(f"  Match {i+1}: {corrected_memory_addr}", (200, 200, 200))
                if len(matches) > 10:
                    _add_verify_result(f"  ... and {len(matches) - 10} more", (200, 200, 200))

        except Exception as e:
            import traceback
            LoadingIndicator.hide()
            dpg.delete_item("memory_verify_results", children_only=True)
            _add_verify_result(f"ERROR: {str(e)}", (255, 100, 100))
            messagebox.showerror("Error", f"Error during search:\n\n{str(e)}")

    threading.Thread(target=search_thread, daemon=True).start()

def _find_file_offset_from_memory(current_project_data: ProjectData):
    """Find file offset by reading from memory address and searching in file"""
    emulator_name = dpg.get_value("emu_tools_emulator_combo")
    if emulator_name == "No emulators running":
        messagebox.showerror("No Emulator", "Please connect to a running emulator first")
        return

    # Check if connected
    if not _emulator_connection.is_valid:
        messagebox.showerror("Not Connected", "Please click Connect button first")
        return

    # Get user input
    memory_address_str = dpg.get_value("memory_address_input").strip()
    size_str = dpg.get_value("memory_size_input").strip()

    if not memory_address_str:
        messagebox.showerror("Invalid Input", "Please enter a memory address (e.g., 0x80123456)")
        return

    try:
        # Parse memory address
        if memory_address_str.startswith("0x"):
            memory_address_int = int(memory_address_str, 16)
        else:
            memory_address_int = int(memory_address_str, 16)

        # Parse size
        size = int(size_str) if size_str else 32

        if size < 4 or size > 1024:
            messagebox.showerror("Invalid Size", "Size must be between 4 and 1024 bytes")
            return

    except ValueError:
        messagebox.showerror("Invalid Input", "Invalid memory address or size format")
        return

    # Show loading indicator
    LoadingIndicator.show("Reading from emulator memory...")

    def search_thread():
        try:
            emu_service = EmulatorService(current_project_data)

            # Calculate target address
            offset = int(memory_address_str.removeprefix("0x").removeprefix("80"), 16)
            target_address = _emulator_connection.main_ram + offset

            # Read memory data
            LoadingIndicator.update_message(f"Reading {size} bytes from memory...")
            memory_data = emu_service._read_memory(_emulator_connection.handle, target_address, size)

            if memory_data is None:
                LoadingIndicator.hide()
                dpg.delete_item("memory_verify_results", children_only=True)
                _add_verify_result("ERROR: Could not read memory", (255, 100, 100))
                messagebox.showerror("Error", "Could not read memory at specified address")
                return

            # Search for this pattern in game files
            LoadingIndicator.update_message("Searching for pattern in game files...")

            current_build = current_project_data.GetCurrentBuildVersion()
            game_files = current_build.GetInjectionFiles()

            if not game_files:
                LoadingIndicator.hide()
                dpg.delete_item("memory_verify_results", children_only=True)
                _add_verify_result("No game files configured", (255, 100, 100))
                return

            # Search each game file
            found_offsets = []
            for game_file in game_files:
                game_file_path = current_build.FindFileInGameFolder(game_file)

                if not os.path.exists(game_file_path):
                    continue

                # Search file for pattern
                with open(game_file_path, 'rb') as f:
                    file_data = f.read()

                    pos = 0
                    while True:
                        pos = file_data.find(memory_data, pos)
                        if pos == -1:
                            break
                        found_offsets.append((game_file, pos))
                        pos += 1

            LoadingIndicator.hide()
            dpg.delete_item("memory_verify_results", children_only=True)

            # Display results
            _add_verify_result(f"Memory Address Search: {memory_address_str}", (255, 200, 100))
            _add_verify_result(f"Pattern Size: {size} bytes", (200, 200, 200))

            # Show memory data preview
            hex_preview = ' '.join(f'{b:02X}' for b in memory_data[:min(32, len(memory_data))])
            if len(memory_data) > 32:
                hex_preview += "..."
            _add_verify_result(f"Memory Data: {hex_preview}", (200, 200, 200))
            _add_verify_result("", (255, 255, 255))  # Spacer

            if not found_offsets:
                _add_verify_result("Pattern not found in any game file", (255, 100, 100))
                _add_verify_result("This memory region may contain runtime-generated data", (255, 100, 100))
            elif len(found_offsets) == 1:
                file_name, file_offset = found_offsets[0]
                _add_verify_result("FOUND!", (100, 255, 100))
                _add_verify_result(f"File: {file_name}", (100, 255, 100))
                _add_verify_result(f"File Address: 0x{file_offset:X}", (100, 255, 100))
                _add_verify_result("", (255, 255, 255))  # Spacer
                _add_verify_result("You can use this file address to configure your hook/patch", (255, 200, 100))
            else:
                _add_verify_result(f"Found {len(found_offsets)} matches:", (255, 200, 100))
                for i, (file_name, file_offset) in enumerate(found_offsets[:10]):
                    _add_verify_result(f"  Match {i+1}: {file_name} at 0x{file_offset:X}", (200, 200, 200))

                if len(found_offsets) > 10:
                    _add_verify_result(f"  ... and {len(found_offsets) - 10} more", (200, 200, 200))

                _add_verify_result("", (255, 255, 255))  # Spacer
                _add_verify_result("Multiple matches - try increasing the pattern size", (255, 200, 100))

        except Exception as e:
            import traceback
            LoadingIndicator.hide()
            dpg.delete_item("memory_verify_results", children_only=True)
            _add_verify_result(f"ERROR: {str(e)}", (255, 100, 100))
            _add_verify_result(traceback.format_exc(), (150, 150, 150))
            messagebox.showerror("Error", f"Error during search:\n\n{str(e)}")

    # Start background thread
    threading.Thread(target=search_thread, daemon=True).start()

def _refresh_emulator_list(current_project_data: ProjectData):
    """Refresh the list of available emulators using centralized manager"""
    # Show loading indicator
    LoadingIndicator.show("Scanning for emulators...")

    def refresh_thread():
        try:
            # Use centralized manager (will notify all registered callbacks)
            manager = get_emulator_manager()
            manager.set_project_data(current_project_data)
            available = manager.scan_emulators()

            # Hide loading indicator
            LoadingIndicator.hide()

            # UI updates are handled by the callback, but we still update locally for immediate feedback
            if available:
                dpg.configure_item("emu_tools_emulator_combo", items=available, default_value=available[0])
                dpg.set_value("emu_tools_connection_status", f"Found {len(available)} running emulator(s). Click Connect.")
                dpg.configure_item("emu_tools_connection_status", color=(255, 200, 100))
                _on_emulator_selected(current_project_data)
            else:
                dpg.configure_item("emu_tools_emulator_combo", items=["No emulators running"], default_value="No emulators running")
                dpg.set_value("emu_tools_connection_status", "No compatible emulators detected")
                dpg.configure_item("emu_tools_connection_status", color=(255, 100, 100))
                dpg.configure_item("emu_tools_connect_button", enabled=False)
        except Exception as e:
            LoadingIndicator.hide()
            messagebox.showerror("Error", f"Error scanning for emulators:\n\n{str(e)}")

    # Run in background thread
    threading.Thread(target=refresh_thread, daemon=True).start()

def _on_emulator_selected(current_project_data: ProjectData):
    """Handle emulator selection"""
    emulator_name = dpg.get_value("emu_tools_emulator_combo")

    if emulator_name == "No emulators running":
        dpg.set_value("emu_tools_connection_status", "No emulator selected")
        dpg.configure_item("emu_tools_connect_button", enabled=False)
        return

    # Enable Connect button
    dpg.configure_item("emu_tools_connect_button", enabled=True)
    dpg.set_value("emu_tools_connection_status", f"Ready to connect to {emulator_name}")

    # Refresh item lists for verification tab
    _on_verify_type_changed(current_project_data)

def _connect_to_emulator(current_project_data: ProjectData):
    """Establish connection to selected emulator"""
    emulator_name = dpg.get_value("emu_tools_emulator_combo")

    if emulator_name == "No emulators running":
        messagebox.showerror("No Emulator", "Please select a running emulator first")
        return

    # Show loading indicator BEFORE starting thread (critical for immediate feedback)
    LoadingIndicator.show("Connecting to emulator...")

    def connect_thread():
        try:
            # Get emulator service
            emu_service = EmulatorService(current_project_data)

            # Establish connection (will be cached)
            handle, main_ram, kernel32 = _get_or_establish_connection(emulator_name, emu_service)

            # Hide loading indicator
            LoadingIndicator.hide()

            if not handle or not main_ram:
                dpg.set_value("emu_tools_connection_status", "Connection failed")
                dpg.configure_item("emu_tools_connection_status", color=(255, 100, 100))
                messagebox.showerror("Connection Failed",
                    f"Could not connect to {emulator_name}.\n\n"
                    "Make sure:\n"
                    "• Emulator is running\n"
                    "• A game is loaded\n"
                    "• Run as Administrator if needed")
                return

            # Success
            dpg.set_value("emu_tools_connection_status", f"Connected to {emulator_name}")
            dpg.configure_item("emu_tools_connection_status", color=(100, 255, 100))

        except Exception as e:
            import traceback
            LoadingIndicator.hide()
            dpg.set_value("emu_tools_connection_status", "Connection error")
            dpg.configure_item("emu_tools_connection_status", color=(255, 100, 100))
            messagebox.showerror("Error", f"Connection error:\n\n{str(e)}\n\n{traceback.format_exc()}")

    # Run in background thread
    threading.Thread(target=connect_thread, daemon=True).start()

def _on_verify_type_changed(current_project_data: ProjectData):
    """Update item list when verify type changes and show/hide manual input groups"""
    verify_type = dpg.get_value("memory_verify_type_combo") if dpg.does_item_exist("memory_verify_type_combo") else "Codecave"

    # Show/hide appropriate controls based on selection
    if verify_type == "Manual Memory Address":
        # Hide item combo, show manual memory address input
        if dpg.does_item_exist("memory_verify_item_combo"):
            dpg.configure_item("memory_verify_item_combo", show=False)
        if dpg.does_item_exist("manual_memory_address_group"):
            dpg.configure_item("manual_memory_address_group", show=True)
        if dpg.does_item_exist("manual_file_offset_group"):
            dpg.configure_item("manual_file_offset_group", show=False)
    elif verify_type == "Manual File Offset":
        # Hide item combo, show manual file offset input
        if dpg.does_item_exist("memory_verify_item_combo"):
            dpg.configure_item("memory_verify_item_combo", show=False)
        if dpg.does_item_exist("manual_memory_address_group"):
            dpg.configure_item("manual_memory_address_group", show=False)
        if dpg.does_item_exist("manual_file_offset_group"):
            dpg.configure_item("manual_file_offset_group", show=True)

        # Populate file combo with injection files
        current_build = current_project_data.GetCurrentBuildVersion()
        game_files = current_build.GetInjectionFiles()
        if dpg.does_item_exist("manual_file_combo"):
            if game_files:
                dpg.configure_item("manual_file_combo", items=game_files, default_value=game_files[0])
            else:
                dpg.configure_item("manual_file_combo", items=["No files"], default_value="No files")
    else:
        # Show item combo, hide manual inputs
        if dpg.does_item_exist("memory_verify_item_combo"):
            dpg.configure_item("memory_verify_item_combo", show=True)
        if dpg.does_item_exist("manual_memory_address_group"):
            dpg.configure_item("manual_memory_address_group", show=False)
        if dpg.does_item_exist("manual_file_offset_group"):
            dpg.configure_item("manual_file_offset_group", show=False)

        # Populate item combo based on type
        current_build = current_project_data.GetCurrentBuildVersion()
        items = []

        if verify_type == "Codecave":
            items = current_build.GetCodeCaveNames()
        elif verify_type == "Hook":
            items = [hook.GetName() for hook in current_build.GetHooks()]

        if dpg.does_item_exist("memory_verify_item_combo"):
            if items:
                dpg.configure_item("memory_verify_item_combo", items=items, default_value=items[0])
            else:
                dpg.configure_item("memory_verify_item_combo", items=["No items"], default_value="No items")

def _scan_all_codecaves(current_project_data: ProjectData):
    """Scan all codecaves to verify they're unused (runs in background thread with loading indicator)"""
    emulator_name = dpg.get_value("emu_tools_emulator_combo")
    if emulator_name == "No emulators running":
        messagebox.showerror("No Emulator", "Please connect to a running emulator first")
        return

    # Clear previous results
    children = dpg.get_item_children("codecave_verification_table", slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

    # Show loading indicator BEFORE starting thread
    LoadingIndicator.show("Connecting to emulator...")
    dpg.set_value("codecave_scan_status", "")

    # Run scan in background thread
    def scan_thread():
        try:
            # Get emulator service
            emu_service = EmulatorService(current_project_data)

            # Get or establish cached connection
            handle, main_ram, kernel32 = _get_or_establish_connection(emulator_name, emu_service)

            if not handle or not main_ram:
                LoadingIndicator.hide()
                dpg.set_value("codecave_scan_status", "Connection failed")
                messagebox.showerror("Error",
                    f"Could not connect to {emulator_name}.\n\n"
                    "Make sure:\n"
                    "• Emulator is running\n"
                    "• A game is loaded\n"
                    "• Run as Administrator if needed")
                return

            LoadingIndicator.update_message("Scanning codecaves...")

            # Scan each codecave
            current_build = current_project_data.GetCurrentBuildVersion()
            codecaves = current_build.GetCodeCaves()

            if not codecaves:
                dpg.set_value("codecave_scan_status", "No codecaves to scan")
                return

            scanned_count = 0
            for codecave in codecaves:
                memory_addr = codecave.GetMemoryAddress()
                if not memory_addr:
                    continue

                size = codecave.GetSize()
                if not size:
                    continue

                # Convert memory address to offset
                offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                target_address = main_ram + offset
                size_int = int(size, 16) if isinstance(size, str) else size

                # Read memory from codecave region
                memory_data = emu_service._read_memory(handle, target_address, size_int)

                if memory_data is None:
                    _add_codecave_result(codecave.GetName(), memory_addr, size, "ERROR",
                                        "Could not read memory", (255, 100, 100))
                    continue

                # Show hex preview of first 16 bytes
                hex_preview = ' '.join(f'{b:02X}' for b in memory_data[:min(16, len(memory_data))])
                if len(memory_data) > 16:
                    hex_preview += "..."

                # Display info - just show the snapshot
                status = "SNAPSHOT"
                details = f"{hex_preview}"
                color = (150, 200, 255)  # Blue - informational

                _add_codecave_result(codecave.GetName(), memory_addr, size, status, details, color)
                scanned_count += 1

            # Hide loading indicator and show success
            LoadingIndicator.hide()
            dpg.set_value("codecave_scan_status", f"Scanned {scanned_count} codecave(s)")

        except Exception as e:
            import traceback
            LoadingIndicator.hide()
            dpg.set_value("codecave_scan_status", "Scan failed")
            messagebox.showerror("Error", f"Error during scan:\n\n{str(e)}\n\n{traceback.format_exc()}")

    # Start background thread
    threading.Thread(target=scan_thread, daemon=True).start()

def _add_codecave_result(name: str, address: str, size: str, status: str, details: str, color: tuple):
    """Add a codecave verification result to the table"""
    with dpg.table_row(parent="codecave_verification_table"):
        dpg.add_text(name)
        dpg.add_text(f"0x{address}")
        dpg.add_text(f"0x{size}")
        dpg.add_text(status, color=color)
        dpg.add_text(details, color=(200, 200, 200))

def _add_verify_result(text: str, color: tuple):
    """Add a result line to the memory verification results window"""
    dpg.add_text(text, color=color, parent="memory_verify_results", wrap=900)

def _search_memory(emu_service: EmulatorService, handle, main_ram: int, pattern: bytes, emu_info) -> List[int]:
    """Search memory for a byte pattern and return list of matching addresses.
    Returns None if search was cancelled."""
    matches = []

    # Determine RAM size based on emulator
    if emu_info.name == "Dolphin":
        ram_size = 0x1800000  # 24 MB for GameCube
    elif emu_info.name == "PCSX2":
        ram_size = 0x2000000  # 32 MB for PS2
    elif emu_info.name == "Duckstation":
        ram_size = 0x200000   # 2 MB for PS1
    else:
        ram_size = 0x2000000  # Default 32 MB

    # Search in chunks to avoid reading too much at once
    chunk_size = 1024 * 1024  # 1 MB chunks
    pattern_len = len(pattern)
    total_chunks = (ram_size + chunk_size - 1) // chunk_size

    # Initialize PINE for PS2 if needed
    pine_ipc = None
    if emu_info.name == "PCSX2":
        try:
            import sys
            from path_helper import get_application_directory
            pine_path = os.path.join(get_application_directory(), 'prereq', 'pine')
            if pine_path not in sys.path:
                sys.path.insert(0, pine_path)
            import prereq.pine.pcsx2_ipc as pcsx2_ipc

            if pcsx2_ipc.init():
                pine_ipc = pcsx2_ipc
        except Exception as e:
            print(f"PINE initialization failed for search: {e}")

    for chunk_num, offset in enumerate(range(0, ram_size, chunk_size)):
        # Check for cancellation
        if LoadingIndicator.is_cancelled():
            return None

        # Update progress
        LoadingIndicator.update_message(f"Searching memory... {chunk_num}/{total_chunks} chunks")

        # Read chunk with overlap to catch patterns at chunk boundaries
        read_size = min(chunk_size + pattern_len, ram_size - offset)

        # Use PINE for PS2, otherwise Windows API
        if pine_ipc:
            try:
                chunk_data = pine_ipc.read_bytes(offset, read_size)
                if chunk_data:
                    chunk_data = bytes(chunk_data)
            except Exception:
                chunk_data = None
        else:
            chunk_data = emu_service._read_memory(handle, main_ram + offset, read_size)

        if chunk_data is None:
            continue

        # Search for pattern in this chunk
        pos = 0
        while True:
            pos = chunk_data.find(pattern, pos)
            if pos == -1:
                break

            # Found a match
            match_address = main_ram + offset + pos
            matches.append(match_address)
            pos += 1

    return matches

def _verify_memory_mapping(current_project_data: ProjectData):
    """Verify that file offset maps correctly to memory (runs in background thread with loading indicator)"""
    emulator_name = dpg.get_value("emu_tools_emulator_combo")
    if emulator_name == "No emulators running":
        messagebox.showerror("No Emulator", "Please connect to a running emulator first")
        return

    # Get selected item
    verify_type = dpg.get_value("memory_verify_type_combo")
    item_name = dpg.get_value("memory_verify_item_combo")

    if item_name == "No items":
        messagebox.showerror("No Item", "Please select an item to verify")
        return

    # Clear previous results
    dpg.delete_item("memory_verify_results", children_only=True)

    # Show loading indicator BEFORE starting thread
    LoadingIndicator.show("Connecting to emulator...")

    # Run verification in background thread
    def verify_thread():
        try:
            # Get emulator service
            emu_service = EmulatorService(current_project_data)

            # Get or establish cached connection
            handle, main_ram, kernel32 = _get_or_establish_connection(emulator_name, emu_service)

            if not handle or not main_ram:
                LoadingIndicator.hide()
                dpg.delete_item("memory_verify_results", children_only=True)
                _add_verify_result("Connection failed", (255, 100, 100))
                messagebox.showerror("Error",
                    f"Could not connect to {emulator_name}.\n\n"
                    "Make sure:\n"
                    "• Emulator is running\n"
                    "• A game is loaded\n"
                    "• Run as Administrator if needed")
                return

            # Update loading message
            LoadingIndicator.update_message(f"Reading file data from {verify_type}...")

            # Get item data based on type
            current_build = current_project_data.GetCurrentBuildVersion()
            file_offset = None
            memory_address = None
            expected_data = None

            if verify_type == "Codecave":
                codecaves = current_build.GetCodeCaves()
                codecave = next((cc for cc in codecaves if cc.GetName() == item_name), None)
                if not codecave:
                    _add_verify_result(f"Could not find codecave: {item_name}", (255, 100, 100))
                    return

                file_offset_str = codecave.GetInjectionFileAddress()
                memory_address = codecave.GetMemoryAddress()
                size = codecave.GetSize()

                if not file_offset_str or not memory_address or not size:
                    _add_verify_result("Codecave is missing file offset, memory address, or size", (255, 100, 100))
                    return

                file_offset = int(file_offset_str, 16)
                size_int = int(size, 16) if isinstance(size, str) else size

                # Read file data
                game_files = current_build.GetInjectionFiles()
                if not game_files:
                    _add_verify_result("No game files configured", (255, 100, 100))
                    return

                # Read from first game file (codecaves are typically in main executable)
                game_file_path = current_build.FindFileInGameFolder(game_files[0])

                if not os.path.exists(game_file_path):
                    _add_verify_result(f"Game file not found: {game_file_path}", (255, 100, 100))
                    return

                with open(game_file_path, 'rb') as f:
                    f.seek(file_offset)
                    expected_data = f.read(size_int)

            elif verify_type == "Hook":
                hooks = current_build.GetHooks()
                hook = next((h for h in hooks if h.GetName() == item_name), None)
                if not hook:
                    dpg.delete_item("memory_verify_results", children_only=True)
                    _add_verify_result(f"Could not find hook: {item_name}", (255, 100, 100))
                    return

                file_offset_str = hook.GetInjectionFileAddress()
                memory_address = hook.GetMemoryAddress()

                if not file_offset_str or not memory_address:
                    dpg.delete_item("memory_verify_results", children_only=True)
                    _add_verify_result("Hook is missing file offset or memory address", (255, 100, 100))
                    return

                file_offset = int(file_offset_str, 16)

                # Hooks are typically 4 bytes (branch instruction)
                size_int = 4

                # Get the file from the hook
                game_file = hook.GetInjectionFile()
                if not game_file:
                    _add_verify_result("Hook has no file specified", (255, 100, 100))
                    return

                game_file_path = current_build.FindFileInGameFolder(game_file)

                if not os.path.exists(game_file_path):
                    _add_verify_result(f"Game file not found: {game_file_path}", (255, 100, 100))
                    return

                with open(game_file_path, 'rb') as f:
                    f.seek(file_offset)
                    expected_data = f.read(size_int)

            elif verify_type == "Binary Patch":
                patches = current_build.GetBinaryPatches()
                patch = next((p for p in patches if p.GetName() == item_name), None)
                if not patch:
                    dpg.delete_item("memory_verify_results", children_only=True)
                    _add_verify_result(f"Could not find binary patch: {item_name}", (255, 100, 100))
                    return

                file_offset_str = patch.GetInjectionFileAddress()
                memory_address = patch.GetMemoryAddress()

                if not file_offset_str or not memory_address:
                    dpg.delete_item("memory_verify_results", children_only=True)
                    _add_verify_result("Binary patch is missing file offset or memory address", (255, 100, 100))
                    return

                file_offset = int(file_offset_str, 16)

                # Get patch data
                patch_bytes = patch.GetPatchBytes()
                if not patch_bytes:
                    _add_verify_result("Binary patch has no patch bytes", (255, 100, 100))
                    return

                size_int = len(patch_bytes)

                # Get the file from the patch
                game_file = patch.GetInjectionFile()
                if not game_file:
                    _add_verify_result("Binary patch has no file specified", (255, 100, 100))
                    return

                game_file_path = current_build.FindFileInGameFolder(game_file)

                if not os.path.exists(game_file_path):
                    _add_verify_result(f"Game file not found: {game_file_path}", (255, 100, 100))
                    return

                with open(game_file_path, 'rb') as f:
                    f.seek(file_offset)
                    expected_data = f.read(size_int)

            # Calculate target memory address
            offset = int(memory_address.removeprefix("0x").removeprefix("80"), 16)

            # Update loading message
            LoadingIndicator.update_message(f"Reading from emulator memory...")

            # Read memory at expected location - use PINE for PS2
            from services.emulator_service import EMULATOR_CONFIGS
            emu_info = EMULATOR_CONFIGS.get(emulator_name)

            if emu_info and emu_info.name == "PCSX2":
                # Use PINE for PS2
                try:
                    import sys
                    from path_helper import get_application_directory
                    pine_path = os.path.join(get_application_directory(), 'prereq', 'pine')
                    if pine_path not in sys.path:
                        sys.path.insert(0, pine_path)
                    import prereq.pine.pcsx2_ipc as pcsx2_ipc

                    # Initialize PINE
                    if not pcsx2_ipc.init():
                        LoadingIndicator.hide()
                        dpg.delete_item("memory_verify_results", children_only=True)
                        _add_verify_result("ERROR: Could not connect to PCSX2 via PINE", (255, 100, 100))
                        return

                    # Read via PINE
                    actual_data = pcsx2_ipc.read_bytes(offset, len(expected_data))
                    if actual_data:
                        actual_data = bytes(actual_data)

                except Exception as e:
                    LoadingIndicator.hide()
                    dpg.delete_item("memory_verify_results", children_only=True)
                    _add_verify_result(f"ERROR: PINE read failed: {e}", (255, 100, 100))
                    return
            else:
                # Use standard Windows API for other emulators
                target_address = main_ram + offset
                actual_data = emu_service._read_memory(handle, target_address, len(expected_data))

            if actual_data is None:
                LoadingIndicator.hide()
                dpg.delete_item("memory_verify_results", children_only=True)
                _add_verify_result("ERROR: Could not read memory", (255, 100, 100))
                return

            # Hide loading indicator and show results
            LoadingIndicator.hide()
            dpg.delete_item("memory_verify_results", children_only=True)
            _add_verify_result(f"Verifying {verify_type}: {item_name}", (255, 200, 100))
            _add_verify_result(f"File Address: 0x{file_offset:X}", (200, 200, 200))
            _add_verify_result(f"Expected Memory Address: {memory_address}", (200, 200, 200))
            _add_verify_result(f"Data Size: {len(expected_data)} bytes", (200, 200, 200))
            _add_verify_result("", (255, 255, 255))  # Spacer

            # Show expected data preview
            hex_preview = ' '.join(f'{b:02X}' for b in expected_data[:min(32, len(expected_data))])
            if len(expected_data) > 32:
                hex_preview += "..."
            _add_verify_result(f"File Data:   {hex_preview}", (200, 200, 200))

            # Show actual data preview
            hex_preview = ' '.join(f'{b:02X}' for b in actual_data[:min(32, len(actual_data))])
            if len(actual_data) > 32:
                hex_preview += "..."
            _add_verify_result(f"Memory Data: {hex_preview}", (200, 200, 200))
            _add_verify_result("", (255, 255, 255))  # Spacer

            # Compare
            if expected_data == actual_data:
                _add_verify_result("VERIFICATION SUCCESSFUL", (100, 255, 100))
                _add_verify_result("File data matches memory at expected address!", (100, 255, 100))
            else:
                _add_verify_result("VERIFICATION FAILED", (255, 200, 100))
                _add_verify_result("File data does not match expected memory location", (255, 200, 100))
                _add_verify_result("", (255, 255, 255))  # Spacer

                # Show loading indicator for search with cancel button
                LoadingIndicator.show("Searching entire RAM for correct pattern...", allow_cancel=True)

                # If pattern is small, expand it with surrounding context to reduce false positives
                search_pattern = expected_data
                pattern_offset_in_search = 0  # Offset of the actual pattern within the search pattern

                MIN_SEARCH_SIZE = 32  # Minimum search pattern size to avoid too many matches
                if len(expected_data) < MIN_SEARCH_SIZE:
                    # Read extra context from the file (before and after the pattern)
                    context_size = (MIN_SEARCH_SIZE - len(expected_data)) // 2

                    try:
                        with open(game_file_path, 'rb') as f:
                            # Read bytes before
                            bytes_before_offset = max(0, file_offset - context_size)
                            f.seek(bytes_before_offset)
                            bytes_before = f.read(file_offset - bytes_before_offset)

                            # Read the actual pattern (already in expected_data)

                            # Read bytes after
                            f.seek(file_offset + len(expected_data))
                            bytes_after = f.read(context_size)

                            # Combine into expanded search pattern
                            search_pattern = bytes_before + expected_data + bytes_after
                            pattern_offset_in_search = len(bytes_before)

                            _add_verify_result(f"Pattern is small ({len(expected_data)} bytes), expanded to {len(search_pattern)} bytes with context", (200, 200, 200))
                    except Exception as e:
                        _add_verify_result(f"Could not read context, searching with original pattern: {e}", (255, 200, 100))

                # Search entire RAM for the pattern
                matches = _search_memory(emu_service, handle, main_ram, search_pattern, _emulator_connection.emu_info)

                # Hide loading indicator after search
                LoadingIndicator.hide()
                _add_verify_result("", (255, 255, 255))  # Spacer

                # Check if search was cancelled
                if matches is None:
                    _add_verify_result("Search cancelled by user", (255, 200, 100))
                elif not matches:
                    _add_verify_result("Pattern not found anywhere in memory", (255, 100, 100))
                    _add_verify_result("The game file may have been modified or the wrong version is loaded", (255, 100, 100))
                elif len(matches) == 1:
                    # Adjust found address to account for pattern offset within search pattern
                    found_address = matches[0] + pattern_offset_in_search
                    _add_verify_result(f"Found at: 0x{found_address:X}", (100, 255, 100))

                    # Calculate what the memory address should be
                    corrected_offset = found_address - main_ram
                    corrected_memory_addr = f"0x80{corrected_offset:06X}"

                    _add_verify_result(f"Correct Memory Address: {corrected_memory_addr}", (100, 255, 100))
                    _add_verify_result(f"Address Offset Difference: 0x{abs(corrected_offset - offset):X}", (200, 200, 200))
                    _add_verify_result("", (255, 255, 255))  # Spacer

                    # Ask user if they want to update
                    response = messagebox.askyesno(
                        "Update Memory Address?",
                        f"Would you like to update the {verify_type.lower()} with the correct memory address?\n\n"
                        f"{verify_type}: {item_name}\n"
                        f"Current Address: {memory_address}\n"
                        f"New Address: {corrected_memory_addr}"
                    )

                    if response:
                        try:
                            if verify_type == "Codecave":
                                codecave.SetMemoryAddress(corrected_memory_addr)
                                _add_verify_result("Updated codecave memory address!", (100, 255, 100))
                            elif verify_type == "Hook":
                                hook.SetMemoryAddress(corrected_memory_addr)
                                _add_verify_result("Updated hook memory address!", (100, 255, 100))
                            elif verify_type == "Binary Patch":
                                patch.SetMemoryAddress(corrected_memory_addr)
                                _add_verify_result("Updated binary patch memory address!", (100, 255, 100))

                            # Save the project file
                            ProjectSerializer.save_project(current_project_data)
                            _add_verify_result("Project configuration saved", (100, 255, 100))
                        except Exception as e:
                            _add_verify_result(f"Error: Could not update: {e}", (255, 100, 100))
                    else:
                        _add_verify_result("Update cancelled by user", (200, 200, 200))
                else:
                    _add_verify_result(f"Found {len(matches)} potential matches:", (255, 200, 100))
                    for i, found_address_raw in enumerate(matches[:10]):  # Show first 10
                        # Adjust for pattern offset
                        found_address = found_address_raw + pattern_offset_in_search
                        corrected_offset = found_address - main_ram
                        corrected_memory_addr = f"0x80{corrected_offset:06X}"
                        _add_verify_result(f"  Match {i+1}: {corrected_memory_addr} (0x{found_address:X})", (200, 200, 200))

                    if len(matches) > 10:
                        _add_verify_result(f"  ... and {len(matches) - 10} more", (200, 200, 200))

                    _add_verify_result("", (255, 255, 255))  # Spacer
                    _add_verify_result("Multiple matches found - manual verification needed", (255, 200, 100))

            # Don't close handle - we're caching it for performance

        except Exception as e:
            import traceback
            LoadingIndicator.hide()
            dpg.delete_item("memory_verify_results", children_only=True)
            _add_verify_result(f"ERROR: {str(e)}", (255, 100, 100))
            _add_verify_result(traceback.format_exc(), (150, 150, 150))
            messagebox.showerror("Error", f"Error during verification:\n\n{str(e)}")

    # Start background thread
    threading.Thread(target=verify_thread, daemon=True).start()

# ==================== Continuous Codecave Monitoring ====================

# Global monitoring state
_codecave_monitor_active = False
_codecave_monitor_thread = None
_codecave_snapshots: Dict[str, bytes] = {}
_codecave_alerted: Dict[str, bool] = {}  

def _start_codecave_monitoring(current_project_data: ProjectData):
    """Start continuous monitoring of all codecaves"""
    global _codecave_monitor_active, _codecave_monitor_thread, _codecave_snapshots

    if _codecave_monitor_active:
        return

    emulator_name = dpg.get_value("emu_tools_emulator_combo")
    if emulator_name == "No emulators running":
        messagebox.showerror("No Emulator", "Please connect to an emulator first")
        return

    # Check if connected
    if not _emulator_connection.is_valid:
        messagebox.showerror("Not Connected", "Please click Connect button first")
        return

    # Clear previous results
    children = dpg.get_item_children("codecave_verification_table", slot=1)
    if children:
        for child in children:
            dpg.delete_item(child)

    # Update UI
    dpg.configure_item("codecave_monitor_start_btn", enabled=False, show=False)
    dpg.configure_item("codecave_monitor_stop_btn", enabled=True, show=True)
    dpg.configure_item("emu_tools_connect_button", enabled=False)
    dpg.set_value("codecave_monitor_status", "Starting monitoring...")
    dpg.configure_item("codecave_monitor_status", color=(255, 200, 100))

    # Start monitoring
    _codecave_monitor_active = True
    _codecave_snapshots = {}
    _codecave_alerted = {}

    def monitor_loop():
        try:
            emu_service = EmulatorService(current_project_data)
            current_build = current_project_data.GetCurrentBuildVersion()
            codecaves = current_build.GetCodeCaves()

            if not codecaves:
                dpg.set_value("codecave_monitor_status", "No codecaves to monitor")
                _stop_codecave_monitoring()
                return

            # Take initial snapshots
            dpg.set_value("codecave_monitor_status", f"Monitoring {len(codecaves)} codecaves...")
            dpg.configure_item("codecave_monitor_status", color=(100, 255, 100))

            for codecave in codecaves:
                memory_addr = codecave.GetMemoryAddress()
                size = codecave.GetSizeAsInt()

                if not memory_addr or size == 0:
                    continue

                # Calculate target address
                offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                target_address = _emulator_connection.main_ram + offset

                # Read initial snapshot
                snapshot = emu_service._read_memory(_emulator_connection.handle, target_address, size)
                if snapshot:
                    _codecave_snapshots[codecave.GetName()] = snapshot

                    # Add to table - show initial status
                    _add_codecave_result(codecave.GetName(), memory_addr, f"{size:X}", "MONITORING", "No writes detected", (100, 200, 255))

            # Continuous monitoring loop
            while _codecave_monitor_active:
                import time
                time.sleep(0.5)  # Check every 500ms

                if not _emulator_connection.validate():
                    dpg.set_value("codecave_monitor_status", "Connection lost")
                    dpg.configure_item("codecave_monitor_status", color=(255, 100, 100))
                    _stop_codecave_monitoring()
                    break

                # Check each codecave for changes
                for codecave in codecaves:
                    if not _codecave_monitor_active:
                        break

                    name = codecave.GetName()
                    if name not in _codecave_snapshots:
                        continue

                    memory_addr = codecave.GetMemoryAddress()
                    offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                    target_address = _emulator_connection.main_ram + offset
                    size = codecave.GetSizeAsInt()

                    # Read current memory
                    current_data = emu_service._read_memory(_emulator_connection.handle, target_address, size)

                    if current_data is None:
                        continue

                    # Compare with snapshot
                    if current_data != _codecave_snapshots[name]:
                        # Check if we've already alerted for this codecave
                        if name not in _codecave_alerted or not _codecave_alerted[name]:
                            # FIRST TIME DETECTING CHANGE! Find exact byte offset(s) that changed
                            old_snapshot = _codecave_snapshots[name]
                            changed_offsets = []
                            for i in range(min(len(current_data), len(old_snapshot))):
                                if current_data[i] != old_snapshot[i]:
                                    changed_offsets.append(i)

                            # Calculate exact memory addresses that were written
                            base_offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                            changed_addresses = [f"0x80{base_offset + off:06X}" for off in changed_offsets[:10]]  # Show first 10

                            dpg.set_value("codecave_monitor_status", f"WRITE DETECTED in {name}!")
                            dpg.configure_item("codecave_monitor_status", color=(255, 100, 100))

                            # Update table row to show change
                            children = dpg.get_item_children("codecave_verification_table", slot=1)
                            if children:
                                for child in children:
                                    dpg.delete_item(child)

                            # Re-add all rows with updated status
                            for cc in codecaves:
                                cc_name = cc.GetName()
                                cc_addr = cc.GetMemoryAddress()
                                cc_size = cc.GetSizeAsInt()

                                if cc_name in _codecave_snapshots:
                                    if cc_name == name:
                                        # This one changed - show exact addresses
                                        if len(changed_addresses) == 1:
                                            details = f"Write detected at {changed_addresses[0]}"
                                        elif len(changed_addresses) <= 5:
                                            details = f"Writes at: {', '.join(changed_addresses)}"
                                        else:
                                            details = f"{len(changed_offsets)} bytes changed (first: {changed_addresses[0]})"

                                        _add_codecave_result(cc_name, cc_addr, f"{cc_size:X}",
                                                            "WRITTEN!",
                                                            details,
                                                            (255, 100, 100))
                                    else:
                                        # Check if this one was previously alerted
                                        if cc_name in _codecave_alerted and _codecave_alerted[cc_name]:
                                            _add_codecave_result(cc_name, cc_addr, f"{cc_size:X}",
                                                                "WRITTEN!", "Write detected earlier", (255, 100, 100))
                                        else:
                                            # Still clean
                                            _add_codecave_result(cc_name, cc_addr, f"{cc_size:X}",
                                                                "OK", "No writes detected", (100, 255, 100))

                            # Alert user with exact addresses (ONLY ONCE)
                            if len(changed_addresses) == 1:
                                addr_info = f"Address written: {changed_addresses[0]}"
                            elif len(changed_addresses) <= 5:
                                addr_info = f"Addresses written:\n" + "\n".join(changed_addresses)
                            else:
                                addr_info = f"{len(changed_offsets)} bytes changed\nFirst address: {changed_addresses[0]}"

                            messagebox.showwarning("Codecave Write Detected!",
                                f"Codecave '{name}' was written to during gameplay!\n\n"
                                f"This codecave may not be safe to use.\n\n"
                                f"{addr_info}\n")

                            # Mark this codecave as alerted
                            _codecave_alerted[name] = True

                        # Update snapshot (always update, even if already alerted)
                        _codecave_snapshots[name] = current_data

        except Exception as e:
            import traceback
            dpg.set_value("codecave_monitor_status", "Monitor error")
            dpg.configure_item("codecave_monitor_status", color=(255, 100, 100))
            messagebox.showerror("Monitor Error", f"Error during monitoring:\n\n{str(e)}\n\n{traceback.format_exc()}")
            _stop_codecave_monitoring()

    _codecave_monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    _codecave_monitor_thread.start()

def _stop_codecave_monitoring():
    """Stop continuous monitoring"""
    global _codecave_monitor_active

    _codecave_monitor_active = False

    # Update UI
    dpg.configure_item("codecave_monitor_start_btn", enabled=True, show=True)
    dpg.configure_item("codecave_monitor_stop_btn", enabled=False, show=False)
    dpg.configure_item("emu_tools_connect_button", enabled=True)
    dpg.set_value("codecave_monitor_status", "Monitoring stopped")
    dpg.configure_item("codecave_monitor_status", color=(150, 150, 150))

def _fill_codecaves_with_pattern(current_project_data: ProjectData):
    """Fill all codecaves with test pattern (0xAA) to detect game crashes or weird behavior"""
    emulator_name = dpg.get_value("emu_tools_emulator_combo")
    if emulator_name == "No emulators running":
        messagebox.showerror("No Emulator", "Please connect to a running emulator first")
        return

    # Check if connected
    if not _emulator_connection.is_valid:
        messagebox.showerror("Not Connected", "Please click Connect button first")
        return

    # Confirm with user
    current_build = current_project_data.GetCurrentBuildVersion()
    codecaves = current_build.GetCodeCaves()

    if not codecaves:
        messagebox.showinfo("No Codecaves", "No codecaves to fill")
        return

    confirm = messagebox.askyesno(
        "Fill Codecaves with Test Pattern",
        f"This will fill {len(codecaves)} codecave(s) with 0xAA bytes.\n\n"
        "This helps detect if the game uses these memory regions.\n"
        "If the game crashes, or exhibits strange behavior, these bytes may not be safe.\n\n"
        "Continue?"
    )

    if not confirm:
        return

    # Show loading indicator
    LoadingIndicator.show("Filling codecaves with pattern...")

    def fill_thread():
        try:
            emu_service = EmulatorService(current_project_data)
            filled_count = 0

            for codecave in codecaves:
                memory_addr = codecave.GetMemoryAddress()
                size = codecave.GetSizeAsInt()

                if not memory_addr or size == 0:
                    continue

                # Calculate target address
                offset = int(memory_addr.removeprefix("0x").removeprefix("80"), 16)
                target_address = _emulator_connection.main_ram + offset

                # Create pattern: fill with 0xAA bytes
                pattern = bytes([0xAA] * size)

                # Write pattern to memory
                success = emu_service._write_memory(_emulator_connection.handle, target_address, pattern)

                if success:
                    filled_count += 1
                    # Update snapshot if monitoring is active
                    if _codecave_monitor_active and codecave.GetName() in _codecave_snapshots:
                        _codecave_snapshots[codecave.GetName()] = pattern

            LoadingIndicator.hide()

            if filled_count == len(codecaves):
                messagebox.showinfo(
                    "Success",
                    f"Filled {filled_count} codecave(s) with 0xAA pattern.\n\n"
                    "Watch for crashes or strange behavior in the game.\n"
                )
            else:
                messagebox.showwarning(
                    "Partial Success",
                    f"Filled {filled_count} of {len(codecaves)} codecave(s).\n\n"
                    "Some codecaves could not be written."
                )

        except Exception as e:
            import traceback
            LoadingIndicator.hide()
            messagebox.showerror("Error", f"Error filling codecaves:\n\n{str(e)}\n\n{traceback.format_exc()}")

    # Run in background thread
    threading.Thread(target=fill_thread, daemon=True).start()
