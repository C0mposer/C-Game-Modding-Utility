import dearpygui.dearpygui as dpg
import os
import sys
import time
import pyperclip
from tkinter import messagebox
from tkinter import filedialog
import tkinter as tk
from typing import Tuple
from classes.project_data.project_data import ProjectData
from classes.mod_builder import ModBuilder
from gui.gui_main_project_callbacks import *
from services.iso_service import ISOService
from services.emulator_service import EmulatorService
from services.emulator_connection_manager import get_emulator_manager
from functions.verbose_print import verbose_print
from services.cheat_code_service import CheatCodeService, check_gecko_length, GECKO_MAX_LINES
from services.game_metadata_service import GameMetadataService
from path_helper import get_application_directory

compiler_output_value = "Ready for compilation..."
emulator_options = ["Dolphin    (Default)", "RetroArch (Citra)", "RPCS3", "Cemu"]
selected_emulator = emulator_options[0]
is_compilation_successful = False

# Get tool directory - initialized lazily to handle PyInstaller bundling
_tool_dir = None
mod_data = None

def _get_tool_dir():
    """Get the tool directory, handling PyInstaller bundling."""
    global _tool_dir
    if _tool_dir is None:
        _tool_dir = get_application_directory()
    return _tool_dir

def _get_mod_data():
    """Get or create the ModBuilder instance with correct tool_dir."""
    global mod_data
    if mod_data is None:
        mod_data = ModBuilder(tool_dir=_get_tool_dir())
    return mod_data

# Check if verbose mode is enabled
VERBOSE_MODE = '-verbose' in sys.argv or '--verbose' in sys.argv

# No warnings mode (can be toggled via GUI checkbox)
NO_WARNINGS_MODE = False

# Per-project "don't ask again" flag for opening folder after build
_dont_ask_open_folder = False

def askyesno_with_checkbox(title, message, checkbox_text="Don't ask me again"):
    """
    Simple yes/no dialog with checkbox, using messagebox style.
    Returns tuple: (yes/no response, checkbox state)
    """
    result = {'response': False, 'dont_ask': False}

    # Create hidden root if needed
    root = tk.Tk()
    root.withdraw()

    # Create dialog
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.resizable(False, False)

    # Message
    tk.Label(dialog, text=message, padx=20, pady=20).pack()

    # Checkbox
    checkbox_var = tk.BooleanVar(value=False)
    tk.Checkbutton(dialog, text=checkbox_text, variable=checkbox_var).pack(pady=(0, 10))

    # Buttons
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=(0, 10))

    def on_yes():
        result['response'] = True
        result['dont_ask'] = checkbox_var.get()
        dialog.destroy()
        root.destroy()

    def on_no():
        result['response'] = False
        result['dont_ask'] = checkbox_var.get()
        dialog.destroy()
        root.destroy()

    tk.Button(button_frame, text="Yes", command=on_yes, width=10).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="No", command=on_no, width=10).pack(side=tk.LEFT, padx=5)

    # Center dialog
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'+{x}+{y}')

    dialog.grab_set()
    dialog.wait_window()

    return result['response'], result['dont_ask']

def reset_build_preferences():
    """Reset ALL build-related state when project closes"""
    global _dont_ask_open_folder, compiler_output_value, is_compilation_successful, mod_data

    _dont_ask_open_folder = False
    compiler_output_value = "Ready for compilation..."
    is_compilation_successful = False
    mod_data = ModBuilder(tool_dir=_get_tool_dir())  # Create fresh ModBuilder instance

    # Reset compiler output textbox if it exists
    if dpg.does_item_exist("compiler_output_textbox"):
        dpg.set_value("compiler_output_textbox", compiler_output_value)

def update_build_status(message: str, status: str = "normal"):
    """
    Update the build status label with a message and color.

    Args:
        message: Status message to display
        status: Status type - "normal", "compiling", "success", "error"
    """
    if not dpg.does_item_exist("build_status_label"):
        return

    dpg.set_value("build_status_label", message)

    # Set color based on status
    if status == "success":
        color = (100, 255, 100)  # Green
    elif status == "error":
        color = (255, 100, 100)  # Red
    elif status == "compiling":
        color = (200, 200, 100)  # Yellow
    else:
        color = (200, 200, 200)  # Gray (normal)

    dpg.bind_item_theme("build_status_label", 0)  # Clear theme first
    with dpg.theme() as status_theme:
        with dpg.theme_component(dpg.mvText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, color, category=dpg.mvThemeCat_Core)
    dpg.bind_item_theme("build_status_label", status_theme)

def update_size_analysis_visual(analyzer):
    """Update the visual code size analysis display with progress bars"""
    # Clear previous content
    if dpg.does_item_exist("size_analysis_container"):
        dpg.delete_item("size_analysis_container", children_only=True)
    else:
        return

    results = analyzer.analyze_all()
    if not results:
        dpg.configure_item("size_analysis_header", show=False)
        return

    # Show the header
    dpg.configure_item("size_analysis_header", show=True)

    # Rows of 3
    amount_of_rows = 3
    current_row = None
    for i, result in enumerate(results):
        # Create a new horizontal row group every 4 items
        if i % amount_of_rows == 0:
            current_row = dpg.add_group(parent="size_analysis_container", horizontal=True)

        # Create vertical group for each item (column)
        with dpg.group(parent=current_row, horizontal=False):
            # Section name and type
            type_str = result.injection_type.replace('_', ' ').title()
            dpg.add_text(f"{type_str}: {result.name}")

            # Size info with status indicator on same line
            used_hex = f"0x{result.used_bytes:X}"
            allocated_hex = f"0x{result.allocated_bytes:X}"
            bytes_left_int = int(allocated_hex, base=16) - int(used_hex, base=16)
            bytes_left_hex = hex(bytes_left_int)
            percentage = result.percentage_used
            
            with dpg.group(horizontal=True):
                dpg.add_text(f"  {used_hex} / {allocated_hex} ({percentage:.1f}%)")
                # if result.is_overflow:
                #     dpg.add_text("OVERFLOW", color=(255, 100, 100))
                # elif result.warning_level == "critical":
                #     bytes_left_color = (255, 50, 0)
                # elif result.warning_level == "warning":
                #     bytes_left_color = (255, 200, 50)
                # else:
                #     dpg.add_text("OK", color=bytes_left_color)
                
                bytes_left_color = (255, 255, 220)
                dpg.add_text(f" {bytes_left_hex} bytes left", color=bytes_left_color)

            # Visual progress bar
            progress_value = min(percentage / 100.0, 1.0)

            dpg.add_progress_bar(
                default_value=progress_value,
                width=300,
                overlay=f"{percentage:.1f}%"
            )

        # Add spacing between rows
        if (i + 1) % amount_of_rows == 0 and i < len(results) - 1:
            dpg.add_spacer(parent="size_analysis_container", height=10)

def display_linker_overflow_visual(overflow_errors):
    """Display linker overflow errors in the size analysis area"""
    if not overflow_errors:
        return

    # Clear previous content
    if dpg.does_item_exist("size_analysis_container"):
        dpg.delete_item("size_analysis_container", children_only=True)
    else:
        return

    # Show the header
    if dpg.does_item_exist("size_analysis_header"):
        dpg.configure_item("size_analysis_header", show=True)

    # Display overflow errors
    with dpg.group(parent="size_analysis_container", horizontal=False):
        dpg.add_text("LINKER ERRORS - OVERFLOW DETECTED", color=(255, 100, 100))
        dpg.add_spacer(height=5)

        for overflow_info in overflow_errors:
            section_name = overflow_info['section']
            overflow_bytes = overflow_info['overflow_bytes']

            with dpg.group(horizontal=False):
                dpg.add_text(f"Section: {section_name}", color=(255, 150, 150))
                dpg.add_text(f"  Overflowed by: {overflow_bytes}", color=(255, 200, 200))
                dpg.add_spacer(height=10)

# Text wrapping helper
def wrap_text(text: str, max_width: int = 120) -> str:
    """Wrap text to fit within a certain character width"""
    lines = text.split('\n')
    wrapped_lines = []
    
    for line in lines:
        if len(line) <= max_width:
            wrapped_lines.append(line)
        else:
            # Wrap long lines
            while len(line) > max_width:
                # Try to break at a space
                break_point = line[:max_width].rfind(' ')
                if break_point == -1:
                    break_point = max_width
                
                wrapped_lines.append(line[:break_point])
                line = line[break_point:].lstrip()
            
            if line:
                wrapped_lines.append(line)
    
    return '\n'.join(wrapped_lines)

