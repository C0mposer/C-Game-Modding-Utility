import dearpygui.dearpygui as dpg
import os
from dpg.widget_themes import *
from classes.project_data.project_data import *
from gui.gui_c_injection import *
from gui import gui_messagebox as messagebox
from tkinter import filedialog
from services.project_serializer import ProjectSerializer
from services.iso_service import ISOService
from services.ghidra_pattern_service import GhidraPatternService
from gui.gui_loading_indicator import LoadingIndicator
from gui.gui_build import refresh_build_panel_ui, update_build_button_label
from gui.gui_prereq_prompt import check_and_prompt_prereqs
from services.emulator_connection_manager import get_emulator_manager
from path_helper import get_application_directory


def _scan_for_os_library_functions(current_project_data: ProjectData):
    """
    Scan main executable for OS library function patterns (PS1/PS2 only).
    Called after extracting/setting game files for a build version.
    """
    import os

    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Only scan PS1/PS2
    if platform not in ["PS1", "PS2"]:
        return

    # Get main executable path
    main_exe = current_build.GetMainExecutable()
    if not main_exe:
        return

    game_folder = current_build.GetGameFolder()
    if not game_folder:
        return

    exe_path = os.path.join(game_folder, main_exe)
    if not os.path.exists(exe_path):
        return

    print(f"\nScanning {main_exe} for OS library function patterns...")

    try:
        service = GhidraPatternService()
        symbols = service.scan_executable(platform, exe_path)

        if symbols:
            print(f"Found {len(symbols)} OS library functions")

            # Get symbols file path
            project_folder = current_project_data.GetProjectFolder()
            symbols_file_name = current_build.GetSymbolsFile()

            # Use symbols/ directory
            symbols_dir = os.path.join(project_folder, "symbols")
            symbols_file = os.path.join(symbols_dir, symbols_file_name)

            # Add symbols to file
            service.add_symbols_to_file(symbols_file, symbols)

            # Generate/update unified header file with build-specific section
            build_name = current_build.GetBuildName()
            include_dir = os.path.join(project_folder, "include")
            header_file = os.path.join(include_dir, "library_symbols.h")
            service.generate_header_file(header_file, symbols, build_name)
        else:
            print("No OS library function patterns found")

    except Exception as e:
        print(f"Error scanning for OS library patterns: {e}")


def _reset_gdb_debugger():
    """Reset GDB debugger state"""
    import gui.gui_gdb_debugger as gdb_debugger

    # Reset the global debugger state
    if hasattr(gdb_debugger, '_debugger_state'):
        if gdb_debugger._debugger_state.is_connected and gdb_debugger._debugger_state.service:
            try:
                gdb_debugger._debugger_state.service.disconnect()
            except:
                pass

        # Reset state
        gdb_debugger._debugger_state.service = None
        gdb_debugger._debugger_state.is_connected = False
        gdb_debugger._debugger_state.current_emulator = ""
        gdb_debugger._debugger_state.current_host = "localhost"
        gdb_debugger._debugger_state.current_port = 3333

    print("GDB debugger state reset")

def _close_all_project_windows():
    """Delete all project-related windows so they get recreated fresh"""
    # List of all project-specific window tags
    window_tags = [
        "gdb_debugger_window",
        "assembly_viewer_window",
        "visual_patcher_window",
        "codecave_finder_window",
        # Add any modals or dialogs
        "add_build_version_modal",
        "pattern_selection_dialog",
        # Memory watch is handled separately via reset_memory_watch_service()
    ]

    for tag in window_tags:
        if dpg.does_item_exist(tag):
            try:
                dpg.delete_item(tag)
                print(f"Deleted window: {tag}")
            except Exception as e:
                print(f"Error deleting window {tag}: {e}")

    # Reset assembly viewer global state
    import gui.gui_assembly_viewer as asm_viewer
    if hasattr(asm_viewer, '_asm_viewer_functions'):
        asm_viewer._asm_viewer_functions.clear()

    # Reset visual patcher global state
    import gui.gui_hex_differ as visual_patcher
    if hasattr(visual_patcher, '_state'):
        visual_patcher._state.file_name = ""
        visual_patcher._state.original_data = None
        visual_patcher._state.patched_data = None
        visual_patcher._state.patch_regions = []
        visual_patcher._state.selected_patch_index = -1
        visual_patcher._state.syncing_scroll = False

    print("All project windows closed and state cleared")

def reset_global_project_state():
    """Comprehensive reset of all project-related state and windows"""
    print("Resetting all project state...")

    # Reset codecave state
    from gui.gui_c_injection import reset_codecave_state
    try:
        reset_codecave_state()
    except Exception as e:
        print(f"Error resetting codecave state: {e}")

    # Reset hook state
    from gui.gui_asm_injection import ClearGuiHookData
    try:
        ClearGuiHookData()
    except Exception as e:
        print(f"Error resetting hook state: {e}")

    # Reset binary patch state
    from gui.gui_binary_patch_injection import ClearGuiBinaryPatchData
    try:
        ClearGuiBinaryPatchData()
    except Exception as e:
        print(f"Error resetting binary patch state: {e}")

    # Reset GDB debugger state
    try:
        _reset_gdb_debugger()
    except Exception as e:
        print(f"Error resetting GDB debugger: {e}")

    # Reset game files state
    from gui.gui_game_files import reset_game_files_state
    try:
        reset_game_files_state()
    except Exception as e:
        print(f"Error resetting game files state: {e}")

    # Reset string editor state (including ProjectData reference)
    from gui.gui_string_editor import reset_string_editor_state
    try:
        reset_string_editor_state()
    except Exception as e:
        print(f"Error resetting string editor state: {e}")

    # Reset codecave finder state (including ProjectData reference)
    from gui.gui_codecave_finder import reset_codecave_finder_state
    try:
        reset_codecave_finder_state()
    except Exception as e:
        print(f"Error resetting codecave finder state: {e}")

    # Close/delete all project-related windows (they'll be recreated fresh if reopened)
    _close_all_project_windows()

    print("Global project state reset complete")

def ShowFullProjectTabs():
    dpg.configure_item("Target Game Files", show=True)
    dpg.configure_item("Modifications", show=True)
    dpg.configure_item("Build", show=True)
    
def callback_add_project_build_version(sender, app_data, current_project_data: ProjectData):
    """Add a new build version to the project"""
    # Create input dialog for build name and sharing option
    if dpg.does_item_exist("add_build_version_modal"):
        dpg.show_item("add_build_version_modal")
        return
    
    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()
    modal_width = 500
    modal_height = 250
    modal_x = (viewport_width - modal_width) // 2
    modal_y = (viewport_height - modal_height) // 2
    
    with dpg.window(
        label="Add New Build Version", 
        modal=True, 
        no_close=True, 
        tag="add_build_version_modal",
        no_move=True, 
        no_resize=True, 
        width=modal_width, 
        height=modal_height, 
        pos=[modal_x, modal_y]
    ):
        dpg.add_text("Enter name for the new build version:")
        dpg.add_input_text(
            tag="new_build_version_name_input", 
            default_value="", 
            width=450, 
            hint="e.g., NTSC, PAL, PS2_NTSC"
        )
        
        dpg.add_spacer(height=15)
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        dpg.add_text("Share game files from existing build?")
        dpg.add_text("(Leave as 'New Files' to extract/select fresh files)", color=(150, 150, 150))
        
        # Get list of existing build versions
        existing_builds = ["New Files (Don't Share)"] + [bv.GetBuildName() for bv in current_project_data.build_versions]
        
        dpg.add_combo(
            items=existing_builds,
            default_value="New Files (Don't Share)",
            label="Share From",
            tag="share_from_build_combo",
            width=450
        )
        
        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Create", 
                callback=callback_create_build_version_from_modal,
                user_data=current_project_data
            )
            dpg.add_button(
                label="Cancel", 
                callback=lambda: dpg.configure_item("add_build_version_modal", show=False)
            )


