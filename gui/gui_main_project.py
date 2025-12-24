# --- START OF FILE: gui/gui_main_project.py ---

import dearpygui.dearpygui as dpg
from dpg.widget_themes import *
from typing import Optional

from classes.project_data.project_data import *
from gui.gui_main_project_callbacks import *
from gui.gui_c_injection import *
from gui.gui_asm_injection import *
from gui.gui_binary_patch_injection import *
from gui.gui_game_files import *
from gui.gui_build import *
from gui.gui_themes import *
from services.project_serializer import ProjectSerializer
from services.auto_save_manager import AutoSaveManager
from gui.gui_text_editors import *
from gui.gui_hex_differ import show_visual_patcher_window
from gui.gui_game_files import _update_game_files_listbox
from dpg.listbox_rc_math import *
from gui.gui_assembly_viewer import show_assembly_viewer_window
from gui.gui_gdb_debugger import show_gdb_debugger_window
from gui.gui_codecave_finder import show_codecave_finder_window
from gui.gui_string_editor import show_string_editor_window
from gui.gui_emulator_tools import show_emulator_tools_window
from later_features.gui_c_debugger_launcher import show_c_debugger_window
from gui.gui_build import refresh_build_panel_ui
from functions.verbose_print import verbose_print
from services.emulator_connection_manager import get_emulator_manager

# Global auto-save manager
_auto_save_manager: Optional[AutoSaveManager] = None

def callback_modifications_tab_changed(sender, app_data, current_project_data: ProjectData):
    """
    When switching between C/ASM/Binary tabs, ensure the first entry
    in that tab is selected and its details are loaded (if nothing
    is selected yet).
    """
    current_build = current_project_data.GetCurrentBuildVersion()

    # Helper to auto-select first item if the details panel is empty
    def _auto_select_first(listbox_tag: str, detail_input_tag: str, names, select_callback):
        if not names:
            return
        if not dpg.does_item_exist(listbox_tag):
            return
        if not dpg.does_item_exist(detail_input_tag):
            return

        # Check if the detail name field is empty
        detail_value = dpg.get_value(detail_input_tag)
        if not detail_value or detail_value == "":
            # Details panel is empty, so select the first item
            first_name = names[0]
            dpg.set_value(listbox_tag, first_name)
            # Trigger the callback to load the details
            select_callback(listbox_tag, first_name, current_project_data)

    if app_data == "C & C++ Injection":
        from gui.gui_c_injection import callback_codecave_selected
        codecave_names = current_build.GetCodeCaveNames()
        _auto_select_first("codecaves_listbox", "codecave_name_detail_input", codecave_names, callback_codecave_selected)

    elif app_data == "hook_injection_tab":
        from gui.gui_asm_injection import callback_hook_selected
        hook_names = current_build.GetHookNames()
        _auto_select_first("hooks_listbox", "hook_name_detail_input", hook_names, callback_hook_selected)

    elif app_data == "binary_patch_injection_tab":
        from gui.gui_binary_patch_injection import callback_binary_patch_selected
        patch_names = current_build.GetBinaryPatchNames()
        _auto_select_first("binary_patches_listbox", "binary_patch_name_detail_input", patch_names, callback_binary_patch_selected)

def trigger_auto_save(immediate: bool = True):
    global _auto_save_manager
    if _auto_save_manager:
        _auto_save_manager.mark_dirty(immediate=immediate)

        # Update dashboard when project changes
        if hasattr(_auto_save_manager, 'project_data'):
            update_project_dashboard(_auto_save_manager.project_data)

        # Show brief feedback in UI
        if dpg.does_item_exist("Project Window"):
            try:
                current_title = dpg.get_item_label("Project Window")
                if not current_title.endswith("*"):
                    dpg.set_item_label("Project Window", current_title + " *")

                # Schedule title restore after save completes
                def restore_title():
                    import time
                    if immediate:
                        time.sleep(0.5)  # Quick restore for immediate saves
                    else:
                        time.sleep(1.0)  # Longer for debounced saves
                    if dpg.does_item_exist("Project Window"):
                        dpg.set_item_label("Project Window", current_title)

                import threading
                threading.Thread(target=restore_title, daemon=True).start()
            except:
                pass
            