# --- GUI Layout Function for Compiler & Emulator ---
def CreateCompileAndBuildGui(current_project_data: ProjectData):
    
    dpg.add_spacer(height=10)

    # --- Compiler Section ---
    dpg.add_text("Compiler Settings", tag="compiler_settings_text")
    dpg.add_separator(tag="compiler_separator")
    
    current_flags = current_project_data.GetCurrentBuildVersion().GetCompilerFlags()
    
    platform = current_project_data.GetCurrentBuildVersion().GetPlatform()

    # Compiler Flags Input
    with dpg.group(horizontal=True, tag="compiler_flags_group"):
        dpg.add_text("Compiler Flags:", tag="compiler_flags_label")
        dpg.add_input_text(
            default_value=current_flags,
            tag="compiler_flags_input",
            hint="e.g., -O2 -Wall -c",
            width=-1,
            callback=callback_compiler_flags_changed,
            user_data=current_project_data
        )

    dpg.add_spacer(height=5)

    # No Warnings Checkbox
    dpg.add_checkbox(
        label="Hide Warnings (errors still shown)",
        tag="no_warnings_checkbox",
        default_value=NO_WARNINGS_MODE,
        callback=callback_no_warnings_changed
    )

    dpg.add_spacer(height=5)

    # Compile Button
    dpg.add_button(
        label="Compile",
        tag="compile_button",
        width=-1,
        callback=callback_compile,
        user_data=current_project_data
    )

    dpg.add_spacer(height=10)

    # Compiler Output (WITH WORD WRAP AND SELECTABLE TEXT!)
    dpg.add_text("Output:", tag="compiler_output_label")

    # Compiler output text area
    dpg.add_input_text(
        default_value=compiler_output_value,
        tag="compiler_output_textbox",
        multiline=True,
        readonly=True,
        width=-1,
        height=200,
        tab_input=True
    )

    # Status indicator below log
    dpg.add_text("", tag="build_status_label")

    # Code Size Visualization (initially hidden)
    with dpg.collapsing_header(label="Code Size Analysis", tag="size_analysis_header", default_open=True, show=False):
        with dpg.group(tag="size_analysis_container"):
            pass  # Will be populated dynamically


        dpg.add_spacer(height=20)

    # Emulator / Build / Export Cheats Section 
    with dpg.group(tag="emulator_iso_buttons_group_container", show=False):
        dpg.add_text("Emulator / Build / Export")
        dpg.add_separator()

        column_width = 320  # Adjusted for 1024px viewport (was 484 for 1500px)
        child_height = 220

        with dpg.group(horizontal=True, tag="emulator_iso_buttons_row_group"):

            # ===== LEFT: Emulator Injection =====
            with dpg.child_window(
                tag="emulator_child_window",
                border=True,
                width=column_width,
                height=child_height
            ):
                dpg.add_text("Emulator Injection")
                dpg.add_separator()

                # Emulator Options Dropdown with Refresh
                with dpg.group(horizontal=True):
                    dpg.add_text("Select Emulator:", tag="select_emulator_label")
                    dpg.add_button(
                        label="Refresh",
                        callback=callback_refresh_emulators,
                        user_data=current_project_data
                    )
                    
                dpg.add_spacer(height=7)
                
                dpg.add_combo(
                    items=["No emulators detected"],
                    default_value="No emulators detected",
                    tag="emulator_dropdown",
                    width=-1,
                )

                dpg.add_spacer(height=5)

                dpg.add_button(
                    label="Inject into Emulator",
                    tag="inject_emulator_button",
                    width=-1,
                    callback=callback_inject_emulator,
                    user_data=current_project_data
                )

            # ===== MIDDLE: Build Options =====
            with dpg.child_window(
                tag="build_options_child_window",
                border=True,
                width=column_width,
                height=child_height
            ):
                
                current_build = current_project_data.GetCurrentBuildVersion()
                platform = current_build.GetPlatform()
                
                dpg.add_text("Build Options")
                dpg.add_separator()
                
                # Only space the gui if there is not ISO options like for GC/Wii
                if platform == "PS1" or platform == "PS2":
                    dpg.add_spacer(height=20)

                is_single_file = current_build.IsSingleFileMode()
                button_label = "Open Patched File" if is_single_file else "Build ISO"

                output_format = current_build.GetOutputFormat() or "iso"

                if platform == "Gamecube":
                    #dpg.add_spacer(height=5)
                    dpg.add_text("Output Format:")
                    with dpg.group(horizontal=True):
                        dpg.add_radio_button(
                            items=["ISO", "CISO", "GCM"],
                            default_value=output_format.upper(),
                            tag="gc_output_format_radio",
                            callback=lambda s, a, u: u.GetCurrentBuildVersion().SetOutputFormat(a.lower()),
                            user_data=current_project_data,
                            horizontal=True
                        )

                elif platform == "Wii":
                    #dpg.add_spacer(height=5)
                    dpg.add_text("Output Format:")
                    with dpg.group(horizontal=True):
                        dpg.add_radio_button(
                            items=["ISO", "WBFS"],
                            default_value=output_format.upper(),
                            tag="wii_output_format_radio",
                            callback=lambda s, a, u: u.GetCurrentBuildVersion().SetOutputFormat(a.lower()),
                            user_data=current_project_data,
                            horizontal=True
                        )
                        
                dpg.add_spacer(height=5)  
                      
                dpg.add_button(
                    label=button_label,
                    tag="build_iso_button",
                    width=-1,
                    callback=callback_build_iso,
                    user_data=current_project_data
                )

                dpg.add_spacer(height=5)

                dpg.add_button(
                    label="Generate xdelta Patch",
                    tag="xdelta_button",
                    width=-1,
                    callback=callback_generate_xdelta,
                    user_data=current_project_data
                )

            # ===== RIGHT: Export Cheats =====
            with dpg.child_window(
                tag="export_cheats_child_window",
                border=True,
                width=column_width,
                height=child_height
            ):
                dpg.add_text("Export Cheats")
                dpg.add_separator()

                current_build = current_project_data.GetCurrentBuildVersion()
                platform = current_build.GetPlatform()

                # Normalize some possible platform strings
                platform_norm = (platform or "").strip().upper()

                if platform_norm in ("PS1", "PSX"):
                    dpg.add_text("PlayStation 1")
                    dpg.add_spacer(height=5)

                    dpg.add_button(
                        label="Generate GameShark Code (PS1)",
                        width=-1,
                        callback=callback_generate_ps1_gameshark,
                        user_data=current_project_data
                    )

                elif platform_norm == "PS2":
                    dpg.add_text("PlayStation 2")
                    dpg.add_spacer(height=5)

                    dpg.add_button(
                    label="Generate pnach (PCSX2)",
                    width=-1,
                    callback=callback_generate_ps2_pnach,
                    user_data=current_project_data
                    )
                    
                    dpg.add_spacer(height=5)
                    
                    dpg.add_button(
                        label="Generate PS2RD/CheatDevicePS2 Code",
                        width=-1,
                        callback=callback_generate_ps2_ps2rd,
                        user_data=current_project_data
                    )

                
                    
                elif platform_norm == "GAMECUBE":
                    dpg.add_text("Gamecube")
                    dpg.add_spacer(height=5)
                    dpg.add_button(
                        label="Generate Action Replay Code",
                        width=-1,
                        callback=callback_generate_gc_ar,
                        user_data=current_project_data
                    )
                    dpg.add_spacer(height=5)
                    dpg.add_button(
                        label="Generate Gecko Code",
                        width=-1,
                        callback=callback_generate_gc_gecko,
                        user_data=current_project_data
                    )

                elif platform_norm == "WII":
                    dpg.add_text("Wii")
                    dpg.add_spacer(height=5)
                    dpg.add_button(
                        label="Generate Action Replay Code",
                        width=-1,
                        callback=callback_generate_wii_ar,
                        user_data=current_project_data
                    )
                    
                    dpg.add_spacer(height=5)
                    
                    dpg.add_button(
                        label="Generate Gecko Code",
                        width=-1,
                        callback=callback_generate_wii_gecko,
                        user_data=current_project_data
                    )
                    
                    dpg.add_spacer(height=5)
                    
                    dpg.add_button(
                        label="Generate Riivolution XML",
                        width=-1,
                        callback=callback_generate_riivolution_xml,
                        user_data=current_project_data
                    )
                    
                    

                else:
                    dpg.add_text("Cheat export not yet implemented for this platform.")
                    dpg.add_spacer(height=5)
                    dpg.add_text("- PS1: GameShark", bullet=True)
                    dpg.add_text("- PS2: PS2RD / pnach (soon)", bullet=True)
                    dpg.add_text("- GCN/Wii: AR / Gecko / Riivolution (planned)", bullet=True)