def callback_create_build_version_from_modal(sender, app_data, current_project_data: ProjectData):
    """Actually create the build version after getting the name"""
    import os

    new_name = dpg.get_value("new_build_version_name_input")
    share_from = dpg.get_value("share_from_build_combo")

    if not new_name:
        messagebox.showerror("Error", "Build version name cannot be empty.")
        return

    # Auto-capitalize for consistency with preprocessor defines
    new_name = new_name.upper()

    # Check if name exists in CURRENT project only
    existing_names = [bv.GetBuildName() for bv in current_project_data.build_versions]
    if new_name in existing_names:
        messagebox.showerror("Error", f"A build version named '{new_name}' already exists in this project.")
        return

    # Create new build version (will be auto-capitalized by SetBuildName)
    current_project_data.AddBuildVersionWithName(new_name)
    new_build = current_project_data.build_versions[-1]
    
    # Handle sharing logic
    if share_from != "New Files (Don't Share)":
        # Find the build to share from
        source_build = None
        for bv in current_project_data.build_versions:
            if bv.GetBuildName() == share_from:
                source_build = bv
                break
        
        if source_build:
            # IMPORTANT: When sharing, use the EXACT same paths as the source build
            # This allows multiple build versions to point to the same game files
            new_build.SetGameFolder(source_build.GetGameFolder())
            new_build.SetSourcePath(source_build.GetSourcePath())
            new_build.SetPlatform(source_build.GetPlatform())
            new_build.SetSymbolsFile(source_build.GetSymbolsFile())
            
            # Copy main executable and injection files
            if source_build.GetMainExecutable():
                new_build.SetMainExecutable(source_build.GetMainExecutable())
                new_build.AddInjectionFile(source_build.GetMainExecutable())
            
            for file in source_build.GetInjectionFiles():
                if file != source_build.GetMainExecutable():
                    new_build.AddInjectionFile(file)
            
            # Copy file offsets
            for file in source_build.GetInjectionFiles():
                offset = source_build.GetInjectionFileOffset(file)
                if offset:
                    new_build.SetInjectionFileOffset(file, offset)
            
            print(f"Created new build version '{new_name}' sharing files from '{share_from}'")
            print(f"  Shared game folder: {source_build.GetGameFolder()}")
            print(f"  Shared symbols file: {source_build.GetSymbolsFile()}")
            
            messagebox.showinfo("Build Version Shared",
                f"New build version '{new_name}' created!\n\n"
                f"Sharing game files from: {share_from}\n"
                f"This build uses the same game files\n"
                f"Compiled code will be build-specific\n\n"
                f"You can now add modifications specific to this build.")
        else:
            print(f"Warning: Could not find source build '{share_from}'")
            new_build.SetSymbolsFile(f"{new_name}.txt")
    else:
        # Set default symbols file for new independent build
        new_build.SetSymbolsFile(f"{new_name}.txt")
        
        # Create symbols file for this build version
        project_folder = current_project_data.GetProjectFolder()
        symbols_dir = os.path.join(project_folder, "symbols")
        symbols_file_path = os.path.join(symbols_dir, f"{new_name}.txt")
        
        try:
            # Ensure symbols directory exists
            os.makedirs(symbols_dir, exist_ok=True)
            
            # Create the symbols file with instructions. (Maybe slim down the instructions eventually? Kinda bulky)
            with open(symbols_file_path, "w") as symbols_file:
                symbols_file.write(
                    f"/* Symbol file for build version: {new_name} */\n"
                    f"/* This is where you put your in-game global variables & functions */\n"
                    f"/* found from RAM search/reverse engineering for this specific version. */\n\n"
                    f"/* Example: */\n"
                    f"/* game_symbol = 0x80001234; */\n"
                )
            
            print(f"Created symbols file: symbols/{new_name}.txt")
            
        except Exception as e:
            print(f"Warning: Could not create symbols file: {str(e)}")
    
    print(f"Created new build version: {new_name}")
    
    update_build_version_listbox(current_project_data)
    
    dpg.configure_item("add_build_version_modal", show=False)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()
    
def _copy_ps1_build_data(original_build, new_build, project_data):
    import os
    import shutil

    project_folder = project_data.GetProjectFolder()
    original_name = original_build.GetBuildName()
    new_name = new_build.GetBuildName()

    # Share the extracted game folder
    original_game_files = os.path.join(project_folder, '.config', 'game_files', original_name)

    if os.path.exists(original_game_files):
        new_build.SetGameFolder(original_game_files)
        new_build.SetSourcePath(original_build.GetSourcePath())
        new_build.SetMainExecutable(original_build.GetMainExecutable())
        print(f"  Sharing game files folder: {original_game_files}")

    # Copy XML file
    original_xml = os.path.join(project_folder, '.config', 'output', f'psxbuild_{original_name}.xml')
    new_xml = os.path.join(project_folder, '.config', 'output', f'psxbuild_{new_name}.xml')

    if os.path.exists(original_xml):
        shutil.copy2(original_xml, new_xml)
        print(f"  Copied XML: {os.path.basename(new_xml)}")


def callback_duplicate_build_version(sender, app_data, current_project_data: ProjectData):
    """Actually create the build version after getting the name"""
    import os

    new_name = current_project_data.GetCurrentBuildVersionName() + "_duplicate"
    original_build = current_project_data.GetCurrentBuildVersion()

    # Create new build version (shares symbols file with original)
    current_project_data.DuplicateBuildVersion(original_build, new_name)

    # Set the duplicated build to use the same symbols file as the original
    new_build = current_project_data.build_versions[-1]  # Get the newly added build
    new_build.SetSymbolsFile(original_build.GetSymbolsFile())

    # If PS1 platform, copy XML and share game files from original build
    if current_project_data.GetCurrentBuildVersion().GetPlatform():
        _copy_ps1_build_data(original_build, new_build, current_project_data)

    # Don't create a new symbols file - just reuse the original's

    print(f"Duplicated build version: {new_name}")
    print(f"  Sharing symbols file: {original_build.GetSymbolsFile()}")

    # Update the listbox
    update_build_version_listbox(current_project_data)

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def callback_switch_project_build_version(sender, app_data, current_project_data: ProjectData):
    """Switch to a different build version"""
    selected_build_name = app_data
    
    if not selected_build_name:
        return
    
    # Find the index of the selected build
    for i, build_version in enumerate(current_project_data.build_versions):
        if build_version.GetBuildName() == selected_build_name:
            # Switch to this build version
            old_index = current_project_data.GetBuildVersionIndex()
            current_project_data.SetBuildVersionIndex(i)

            # Check prerequisites for the new build version's platform
            tool_dir = get_application_directory()
            new_platform = build_version.GetPlatform()

            if not check_and_prompt_prereqs(tool_dir, new_platform, None):
                # User cancelled download - switch back to old build
                current_project_data.SetBuildVersionIndex(old_index)
                return

            print(f"Switched from build #{old_index} to build #{i}: {selected_build_name}")

            # Refresh the entire UI to show the new build version's data
            refresh_ui_for_current_build(current_project_data)

            from gui.gui_main_project import trigger_auto_save
            trigger_auto_save()
            return
    
    print(f"Error: Could not find build version '{selected_build_name}'")


def callback_rename_build_version(sender, app_data, current_project_data: ProjectData):
    current_build = current_project_data.GetCurrentBuildVersion()
    current_name = current_build.GetBuildName()
    
    # Create input dialog
    if dpg.does_item_exist("rename_build_version_modal"):
        dpg.set_value("rename_build_version_name_input", current_name)
        dpg.show_item("rename_build_version_modal")
        return
    
    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()
    modal_width = 400
    modal_height = 150
    modal_x = (viewport_width - modal_width) // 2
    modal_y = (viewport_height - modal_height) // 2
    
    with dpg.window(
        label="Rename Build Version", 
        modal=True, 
        no_close=True, 
        tag="rename_build_version_modal",
        no_move=True, 
        no_resize=True, 
        width=modal_width, 
        height=modal_height, 
        pos=[modal_x, modal_y]
    ):
        dpg.add_text(f"Rename '{current_name}' to:")
        dpg.add_input_text(
            tag="rename_build_version_name_input", 
            default_value=current_name, 
            width=350
        )
        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Rename", 
                callback=callback_do_rename_build_version,
                user_data=current_project_data
            )
            dpg.add_button(
                label="Cancel", 
                callback=lambda: dpg.configure_item("rename_build_version_modal", show=False)
            )


