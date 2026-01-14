import dearpygui.dearpygui as dpg
import os
from dpg.widget_themes import *
from typing import Optional

from classes.project_data.project_data import *
from gui.gui_main_project_callbacks import *
from gui.gui_c_injection import *
from gui.gui_asm_injection import *
from gui.gui_binary_patch_injection import *
from gui.gui_game_files import *
from gui.gui_build import *
# from gui.gui_themes import *
from services.project_serializer import ProjectSerializer
from services.auto_save_manager import AutoSaveManager
from gui.gui_text_editors import *
from gui.gui_hex_differ import show_visual_patcher_window
from gui.gui_game_files import _update_game_files_listbox
from dpg.listbox_rc_math import *
from gui.gui_assembly_viewer import show_assembly_viewer_window
from later_features.gui_gdb_debugger import show_gdb_debugger_window
from gui.gui_codecave_finder import show_codecave_finder_window
from gui.gui_emulator_tools import show_emulator_tools_window
from gui.gui_help import *
from later_features.gui_c_debugger_launcher import show_c_debugger_window
from gui.gui_build import refresh_build_panel_ui
from gui.gui_prereq_prompt import check_and_prompt_prereqs
from functions.verbose_print import verbose_print
from services.emulator_connection_manager import get_emulator_manager
from path_helper import get_application_directory

# Global save manager
_auto_save_manager: Optional[AutoSaveManager] = None

def callback_modifications_tab_changed(sender, app_data, current_project_data: ProjectData):
    current_build = current_project_data.GetCurrentBuildVersion()

    def _auto_select_first(listbox_tag: str, detail_input_tag: str, names, select_callback):
        if not names:
            return
        if not dpg.does_item_exist(listbox_tag):
            return
        if not dpg.does_item_exist(detail_input_tag):
            return

        detail_value = dpg.get_value(detail_input_tag)
        if not detail_value or detail_value == "":
            # Select the first item
            first_name = names[0]
            dpg.set_value(listbox_tag, first_name)
            # Load the details
            select_callback(listbox_tag, first_name, current_project_data)

    if app_data == "code_injection_tab":
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

        if dpg.does_item_exist("Project Window"):
            try:
                current_title = dpg.get_item_label("Project Window")
                if not current_title.endswith("*"):
                    dpg.set_item_label("Project Window", current_title + " *")


                def restore_title():
                    import time
                    if immediate:
                        time.sleep(0.5)
                    else:
                        time.sleep(1.0)
                    if dpg.does_item_exist("Project Window"):
                        dpg.set_item_label("Project Window", current_title)

                import threading
                threading.Thread(target=restore_title, daemon=True).start()
            except:
                pass
            
_hotkey_manager = None

def get_hotkey_manager():
    return _hotkey_manager

def reset_main_project_state():
    global _auto_save_manager, _hotkey_manager

    # Clear auto-save manager (should already be done but might as well double check)
    if _auto_save_manager:
        try:
            _auto_save_manager.stop()
        except:
            pass
        _auto_save_manager = None

    # Clear hotkey manager
    _hotkey_manager = None

# Init the main project window
def InitMainProjectWindow():
    dpg.delete_item("Project Window")
    dpg.delete_item("startup_window")
    
    # Setup initial Project Data
    current_project_data = ProjectData()
    current_project_data.SetProjectName(name=dpg.get_value("gui_enter_project_name_tag"))
    current_project_data.SetDefaultNewProjectData()
    current_project_data.SetProjectFolder(current_project_data.GetProjectName())
    
    ProjectSerializer.save_project(current_project_data)
    
    # Init the window
    _init_project_window_ui(current_project_data)

    # Register emulator callbacks
    _init_emulator_callbacks(current_project_data)

    AddRelevantGameFileOptions(current_project_data)