# --- Validation Function ---
def validate_project_for_compilation(current_project_data: ProjectData) -> Tuple[bool, str]:
    """Validate that project is ready for compilation"""
    
    # Check if there are any codecaves or hooks
    if (not current_project_data.GetCurrentBuildVersion().GetCodeCaves() and 
        not current_project_data.GetCurrentBuildVersion().GetHooks()):
        return False, "No codecaves or hooks defined. Add code to compile."
    
    # Check if codecaves have source files
    for cave in current_project_data.GetCurrentBuildVersion().GetCodeCaves():
        if not cave.GetCodeFilesPaths():
            return False, f"Codecave '{cave.GetName()}' has no source files."
        if not cave.GetMemoryAddress():
            return False, f"Codecave '{cave.GetName()}' has no memory address set."
    
    # Check if hooks have source files  
    for hook in current_project_data.GetCurrentBuildVersion().GetHooks():
        if not hook.GetCodeFilesPaths():
            return False, f"Hook '{hook.GetName()}' has no source files."
        if not hook.GetMemoryAddress():
            return False, f"Hook '{hook.GetName()}' has no memory address set."
        
    # Check binary patches
    for patch in current_project_data.GetCurrentBuildVersion().GetBinaryPatches():
        if not patch.GetCodeFilesPaths():
            return False, f"Binary patch '{patch.GetName()}' has no binary file selected."
        if not patch.GetMemoryAddress():
            return False, f"Binary patch '{patch.GetName()}' has no memory address set."
    
    # Check if symbols file exists
    project_folder = current_project_data.GetProjectFolder()
    build_name = current_project_data.GetCurrentBuildVersion().GetBuildName()
    symbols_file = current_project_data.GetCurrentBuildVersion().GetSymbolsFile()
    
    if not symbols_file:
        return False, f"Symbols file not found: {symbols_file}"
    
    return True, "Validation passed"


# --- Callbacks for the GUI Elements ---

def callback_compile(sender, app_data, current_project_data):
    """
    Callback function for the 'Compile' button.
    Uses the new CompilationService with verbose mode detection.
    """
    global is_compilation_successful, mod_data

    verbose_print("Compile button pressed!")
    
    # Validate before compiling
    is_valid, message = validate_project_for_compilation(current_project_data)
    if not is_valid:
        messagebox.showerror("Validation Failed", message)
        dpg.set_value("compiler_output_textbox", f"Validation failed: {message}\n")
        return
    
    # Clear previous output
    dpg.set_value("compiler_output_textbox", "")
    update_build_status("Compiling...", "compiling")

    # Create compilation service with verbose mode
    from services.compilation_service import CompilationService

    compilation_service = CompilationService(current_project_data, _get_mod_data(), verbose=VERBOSE_MODE, no_warnings=NO_WARNINGS_MODE)
    
    # Set up progress callbacks
    def on_progress(message: str):
        current_output = dpg.get_value("compiler_output_textbox")
        new_output = current_output + message + "\n"
        # Wrap the entire output to prevent horizontal scrolling
        wrapped_output = wrap_text(new_output, max_width=160)
        dpg.set_value("compiler_output_textbox", wrapped_output)

    def on_error(message: str):
        try:
            current_output = dpg.get_value("compiler_output_textbox")
            new_output = current_output + f"{message}\n"
            # Wrap the entire output to prevent horizontal scrolling
            wrapped_output = wrap_text(new_output, max_width=160)
            dpg.set_value("compiler_output_textbox", wrapped_output)
        except Exception as e:
            print(f"Error in on_error callback: {e}")
            import traceback
            traceback.print_exc()
    
    compilation_service.on_progress = on_progress
    compilation_service.on_error = on_error

    # Run compilation with timing
    start_time = time.time()
    result = compilation_service.compile_project()
    elapsed_time = time.time() - start_time

    # Update success state
    is_compilation_successful = result.success
    
    # Show/hide emulator buttons based on success
    dpg.configure_item("emulator_iso_buttons_group_container", show=result.success)

    # Check if emulators were already scanned (from other windows) and populate dropdown
    if result.success:
        manager = get_emulator_manager()
        if manager.available_emulators:
            dpg.configure_item("emulator_dropdown", items=manager.available_emulators)
            dpg.set_value("emulator_dropdown", manager.available_emulators[0])
            print(f"[Build] Restored {len(manager.available_emulators)} emulators from cache")

    # ALWAYS show size analysis on successful compilation
    if result.success:
        from services.size_analyzer_service import SizeAnalyzerService
        analyzer = SizeAnalyzerService(current_project_data)

        display_size_analysis_console(analyzer)

        # Update visual size analysis display (progress bars below status)
        update_size_analysis_visual(analyzer)

        # Build shared banner strings
        banner_top = "\n" + "=" * 60
        banner_msg = f"COMPILATION SUCCESSFUL! (Took {elapsed_time:.2f}s)"
        banner_bottom = "=" * 60

        # Show success message after size analysis in the log window
        on_progress(banner_top)
        on_progress(banner_msg)
        on_progress(banner_bottom)

        # Also print the same banner to the command line / terminal
        print(banner_top)
        print(banner_msg)
        print(banner_bottom)

        # Update status indicator
        update_build_status(f"Compilation Successful! ({elapsed_time:.2f}s)", "success")
    else:
        # Compilation failed
        update_build_status("Compilation Failed!", "error")

        # If linker overflow errors exist, display them in the size analysis area
        if result.linker_overflow_errors:
            display_linker_overflow_visual(result.linker_overflow_errors)
        else:
            # Hide visual size analysis if no overflow errors
            if dpg.does_item_exist("size_analysis_header"):
                dpg.configure_item("size_analysis_header", show=False)