def callback_do_rename_build_version(sender, app_data, current_project_data: ProjectData):
    new_name = dpg.get_value("rename_build_version_name_input")
    current_build = current_project_data.GetCurrentBuildVersion()
    old_name = current_build.GetBuildName()

    if not new_name:
        messagebox.showerror("Error", "Build version name cannot be empty.")
        return

    # Auto-capitalize for consistency with preprocessor defines
    new_name = new_name.upper()

    if new_name == old_name:
        dpg.configure_item("rename_build_version_modal", show=False)
        return

    # Check if name already exists
    existing_names = [bv.GetBuildName() for bv in current_project_data.build_versions]
    if new_name in existing_names:
        messagebox.showerror("Error", f"A build version named '{new_name}' already exists.")
        return

    # Rename the build version (will be auto-capitalized by SetBuildName)
    current_build.SetBuildName(new_name)

    print(f"Renamed build version from '{old_name}' to '{new_name}'")

    # Update library_symbols.h if it exists (for PS1/PS2 projects)
    platform = current_build.GetPlatform()
    if platform in ["PS1", "PS2"]:
        project_folder = current_project_data.GetProjectFolder()
        include_dir = os.path.join(project_folder, "include")
        header_file = os.path.join(include_dir, "library_symbols.h")

        if os.path.exists(header_file):
            from services.ghidra_pattern_service import GhidraPatternService
            service = GhidraPatternService()
            service.rename_build_in_header(header_file, old_name, new_name)

    # Update UI
    update_build_version_listbox(current_project_data)
    dpg.set_value("current_build_label", f"Editing: {new_name}")

    # Hide modal
    dpg.configure_item("rename_build_version_modal", show=False)

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def callback_delete_build_version(sender, app_data, current_project_data: ProjectData):
    """Delete the currently selected build version"""
    if len(current_project_data.build_versions) <= 1:
        messagebox.showwarning("Cannot Delete", "You must have at least one build version.")
        return
    
    current_build = current_project_data.GetCurrentBuildVersion()
    current_name = current_build.GetBuildName()
    
    response = messagebox.askyesno(
        "Delete Build Version",
        f"Are you sure you want to delete build version '{current_name}'?\n\nThis cannot be undone."
    )
    
    if not response:
        return
    
    # Delete the current build version
    current_index = current_project_data.GetBuildVersionIndex()
    current_project_data.build_versions.pop(current_index)
    
    # Switch to the first build version
    current_project_data.SetBuildVersionIndex(0)
    
    print(f"Deleted build version: {current_name}")
    
    # Refresh UI
    update_build_version_listbox(current_project_data)
    refresh_ui_for_current_build(current_project_data)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def update_build_version_listbox(current_project_data: ProjectData):
    """Update the build version listbox with current data"""
    build_names = [bv.GetBuildName() for bv in current_project_data.build_versions]
    current_name = current_project_data.GetCurrentBuildVersion().GetBuildName()
    
    dpg.configure_item("build_version_listbox", items=build_names)
    dpg.set_value("build_version_listbox", current_name)


def refresh_ui_for_current_build(current_project_data: ProjectData):
    """Refresh all UI elements to reflect the current build version"""
    current_build = current_project_data.GetCurrentBuildVersion()
    
    # Update the "Editing:" label
    dpg.set_value("current_build_label", f"Editing: {current_build.GetBuildName()}")
    
    # Update platform combo
    platform = current_build.GetPlatform()
    dpg.set_value("platform_combo", platform if platform else "Choose a Platform")
    
    # Update platform-specific buttons
    import gui.gui_main_project
    gui.gui_main_project.AddRelevantGameFileOptions(current_project_data)
    
    # Update PS1 codecave button visibility
    from gui.gui_c_injection import update_ps1_codecave_button_visibility
    update_ps1_codecave_button_visibility(current_project_data)

    # Refresh build panel UI for the new platform
    from gui.gui_main_project import refresh_build_panel_ui, update_build_button_label
    refresh_build_panel_ui(current_project_data)
    update_build_button_label(current_project_data)

    # Update game files listbox with formatted items
    game_files = current_build.GetInjectionFiles()
    if game_files:
        from gui.gui_game_files import _get_formatted_file_list
        formatted_items = _get_formatted_file_list(current_project_data)
        dpg.configure_item("game_files_listbox", items=formatted_items)
        
        # Select main executable if it exists
        if current_build.GetMainExecutable():
            main_exe = current_build.GetMainExecutable()
            for formatted_item in formatted_items:
                if main_exe in formatted_item and "(Main)" in formatted_item:
                    dpg.set_value("game_files_listbox", formatted_item)
                    break
    else:
        dpg.configure_item("game_files_listbox", items=())
    
    # Clear and update codecaves
    from gui.gui_c_injection import UpdateCodecavesListbox, ClearGuiCodecaveData
    ClearGuiCodecaveData()
    UpdateCodecavesListbox(current_project_data)
    
    # Clear and update hooks
    from gui.gui_asm_injection import UpdateHooksListbox, ClearGuiHookData
    ClearGuiHookData()
    UpdateHooksListbox(current_project_data)
    
    # Clear and update binary patches
    from gui.gui_binary_patch_injection import UpdateBinaryPatchesListbox, ClearGuiBinaryPatchData
    ClearGuiBinaryPatchData()
    UpdateBinaryPatchesListbox(current_project_data)
    
    # Show/hide tabs based on whether platform and game folder are set
    if platform and platform != "Choose a Platform" and current_build.GetGameFolder():
        dpg.configure_item("Target Game Files", show=True)
        dpg.configure_item("Modifications", show=True)
    else:
        dpg.configure_item("Target Game Files", show=False)
        dpg.configure_item("Modifications", show=False)
        
    if dpg.does_item_exist("compiler_flags_input"):
        dpg.set_value("compiler_flags_input", current_build.GetCompilerFlags())
        
    # Update symbols file dropdown
    if dpg.does_item_exist("symbols_file_combo"):
        project_folder = current_project_data.GetProjectFolder()
        symbols_dir = os.path.join(project_folder, "symbols")
        symbols_files = []

        if os.path.exists(symbols_dir):
            symbols_files = [f for f in os.listdir(symbols_dir) if f.endswith('.txt')]

        current_symbols = current_build.GetSymbolsFile()

        # Update items and selection
        dpg.configure_item("symbols_file_combo", items=symbols_files if symbols_files else [current_symbols])
        dpg.set_value("symbols_file_combo", current_symbols)

    # Hide Emulator / Build / Export section until this build is compiled
    if dpg.does_item_exist("emulator_iso_buttons_group_container"):
        dpg.configure_item("emulator_iso_buttons_group_container", show=False)

    # Hide Code Size Analysis until this build is compiled
    if dpg.does_item_exist("size_analysis_header"):
        dpg.configure_item("size_analysis_header", show=False)

    # Clear any old build status text
    if dpg.does_item_exist("build_status_label"):
        dpg.set_value("build_status_label", "")

    # Update project dashboard
    from gui.gui_main_project import update_project_dashboard
    update_project_dashboard(current_project_data)

    print(f"UI refreshed for build version: {current_build.GetBuildName()}")

def callback_save_project(sender, button_data, current_project_data: ProjectData):
    """Manually save the project"""
    import gui.gui_main_project
    
    # Check if auto-save already handled it
    if gui.gui_main_project._auto_save_manager:
        if not gui.gui_main_project._auto_save_manager.save_pending:
            messagebox.showinfo("Already Saved", "Project is already up to date!")
            return
    
    success = ProjectSerializer.save_project(current_project_data)
    if success:
        # Clear pending flag
        if gui.gui_main_project._auto_save_manager:
            gui.gui_main_project._auto_save_manager.save_pending = False
    else:
        messagebox.showerror("Error", "Failed to save project.")