_hotkey_manager = None

def get_hotkey_manager():
    """Get the current hotkey manager instance"""
    return _hotkey_manager

def reset_main_project_state():
    """Reset gui_main_project global state when project closes"""
    global _auto_save_manager, _hotkey_manager

    # Stop and clear auto-save manager (should already be done in close callback, but double-check)
    if _auto_save_manager:
        try:
            _auto_save_manager.stop()
        except:
            pass
        _auto_save_manager = None

    # Clear hotkey manager
    _hotkey_manager = None

# Init the main project window for a NEW project
def InitMainProjectWindow():
    """Initialize a NEW project window"""
    dpg.delete_item("Project Window")
    dpg.delete_item("startup_window")
    
    # Setup initial Project Data
    current_project_data = ProjectData()
    current_project_data.SetProjectName(name=dpg.get_value("gui_enter_project_name_tag"))
    current_project_data.SetDefaultNewProjectData()
    current_project_data.SetProjectFolder(current_project_data.GetProjectName())
    
    # Save the new project immediately
    ProjectSerializer.save_project(current_project_data)
    
    # Initialize the project window
    _init_project_window_ui(current_project_data)

    # Register emulator callbacks early so they receive scan events
    _init_emulator_callbacks(current_project_data)

    AddRelevantGameFileOptions(current_project_data)

def InitMainProjectWindowWithData(project_data: ProjectData):
    """Initialize project window with LOADED data"""
    
    from gui.gui_c_injection import reset_codecave_state, reset_hook_state, reset_binary_patch_state
    
    dpg.delete_item("Project Window")
    dpg.delete_item("startup_window")
    
    # Initialize the project window
    _init_project_window_ui(project_data)
    
    current_build = project_data.GetCurrentBuildVersion()
    
    # Update all listboxes with loaded data
    from gui.gui_asm_injection import UpdateHooksListbox
    from gui.gui_c_injection import UpdateCodecavesListbox
    from gui.gui_binary_patch_injection import UpdateBinaryPatchesListbox
    from gui.gui_game_files import _update_game_files_listbox
    
    UpdateHooksListbox(project_data)
    UpdateCodecavesListbox(project_data)
    UpdateBinaryPatchesListbox(project_data)
    _update_game_files_listbox(project_data)
    
    # Update game files in combo dropdowns
    if current_build.GetInjectionFiles():
        from gui.gui_c_injection import CInjectionChangeGameFiles
        from gui.gui_asm_injection import HookInjectionChangeGameFiles  
        from gui.gui_binary_patch_injection import BinaryPatchInjectionChangeGameFiles
        
        CInjectionChangeGameFiles(current_build.GetInjectionFiles())
        HookInjectionChangeGameFiles(current_build.GetInjectionFiles())
        BinaryPatchInjectionChangeGameFiles(current_build.GetInjectionFiles())
    
    # Verify multi-patches loaded
    multipatches = current_build.GetMultiPatches()
    if multipatches:
        print(f"Loaded {len(multipatches)} multi-patch(es):")
        for mp in multipatches:
            print(f"    • {mp.GetName()} → {mp.GetFilePath()}")
    
    #print(f"Project window initialized: {project_data.GetProjectName()}")

    # Auto-select first item in each tab if items exist
    from gui.gui_c_injection import callback_codecave_selected
    from gui.gui_asm_injection import callback_hook_selected
    from gui.gui_binary_patch_injection import callback_binary_patch_selected

    codecave_names = current_build.GetCodeCaveNames()
    if codecave_names:
        first_codecave = codecave_names[0]
        dpg.set_value("codecaves_listbox", first_codecave)
        callback_codecave_selected("codecaves_listbox", first_codecave, project_data)

    hook_names = current_build.GetHookNames()
    if hook_names:
        first_hook = hook_names[0]
        dpg.set_value("hooks_listbox", first_hook)
        callback_hook_selected("hooks_listbox", first_hook, project_data)

    patch_names = current_build.GetBinaryPatchNames()
    if patch_names:
        first_patch = patch_names[0]
        dpg.set_value("binary_patches_listbox", first_patch)
        callback_binary_patch_selected("binary_patches_listbox", first_patch, project_data)

    # Register emulator callbacks early so they receive scan events
    _init_emulator_callbacks(project_data)