# ========== NEW FUNCTION: Console output with full formatting ==========
def display_size_analysis_console(analyzer):
    """Display detailed code size analysis to Windows console with progress bars"""
    from services.size_analyzer_service import SizeAnalyzerService
    
    results = analyzer.analyze_all()
    
    if not results:
        print("\nNo size data available (compile first or set sizes)")
        return
    
    print("\n" + "=" * 60)
    print("CODE SIZE ANALYSIS")
    print("=" * 60)
    
    for result in results:
        # Format type
        type_str = result.injection_type.replace('_', ' ').title()
        
        # Format sizes
        used_hex = f"0x{result.used_bytes:X}"
        allocated_hex = f"0x{result.allocated_bytes:X}"
        percentage = result.percentage_used
        
        # Create progress bar (full Unicode for console)
        bar_width = 30
        filled = int((percentage / 100.0) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        # Color/symbol based on warning level
        # if result.warning_level == "overflow":
        #     status = "🔴 OVERFLOW"
        # elif result.warning_level == "critical":
        #     status = "🟠 CRITICAL"
        # elif result.warning_level == "warning":
        #     status = "🟡 WARNING"
        # else:
        #     status = "🟢 OK"
        
        # Build output line
        print(f"\n{type_str}: {result.name}")
        print(f"  Used: {used_hex} of {allocated_hex} ({percentage:.1f}%)")
        print(f"  [{bar}]")
        print(f"  0x{result.remaining_bytes:X} bytes remaining")
        
        if result.is_overflow:
            overflow = result.used_bytes - result.allocated_bytes
            print(f"  OVERFLOW BY 0x{overflow:X} bytes!")
    
    # Summary
    summary = analyzer.get_summary()
    print("\n" + "-" * 60)
    print(f"SUMMARY: {summary['total_count']} target(s)")
    print(f"  Total Used: 0x{summary['total_used']:X} bytes")
    print(f"  Total Allocated: 0x{summary['total_allocated']:X} bytes")
    print(f"  Overall: {summary['percentage_used']:.1f}% used")
    
    if summary['overflow_count'] > 0:
        print(f"  🔴 {summary['overflow_count']} OVERFLOW(S)!")
    if summary['critical_count'] > 0:
        print(f"  🟠 {summary['critical_count']} at >90% capacity")
    if summary['warning_count'] > 0:
        print(f"  🟡 {summary['warning_count']} at >75% capacity")

    print("=" * 60)

    # # Show compilation success message
    # print("\n" + "=" * 60)
    # print("COMPILATION SUCCESSFUL!")
    # print("=" * 60)


# ========== NEW FUNCTION: Simple console output for non-verbose mode ==========
def display_size_analysis_console_simple(analyzer):
    """Display simple code size analysis to console (non-verbose mode)"""
    from services.size_analyzer_service import SizeAnalyzerService
    
    results = analyzer.analyze_all()
    
    if not results:
        return
    
    print("\nCode Size Analysis:")
    
    for result in results:
        # Format type
        type_str = result.injection_type.replace('_', ' ').title()
        
        # Format sizes
        percentage = result.percentage_used
        
        # Status symbol
        if result.warning_level == "overflow":
            status_symbol = "[X]"
        elif result.warning_level == "critical":
            status_symbol = "[!]"
        elif result.warning_level == "warning":
            status_symbol = "[*]"
        else:
            status_symbol = "[+]"
        
        # Simple one-line output
        print(f"  {status_symbol} {result.name}: {percentage:.1f}% used")
        
        if result.is_overflow:
            overflow = result.used_bytes - result.allocated_bytes
            print(f"      WARNING: Overflowed by 0x{overflow:X} bytes!")
    
    # Summary
    summary = analyzer.get_summary()
    if summary['overflow_count'] > 0:
        print(f"\n  WARNING: {summary['overflow_count']} section(s) overflowed!")
    print("")


# ========== NEW FUNCTION: GUI output without Unicode chars ==========
def display_size_analysis_gui(analyzer, log_func):
    """Display simplified code size analysis in DearPyGUI window (ASCII only)"""
    from services.size_analyzer_service import SizeAnalyzerService
    
    results = analyzer.analyze_all()
    
    if not results:
        if VERBOSE_MODE:
            log_func("\n[DEBUG] No size analysis results available")
        return  # Don't show "No size data" in non-verbose mode
    
    # ALWAYS show size analysis header
    log_func("\n" + "=" * 60)
    log_func("CODE SIZE ANALYSIS")
    log_func("=" * 60)
    
    # ALWAYS show ALL sections
    for result in results:
        # Format type
        type_str = result.injection_type.replace('_', ' ').title()
        
        # Format sizes
        used_hex = f"0x{result.used_bytes:X}"
        allocated_hex = f"0x{result.allocated_bytes:X}"
        percentage = result.percentage_used
        
        # Create ASCII progress bar (no Unicode)
        bar_width = 30
        filled = int((percentage / 100.0) * bar_width)
        bar = "#" * filled + "-" * (bar_width - filled)
        
        # Status based on warning level
        if result.warning_level == "overflow":
            status = "OVERFLOW"
            status_symbol = "[X]"
        elif result.warning_level == "critical":
            status = "CRITICAL"
            status_symbol = "[!]"
        elif result.warning_level == "warning":
            status = "WARNING"
            status_symbol = "[*]"
        else:
            status = "OK"
            status_symbol = "[+]"
        
        # Build output
        log_func(f"\n{type_str}: {result.name}")
        log_func(f"  Used: {used_hex} / {allocated_hex} ({percentage:.1f}%)")
        log_func(f"  [{bar}] {status_symbol} {status}")
        
        if result.is_overflow:
            overflow = result.used_bytes - result.allocated_bytes
            log_func(f"  WARNING: Overflowed by 0x{overflow:X} bytes!")
        elif result.remaining_bytes < 16:
            log_func(f"  WARNING: Only 0x{result.remaining_bytes:X} bytes remaining")
    
    # ALWAYS show summary
    summary = analyzer.get_summary()
    log_func("\n" + "-" * 60)
    log_func(f"SUMMARY: {summary['total_count']} target(s)")
    log_func(f"  Total Used: 0x{summary['total_used']:X} bytes")
    log_func(f"  Total Allocated: 0x{summary['total_allocated']:X} bytes")
    log_func(f"  Overall: {summary['percentage_used']:.1f}% used")
    
    if summary['overflow_count'] > 0:
        log_func(f"  [X] {summary['overflow_count']} OVERFLOW(S)!")
    if summary['critical_count'] > 0:
        log_func(f"  [!] {summary['critical_count']} at >90% capacity")
    if summary['warning_count'] > 0:
        log_func(f"  [*] {summary['warning_count']} at >75% capacity")
    
    log_func("=" * 60)


def callback_select_emulator(sender, app_data, user_data):
    """
    Callback function for the 'Emulator Options' dropdown.
    Updates the global selected emulator.
    """
    global selected_emulator
    selected_emulator = app_data
    print(f"Selected emulator: {selected_emulator}")


# Replace the callback_inject_emulator function:

def callback_inject_emulator(sender, app_data, current_project_data):
    """
    Callback function for the 'Inject into Emulator' button.
    Injects compiled code into the selected running emulator.
    """
    global is_compilation_successful

    #print("Inject into Emulator button pressed!")
    
    if not is_compilation_successful:
        messagebox.showerror("Injection Failed", "Compilation was not successful. Cannot inject.")
        print("Injection failed: Compilation errors present.")
        return

    # Get selected emulator
    selected_emulator = dpg.get_value("emulator_dropdown")
    
    if not selected_emulator or selected_emulator == "No emulators detected":
        messagebox.showerror("No Emulator", "No emulator selected or detected.")
        return
    
    # Create emulator service
    emu_service = EmulatorService(current_project_data)
    
    # Clear output
    dpg.set_value("compiler_output_textbox", "")
    
    def log_message(msg: str):
        current = dpg.get_value("compiler_output_textbox")
        dpg.set_value("compiler_output_textbox", current + msg + "\n")
    
    log_message("=" * 60)
    log_message(f"INJECTING INTO {selected_emulator}")
    log_message("=" * 60)
    update_build_status("Injecting...", "compiling")

    # Perform injection with timing
    start_time = time.time()
    result = emu_service.inject_into_emulator(selected_emulator)
    elapsed_time = time.time() - start_time

    log_message("")
    if result.success:
        log_message(f"{result.message} (Took {elapsed_time:.2f}s)")
        update_build_status(f"Injected into {selected_emulator}! ({elapsed_time:.2f}s)", "success")
        #messagebox.showinfo("Injection Success", result.message)
    else:
        log_message("" + result.message)
        update_build_status(f"Failed to inject into {selected_emulator}!", "error")
        messagebox.showerror("Injection Failed", result.message)


def callback_refresh_emulators(sender, app_data, current_project_data):
    """Refresh the list of available emulators using centralized manager"""
    from gui.gui_loading_indicator import LoadingIndicator

    # Show loading indicator
    LoadingIndicator.show("Scanning for emulators...")

    def scan_async():
        try:
            # Use centralized manager (will notify all registered callbacks)
            manager = get_emulator_manager()
            manager.set_project_data(current_project_data)
            available = manager.scan_emulators()

            # Update UI on main thread
            def update_ui():
                if available:
                    dpg.configure_item("emulator_dropdown", items=available)
                    dpg.set_value("emulator_dropdown", available[0])
                    print(f"Found {len(available)} running emulator(s): {', '.join(available)}")

                    # Log to output window
                    current = dpg.get_value("compiler_output_textbox")
                    dpg.set_value("compiler_output_textbox",
                        current + f"\nFound emulators: {', '.join(available)}\n")
                else:
                    dpg.configure_item("emulator_dropdown", items=["No emulators detected"])
                    dpg.set_value("emulator_dropdown", "No emulators detected")
                    print("No compatible emulators detected")

                    # Log to output window
                    current = dpg.get_value("compiler_output_textbox")
                    dpg.set_value("compiler_output_textbox",
                        current + "\nNo compatible emulators detected\n")

                    # Show error popup
                    from tkinter import messagebox
                    messagebox.showerror("No Emulators Found", "Could not find any emulators.\n\nPlease make sure your emulator is running.")

                LoadingIndicator.hide()

            # Schedule UI update on main thread
            dpg.split_frame()
            update_ui()

        except Exception as e:
            print(f"Error scanning emulators: {e}")
            LoadingIndicator.hide()

    import threading
    thread = threading.Thread(target=scan_async, daemon=True)
    thread.start()
    
def refresh_build_panel_ui(current_project_data: ProjectData):
    """
    Rebuild the 'Build Options' and 'Export Cheats' panels so they always
    reflect the CURRENT build version & platform.
    """
    # If the container for these child windows doesn't exist yet (e.g. build tab
    # not created or we are in CLI mode), just bail out.
    if not dpg.does_item_exist("emulator_iso_buttons_group_container"):
        return

    # Try to keep the same width / height as the existing windows if they exist
    column_width = None
    child_height = None

    if dpg.does_item_exist("build_options_child_window"):
        column_width = dpg.get_item_width("build_options_child_window")
        child_height = dpg.get_item_height("build_options_child_window")
        dpg.delete_item("build_options_child_window")

    if dpg.does_item_exist("export_cheats_child_window"):
        if column_width is None:
            column_width = dpg.get_item_width("export_cheats_child_window")
        if child_height is None:
            child_height = dpg.get_item_height("export_cheats_child_window")
        dpg.delete_item("export_cheats_child_window")

    # Fallback to the same logic used in CreateCompileAndBuildGui
    if column_width is None:
        group_width = dpg.get_item_width("emulator_iso_buttons_group_container")
        column_width = max(int(group_width / 3) - 5, 0)

    if child_height is None:
        # Same default you used when originally creating these
        child_height = 230

    # --- MIDDLE: Build Options ---
    with dpg.child_window(
        tag="build_options_child_window",
        parent="emulator_iso_buttons_row_group",
        border=True,
        width=column_width,
        height=child_height
    ):
        current_build = current_project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()

        dpg.add_text("Build Options")
        dpg.add_separator()

        # Only space the GUI if there are no ISO options (PS1/PS2)
        if platform == "PS1" or platform == "PS2":
            dpg.add_spacer(height=20)

        is_single_file = current_build.IsSingleFileMode()
        button_label = "Open Patched File" if is_single_file else "Build ISO"

        output_format = current_build.GetOutputFormat() or "iso"

        if platform == "Gamecube":
            dpg.add_text("Output Format:")
            with dpg.group(horizontal=True):
                dpg.add_radio_button(
                    items=["ISO", "CISO", "GCM"],
                    default_value=output_format.upper(),
                    tag="gc_output_format_radio",
                    callback=lambda s, a, u: u.GetCurrentBuildVersion().SetOutputFormat(a.lower()),
                    user_data=current_project_data,
                    horizontal=True
                )

        elif platform == "Wii":
            dpg.add_text("Output Format:")
            with dpg.group(horizontal=True):
                dpg.add_radio_button(
                    items=["ISO", "WBFS"],
                    default_value=output_format.upper(),
                    tag="wii_output_format_radio",
                    callback=lambda s, a, u: u.GetCurrentBuildVersion().SetOutputFormat(a.lower()),
                    user_data=current_project_data,
                    horizontal=True
                )

        dpg.add_spacer(height=5)

        dpg.add_button(
            label=button_label,
            tag="build_iso_button",
            width=-1,
            callback=callback_build_iso,
            user_data=current_project_data
        )

        dpg.add_spacer(height=5)

        dpg.add_button(
            label="Generate xdelta Patch",
            tag="xdelta_button",
            width=-1,
            callback=callback_generate_xdelta,
            user_data=current_project_data
        )

    # --- RIGHT: Export Cheats ---
    with dpg.child_window(
        tag="export_cheats_child_window",
        parent="emulator_iso_buttons_row_group",
        border=True,
        width=column_width,
        height=child_height
    ):
        dpg.add_text("Export Cheats")
        dpg.add_separator()

        current_build = current_project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()

        # Normalize platform
        platform_norm = (platform or "").strip().upper()

        if platform_norm in ("PS1", "PSX"):
            dpg.add_text("PlayStation 1")
            dpg.add_spacer(height=5)

            dpg.add_button(
                label="Generate GameShark Code (PS1)",
                width=-1,
                callback=callback_generate_ps1_gameshark,
                user_data=current_project_data
            )

        elif platform_norm == "PS2":
            dpg.add_text("PlayStation 2")
            dpg.add_spacer(height=5)

            dpg.add_button(
                label="Generate PS2RD Code (PS2)",
                width=-1,
                callback=callback_generate_ps2_ps2rd,
                user_data=current_project_data
            )

            dpg.add_spacer(height=5)

            dpg.add_button(
                label="Generate .pnach File (PCSX2)",
                width=-1,
                callback=callback_generate_ps2_pnach,
                user_data=current_project_data
            )

        elif platform_norm == "GAMECUBE":
            dpg.add_text("Gamecube")
            dpg.add_spacer(height=5)
            dpg.add_button(
                label="Generate Action Replay Code",
                width=-1,
                callback=callback_generate_gc_ar,
                user_data=current_project_data
            )
            dpg.add_spacer(height=5)
            dpg.add_button(
                label="Generate Gecko Code",
                width=-1,
                callback=callback_generate_gc_gecko,
                user_data=current_project_data
            )

        elif platform_norm == "WII":
            dpg.add_text("Wii")
            dpg.add_spacer(height=5)
            dpg.add_button(
                label="Generate Action Replay Code",
                width=-1,
                callback=callback_generate_wii_ar,
                user_data=current_project_data
            )

            dpg.add_spacer(height=5)

            dpg.add_button(
                label="Generate Gecko Code",
                width=-1,
                callback=callback_generate_wii_gecko,
                user_data=current_project_data
            )

            dpg.add_spacer(height=5)

            dpg.add_button(
                label="Generate Riivolution XML",
                width=-1,
                callback=callback_generate_riivolution_xml,
                user_data=current_project_data
            )
        else:
            dpg.add_text("Cheat export not yet implemented for this platform.")
            dpg.add_spacer(height=5)
            dpg.add_text(f"Platform: {platform_norm}")


def callback_build_iso(sender, app_data, user_data):
    """
    Callback function for the 'Build ISO' button.
    Builds complete ISO with all patches, or patches single file.
    """
    from gui.gui_loading_indicator import LoadingIndicator
    global is_compilation_successful

    print("Build ISO button pressed!")
    
    current_project_data = user_data
    
    if current_project_data is None:
        messagebox.showerror("Error", "No project data available")
        return
    
    if not is_compilation_successful:
        messagebox.showerror("Build Failed", "Compilation was not successful. Must compile first.")
        print("Build failed: Compilation errors present.")
        return

    # Check if single file mode
    current_build = current_project_data.GetCurrentBuildVersion()
    
    if current_build.IsSingleFileMode():
        # Single file mode - just patch the file
        main_exe = current_build.GetMainExecutable()
        project_folder = current_project_data.GetProjectFolder()
        
        # Show loading indicator
        LoadingIndicator.show("Patching file...")
        
        def patch_async():
            try:
                # Create ISO service and patch
                iso_service = ISOService(current_project_data, verbose=False, tool_dir=_tool_dir)
                
                # Clear output
                dpg.set_value("compiler_output_textbox", "")
                
                def on_progress(message: str):
                    current_output = dpg.get_value("compiler_output_textbox")
                    dpg.set_value("compiler_output_textbox", current_output + message + "\n")
                
                on_progress("=" * 60)
                on_progress("PATCHING SINGLE FILE")
                on_progress("=" * 60)
                on_progress(f"\nFile: {main_exe}")
                on_progress(f"Mode: Single File (No ISO)")
                
                # Patch the file with timing
                on_progress("\nPatching executable with compiled code...")
                start_time = time.time()
                patch_result = iso_service.patch_executable()
                elapsed_time = time.time() - start_time

                def update_ui():
                    LoadingIndicator.hide()

                    if patch_result.success:
                        patched_file = os.path.join(f'{project_folder}/build/', f"patched_{main_exe}")

                        on_progress("\n" + "=" * 60)
                        on_progress(f"PATCHING COMPLETE! (Took {elapsed_time:.2f}s)")
                        on_progress("=" * 60)
                        on_progress(f"\nOutput: {patched_file}")

                        # Update status indicator
                        update_build_status(f"Patching Complete! ({elapsed_time:.2f}s)", "success")

                        # Ask user if they want to open the folder
                        global _dont_ask_open_folder
                        if not _dont_ask_open_folder:
                            response, dont_ask = askyesno_with_checkbox(
                                "Patching Complete",
                                f"File patched successfully!\n\n"
                                f"Output: patched_{main_exe}\n\n"
                                f"Open folder in explorer?"
                            )

                            # Save checkbox preference
                            if dont_ask:
                                _dont_ask_open_folder = True

                            if response:
                                import subprocess
                                folder = os.path.dirname(patched_file)
                                subprocess.Popen(f'explorer "{folder}"', shell=True)
                    else:
                        on_progress("\n" + "=" * 60)
                        on_progress("PATCHING FAILED!")
                        on_progress("=" * 60)
                        on_progress(f"\nError: {patch_result.message}")

                        update_build_status("Patching Failed!", "error")

                        messagebox.showerror("Patching Failed", patch_result.message)
                
                dpg.split_frame()
                update_ui()
                
            except Exception as e:
                LoadingIndicator.hide()
                import traceback
                messagebox.showerror("Error", f"Patching failed: {str(e)}\n\n{traceback.format_exc()}")
        
        import threading
        thread = threading.Thread(target=patch_async, daemon=True)
        thread.start()
        return

    LoadingIndicator.show("Building ISO...")
    
    def build_async():
        try:
            iso_service = ISOService(current_project_data, tool_dir=_tool_dir)
            
            # Clear log
            dpg.set_value("compiler_output_textbox", "")
            
            def on_progress(message: str):
                current_output = dpg.get_value("compiler_output_textbox")
                dpg.set_value("compiler_output_textbox", current_output + message + "\n")
            
            on_progress("=" * 60)
            on_progress("STARTING ISO BUILD")
            on_progress("=" * 60)
            
            # Run full build
            on_progress("\n[1/4] Patching executable with compiled code...")
            LoadingIndicator.update_message("Building Modded Game ISO...")
            start_time = time.time()
            result = iso_service.full_build()
            elapsed_time = time.time() - start_time

            # Update UI on main thread
            def update_ui():
                LoadingIndicator.hide()

                if result.success:
                    on_progress("\n" + "=" * 60)
                    on_progress(f"BUILD COMPLETE! (Took {elapsed_time:.2f}s)")
                    on_progress("=" * 60)
                    on_progress(f"\nOutput: {result.output_path}")

                    update_build_status(f"ISO Build Complete! ({elapsed_time:.2f}s)", "success")

                    output_path_split = result.output_path.split("\\")
                    output_path_short = output_path_split[-3] + "\\" + output_path_split[-2] + "\\" + output_path_split[-1] # Get only the path starting from the project folder
                    
                    # Ask user if they want to open the folder, unless checkbox has been checked to not show again
                    global _dont_ask_open_folder
                    if not _dont_ask_open_folder:
                        response, dont_ask = askyesno_with_checkbox(
                            "Build Complete",
                            f"ISO built successfully!\n\n{output_path_short}\n\nOpen folder in explorer?"
                        )

                        # Save preference
                        if dont_ask:
                            _dont_ask_open_folder = True

                        if response:
                            import subprocess
                            folder = os.path.dirname(result.output_path)
                            subprocess.Popen(f'explorer "{folder}"', shell=True)

                else:
                    on_progress("\n" + "=" * 60)
                    on_progress("BUILD FAILED!")
                    on_progress("=" * 60)
                    on_progress(f"\nError: {result.message}")

                    # Update status indicator
                    update_build_status("ISO Build Failed!", "error")

                    messagebox.showerror("Build Failed", result.message)
            
            dpg.split_frame()
            update_ui()
            
        except Exception as e:
            LoadingIndicator.hide()
            messagebox.showerror("Error", f"Build failed: {str(e)}")
    
    import threading
    thread = threading.Thread(target=build_async, daemon=True)
    thread.start()
    


def callback_generate_xdelta(sender, app_data, user_data):
    from gui.gui_loading_indicator import LoadingIndicator
    from tkinter import filedialog
    
    print("Generate xdelta Patch button pressed!")
    
    current_project_data = user_data
    
    if current_project_data is None:
        messagebox.showerror("Error", "No project data available")
        return
    
    current_build = current_project_data.GetCurrentBuildVersion()

    # Check if we need to prompt for original file
    original_file = None

    # For single file mode, we don't need to prompt - the service will use single_file_path
    # For ISO mode from folder, we need to prompt
    is_single_file = current_build.IsSingleFileMode()

    if not is_single_file:
        source_path = current_build.GetSourcePath()

        if not source_path:
            # No source path set - prompt user
            messagebox.showinfo(
                "Select Original File",
                "Please select the original (unmodded) ISO/file to compare against."
            )
            original_file = filedialog.askopenfilename(
                title="Select Original ISO/File",
                filetypes=[("All Files", "*.*")]
            )
            if not original_file:
                print("User cancelled file selection")
                return
        elif os.path.isdir(source_path):
            # Source is a directory (extracted folder) - need to prompt
            messagebox.showinfo(
                "Select Original File",
                "This project was created from an extracted folder.\n\n"
                "Please select the original (unmodded) ISO file."
            )
            original_file = filedialog.askopenfilename(
                title="Select Original ISO File",
                filetypes=[("All Files", "*.*")]
            )
            if not original_file:
                print("User cancelled file selection")
                return
    
    # Show loading indicator
    LoadingIndicator.show("Generating xdelta patch...")
    
    def generate_async():
        try:
            # Create ISO service and generate patch
            iso_service = ISOService(current_project_data, tool_dir=_tool_dir)
            
            # Clear output
            dpg.set_value("compiler_output_textbox", "")
            
            def on_progress(message: str):
                current_output = dpg.get_value("compiler_output_textbox")
                dpg.set_value("compiler_output_textbox", current_output + message + "\n")
            
            on_progress("=" * 60)
            on_progress("XDELTA PATCH GENERATION")
            on_progress("=" * 60)

            # Generate the patch
            start_time = time.time()
            result = iso_service.generate_xdelta_patch(original_file)
            elapsed_time = time.time() - start_time

            def update_ui():
                LoadingIndicator.hide()

                if result.success:
                    on_progress("\n" + "=" * 60)
                    on_progress(f"PATCH GENERATED SUCCESSFULLY! (Took {elapsed_time:.2f}s)")
                    on_progress("=" * 60)
                    on_progress(f"\n{result.message}")
                    on_progress(f"Location: {result.output_path}")

                    # Update status indicator
                    update_build_status(f"Patch Generated! ({elapsed_time:.2f}s)", "success")

                    # Ask if user wants to open folder
                    global _dont_ask_open_folder
                    if not _dont_ask_open_folder:
                        response, dont_ask = askyesno_with_checkbox(
                            "Patch Generated",
                            f"xdelta patch generated successfully!\n\n"
                            f"File: {os.path.basename(result.output_path)}\n\n"
                            f"Open folder in explorer?"
                        )

                        if dont_ask:
                            _dont_ask_open_folder = True

                        if response:
                            import subprocess
                            folder = os.path.dirname(result.output_path)
                            subprocess.Popen(f'explorer "{folder}"', shell=True)
                else:
                    on_progress("\n" + "=" * 60)
                    on_progress("PATCH GENERATION FAILED!")
                    on_progress("=" * 60)
                    on_progress(f"\nError: {result.message}")

                    # Update status indicator
                    update_build_status("Patch Generation Failed!", "error")

                    messagebox.showerror("Patch Failed", f"Failed to generate patch:\n{result.message}")
            
            # Schedule UI update on main thread
            dpg.split_frame()
            update_ui()
            
        except Exception as e:
            print(f"Error generating patch: {e}")
            import traceback
            traceback.print_exc()
            LoadingIndicator.hide()
    
    import threading
    thread = threading.Thread(target=generate_async, daemon=True)
    thread.start()

def callback_compiler_flags_changed(sender, app_data, current_project_data: ProjectData):
    """Save compiler flags when user changes them"""
    current_project_data.GetCurrentBuildVersion().SetCompilerFlags(app_data)

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

def callback_no_warnings_changed(sender, app_data):
    """Update global NO_WARNINGS_MODE when checkbox is toggled"""
    global NO_WARNINGS_MODE
    NO_WARNINGS_MODE = app_data
    
    
def callback_generate_ps1_gameshark(sender, app_data, current_project_data: ProjectData):
    """Generate PS1 GameShark codes from compiled bins and copy to clipboard."""
    global is_compilation_successful

    if not is_compilation_successful:
        messagebox.showerror("Cheat Export Failed", "You must compile successfully before generating cheats.")
        return

    try:
        service = CheatCodeService(current_project_data)
        code = service.generate_ps1_gameshark()

        # Show in compiler output textbox
        dpg.set_value("compiler_output_textbox", code)

        pyperclip.copy(code)
        messagebox.showinfo("Cheats Generated", "PS1 GameShark codes generated and copied to clipboard.")


    except FileNotFoundError as e:
        messagebox.showerror(
            "Cheat Export Failed",
            f"{e}\n\nMake sure you compiled the project at least once."
        )
    except Exception as e:
        import traceback
        messagebox.showerror(
            "Cheat Export Failed",
            f"Unexpected error generating PS1 GameShark codes:\n{e}\n\n{traceback.format_exc()}"
        )


def callback_generate_ps2_ps2rd(sender, app_data, current_project_data: ProjectData):
    """Generate PS2 PS2RD codes from compiled bins and copy to clipboard."""
    global is_compilation_successful

    if not is_compilation_successful:
        messagebox.showerror("Cheat Export Failed", "You must compile successfully before generating cheats.")
        return

    try:
        service = CheatCodeService(current_project_data)
        code = service.generate_ps2_ps2rd()

        dpg.set_value("compiler_output_textbox", code)

        pyperclip.copy(code)
        messagebox.showinfo("Cheats Generated", "PS2 PS2RD codes generated and copied to clipboard.")

    except FileNotFoundError as e:
        messagebox.showerror(
            "Cheat Export Failed",
            f"{e}\n\nMake sure you compiled the project at least once."
        )
    except Exception as e:
        import traceback
        messagebox.showerror(
            "Cheat Export Failed",
            f"Unexpected error generating PS2 PS2RD codes:\n{e}\n\n{traceback.format_exc()}"
        )


def callback_generate_ps2_pnach(sender, app_data, current_project_data: ProjectData):
    """Generate PCSX2 .pnach, copy to clipboard, and save via Tk file dialog."""
    global is_compilation_successful

    if not is_compilation_successful:
        messagebox.showerror(
            "Cheat Export Failed",
            "You must compile successfully before generating cheats."
        )
        return

    try:
        service = CheatCodeService(current_project_data)
        # Default one_shot=True -> place=0 (boot-only writes)
        pnach_text = service.generate_ps2_pnach()

        # Show full pnach in the DPG output box
        dpg.set_value("compiler_output_textbox", pnach_text)

        # Copy to clipboard
        pyperclip.copy(pnach_text)

        # Build a reasonable default filename
        build = current_project_data.GetCurrentBuildVersion()
        project_folder = current_project_data.GetProjectFolder()

        get_serial = getattr(build, "GetGameSerial", None)
        serial = get_serial() if callable(get_serial) else ""

        get_crc = getattr(build, "GetGameCRC", None)
        crc = get_crc() if callable(get_crc) else ""

        get_proj_name = getattr(current_project_data, "GetProjectName", None)
        proj_name = get_proj_name() if callable(get_proj_name) else "patch"

        if serial and crc:
            default_name = f"{serial}_{crc}.pnach"
        elif crc:
            default_name = f"{crc}.pnach"
        else:
            default_name = f"{proj_name}.pnach"

        # Tkinter "Save As" dialog
        file_path = filedialog.asksaveasfilename(
            title="Save PCSX2 .pnach file",
            defaultextension=".pnach",
            initialdir=project_folder,
            initialfile=default_name,
            filetypes=[("PCSX2 pnach files", "*.pnach"), ("All Files", "*.*")],
        )

        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(pnach_text)

            messagebox.showinfo(
                "pnach Generated",
                "PCSX2 .pnach generated, copied to clipboard,\n"
                f"and saved to:\n{file_path}"
            )
        else:
            # User cancelled save dialog, but generation still succeeded
            messagebox.showinfo(
                "pnach Generated",
                "PCSX2 .pnach generated and copied to clipboard.\n\n"
                "File was not saved because the dialog was cancelled."
            )

    except FileNotFoundError as e:
        messagebox.showerror(
            "Cheat Export Failed",
            f"{e}\n\nMake sure you compiled the project at least once."
        )
    except Exception as e:
        import traceback
        messagebox.showerror(
            "Cheat Export Failed",
            f"Unexpected error generating PCSX2 .pnach:\n{e}\n\n{traceback.format_exc()}"
        )



def callback_generate_gc_ar(sender, app_data, current_project_data: ProjectData):
    global is_compilation_successful

    if not is_compilation_successful:
        messagebox.showerror("Cheat Export Failed", "You must compile successfully before generating cheats.")
        return

    from services.cheat_code_service import CheatCodeService
    service = CheatCodeService(current_project_data)

    try:
        code_and_name = service.generate_gc_action_replay()
        codes_only = _codes_strip_name(code_and_name)
        dpg.set_value("compiler_output_textbox", codes_only)

        pyperclip.copy(codes_only)

        messagebox.showinfo("Cheats Generated", "GameCube Action Replay codes generated and copied to clipboard.")

    except Exception as e:
        import traceback
        messagebox.showerror(
            "Cheat Export Failed",
            f"Error generating GameCube AR codes:\n{e}\n\n{traceback.format_exc()}"
        )
        print_error(f"Error generating GameCube AR codes:\n{e}\n\n{traceback.format_exc()}")


def callback_generate_wii_ar(sender, app_data, current_project_data: ProjectData):
    global is_compilation_successful

    if not is_compilation_successful:
        messagebox.showerror("Cheat Export Failed", "You must compile successfully before generating cheats.")
        return

    from services.cheat_code_service import CheatCodeService
    service = CheatCodeService(current_project_data)

    try:
        code_and_name = service.generate_gc_action_replay()
        codes_only = _codes_strip_name(code_and_name)
        dpg.set_value("compiler_output_textbox", codes_only)

        pyperclip.copy(codes_only)
        messagebox.showinfo("Cheats Generated", "Wii Action Replay codes generated and copied to clipboard.")
        
    except Exception as e:
        import traceback
        messagebox.showerror(
            "Cheat Export Failed",
            f"Error generating Wii AR codes:\n{e}\n\n{traceback.format_exc()}"
        )
        
def callback_generate_gc_gecko(sender, app_data, current_project_data: ProjectData):
    global is_compilation_successful

    if not is_compilation_successful:
        messagebox.showerror(
            "Cheat Export Failed",
            "You must compile successfully before generating cheats."
        )
        return

    from services.cheat_code_service import CheatCodeService
    service = CheatCodeService(current_project_data)

    try:
        # CheatCodeService should default to one_shot=True internally
        code_and_name = service.generate_gc_gecko()
        codes_only = _codes_strip_name(code_and_name)
        
        #generate seperate non one-shot version for .gct file. Strangely doesn't work on console if one shot?
        code_and_name_gct = service.generate_gc_gecko(one_shot=False)
        codes_only_gct = _codes_strip_name(code_and_name_gct)
        
        ok, count, max_lines = check_gecko_length(codes_only, GECKO_MAX_LINES)

        if not ok:
            messagebox.showwarning(
                "Gecko Code Length Warning",
                (
                    f"This Gecko code has {count} lines.\n\n"
                    f"Typical Gecko handlers only support around "
                    f"{max_lines} lines per code list.\n"
                    "Lines beyond this limit may be ignored by the code handler."
                )
            )

        dpg.set_value("compiler_output_textbox", codes_only)
        pyperclip.copy(codes_only)
        
        if ok:
            #cheat_file_name = current_project_data.GetCurrentBuildVersion().GetBuildName() + " Gecko"
            build = current_project_data.GetCurrentBuildVersion()
            game_id = GameMetadataService.get_gamecube_game_id(build)
            cheat_file_name = game_id
            project_folder = current_project_data.GetProjectFolder()

            # Generate GCT file
            initial_dir = os.path.join(project_folder, "build")
            os.makedirs(initial_dir, exist_ok=True)

            file_path = filedialog.asksaveasfilename(
                title="Save GCT",
                defaultextension=".gct",
                initialdir=initial_dir,
                initialfile=cheat_file_name,
                filetypes=[("Gecko Cheat Format", "*.gct"), ("All Files", "*.*")],
            )

            header =     bytes([0x00, 0xD0, 0xC0, 0xDE])
            terminator = bytes([0xF0, 0x00, 0x00, 0x00])
            end =        bytes([0x00, 0x00, 0x00, 0x00])
            
            hex_codes_only = bytes.fromhex(codes_only_gct.strip(" ").strip("\n"))
            if file_path:
                with open(file_path, "wb",) as f:
                    f.write(header)
                    f.write(header)
                    f.write(bytes(hex_codes_only))
                    f.write(terminator)
                    f.write(end)
                    
            messagebox.showinfo(
                "Cheats Generated",
                "GameCube Gecko codes generated and copied to clipboard."
            )

    except Exception as e:
        import traceback
        messagebox.showerror(
            "Cheat Export Failed",
            f"Error generating GameCube Gecko codes:\n{e}\n\n{traceback.format_exc()}"
        )
    
def callback_generate_wii_gecko(sender, app_data, current_project_data: ProjectData):
    global is_compilation_successful

    if not is_compilation_successful:
        messagebox.showerror(
            "Cheat Export Failed",
            "You must compile successfully before generating cheats."
        )
        return

    from services.cheat_code_service import CheatCodeService
    service = CheatCodeService(current_project_data)

    try:
        # CheatCodeService should default to one_shot=True internally
        code_and_name = service.generate_wii_gecko()
        codes_only = _codes_strip_name(code_and_name)
        
        ok, count, max_lines = check_gecko_length(codes_only, GECKO_MAX_LINES)

        if not ok:
                messagebox.showwarning(
                    "Gecko Code Length Warning",
                    (
                        f"This Gecko code has {count} lines.\n\n"
                        f"Typical Gecko handlers only support around "
                        f"{max_lines} lines per code list.\n"
                        "Lines beyond this limit may be ignored by the code handler."
                    )
                )

        dpg.set_value("compiler_output_textbox", codes_only)
        pyperclip.copy(codes_only)
        
        if ok:
            #cheat_file_name = current_project_data.GetCurrentBuildVersion().GetBuildName() + " Gecko"
            build = current_project_data.GetCurrentBuildVersion()
            game_id = GameMetadataService.get_gamecube_game_id(build)
            cheat_file_name = game_id
            project_folder = current_project_data.GetProjectFolder()

            # Generate GCT file
            initial_dir = os.path.join(project_folder, "build")
            os.makedirs(initial_dir, exist_ok=True)

            file_path = filedialog.asksaveasfilename(
                title="Save GCT",
                defaultextension=".gct",
                initialdir=initial_dir,
                initialfile=cheat_file_name,
                filetypes=[("Gecko Cheat Format", "*.gct"), ("All Files", "*.*")],
            )

            header =     bytes([0x00, 0xD0, 0xC0, 0xDE])
            terminator = bytes([0xF0, 0x00, 0x00, 0x00])
            end =        bytes([0x00, 0x00, 0x00, 0x00])
            
            hex_codes_only = bytes.fromhex(codes_only.strip(" ").strip("\n"))
            if file_path:
                with open(file_path, "wb",) as f:
                    f.write(header)
                    f.write(header)
                    f.write(bytes(hex_codes_only))
                    f.write(terminator)
                    f.write(end)
                    
            messagebox.showinfo(
                "Cheats Generated",
                "Wii Gecko codes generated and copied to clipboard."
            )

    except Exception as e:
        import traceback
        messagebox.showerror(
            "Cheat Export Failed",
            f"Error generating Wii Gecko codes:\n{e}\n\n{traceback.format_exc()}"
        )

    
def _codes_strip_name(full_text: str) -> str:
    """
    Strip the first two lines (usually title + 'Mod' / header) before copying
    to clipboard. Returns only the actual code lines.
    """
    lines = full_text.splitlines()
    if len(lines) <= 2:
        # Nothing (or almost nothing) to strip
        return full_text.strip()
    
    # Drop the first two lines, keep the rest
    codes_only = "\n".join(lines[2:])
    return codes_only.strip()

def show_gecko_length_warning_popup(line_count: int, max_lines: int):
    """
    Modal popup telling the user the Gecko code exceeds the handler limit.
    """
    popup_tag = "gecko_length_warning_popup"

    if dpg.does_item_exist(popup_tag):
        dpg.delete_item(popup_tag)

    with dpg.window(
        tag=popup_tag,
        label="Gecko Code Length Warning",
        modal=True,
        no_move=False,
        no_resize=True,
        no_collapse=True,
        autosize=True,
        pos=(200, 200),  # tweak as you like
    ):
        dpg.add_text(
            f"This Gecko code has {line_count} lines.\n\n"
            f"Typical Gecko/Ocarina handlers only support up to "
            f"{max_lines} lines per code list.\n"
            "Lines beyond this limit may be ignored on hardware / loaders."
        )
        dpg.add_spacer(height=8)
        dpg.add_button(
            label="OK",
            width=80,
            callback=lambda: dpg.delete_item(popup_tag)
        )

def update_build_button_label(current_project_data: ProjectData):
    """Update the build button label based on single file mode"""
    import dearpygui.dearpygui as dpg
    
    if not dpg.does_item_exist("build_iso_button"):
        return
    
    current_build = current_project_data.GetCurrentBuildVersion()
    
    if current_build.IsSingleFileMode():
        dpg.set_item_label("build_iso_button", "Patch File")
    else:
        dpg.set_item_label("build_iso_button", "Build ISO")
        
def callback_generate_riivolution_xml(sender, app_data, current_project_data: ProjectData):
    """
    Generate a Riivolution XML file based on the current build's injection files.

    - Uses CheatCodeService.generate_wii_riivolution_file_patches()
      (works for both GameCube and Wii projects).
    - Shows XML in the compiler output textbox.
    - Copies XML to clipboard.
    - Prompts user to save as a .xml file in a /riivolution folder.
    """
    global is_compilation_successful

    # You *could* allow this without compilation, but keeping it consistent
    # with other exports for now.
    if not is_compilation_successful:
        messagebox.showerror(
            "Riivolution Export Failed",
            "You must compile successfully before generating Riivolution patches."
        )
        return

    try:
        service = CheatCodeService(current_project_data)
        # This function supports both GC and Wii (name says Wii, but logic checks platform)
        xml_text = service.generate_wii_riivolution_file_patches()

        # Show in DPG output box
        dpg.set_value("compiler_output_textbox", xml_text)

        # Copy to clipboard
        pyperclip.copy(xml_text)

        # Build default save path & filename
        build = current_project_data.GetCurrentBuildVersion()
        project_folder = current_project_data.GetProjectFolder()

        get_proj_name = getattr(current_project_data, "GetProjectName", None)
        proj_name = get_proj_name() if callable(get_proj_name) else "RiivolutionMod"

        # Use project/build name for a sensible default
        build_name = getattr(build, "GetBuildName", lambda: "default")()
        default_name = f"{proj_name}_{build_name}_riivolution.xml"

        # Put user in /riivolution under the project folder
        initial_dir = os.path.join(project_folder, "riivolution")
        os.makedirs(initial_dir, exist_ok=True)

        file_path = filedialog.asksaveasfilename(
            title="Save Riivolution XML",
            defaultextension=".xml",
            initialdir=initial_dir,
            initialfile=default_name,
            filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")],
        )

        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(xml_text)

            messagebox.showinfo(
                "Riivolution XML Generated",
                "Riivolution XML generated, copied to clipboard,\n"
                f"and saved to:\n{file_path}"
            )
        else:
            # User cancelled save dialog; still a success
            messagebox.showinfo(
                "Riivolution XML Generated",
                "Riivolution XML generated and copied to clipboard.\n\n"
                "File was not saved because the dialog was cancelled."
            )

    except FileNotFoundError as e:
        messagebox.showerror(
            "Riivolution Export Failed",
            f"{e}\n\nMake sure you compiled the project at least once."
        )
    except Exception as e:
        import traceback
        messagebox.showerror(
            "Riivolution Export Failed",
            f"Unexpected error generating Riivolution XML:\n{e}\n\n{traceback.format_exc()}"
        )