def callback_rename_project(_, __, current_project_data: ProjectData):
    """Show rename project modal dialog"""
    import dearpygui.dearpygui as dpg

    old_name = current_project_data.GetProjectName()

    if dpg.does_item_exist("rename_project_modal"):
        dpg.set_value("rename_project_input", old_name)
        dpg.show_item("rename_project_modal")
    else:
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        modal_width = 400
        modal_height = 170
        modal_x = (viewport_width - modal_width) // 2
        modal_y = (viewport_height - modal_height) // 2

        with dpg.window(label="Rename Project", modal=True, no_close=True, tag="rename_project_modal",
                        no_move=True, no_resize=True, width=modal_width, height=modal_height,
                        pos=[modal_x, modal_y], show=False):
            dpg.add_text(f"Current name: {old_name}")
            dpg.add_text("Enter new project name:")
            dpg.add_input_text(tag="rename_project_input", default_value=old_name, width=350)
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Rename", callback=callback_execute_rename_project, user_data=current_project_data)
                dpg.add_button(label="Cancel", callback=lambda s,a,u: dpg.configure_item("rename_project_modal", show=False))
        dpg.show_item("rename_project_modal")


def callback_execute_rename_project(_, __, current_project_data: ProjectData):
    """Execute the actual project rename"""
    import os
    import re
    import dearpygui.dearpygui as dpg

    old_name = current_project_data.GetProjectName()
    new_name = dpg.get_value("rename_project_input")

    if not new_name or new_name == old_name:
        dpg.configure_item("rename_project_modal", show=False)
        return

    # Validate name (no special chars, not empty)
    new_name = new_name.strip()
    if not new_name:
        messagebox.showerror("Invalid Name", "Project name cannot be empty.")
        return

    # Remove invalid filename characters
    invalid_chars = r'[<>:"/\\|?*]'
    if re.search(invalid_chars, new_name):
        messagebox.showerror(
            "Invalid Name",
            "Project name cannot contain: < > : \" / \\ | ? *"
        )
        return

    # Get current .modproj file path
    project_folder = current_project_data.GetProjectFolder()
    old_modproj_files = [f for f in os.listdir(project_folder) if f.endswith('.modproj')]

    if not old_modproj_files:
        messagebox.showerror("Error", "Could not find .modproj file.")
        return

    old_modproj_path = os.path.join(project_folder, old_modproj_files[0])
    new_modproj_path = os.path.join(project_folder, f"{new_name}.modproj")

    # Check if target file already exists
    if os.path.exists(new_modproj_path) and old_modproj_path != new_modproj_path:
        messagebox.showerror(
            "File Exists",
            f"A file named '{new_name}.modproj' already exists in this folder."
        )
        return

    try:
        # Update project name in data
        current_project_data.SetProjectName(new_name)

        # Save project (creates/updates the file)
        success = ProjectSerializer.save_project(current_project_data)
        if not success:
            messagebox.showerror("Error", "Failed to save project with new name.")
            return

        # If the filename changed, rename the file and delete the old one
        if old_modproj_path != new_modproj_path:
            # The new file was created by save_project, remove the old one
            if os.path.exists(old_modproj_path):
                os.remove(old_modproj_path)

        # Update GUI window title
        import dearpygui.dearpygui as dpg
        if dpg.does_item_exist("primary_window"):
            dpg.set_item_label("primary_window", f"Code Injection Toolchain - {new_name}")

        # Update recent projects list
        from services.recent_projects_service import RecentProjectsService
        RecentProjectsService.remove_recent_project(old_modproj_path)
        RecentProjectsService.add_recent_project(
            new_modproj_path,
            new_name,
            current_project_data.GetCurrentBuildVersion().GetPlatform()
        )

        # Close modal
        dpg.configure_item("rename_project_modal", show=False)

        messagebox.showinfo(
            "Success",
            f"Project renamed to '{new_name}'\n\n"
            f"File: {new_name}.modproj"
        )

    except Exception as e:
        messagebox.showerror("Error", f"Failed to rename project: {str(e)}")
        dpg.configure_item("rename_project_modal", show=False)

def callback_clean_build(_, __, current_project_data: ProjectData):
    """Clean build artifacts and force full rebuild"""
    import os
    import shutil

    # result = messagebox.askyesno(
    #     "Clean Build",
    #     "This will delete all compiled files and force a full rebuild on next compile.\n\nContinue?"
    # )

    # if not result:
    #     return

    project_folder = current_project_data.GetProjectFolder()

    # Directories to clean
    clean_dirs = [
        os.path.join(project_folder, '.config', 'output', 'object_files'),
        os.path.join(project_folder, '.config', 'output', 'bin_files'),
        os.path.join(project_folder, '.config', 'output', 'memory_map'),
        os.path.join(project_folder, '.config', 'output', 'iso_build'),
    ]

    # Files to clean
    clean_files = [
        os.path.join(project_folder, 'ModdedGame.bin'),
        os.path.join(project_folder, 'ModdedGame.cue'),
        os.path.join(project_folder, 'ModdedGame.iso'),
    ]

    # Add patched files
    for file_name in current_project_data.GetCurrentBuildVersion().GetInjectionFiles():
        clean_files.append(os.path.join(project_folder, f'patched_{file_name}'))

    # Clear build cache
    cache_path = os.path.join(project_folder, '.config', 'output', '.build_cache.json')
    if os.path.exists(cache_path):
        clean_files.append(cache_path)

    files_removed = 0

    # Clean directories
    for dir_path in clean_dirs:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                os.makedirs(dir_path, exist_ok=True)
                files_removed += 1
            except Exception as e:
                print(f"Could not clean {dir_path}: {e}")

    # Clean files
    for file_path in clean_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                files_removed += 1
            except Exception as e:
                print(f"Could not remove {file_path}: {e}")

    if files_removed > 0:
        messagebox.showinfo("Clean Complete", f"Cleaned {files_removed} artifact(s).\n\nNext compile will rebuild all files.")
    else:
        messagebox.showinfo("Clean Complete", "Nothing to clean.")

def reset_memory_watch_service():
    """Reset the memory watch service when changing/closing projects"""
    try:
        # Import the reset function for project changes
        from gui.gui_memory_watch import reset_memory_watch_for_project_change
        
        reset_memory_watch_for_project_change()
        print("Memory watch reset for project change")
    except Exception as e:
        print(f"Could not reset memory watch service: {e}")


# Then update these existing functions:

def callback_close_project(sender, button_data, current_project_data):
    """Close current project and return to startup screen"""
    import gui.gui_main_project
    import gui.gui_startup_window

    # Stop auto-save and clear it
    if gui.gui_main_project._auto_save_manager:
        gui.gui_main_project._auto_save_manager.save_now()
        gui.gui_main_project._auto_save_manager.stop()
        gui.gui_main_project._auto_save_manager = None

    # Reset memory watch service
    reset_memory_watch_service()

    # Reset emulator connection manager
    get_emulator_manager().reset_for_project_close()

    # Reset all global project state
    reset_global_project_state()

    # Reset build preferences and state
    from gui.gui_build import reset_build_preferences
    reset_build_preferences()

    # Reset main project state (auto-save manager, hotkey manager, etc.)
    gui.gui_main_project.reset_main_project_state()

    # Delete project window
    if dpg.does_item_exist("Project Window"):
        dpg.delete_item("Project Window")

    # Clear project data reference
    current_project_data = None

    # Return to startup
    gui.gui_startup_window.InitMainWindow()
    dpg.set_primary_window("startup_window", True)

    print("Project closed successfully")