def _init_emulator_callbacks(project_data: ProjectData):
    """Register emulator scan callbacks early so all windows receive scan events"""
    manager = get_emulator_manager()
    manager.set_project_data(project_data)

    # Import and register callbacks from GUI modules
    from gui.gui_emulator_tools import _on_emulators_scanned_callback as emu_tools_callback
    from gui.gui_memory_watch import register_memory_watch_callback

    # Register both callbacks
    manager.register_scan_callback(emu_tools_callback)
    register_memory_watch_callback(manager)

    #print(f"[ProjectInit] Registered emulator callbacks (total: {len(manager.on_emulators_scanned)})")


def _load_boxart_texture(current_project_data: ProjectData):
    """Load box art texture if it exists"""
    from services.game_boxart_service import GameBoxartService

    boxart_path = GameBoxartService.get_boxart_path(current_project_data)
    if os.path.exists(boxart_path):
        try:
            # Load the image
            width, height, _channels, data = dpg.load_image(boxart_path)

            # Create texture registry if it doesn't exist
            if not dpg.does_item_exist("texture_registry"):
                with dpg.texture_registry(tag="texture_registry"):
                    pass

            # Remove old texture if it exists
            if dpg.does_item_exist("game_boxart_texture"):
                dpg.delete_item("game_boxart_texture")

            # Add texture
            with dpg.texture_registry():
                dpg.add_static_texture(width=width, height=height, default_value=data, tag="game_boxart_texture")

            return True
        except Exception as e:
            print(f"Failed to load box art texture: {e}")
            return False
    return False

def update_boxart_display(current_project_data: ProjectData):
    """Update the box art display in the GUI after downloading"""
    from services.game_boxart_service import GameBoxartService

    # Try to load the texture
    if _load_boxart_texture(current_project_data):
        # Remove the "No box art" text if it exists
        if dpg.does_item_exist("boxart_container"):
            # Clear existing children
            children = dpg.get_item_children("boxart_container", slot=1)
            if children:
                for child in children:
                    dpg.delete_item(child)

            # Add the image
            if dpg.does_item_exist("game_boxart_texture"):
                dpg.add_image("game_boxart_texture", width=180, height=180, tag="game_boxart_image", parent="boxart_container")
                print(" Box art display updated")

def update_project_dashboard(current_project_data: ProjectData):
    """Update the project dashboard with current statistics"""
    from services.project_dashboard_service import ProjectDashboardService

    # Get current stats
    stats = ProjectDashboardService.get_project_stats(current_project_data)

    # Build dashboard display
    lines = []

    # Row 1: Platform and Build info
    lines.append(f"Platform: {stats['platform']}  |  Build: {stats['current_build']}  ({stats['build_count']} total)")

    # Row 2: Modifications summary
    mod_parts = []
    if stats['codecaves'] > 0:
        mod_parts.append(f"{stats['codecaves']} Codecave{'s' if stats['codecaves'] != 1 else ''}")
    if stats['hooks'] > 0:
        mod_parts.append(f"{stats['hooks']} Hook{'s' if stats['hooks'] != 1 else ''}")
    if stats['patches'] > 0:
        mod_parts.append(f"{stats['patches']} Patch{'es' if stats['patches'] != 1 else ''}")
    if stats['multipatches'] > 0:
        mod_parts.append(f"{stats['multipatches']} Multi-Patch{'es' if stats['multipatches'] != 1 else ''}")

    if mod_parts:
        lines.append(f"Modifications: {', '.join(mod_parts)}  ({stats['total_modifications']} total)")
    else:
        lines.append("Modifications: None")

    # Row 3: Lines of code
    if stats['total_lines'] > 0:
        lines.append(f"Lines of Code: {stats['total_lines']}")

    # Row 4: Resources (Main Exe, Symbols, Size)
    extra_parts = []

    # Main executable first
    if stats['main_executable'] != "Not set":
        extra_parts.append(f"Main EXE: {stats['main_executable']}")

    # Symbols second
    if stats['symbols_count'] > 0:
        extra_parts.append(f"{stats['symbols_count']} Symbol{'s' if stats['symbols_count'] != 1 else ''}")

    # Size last
    if stats['total_code_size'] > 0:
        if stats['total_code_size_kb'] < 1:
            extra_parts.append(f"Size: {stats['total_code_size']} bytes")
        else:
            extra_parts.append(f"Size: {stats['total_code_size_kb']:.2f} KB")

    if extra_parts:
        lines.append(f"{', '.join(extra_parts)}")

    # Update both dashboard text widgets
    dashboard_text = "\n".join(lines)
    if dpg.does_item_exist("dashboard_text_basic"):
        dpg.set_value("dashboard_text_basic", dashboard_text)
    if dpg.does_item_exist("dashboard_text_build"):
        dpg.set_value("dashboard_text_build", dashboard_text)