def InitMainProjectWindowWithData(project_data: ProjectData):
    
    from gui.gui_c_injection import reset_codecave_state, reset_hook_state, reset_binary_patch_state
    
    reset_codecave_state()
    reset_hook_state()
    reset_binary_patch_state()
    
    # Delete all pop up windows. (I spent so long trying to figure out where some persisting old project data was coming from, and it was some windows not being deleted.)
    # Add to this list if more windows that rely on project data get added to the util
    window_tags = [
        "add_hook_modal",
        "rename_hook_modal",
        "pattern_selection_modal",
        "add_codecave_modal",
        "rename_codecave_modal",
        "add_binary_patch_modal",
        "rename_binary_patch_modal",
        "add_build_version_modal",
        "rename_build_version_modal",
        "rename_project_modal",
        "assembly_viewer_window",
        "visual_patcher_window",
        "codecave_finder_window",
        "emulator_tools_window"
    ]
    for tag in window_tags:
        if dpg.does_item_exist(tag):
            try:
                dpg.delete_item(tag)
            except:
                print("Error deleting a window on project switch")
    
    dpg.delete_item("Project Window")
    dpg.delete_item("startup_window")
    dpg.split_frame()
    
    # Init window
    _init_project_window_ui(project_data)
    
    current_build = project_data.GetCurrentBuildVersion()
    
    # Update listboxes
    from gui.gui_asm_injection import UpdateHooksListbox
    from gui.gui_c_injection import UpdateCodecavesListbox
    from gui.gui_binary_patch_injection import UpdateBinaryPatchesListbox
    from gui.gui_game_files import _update_game_files_listbox
    
    UpdateHooksListbox(project_data)
    UpdateCodecavesListbox(project_data)
    UpdateBinaryPatchesListbox(project_data)
    _update_game_files_listbox(project_data)
    
    # Update game files in dropdowns
    if current_build.GetInjectionFiles():
        from gui.gui_c_injection import CInjectionChangeGameFiles
        from gui.gui_asm_injection import HookInjectionChangeGameFiles  
        from gui.gui_binary_patch_injection import BinaryPatchInjectionChangeGameFiles
        
        CInjectionChangeGameFiles(current_build.GetInjectionFiles())
        HookInjectionChangeGameFiles(current_build.GetInjectionFiles())
        BinaryPatchInjectionChangeGameFiles(current_build.GetInjectionFiles())
    
    # Verify multi-patches
    multipatches = current_build.GetMultiPatches()
    if multipatches:
        print(f"Loaded {len(multipatches)} multi-patch(es):")
        for mp in multipatches:
            print(f"    - {mp.GetName()} -> {mp.GetFilePath()}")
    
    #print(f"Project window initialized: {project_data.GetProjectName()}")

    # Auto-select first item in each tab
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

    # Register emulator callbacks
    _init_emulator_callbacks(project_data)


def _init_emulator_callbacks(project_data: ProjectData):
    manager = get_emulator_manager()
    manager.set_project_data(project_data)

    from gui.gui_emulator_tools import _on_emulators_scanned_callback as emu_tools_callback
    from gui.gui_memory_watch import register_memory_watch_callback

    manager.register_scan_callback(emu_tools_callback)
    register_memory_watch_callback(manager)


def _load_boxart_texture(current_project_data: ProjectData):
    from services.game_boxart_service import GameBoxartService

    boxart_path = GameBoxartService.get_boxart_path(current_project_data)
    if os.path.exists(boxart_path):
        try:
            # Load the image
            width, height, _channels, data = dpg.load_image(boxart_path)

            if not dpg.does_item_exist("texture_registry"):
                with dpg.texture_registry(tag="texture_registry"):
                    pass

            # Remove old image if it exists
            if dpg.does_item_exist("game_boxart_texture"):
                dpg.delete_item("game_boxart_texture")

            # Add image
            with dpg.texture_registry():
                dpg.add_static_texture(width=width, height=height, default_value=data, tag="game_boxart_texture")

            return True
        except Exception as e:
            print(f"Failed to load box art texture: {e}")
            return False
    return False

def update_boxart_display(current_project_data: ProjectData):
    from services.game_boxart_service import GameBoxartService

    if _load_boxart_texture(current_project_data):
        # Remove the default text
        if dpg.does_item_exist("boxart_container"):
            children = dpg.get_item_children("boxart_container", slot=1)
            if children:
                for child in children:
                    dpg.delete_item(child)

            # Add image
            if dpg.does_item_exist("game_boxart_texture"):
                dpg.add_image("game_boxart_texture", width=180, height=180, tag="game_boxart_image", parent="boxart_container")
                print(" Box art display updated")