def callback_load_different_project(sender, button_data, current_project_data):
    """Close current project and load a different one"""
    import gui.gui_main_project

    # Ask user to confirm
    response = messagebox.askyesno(
        "Load Different Project",
        "This will close the current project. Any unsaved changes will be saved. Continue?"
    )

    if not response:
        return

    # Stop auto-save for current project and clear it
    if gui.gui_main_project._auto_save_manager:
        gui.gui_main_project._auto_save_manager.save_now()
        gui.gui_main_project._auto_save_manager.stop()
        gui.gui_main_project._auto_save_manager = None

    # Reset memory watch service
    reset_memory_watch_service()

    # Reset emulator connection manager
    get_emulator_manager().reset_for_project_close()

    # Reset all global project state
    reset_global_project_state()

    # Reset build preferences and state
    from gui.gui_build import reset_build_preferences
    reset_build_preferences()

    # Reset main project state (auto-save manager, hotkey manager, etc.)
    gui.gui_main_project.reset_main_project_state()

    # Open file dialog
    file_path = filedialog.askopenfilename(
        title="Load Project",
        filetypes=[("Mod Project Files", "*.modproj"), ("All Files", "*.*")],
        initialdir="projects"
    )

    if not file_path:
        return  # User cancelled

    # Show loading indicator after file dialog closes
    try:
        LoadingIndicator.show("Loading Project...")
        dpg.split_frame()
    except:
        # If loading indicator fails (context issues), continue anyway
        pass

    # Load the project (don't show loading again internally)
    new_project_data = ProjectSerializer.load_project(file_path, show_loading=False)

    # Hide loading indicator
    try:
        LoadingIndicator.hide()
    except:
        pass

    if new_project_data is None:
        messagebox.showerror("Load Failed", "Failed to load project file.")
        return

    # Close current project window
    if dpg.does_item_exist("Project Window"):
        dpg.delete_item("Project Window")

    # Open new project
    gui.gui_main_project.InitMainProjectWindowWithData(new_project_data)

    print("Different project loaded successfully")
    
def callback_extract_ps1_bin(sender, app_data, current_project_data: ProjectData):
    """Extract PS1 BIN/CUE file with template prompt"""
    from gui.gui_loading_indicator import LoadingIndicator
    from services.binmerge_service import BinmergeService

    # Choose ISO file (prefer CUE for multi-bin games)
    original_file_path = filedialog.askopenfilename(
        title="Choose PS1 BIN/CUE File (use .cue for multi-bin games)",
        filetypes=[("PS1 Images", "*.bin;*.cue"), ("All Files", "*.*")]
    )

    if not original_file_path:
        return

    # Process the file (handle multi-bin merging if needed)
    print(f"\nProcessing PS1 file: {os.path.basename(original_file_path)}")
    success, bin_to_extract, message = BinmergeService.process_ps1_file(original_file_path)

    if not success:
        messagebox.showerror("Error", f"Failed to process PS1 file:\n\n{message}")
        return

    print(f" {message}")
    print(f"  BIN to extract: {os.path.basename(bin_to_extract)}")

    # Keep track of both the original file (for source_path) and the bin to extract
    iso_path = bin_to_extract
    source_path_to_save = original_file_path  # Preserve original CUE/BIN path for rebuilding

    # Check if game files already exist for this build
    current_build = current_project_data.GetCurrentBuildVersion()
    project_folder = current_project_data.GetProjectFolder()
    build_name = current_build.GetBuildName()
    output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)

    # Warn user if existing game files will be overwritten
    if os.path.exists(output_dir) and os.listdir(output_dir):
        response = messagebox.askyesno(
            "Replace Existing Game Files?",
            f"The build '{build_name}' already has extracted game files.\n\n"
            f"Do you want to replace them with the new BIN/CUE?\n\n"
            f"This will overwrite all existing game files for this build."
        )
        if not response:
            return

    # Show loading indicator
    LoadingIndicator.show("Extracting PS1 BIN...")
    
    def extract_async():
        try:
            current_build = current_project_data.GetCurrentBuildVersion()
            project_folder = current_project_data.GetProjectFolder()
            build_name = current_build.GetBuildName()
            
            # Use build-specific output directory
            output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)
            
            # Create ISO service and extract
            iso_service = ISOService(current_project_data, verbose=False)
            result = iso_service.extract_iso(iso_path, output_dir)

            # Update UI on main thread
            def update_ui():
                print("DEBUG: update_ui() called in PS1 extraction callback")
                LoadingIndicator.hide()

                if result.success:
                    messagebox.showinfo("Success",
                        f"PS1 BIN extracted successfully!\n\n")

                    # Set paths (extraction already put files in build-specific folder)
                    current_build.SetGameFolder(output_dir)
                    current_build.SetSourcePath(source_path_to_save)  # Use original file path (CUE or BIN)

                    # Search for main executable
                    main_exe = current_build.SearchForMainExecutableInGameFolder()
                    print(f"DEBUG: Searched for main exe, result: {main_exe}")

                    if main_exe:
                        print("DEBUG: Entered main_exe block")
                        current_build.SetMainExecutable(main_exe)
                        current_build.AddInjectionFile(main_exe)
                        current_build.AutoSetFileOffsetForPlatform()

                        try:
                            CInjectionChangeGameFiles(current_build.GetInjectionFiles())
                            dpg.configure_item("game_files_listbox", items=(main_exe,))
                            dpg.set_value("game_files_listbox", main_exe)

                            dpg.set_value("File Offset From Ram Input", "F800")

                            dpg.configure_item("Target Game Files", show=True)
                            dpg.configure_item("Modifications", show=True)
                        except Exception as e:
                            print(f"Warning: GUI update failed (this is OK): {e}")

                        # Download box art
                        print("DEBUG: About to attempt box art download")
                        from services.game_boxart_service import GameBoxartService
                        from gui.gui_main_project import update_boxart_display
                        download_result = GameBoxartService.download_boxart(current_project_data)
                        print(f"DEBUG: Box art download result: {download_result}")
                        if download_result:
                            update_boxart_display(current_project_data)
                            print("DEBUG: Called update_boxart_display")
                        else:
                            print("DEBUG: Box art download returned False, not updating display")

                        from gui.gui_main_project import trigger_auto_save
                        trigger_auto_save()

                        # Scan for OS library functions
                        #_scan_for_os_library_functions(current_project_data)

                        messagebox.showinfo("Success",
                            f"Game files set up for build '{build_name}'!\n\n"
                            f"Main executable: {main_exe}\n"
                            f"Working directory: .config/game_files/{build_name}/\n"
                            f"File offset: 0xF800 (default for PS1)")

                        from services.template_service import show_ps1_template_prompt
                        show_ps1_template_prompt(current_project_data)    
                    
                    else:
                        messagebox.showwarning("Warning", "Could not find main executable in extracted files.")
                else:
                    messagebox.showerror("Extraction Failed", result.message)
            
            dpg.split_frame()
            update_ui()
            
        except Exception as e:
            LoadingIndicator.hide()
            import traceback
            messagebox.showerror("Error", f"Extraction failed: {str(e)}\n\n{traceback.format_exc()}")
    
    import threading
    thread = threading.Thread(target=extract_async, daemon=True)
    thread.start()