def _init_project_window_ui(current_project_data: ProjectData):
    """Internal function to create the project window UI"""
    from gui.gui_memory_watch import show_memory_watch_window
    from services.project_dashboard_service import ProjectDashboardService
    global _auto_save_manager

    # Start auto-save
    _auto_save_manager = AutoSaveManager(current_project_data)
    _auto_save_manager.start()

    # Load box art texture
    has_boxart = _load_boxart_texture(current_project_data)

    with dpg.window(label="Project Window", tag="Project Window", no_move=True, no_resize=True, no_collapse=True, menubar=False) as main_project_window:
        dpg.set_primary_window("Project Window", True)
        
        global _hotkey_manager
        from gui.gui_hotkeys import setup_hotkeys_for_project
        _hotkey_manager = setup_hotkeys_for_project(current_project_data)
        
        with dpg.menu_bar():
            with dpg.menu(label="File"):
                dpg.add_menu_item(label="Save Project", callback=callback_save_project, user_data=current_project_data)
                dpg.add_menu_item(label="Open Project", callback=callback_load_different_project, user_data=current_project_data)
                dpg.add_menu_item(label="Close Project", callback=callback_close_project, user_data=current_project_data)
            with dpg.menu(label="Edit"):
                dpg.add_menu_item(label="Rename Project", callback=callback_rename_project, user_data=current_project_data)
                dpg.add_menu_item(label="Clean Build", callback=callback_clean_build, user_data=current_project_data)
            with dpg.menu(label="Tools"):
                dpg.add_menu_item(
                    label="Assembly Viewer",
                    callback=lambda: show_assembly_viewer_window(None, None, current_project_data)
                )
                dpg.add_menu_item(
                    label="Hex Differ",
                    callback=lambda: show_visual_patcher_window(None, None, current_project_data)
                )
                dpg.add_menu_item(
                    label="Codecave Finder",
                    callback=lambda: show_codecave_finder_window(None, None, current_project_data)
                )
                # WIP
                # dpg.add_menu_item(
                #     label="String Search & Editor",
                #     callback=lambda: show_string_editor_window(None, None, current_project_data)
                # )
                # WIP
                dpg.add_menu_item(
                    label="Verification Tools",
                    callback=lambda: show_emulator_tools_window(None, None, current_project_data)
                )
                dpg.add_menu_item(
                    label="Memory Watch",
                    callback=lambda: show_memory_watch_window(current_project_data)
                )
                # Probably not needed
                # dpg.add_menu_item(
                #     label="Connect to GDB Server",
                #     callback=lambda: show_gdb_debugger_window(None, None, current_project_data)
                # )
            with dpg.menu(label="Text Editors"):
                dpg.add_menu_item(label="Open in VSCode", callback=callback_open_vscode, user_data=current_project_data)
                dpg.add_menu_item(label="Open in Zed", callback=callback_open_zed, user_data=current_project_data)
                dpg.add_menu_item(label="Open in Sublime Text", callback=callback_open_sublime, user_data=current_project_data)
                dpg.add_menu_item(label="Open in Notepad++", callback=callback_open_notepadpp, user_data=current_project_data)
            # with dpg.menu(label="Themes"):
            #     dpg.add_menu_item(label="Theme Editor", callback=show_theme_customization_window, user_data=current_project_data)
            
        with dpg.tab_bar(tag="main_tab_bar"):
            #! Basic Tab
            with dpg.tab(label="Basic Settings", tag="Basic Settings"):
                # Box art and project info in horizontal group
                with dpg.group(horizontal=True):
                    # Left side: Box art
                    with dpg.child_window(width=190, height=190, border=False, tag="boxart_container"):
                        if has_boxart and dpg.does_item_exist("game_boxart_texture"):
                            dpg.add_image("game_boxart_texture", width=180, height=180, tag="game_boxart_image")
                        else:
                            dpg.add_text("No box art", tag="no_boxart_text", color=(128, 128, 128))
                            dpg.add_spacer(height=10)
                            dpg.add_text("(Will download when\ngame is extracted)", wrap=180, color=(100, 100, 100))

                    # Right side: Project info and build versions
                    with dpg.group():
                        dpg.add_text("Project: " + current_project_data.GetProjectName())
                        dpg.add_separator()
                        dpg.add_text("Build Versions:")

                        # Build version listbox - show all build versions
                        build_version_names = [bv.GetBuildName() for bv in current_project_data.build_versions]
                        current_build_name = current_project_data.GetCurrentBuildVersion().GetBuildName()

                        dpg.add_listbox(
                            items=build_version_names,
                            label="Select Build Version",
                            default_value=current_build_name,
                            num_items=5,
                            callback=callback_switch_project_build_version,
                            user_data=current_project_data,
                            tag="build_version_listbox"
                        )

                        # Buttons for managing build versions
                        with dpg.group(horizontal=True):
                            dpg.add_button(
                                label="Add New Build Version",
                                tag="Add Build Version",
                                callback=callback_add_project_build_version,
                                user_data=current_project_data
                            )
                            dpg.add_button(
                                label="Duplicate Selected Build Version",
                                tag="Duplicate Selected Build Version",
                                callback=callback_duplicate_build_version,
                                user_data=current_project_data
                            )
                            dpg.add_button(
                                label="Rename Build Version",
                                callback=callback_rename_build_version,
                                user_data=current_project_data
                            )
                            dpg.add_button(
                                label="Delete Build Version",
                                callback=callback_delete_build_version,
                                user_data=current_project_data
                            )

                dpg.add_separator()
                for _ in range(2):
                    dpg.add_spacer()

                dpg.add_text(f"Editing: {current_project_data.GetCurrentBuildVersionName()}", tag="current_build_label")
                
                # Platform selector
                current_platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
                default_platform = current_platform if current_platform else "Choose a Platform"
                
                dpg.add_combo(
                    ("PS1", "PS2", "Gamecube", "Wii", "N64"),
                    label="Platform",
                    default_value=default_platform,
                    callback=callback_platform_combobox,
                    user_data=current_project_data,
                    tag="platform_combo"
                )

                dpg.add_separator()

            #! Files To Inject Into Tab
            with dpg.tab(label="Game Files To Inject Into", tag="Game Files To Inject Into", show=False):
                CreateGameFilesGui(current_project_data)

            #! Modifications
            with dpg.tab(label="Modifications", tag="Modifications", show=False):
                with dpg.tab_bar(
                tag="modifications_tab_bar",
                user_data=current_project_data,
                callback=callback_modifications_tab_changed
            ):
                    CreateCInjectionGui(current_project_data)
                    CreateASMInjectionGui(current_project_data)
                    CreateBinaryFileInjectionGui(current_project_data)
                    SelectFirstModificationsInGui(current_project_data)

            with dpg.tab(label="Build Project", tag="Build", show=True):
                CreateCompileAndBuildGui(current_project_data)

                # Project Dashboard in Build tab
                dpg.add_separator()
                dpg.add_text("Project Dashboard", color=(180, 180, 180))
                dpg.add_text("Loading project statistics...", tag="dashboard_text_build", wrap=0, color=(200, 200, 200))

    # Update dashboard with initial stats
    update_project_dashboard(current_project_data)

    # IMPORTANT: After UI is created, restore the state based on loaded data
    _restore_project_state(current_project_data)
    current_build = current_project_data.GetCurrentBuildVersion()
    if current_build.GetPlatform() and not current_build.GetGameFolder():
        # New project with platform but no game folder set yet
        AddRelevantGameFileOptions(current_project_data)
    