def update_project_dashboard(current_project_data: ProjectData):
    from services.project_dashboard_service import ProjectDashboardService

    stats = ProjectDashboardService.get_project_stats(current_project_data)
    
    lines = []

    # Platform and Build info
    lines.append(f"Platform: {stats['platform']}  |  Build: {stats['current_build']}  ({stats['build_count']} total)")

    # Modifications summary
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

    # Lines of code
    if stats['total_lines'] > 0:
        lines.append(f"Lines of Code: {stats['total_lines']}")

    # Resources
    extra_parts = []

    # Main executable
    if stats['main_executable'] != "Not set":
        extra_parts.append(f"Main EXE: {stats['main_executable']}")

    # Symbols
    if stats['symbols_count'] > 0:
        extra_parts.append(f"{stats['symbols_count']} Symbol{'s' if stats['symbols_count'] != 1 else ''}")

    # Size
    if stats['total_code_size'] > 0:
        if stats['total_code_size_kb'] < 1:
            extra_parts.append(f"Size: {stats['total_code_size']} bytes")
        else:
            extra_parts.append(f"Size: {stats['total_code_size_kb']:.2f} KB")

    if extra_parts:
        lines.append(f"{', '.join(extra_parts)}")


    dashboard_text = "\n".join(lines)
    if dpg.does_item_exist("dashboard_text_basic"):
        dpg.set_value("dashboard_text_basic", dashboard_text)
    if dpg.does_item_exist("dashboard_text_build"):
        dpg.set_value("dashboard_text_build", dashboard_text)

def _init_project_window_ui(current_project_data: ProjectData):
    from gui.gui_memory_watch import show_memory_watch_window
    from services.project_dashboard_service import ProjectDashboardService
    global _auto_save_manager

    _auto_save_manager = AutoSaveManager(current_project_data)
    _auto_save_manager.start()

    # Load box art
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
                    label="Runtime Verification",
                    callback=lambda: show_emulator_tools_window(None, None, current_project_data)
                )
                dpg.add_menu_item(
                    label="Memory Watch",
                    callback=lambda: show_memory_watch_window(current_project_data)
                )
            with dpg.menu(label="Text Editors"):
                dpg.add_menu_item(label="Open in VSCode", callback=callback_open_vscode, user_data=current_project_data)
                dpg.add_menu_item(label="Open in Zed", callback=callback_open_zed, user_data=current_project_data)
                dpg.add_menu_item(label="Open in Sublime Text", callback=callback_open_sublime, user_data=current_project_data)
                dpg.add_menu_item(label="Open in Notepad++", callback=callback_open_notepadpp, user_data=current_project_data)
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="View Wiki", callback=callback_open_wiki)
                dpg.add_menu_item(label="About", callback=callback_open_about)
            # with dpg.menu(label="Themes"):
            #     dpg.add_menu_item(label="Theme Editor", callback=show_theme_customization_window, user_data=current_project_data)
            
        with dpg.tab_bar(tag="main_tab_bar"):
            #! Basic Tab
            with dpg.tab(label="Basic Settings", tag="Basic Settings"):
                # Box art and project inf
                with dpg.group(horizontal=True):
                    # Box art
                    with dpg.child_window(width=190, height=190, border=False, tag="boxart_container"):
                        if has_boxart and dpg.does_item_exist("game_boxart_texture"):
                            dpg.add_image("game_boxart_texture", width=180, height=180, tag="game_boxart_image")
                        else:
                            dpg.add_text("No box art", tag="no_boxart_text", color=(128, 128, 128))
                            dpg.add_spacer(height=10)
                            dpg.add_text("(Will download when\ngame is extracted)", wrap=180, color=(100, 100, 100))

                    # Project info and build versions
                    with dpg.group():
                        dpg.add_text("Project: " + current_project_data.GetProjectName())
                        dpg.add_separator()
                        dpg.add_text("Build Versions:")

                        # Build version listbox
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
                
                # Platform selection
                current_platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
                default_platform = current_platform if current_platform else "Choose a Platform"
                
                dpg.add_combo(
                    ("PS1", "PS2", "Gamecube", "Wii"),
                    label="Platform",
                    default_value=default_platform,
                    callback=callback_platform_combobox,
                    user_data=current_project_data,
                    tag="platform_combo"
                )

                dpg.add_separator()

            #! Files To Inject Into Tab
            with dpg.tab(label="Target Game Files", tag="Target Game Files", show=False):
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

                # Project Dashboard
                dpg.add_separator()
                dpg.add_text("Project Dashboard", color=(180, 180, 180))
                dpg.add_text("Loading project statistics...", tag="dashboard_text_build", wrap=0, color=(200, 200, 200))

    # Update dashboard with stats
    update_project_dashboard(current_project_data)

    # After UI is created, restore the project state
    _restore_project_state(current_project_data)
    current_build = current_project_data.GetCurrentBuildVersion()
    if current_build.GetPlatform() and not current_build.GetGameFolder():
        # New project with platform but no game folder
        AddRelevantGameFileOptions(current_project_data)
    