def callback_extract_ps2_iso(sender, app_data, current_project_data: ProjectData):
    """Extract PS2 ISO file"""
    from gui.gui_loading_indicator import LoadingIndicator

    # Choose ISO file
    iso_path = filedialog.askopenfilename(
        title="Choose PS2 ISO File",
        filetypes=[("ISO Images", "*.iso"), ("All Files", "*.*")]
    )

    if not iso_path:
        return

    # Check if game files already exist for this build
    current_build = current_project_data.GetCurrentBuildVersion()
    project_folder = current_project_data.GetProjectFolder()
    build_name = current_build.GetBuildName()
    output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)

    # Warn user if existing game files will be overwritten
    if os.path.exists(output_dir) and os.listdir(output_dir):
        response = messagebox.askyesno(
            "Replace Existing Game Files?",
            f"The build '{build_name}' already has extracted game files.\n\n"
            f"Do you want to replace them with the new ISO?\n\n"
            f"This will overwrite all existing game files for this build."
        )
        if not response:
            return

    # Show loading indicator
    LoadingIndicator.show("Extracting PS2 ISO...")
    
    def extract_async():
        try:
            current_build = current_project_data.GetCurrentBuildVersion()
            project_folder = current_project_data.GetProjectFolder()
            build_name = current_build.GetBuildName()
            
            # Use build-specific output directory
            output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)
            
            # Create ISO service and extract
            iso_service = ISOService(current_project_data, verbose=False)
            result = iso_service.extract_iso(iso_path, output_dir)
            
            # Update UI on main thread
            def update_ui():
                LoadingIndicator.hide()
                
                if result.success:
                    messagebox.showinfo("Success", 
                        f"PS2 ISO extracted successfully!\n\n")
                    
                    # Set paths
                    current_build.SetGameFolder(output_dir)
                    current_build.SetSourcePath(iso_path)
                    
                    # Search for main executable
                    main_exe = current_build.SearchForMainExecutableInGameFolder()
                    
                    if main_exe:
                        current_build.SetMainExecutable(main_exe)
                        current_build.AddInjectionFile(main_exe)
                        current_build.AutoSetFileOffsetForPlatform()

                        CInjectionChangeGameFiles(current_build.GetInjectionFiles())
                        dpg.configure_item("game_files_listbox", items=(main_exe,))
                        dpg.set_value("game_files_listbox", main_exe)

                        offset = current_build.GetInjectionFileOffset(main_exe)
                        #dpg.set_value("File Offset From Ram Input", offset if offset else "")

                        dpg.configure_item("Target Game Files", show=True)
                        dpg.configure_item("Modifications", show=True)

                        # Download box art
                        from services.game_boxart_service import GameBoxartService
                        from gui.gui_main_project import update_boxart_display
                        if GameBoxartService.download_boxart(current_project_data):
                            update_boxart_display(current_project_data)

                        from gui.gui_main_project import trigger_auto_save
                        trigger_auto_save()

                        # Scan for OS library functions
                        #_scan_for_os_library_functions(current_project_data)

                        # Setup PS2 _print syscall for Hello World
                        print("Setting up PS2 _print syscall...")
                        from services.template_service import TemplateService
                        template_service = TemplateService(current_project_data)
                        if template_service.setup_ps2_print_syscall():
                            print(" PS2 _print syscall setup complete")
                        else:
                            print(" PS2 _print syscall setup failed")

                        messagebox.showinfo("Success",
                            f"Game files set up for build '{build_name}'!\n\n"
                            f"Main executable: {main_exe}\n")
                    else:
                        messagebox.showwarning("Warning", "Could not find main executable in extracted files.")
                else:
                    messagebox.showerror("Extraction Failed", result.message)
            
            dpg.split_frame()
            update_ui()
            
        except Exception as e:
            LoadingIndicator.hide()
            import traceback
            messagebox.showerror("Error", f"Extraction failed: {str(e)}\n\n{traceback.format_exc()}")
    
    import threading
    thread = threading.Thread(target=extract_async, daemon=True)
    thread.start()


def callback_extract_gamecube_iso(sender, app_data, current_project_data: ProjectData):
    """Extract GameCube ISO file"""
    from gui.gui_loading_indicator import LoadingIndicator

    # Choose ISO file
    iso_path = filedialog.askopenfilename(
        title="Choose GameCube ISO/RVZ File",
        filetypes=[("GameCube Images", "*.iso;*.gcm;*.nkit.iso;*.ciso;*.rvz"), ("All Files", "*.*")]
    )

    if not iso_path:
        return

    # Check if game files already exist for this build
    current_build = current_project_data.GetCurrentBuildVersion()
    project_folder = current_project_data.GetProjectFolder()
    build_name = current_build.GetBuildName()
    output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)
    root_dir = os.path.join(output_dir, 'root')

    # Warn user if existing game files will be overwritten
    if os.path.exists(root_dir) and os.listdir(root_dir):
        response = messagebox.askyesno(
            "Replace Existing Game Files?",
            f"The build '{build_name}' already has extracted game files.\n\n"
            f"Do you want to replace them with the new ISO?\n\n"
            f"This will overwrite all existing game files for this build."
        )
        if not response:
            return

        # Delete existing root directory to avoid gc-fst error
        try:
            import shutil
            shutil.rmtree(root_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove existing game files: {e}")
            return

    # Show loading indicator
    LoadingIndicator.show("Extracting GameCube ISO...")
    
    def extract_async():
        try:
            current_build = current_project_data.GetCurrentBuildVersion()
            project_folder = current_project_data.GetProjectFolder()
            build_name = current_build.GetBuildName()
            
            # Use build-specific output directory
            output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)
            
            # Create ISO service and extract
            iso_service = ISOService(current_project_data, verbose=False)
            result = iso_service.extract_iso(iso_path, output_dir)
            
            # Update UI on main thread
            def update_ui():
                LoadingIndicator.hide()
                
                if result.success:
                    messagebox.showinfo("Success", 
                        f"GameCube ISO extracted successfully!\n\n"
                        f"Build: {build_name}\n"
                        f"Location: .config/game_files/{build_name}/")
                    
                    # For GameCube, files are in root/ subdirectory
                    game_folder = os.path.join(output_dir, 'root')
                    current_build.SetGameFolder(game_folder)
                    current_build.SetSourcePath(iso_path)

                    # Search for main executable
                    main_exe = current_build.SearchForMainExecutableInGameFolder()

                    if main_exe:
                        current_build.SetMainExecutable(main_exe)
                        current_build.AddInjectionFile(main_exe)
                        current_build.AutoSetFileOffsetForPlatform()

                        # Try to find and setup OSReport for Hello World
                        print("Searching for OSReport pattern...")
                        from services.pattern_service import PatternService
                        pattern_service = PatternService(current_project_data)
                        if pattern_service.setup_osreport():
                            print(" OSReport setup complete")
                        else:
                            print(" OSReport pattern not found or not applicable")

                        CInjectionChangeGameFiles(current_build.GetInjectionFiles())
                        dpg.configure_item("game_files_listbox", items=(main_exe,))
                        dpg.set_value("game_files_listbox", main_exe)

                        offset = current_build.GetInjectionFileOffset(main_exe)
                        #dpg.set_value("File Offset From Ram Input", offset if offset else "")

                        dpg.configure_item("Target Game Files", show=True)
                        dpg.configure_item("Modifications", show=True)

                        # Download box art
                        from services.game_boxart_service import GameBoxartService
                        from gui.gui_main_project import update_boxart_display
                        if GameBoxartService.download_boxart(current_project_data):
                            update_boxart_display(current_project_data)

                        from gui.gui_main_project import trigger_auto_save
                        trigger_auto_save()

                        messagebox.showinfo("Success",
                            f"Game files set up for build '{build_name}'!\n\n"
                            f"Main executable: {main_exe}\n")
                    else:
                        messagebox.showwarning("Warning", "Could not find main.dol or start.dol in extracted folder.")
                else:
                    messagebox.showerror("Extraction Failed", result.message)
            
            dpg.split_frame()
            update_ui()
            
        except Exception as e:
            LoadingIndicator.hide()
            import traceback
            messagebox.showerror("Error", f"Extraction failed: {str(e)}\n\n{traceback.format_exc()}")
    
    import threading
    thread = threading.Thread(target=extract_async, daemon=True)
    thread.start()