def SelectFirstModificationsInGui(current_project_data: ProjectData):
    """
    Ensure each of the three modification types has a selected item
    (if there is at least one), and load its details.
    """
    from gui.gui_c_injection import UpdateCodecavesListbox, callback_codecave_selected
    from gui.gui_asm_injection import UpdateHooksListbox, callback_hook_selected
    from gui.gui_binary_patch_injection import UpdateBinaryPatchesListbox, callback_binary_patch_selected

    current_build = current_project_data.GetCurrentBuildVersion()

    def _auto_select_first(listbox_tag: str, names, select_callback):
        if not names:
            return
        if not dpg.does_item_exist(listbox_tag):
            return
        current_value = dpg.get_value(listbox_tag)
        if current_value:
            return
        first_name = names[0]
        dpg.set_value(listbox_tag, first_name)
        select_callback(listbox_tag, first_name, current_project_data)

    # C / C++ codecaves
    UpdateCodecavesListbox(current_project_data)
    codecave_names = current_build.GetCodeCaveNames()
    _auto_select_first("codecaves_listbox", codecave_names, callback_codecave_selected)

    # ASM / Hook injection
    UpdateHooksListbox(current_project_data)
    hook_names = current_build.GetHookNames()
    _auto_select_first("hooks_listbox", hook_names, callback_hook_selected)

    # Binary patches
    UpdateBinaryPatchesListbox(current_project_data)
    patch_names = current_build.GetBinaryPatchNames()
    _auto_select_first("binary_patches_listbox", patch_names, callback_binary_patch_selected)