def SelectFirstModificationsInGui(current_project_data: ProjectData):
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
    current_build = current_project_data.GetCurrentBuildVersion()
    
    # Update build version listbox
    from gui.gui_main_project_callbacks import update_build_version_listbox
    update_build_version_listbox(current_project_data)
    
    # If platform is set, show the rest of the tabs
    if current_build.GetPlatform() and current_build.GetPlatform() != "Choose a Platform":
        verbose_print(f"Restoring project state for platform: {current_build.GetPlatform()}")
        
        # Add the platform-specific options
        AddRelevantGameFileOptions(current_project_data)
        
        # If game folder is set, show the tabs
        if current_build.GetGameFolder():
            dpg.configure_item("Target Game Files", show=True)
            dpg.configure_item("Modifications", show=True)
            
            # Restore game files listbox
            if current_build.GetInjectionFiles():
                CInjectionChangeGameFiles(current_build.GetInjectionFiles())
                
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
    # Check prerequisites when platform is changed
    tool_dir = get_application_directory()

    # Get the old platform before we change it
    old_platform = current_project_data.GetCurrentBuildVersion().GetPlatform()

    if not check_and_prompt_prereqs(tool_dir, combo_box_data, None):
        # User cancelled download - revert to old platform in combobox
        if dpg.does_item_exist("combobox_platform"):
            dpg.set_value("combobox_platform", old_platform)
        return

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
        # Single file button
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
        # Single file button
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
        # Choosing a folder can't work for ps1 because we need the original XML structure from a mkpsxiso extract. Maybe in the future I could let someone choose a mkpsxiso xml? Not a priority right now either way.
        # dpg.add_button(
        #     label="Choose Extracted BIN Folder", 
        #     tag="Choose Extracted PS1 Bin Folder", 
        #     parent="Basic Settings", 
        #     callback=callback_choose_ps1_iso_folder, 
        #     user_data=current_project_data
        # )
        # Single file button
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
        # Single file button
        dpg.add_button(
            label="Choose Single Game File (No ISO)", 
            tag="Choose Single Wii File", 
            parent="Basic Settings", 
            callback=callback_choose_single_file, 
            user_data=current_project_data
        )
        
    elif current_project_build.IsPlatformN64():
        # Single file button (N64 is single-file by default cuz its a rom not a disk)
        dpg.add_button(
            label="Choose N64 ROM File", 
            tag="Choose Single N64 File", 
            parent="Basic Settings", 
            callback=callback_choose_single_file, 
            user_data=current_project_data
        )

    # Symbols Drop Down
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

    # Project Dashboard
    dpg.add_separator(parent="Basic Settings", tag="dashboard_separator_basic")
    dpg.add_text("Project Dashboard", color=(180, 180, 180), parent="Basic Settings", tag="dashboard_title_basic")
    dpg.add_text("Loading project statistics...", tag="dashboard_text_basic", wrap=0, color=(200, 200, 200), parent="Basic Settings")

    # Update dashboard
    update_project_dashboard(current_project_data)

def callback_symbols_file_changed(sender, app_data, current_project_data: ProjectData):
    selected_file = app_data
    current_project_data.GetCurrentBuildVersion().SetSymbolsFile(selected_file)
    
    print(f"Build '{current_project_data.GetCurrentBuildVersionName()}' now uses symbols file: {selected_file}")
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()