def callback_extract_wii_iso(sender, app_data, current_project_data: ProjectData):
    """Extract Wii ISO file"""
    from gui.gui_loading_indicator import LoadingIndicator

    # Choose ISO file
    iso_path = filedialog.askopenfilename(
        title="Choose Wii ISO/WBFS/RVZ File",
        filetypes=[("Wii Images", "*.iso;*.wbfs;*.nkit.iso;*.rvz"), ("All Files", "*.*")]
    )

    if not iso_path:
        return

    # Check if game files already exist for this build
    current_build = current_project_data.GetCurrentBuildVersion()
    project_folder = current_project_data.GetProjectFolder()
    build_name = current_build.GetBuildName()
    output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)

    # Warn user if existing game files will be overwritten
    if os.path.exists(output_dir) and os.listdir(output_dir):
        response = messagebox.askyesno(
            "Replace Existing Game Files?",
            f"The build '{build_name}' already has extracted game files.\n\n"
            f"Do you want to replace them with the new ISO?\n\n"
            f"This will overwrite all existing game files for this build."
        )
        if not response:
            return

    # Show loading indicator
    LoadingIndicator.show("Extracting Wii ISO...")
    
    def extract_async():
        try:
            current_build = current_project_data.GetCurrentBuildVersion()
            project_folder = current_project_data.GetProjectFolder()
            build_name = current_build.GetBuildName()
            
            # Use build-specific output directory
            output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)
            
            # Create ISO service and extract
            iso_service = ISOService(current_project_data, verbose=False)
            result = iso_service.extract_iso(iso_path, output_dir)
            
            # Update UI on main thread
            def update_ui():
                LoadingIndicator.hide()
                
                if result.success:
                    messagebox.showinfo("Success",
                        f"Wii ISO extracted successfully!\n\n"
                        f"Build: {build_name}\n")

                    # Set paths
                    current_build.SetGameFolder(output_dir)
                    current_build.SetSourcePath(iso_path)

                    # Search for main executable
                    main_exe = current_build.SearchForMainExecutableInGameFolder()

                    if main_exe:
                        current_build.SetMainExecutable(main_exe)
                        current_build.AddInjectionFile(main_exe)
                        current_build.AutoSetFileOffsetForPlatform()

                        # Try to find and setup OSReport for Hello World
                        print("Searching for OSReport pattern...")
                        from services.pattern_service import PatternService
                        pattern_service = PatternService(current_project_data)
                        if pattern_service.setup_osreport():
                            print(" OSReport setup complete")
                        else:
                            print(" OSReport pattern not found or not applicable")

                        CInjectionChangeGameFiles(current_build.GetInjectionFiles())
                        dpg.configure_item("game_files_listbox", items=(main_exe,))
                        dpg.set_value("game_files_listbox", main_exe)

                        offset = current_build.GetInjectionFileOffset(main_exe)
                        #dpg.set_value("File Offset From Ram Input", offset if offset else "")

                        dpg.configure_item("Target Game Files", show=True)
                        dpg.configure_item("Modifications", show=True)

                        # Download box art
                        from services.game_boxart_service import GameBoxartService
                        from gui.gui_main_project import update_boxart_display
                        if GameBoxartService.download_boxart(current_project_data):
                            update_boxart_display(current_project_data)

                        from gui.gui_main_project import trigger_auto_save
                        trigger_auto_save()

                        messagebox.showinfo("Success",
                            f"Game files set up for build '{build_name}'!\n\n"
                            f"Main executable: {main_exe}\n")
                    else:
                        messagebox.showwarning("Warning", "Could not find main.dol or start.dol in extracted folder.")
                else:
                    messagebox.showerror("Extraction Failed", result.message)
            
            dpg.split_frame()
            update_ui()
            
        except Exception as e:
            LoadingIndicator.hide()
            import traceback
            messagebox.showerror("Error", f"Extraction failed: {str(e)}\n\n{traceback.format_exc()}")
    
    import threading
    thread = threading.Thread(target=extract_async, daemon=True)
    thread.start()


def callback_choose_ps1_iso_folder(sender, button_data, current_project_data: ProjectData):
    """Choose already-extracted PS1 BIN folder with auto offset"""
    bin_folder_path = filedialog.askdirectory(title="Choose Extracted PS1 BIN folder")
    if not bin_folder_path:
        return
    
    from gui.gui_loading_indicator import LoadingIndicator
    LoadingIndicator.show("Copying game files...")
    
    def process_async():
        try:
            current_build = current_project_data.GetCurrentBuildVersion()
            project_folder = current_project_data.GetProjectFolder()
            build_name = current_build.GetBuildName()
            
            # Copy to build-specific folder
            if not current_build.CopyGameFilesToLocal(bin_folder_path, project_folder):
                LoadingIndicator.hide()
                messagebox.showerror("Error", "Failed to copy game files to project folder")
                return
            
            # Game folder is now build-specific
            local_game_files = os.path.join(project_folder, '.config', 'game_files', build_name)
            current_build.SetGameFolder(local_game_files)
            current_build.SetSourcePath(bin_folder_path)
            
            main_exe = current_build.SearchForMainExecutableInGameFolder()
            
            def update_ui():
                LoadingIndicator.hide()
                
                if main_exe != None:
                    print_dark_grey(f"Set Main Executable of Build Version to be: {main_exe}")
                    current_build.SetMainExecutable(main_exe)
                    current_build.AddInjectionFile(main_exe)
                    
                    current_build.AutoSetFileOffsetForPlatform()
                    
                    CInjectionChangeGameFiles(current_build.GetInjectionFiles())
                    dpg.configure_item("game_files_listbox", items=(current_build.GetMainExecutable(), ))
                    dpg.set_value("game_files_listbox", main_exe)
                    
                    offset = current_build.GetInjectionFileOffset(main_exe)
                    dpg.set_value("File Offset From Ram Input", "F800")
                
                dpg.configure_item("Target Game Files", show=True)
                dpg.configure_item("Modifications", show=True)

                # Download box art
                from services.game_boxart_service import GameBoxartService
                from gui.gui_main_project import update_boxart_display
                if GameBoxartService.download_boxart(current_project_data):
                    update_boxart_display(current_project_data)

                from gui.gui_main_project import trigger_auto_save
                trigger_auto_save()

                # Scan for OS library functions
                #_scan_for_os_library_functions(current_project_data)

                offset = current_build.GetInjectionFileOffset(main_exe) if main_exe else None
                messagebox.showinfo("Success",
                    f"Game files copied for build '{build_name}'!\n\n")

                if current_build.GetPlatform() == "PS1":
                    from services.template_service import show_ps1_template_prompt
                    show_ps1_template_prompt(current_project_data)
            
            dpg.split_frame()
            update_ui()
            
        except Exception as e:
            LoadingIndicator.hide()
            import traceback
            messagebox.showerror("Error", f"Failed: {str(e)}\n\n{traceback.format_exc()}")
    
    import threading
    thread = threading.Thread(target=process_async, daemon=True)
    thread.start()



def callback_choose_ps2_iso_folder(sender, button_data, current_project_data: ProjectData):
    """Choose already-extracted PS2 ISO folder"""
    iso_folder_path = filedialog.askdirectory(title="Choose Extracted PS2 ISO folder")
    if not iso_folder_path:
        return
        
    current_project_data.GetCurrentBuildVersion().SetGameFolder(iso_folder_path)
    current_project_data.GetCurrentBuildVersion().SetSourcePath(iso_folder_path)
    main_exe = current_project_data.GetCurrentBuildVersion().SearchForMainExecutableInGameFolder()
    
    if main_exe != None:
        print_dark_grey(f"Set Main Executable of Build Version to be: {main_exe}")
        current_project_data.GetCurrentBuildVersion().SetMainExecutable(main_exe)
        current_project_data.GetCurrentBuildVersion().AddInjectionFile(main_exe)
        
        current_project_data.GetCurrentBuildVersion().AutoSetFileOffsetForPlatform()
        
        CInjectionChangeGameFiles(current_project_data.GetCurrentBuildVersion().GetInjectionFiles())
        dpg.configure_item("game_files_listbox", items=(current_project_data.GetCurrentBuildVersion().GetMainExecutable(), ))
        
        offset = current_project_data.GetCurrentBuildVersion().GetInjectionFileOffset(main_exe)
        #dpg.set_value("File Offset From Ram Input", offset if offset else "")
    
    dpg.configure_item("Target Game Files", show=True)
    dpg.configure_item("Modifications", show=True)

    # Download box art
    from services.game_boxart_service import GameBoxartService
    from gui.gui_main_project import update_boxart_display
    if GameBoxartService.download_boxart(current_project_data):
        update_boxart_display(current_project_data)

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    # Scan for OS library functions
    #_scan_for_os_library_functions(current_project_data)

    # Setup PS2 _print syscall for Hello World
    print("Setting up PS2 _print syscall...")
    from services.template_service import TemplateService
    template_service = TemplateService(current_project_data)
    if template_service.setup_ps2_print_syscall():
        print(" PS2 _print syscall setup complete")
    else:
        print(" PS2 _print syscall setup failed")