def _restore_project_state(current_project_data: ProjectData):
    """Restore GUI state after loading a project"""
    current_build = current_project_data.GetCurrentBuildVersion()
    
    # Update build version listbox
    from gui.gui_main_project_callbacks import update_build_version_listbox
    update_build_version_listbox(current_project_data)
    
    # If platform is set, show the appropriate options and tabs
    if current_build.GetPlatform() and current_build.GetPlatform() != "Choose a Platform":
        verbose_print(f"Restoring project state for platform: {current_build.GetPlatform()}")
        
        # Add the platform-specific buttons
        AddRelevantGameFileOptions(current_project_data)
        
        # If game folder is set, show the tabs
        if current_build.GetGameFolder():
            dpg.configure_item("Game Files To Inject Into", show=True)
            dpg.configure_item("Modifications", show=True)
            
            # FIX: Restore game files listbox with formatted items
            if current_build.GetInjectionFiles():
                CInjectionChangeGameFiles(current_build.GetInjectionFiles())
                
                # Import the formatting function from gui_game_files
                from gui.gui_game_files import _get_formatted_file_list
                
                # Use formatted list for display
                formatted_items = _get_formatted_file_list(current_project_data)
                dpg.configure_item("game_files_listbox", items=formatted_items)
                
                # If there's a main executable, select it (also formatted)
                if current_build.GetMainExecutable():
                    main_exe = current_build.GetMainExecutable()
                    # Find the formatted version of the main exe
                    for formatted_item in formatted_items:
                        if main_exe in formatted_item and "(Main)" in formatted_item:
                            dpg.set_value("game_files_listbox", formatted_item)
                            break
        
        # Restore codecaves listbox
        codecave_names = current_build.GetCodeCaveNames()
        if codecave_names:
            dpg.configure_item("codecaves_listbox", items=codecave_names)
        
        # Restore hooks listbox
        hook_names = current_build.GetHookNames()
        if hook_names:
            dpg.configure_item("hooks_listbox", items=hook_names)
        
        # Restore binary patches listbox
        patch_names = current_build.GetBinaryPatchNames()
        if patch_names:
            dpg.configure_item("binary_patches_listbox", items=patch_names)
            
        from gui.gui_build import update_build_button_label
        update_build_button_label(current_project_data)
        
        refresh_build_panel_ui(current_project_data)
        
        #print("Project state restored")
            
        