def callback_choose_gamecube_iso_folder(sender, button_data, current_project_data: ProjectData):
    """Choose already-extracted GameCube/Wii ISO folder"""
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    title = f"Choose Extracted {platform} ISO folder"
    iso_folder_path = filedialog.askdirectory(title=title)
    if not iso_folder_path:
        return

    # GameCube extractions have a 'root' subdirectory containing the actual files
    # Wii extractions (from Dolphin) have a 'DATA' subdirectory containing the actual files
    # Check if we need to navigate to the appropriate subdirectory

    game_folder = iso_folder_path  # Default to user selection

    # Check for Wii 'DATA' folder first (Dolphin extraction format)
    data_subdir = os.path.join(iso_folder_path, 'DATA')
    if os.path.exists(data_subdir) and os.path.isdir(data_subdir):
        game_folder = data_subdir
        print(f"  Detected 'DATA' subdirectory (Wii Dolphin extraction), using: {game_folder}")
    else:
        # Check for GameCube 'root' folder (wit/gc-fst extraction format)
        root_subdir = os.path.join(iso_folder_path, 'root')
        if os.path.exists(root_subdir) and os.path.isdir(root_subdir):
            game_folder = root_subdir
            print(f"  Detected 'root' subdirectory (GameCube extraction), using: {game_folder}")

    current_project_data.GetCurrentBuildVersion().SetGameFolder(game_folder)
    current_project_data.GetCurrentBuildVersion().SetSourcePath(iso_folder_path)
    
    main_exe = current_project_data.GetCurrentBuildVersion().SearchForMainExecutableInGameFolder()
    
    if main_exe != None:
        print_dark_grey(f"Set Main Executable of Build Version to be: {main_exe}")
        current_project_data.GetCurrentBuildVersion().SetMainExecutable(main_exe)
        current_project_data.GetCurrentBuildVersion().AddInjectionFile(main_exe)
        
        current_project_data.GetCurrentBuildVersion().AutoSetFileOffsetForPlatform()
        offset = current_project_data.GetCurrentBuildVersion().GetInjectionFileOffset(main_exe)
        #dpg.set_value("File Offset From Ram Input", offset if offset else "")

        # Try to find and setup OSReport for Hello World
        print("Searching for OSReport pattern...")
        from services.pattern_service import PatternService
        pattern_service = PatternService(current_project_data)
        if pattern_service.setup_osreport():
            print(" OSReport setup complete")
        else:
            print(" OSReport pattern not found or not applicable")

        CInjectionChangeGameFiles(current_project_data.GetCurrentBuildVersion().GetInjectionFiles())
        dpg.configure_item("game_files_listbox", items=(current_project_data.GetCurrentBuildVersion().GetMainExecutable(), ))

    dpg.configure_item("Target Game Files", show=True)
    dpg.configure_item("Modifications", show=True)

    # Download box art
    from services.game_boxart_service import GameBoxartService
    from gui.gui_main_project import update_boxart_display
    if GameBoxartService.download_boxart(current_project_data):
        update_boxart_display(current_project_data)

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    platform_name = current_build.GetPlatform()
    messagebox.showinfo("Success",
        f"{platform_name} folder set!\n\n"
        f"Main executable: {main_exe}\n")


def callback_choose_n64_rom(sender, app_data, current_project_data: ProjectData):
    """Choose N64 ROM file (doesn't need extraction)"""
    
    rom_path = filedialog.askopenfilename(
        title="Choose N64 ROM File",
        filetypes=[("N64 ROMs", "*.n64;*.z64;*.v64"), ("All Files", "*.*")]
    )
    
    if not rom_path:
        return
    
    # For N64, we just set the ROM as the game folder and main executable
    current_project_data.GetCurrentBuildVersion().SetGameFolder(os.path.dirname(rom_path))
    rom_name = os.path.basename(rom_path)
    current_project_data.GetCurrentBuildVersion().SetMainExecutable(rom_name)
    current_project_data.GetCurrentBuildVersion().AddInjectionFile(rom_name)
    
    CInjectionChangeGameFiles(current_project_data.GetCurrentBuildVersion().GetInjectionFiles())
    dpg.configure_item("game_files_listbox", items=(rom_name,))
    
    dpg.configure_item("Target Game Files", show=True)
    dpg.configure_item("Modifications", show=True)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()
    messagebox.showinfo("Success", f"N64 ROM set: {rom_name}")
    
def callback_choose_single_file(sender, app_data, current_project_data: ProjectData):
    """Choose a single file for modification (no ISO rebuilding)"""
    from tkinter import filedialog
    from gui import gui_messagebox as messagebox
    
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()
    
    # Platform-specific file filters
    if platform == "PS1":
        filetypes = [
            ("PS1 Executables", "SCUS*;SCES*;SLUS*;SLES*;SCPS*;SLPS*"),
            ("All Files", "*.*")
        ]
        title = "Choose PS1 Executable File"
    elif platform == "PS2":
        filetypes = [
            ("PS2 Executables", "SCUS*;SCES*;SLUS*;SLES*"),
            ("ELF Files", "*.elf"),
            ("All Files", "*.*")
        ]
        title = "Choose PS2 Executable File"
    elif platform in ["Gamecube", "Wii"]:
        filetypes = [
            ("DOL Files", "*.dol"),
            ("All Files", "*.*")
        ]
        title = f"Choose {platform} Executable File"
    elif platform == "N64":
        filetypes = [
            ("N64 ROMs", "*.n64;*.z64;*.v64"),
            ("All Files", "*.*")
        ]
        title = "Choose N64 ROM File"
    else:
        messagebox.showerror("Error", f"Platform {platform} not supported")
        return
    
    # Choose file
    file_path = filedialog.askopenfilename(
        title=title,
        filetypes=filetypes
    )
    
    if not file_path:
        return  # User cancelled
    
    import os
    filename = os.path.basename(file_path)
    file_dir = os.path.dirname(file_path)
    
    # Enable single file mode
    current_build.SetSingleFileMode(True)
    current_build.SetSingleFilePath(file_path)
    
    # Set as game folder (parent directory)
    current_build.SetGameFolder(file_dir)
    
    # Set as main executable
    current_build.SetMainExecutable(filename)
    current_build.AddInjectionFile(filename)
    
    # Auto-set file offset
    current_build.AutoSetFileOffsetForPlatform()
    
    # Update GUI
    from gui.gui_c_injection import CInjectionChangeGameFiles
    CInjectionChangeGameFiles(current_build.GetInjectionFiles())
    
    import dearpygui.dearpygui as dpg
    dpg.configure_item("game_files_listbox", items=(filename,))
    dpg.set_value("game_files_listbox", filename)
    
    # Update file offset display
    offset = current_build.GetInjectionFileOffset(filename)
    #dpg.set_value("File Offset From Ram Input", offset if offset else "")
    
    # Show modification tabs
    dpg.configure_item("Target Game Files", show=True)
    dpg.configure_item("Modifications", show=True)

    # Download box art
    from services.game_boxart_service import GameBoxartService
    from gui.gui_main_project import update_boxart_display
    if GameBoxartService.download_boxart(current_project_data):
        update_boxart_display(current_project_data)

    # Update build button label
    from gui.gui_build import update_build_button_label
    update_build_button_label(current_project_data)

    # Trigger auto-save
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    # Show success message
    messagebox.showinfo("Single File Build Version", 
        f"{filename} selected\n\n")
    
    # For PS1, still offer template if applicable
    if platform == "PS1":
        from services.template_service import show_ps1_template_prompt
        show_ps1_template_prompt(current_project_data)