def callback_platform_combobox(sender, combo_box_data, current_project_data: ProjectData):
    current_project_data.GetCurrentBuildVersion().SetPlatform(combo_box_data)
    if hasattr(current_project_data, "platform"):
        if current_project_data.platform == "PS2":
            current_project_data.compiler_flags = "-O2 -fsingle-precision-constant"  # Default flags for PS2. Always use floats if PS2. Might need to change, because unsure if double support is needed, but
                                                                                     # The problem is it tries to link to libraries like fptodp, dpadd, dptofp, etc.
    refresh_build_panel_ui(current_project_data)
    update_build_button_label(current_project_data)
    
    print(f"Current Platform for {current_project_data.GetCurrentBuildVersion().GetBuildName()} is: {current_project_data.GetCurrentBuildVersion().GetPlatform()}")
    AddRelevantGameFileOptions(current_project_data)
    
    # Update PS1 codecave button visibility
    from gui.gui_c_injection import update_ps1_codecave_button_visibility
    update_ps1_codecave_button_visibility(current_project_data)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    

            
def RemoveAllGameFileOptions():
    items_to_remove = [
        "Choose ISO File to Extract",
        "Choose PS1 Bin FIle to Extract",
        "Choose Extracted ISO Folder",
        "Choose Extracted PS1 Bin Folder",
        "Choose .n64 Rom File",
        "Extract GameCube ISO Button",
        "Choose GameCube Extracted Folder",
        "Choose Single GameCube File",
        "Extract Wii ISO Button",
        "Choose Wii Extracted Folder",
        "Choose Single Wii File",
        "Choose Single PS2 File",
        "Choose Single PS1 File",
        "Choose Single N64 File",
        "symbols_separator",
        "symbols_label",
        "symbols_file_combo",
        "symbols_hint_text",
        "single_file_mode_text",
        "dashboard_separator_basic",
        "dashboard_title_basic",
        "dashboard_text_basic"
    ]

    for item in items_to_remove:
        if dpg.does_item_exist(item):
            dpg.delete_item(item)
    
def AddRelevantGameFileOptions(current_project_data: ProjectData):
    RemoveAllGameFileOptions()

    current_project_build = current_project_data.GetCurrentBuildVersion()

    # If in single file mode, don't show any file extraction/selection options
    if current_project_build.IsSingleFileMode():
        dpg.add_text(
            "Single File Mode - File already selected",
            tag="single_file_mode_text",
            parent="Basic Settings",
            color=(100, 150, 255)
        )
        return

    if current_project_build.IsPlatformPS2():
        dpg.add_button(
            label="Choose PS2 ISO", 
            tag="Choose ISO File to Extract", 
            parent="Basic Settings",
            callback=callback_extract_ps2_iso,
            user_data=current_project_data
        )
        dpg.add_button(
            label="Choose Extracted ISO Folder", 
            tag="Choose Extracted ISO Folder", 
            parent="Basic Settings", 
            callback=callback_choose_ps2_iso_folder, 
            user_data=current_project_data
        )
        # NEW: Single file button
        dpg.add_button(
            label="Choose Single Game File (No ISO)", 
            tag="Choose Single PS2 File", 
            parent="Basic Settings", 
            callback=callback_choose_single_file, 
            user_data=current_project_data
        )
        
    elif current_project_build.IsPlatformGameCube():
        dpg.add_button(
            label="Choose GameCube ISO", 
            tag="Extract GameCube ISO Button",
            parent="Basic Settings",
            callback=callback_extract_gamecube_iso,
            user_data=current_project_data
        )
        dpg.add_button(
            label="Choose Extracted ISO Folder", 
            tag="Choose GameCube Extracted Folder",
            parent="Basic Settings", 
            callback=callback_choose_gamecube_iso_folder,
            user_data=current_project_data
        )
        # NEW: Single file button
        dpg.add_button(
            label="Choose Single Game File (No ISO)", 
            tag="Choose Single GameCube File", 
            parent="Basic Settings", 
            callback=callback_choose_single_file, 
            user_data=current_project_data
        )
        
    elif current_project_build.IsPlatformPS1():
        dpg.add_button(
            label="Choose PS1 BIN",
            tag="Choose PS1 Bin FIle to Extract",
            parent="Basic Settings",
            callback=callback_extract_ps1_bin,
            user_data=current_project_data
        )
        # Add tooltip for multi-bin games
        with dpg.tooltip("Choose PS1 Bin FIle to Extract"):
            dpg.add_text("For multi-bin PS1 games, select the .cue file.\nThe tool will automatically merge the bins for you.")
        # Extract bin can't work for ps1 because we need the original XML structure 
        # dpg.add_button(
        #     label="Choose Extracted BIN Folder", 
        #     tag="Choose Extracted PS1 Bin Folder", 
        #     parent="Basic Settings", 
        #     callback=callback_choose_ps1_iso_folder, 
        #     user_data=current_project_data
        # )
        # NEW: Single file button
        dpg.add_button(
            label="Choose Single Game File (No ISO)", 
            tag="Choose Single PS1 File", 
            parent="Basic Settings", 
            callback=callback_choose_single_file, 
            user_data=current_project_data
        )
        
    elif current_project_build.IsPlatformWii():
        dpg.add_button(
            label="Choose Wii ISO", 
            tag="Extract Wii ISO Button",
            parent="Basic Settings",
            callback=callback_extract_wii_iso,
            user_data=current_project_data
        )
        dpg.add_button(
            label="Choose Extracted ISO Folder", 
            tag="Choose Wii Extracted Folder",
            parent="Basic Settings",
            callback=callback_choose_gamecube_iso_folder,
            user_data=current_project_data
        )
        # NEW: Single file button
        dpg.add_button(
            label="Choose Single Game File (No ISO)", 
            tag="Choose Single Wii File", 
            parent="Basic Settings", 
            callback=callback_choose_single_file, 
            user_data=current_project_data
        )
        
    elif current_project_build.IsPlatformN64():
        # NEW: Single file button (N64 is already single-file by default, but for consistency)
        dpg.add_button(
            label="Choose N64 ROM File", 
            tag="Choose Single N64 File", 
            parent="Basic Settings", 
            callback=callback_choose_single_file, 
            user_data=current_project_data
        )

    # Add Symbols Drop Down
    dpg.add_separator(parent="Basic Settings", tag="symbols_separator")
    dpg.add_text(
        "Symbols File for Current Build:",
        parent="Basic Settings",
        tag="symbols_label"
    )
    
    symbols_dir = os.path.join(current_project_data.GetProjectFolder(), "symbols")
    symbols_files = []
    if os.path.exists(symbols_dir):
        symbols_files = [f for f in os.listdir(symbols_dir) if f.endswith('.txt')]

    current_symbols = current_project_data.GetCurrentBuildVersion().GetSymbolsFile()

    dpg.add_combo(
        items=symbols_files if symbols_files else [current_symbols],
        default_value=current_symbols,
        label="Symbols File",
        callback=callback_symbols_file_changed,
        user_data=current_project_data,
        tag="symbols_file_combo",
        parent="Basic Settings",  # ADD THIS
        width=300
    )

    # Project Dashboard at the very bottom of Basic Settings
    dpg.add_separator(parent="Basic Settings", tag="dashboard_separator_basic")
    dpg.add_text("Project Dashboard", color=(180, 180, 180), parent="Basic Settings", tag="dashboard_title_basic")
    dpg.add_text("Loading project statistics...", tag="dashboard_text_basic", wrap=0, color=(200, 200, 200), parent="Basic Settings")

    # Update dashboard immediately after creation
    update_project_dashboard(current_project_data)

def callback_symbols_file_changed(sender, app_data, current_project_data: ProjectData):
    """Handle symbols file selection change"""
    selected_file = app_data
    current_project_data.GetCurrentBuildVersion().SetSymbolsFile(selected_file)
    
    print(f"Build '{current_project_data.GetCurrentBuildVersionName()}' now uses symbols file: {selected_file}")
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()