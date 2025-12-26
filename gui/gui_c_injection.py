import dearpygui.dearpygui as dpg
from dpg.widget_themes import *
from classes.project_data.project_data import *
from classes.injection_targets.code_cave import *
from functions.helper_funcs import *
import os
from functions.verbose_print import verbose_print
from functions.alignment_validator import *
from classes.injection_targets.injection_target import (
    INJECTION_TYPE_EXISTING_FILE,
    INJECTION_TYPE_NEW_FILE,
    INJECTION_TYPE_MEMORY_ONLY,
)

from gui import gui_messagebox as messagebox
from tkinter import filedialog

_currently_selected_codecave_name = None
_currently_selected_codecave_index = -1

# Global state variables for popup input fields
_new_codecave_name_input_value = ""
_rename_codecave_name_input_value = ""

def reset_codecave_state():
    """Reset all codecave GUI state - call when switching projects"""
    global _currently_selected_codecave_name
    global _currently_selected_codecave_index
    
    _currently_selected_codecave_name = None
    _currently_selected_codecave_index = -1
    
    # Clear GUI fields
    ClearGuiCodecaveData()
    
    
def reset_hook_state():
    from gui.gui_asm_injection import ClearGuiHookData
    """Reset all hook GUI state - call when switching projects"""
    global _currently_selected_hook_name
    global _currently_selected_hook_index
    
    _currently_selected_hook_name = None
    _currently_selected_hook_index = -1
    
    # Clear GUI fields
    ClearGuiHookData()
    
def reset_binary_patch_state():
    """Reset all binary patch GUI state - call when switching projects"""
    from gui.gui_binary_patch_injection import ClearGuiBinaryPatchData
    global _currently_selected_binary_patch_name
    global _currently_selected_binary_patch_index
    
    _currently_selected_binary_patch_name = None
    _currently_selected_binary_patch_index = -1
    
    # Clear GUI fields
    ClearGuiBinaryPatchData()
    
    #print("  Binary patch state reset")
    


def CreateCInjectionGui(current_project_data: ProjectData):
    with dpg.tab(label="Code Injection", tag="C & C++ Injection"):

        dpg.add_text("Codecaves:")
        dpg.add_listbox(items=[], tag="codecaves_listbox",
                        callback=callback_codecave_selected,
                        user_data=current_project_data, num_items=5)

        # Right-click context menu for the listbox
        with dpg.popup(parent="codecaves_listbox", mousebutton=dpg.mvMouseButton_Right):
            dpg.add_menu_item(label="Rename Codecave",
                              callback=callback_show_rename_codecave_popup,
                              user_data=current_project_data)

        # Buttons related to managing the list of codecaves
        with dpg.group(horizontal=True):
            dpg.add_button(tag="add_new_codecave_button", label="Add New Codecave",
                           callback=callback_show_add_codecave_popup,
                           user_data=current_project_data)
            dpg.add_button(tag="remove_codecave", label="Remove Selected Codecave",
                           callback=callback_remove_codecave,
                           user_data=current_project_data)

            # PS1-specific button (hidden by default)
            dpg.add_button(
                tag="add_ps1_header_codecave_button",
                label="📦 Add PS1 Header Codecave",
                callback=callback_add_ps1_header_codecave,
                user_data=current_project_data,
                show=False  # Hidden by default, shown only for PS1 projects
            )

            # Apply theme to make it stand out
            with dpg.theme() as ps1_header_theme:
                with dpg.theme_component(dpg.mvButton):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 100, 180), category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 120, 200), category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (40, 80, 160), category=dpg.mvThemeCat_Core)

            dpg.bind_item_theme("add_ps1_header_codecave_button", ps1_header_theme)

        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Disabled checkbox
        dpg.add_text("Codecave Name")
        with dpg.group(horizontal=True):
            # Codecave Name
            dpg.add_input_text(tag="codecave_name_detail_input",
                            hint="Name of selected codecave",
                            enabled=False)
            dpg.add_checkbox(label="Disabled", tag="codecave_disabled_checkbox",
                            callback=callback_codecave_disabled_checkbox_changed,
                            user_data=current_project_data)
            with dpg.tooltip("codecave_disabled_checkbox", delay=1):
                dpg.add_text("This temporarily removes it from compilation/building")


        # C/C++ files Listbox
        dpg.add_text("C/C++/ASM Files")
        dpg.add_listbox([], tag="C/C++ Files Listbox",
                        callback=callback_code_file_selected,
                        user_data=current_project_data,
                        num_items=6)

        # C/C++ Files buttons
        with dpg.group(horizontal=True):
            dpg.add_button(tag="Add C/C++ File", label="Add Code Files",
                           callback=callback_add_code_file,
                           user_data=current_project_data)
            dpg.add_button(label="Remove Selected Code File",
                           tag="Remove Selected C/C++ File",
                           callback=callback_remove_selected_code_file,
                           user_data=current_project_data)
            dpg.add_button(label="Clear Code Files List",
                           callback=callback_clear_code_files,
                           user_data=current_project_data)

        # Injection Type
        dpg.add_text("Injection Type")
        with dpg.group(horizontal=True):
            dpg.add_radio_button(
                items=["Inject into existing file", "Create new file on disk", "Memory Only"],
                tag="codecave_injection_type_radio",
                default_value="Inject into existing file",
                callback=callback_codecave_injection_type_changed,
                user_data=current_project_data,
                horizontal=True
            )

        # Existing game file selection (show/hide based on injection type)
        with dpg.group(tag="codecave_existing_file_group", show=True):
            dpg.add_text("Game File to Inject Into")
            dpg.add_combo(("",), tag="target_game_file",
                         callback=callback_codecave_injection_file_changed,
                         user_data=current_project_data)

        # New file creation (show/hide based on injection type)
        with dpg.group(tag="codecave_new_file_group", show=False):
            dpg.add_text("New File Name (will be created on disk)")
            with dpg.group(horizontal=True):
                dpg.add_input_text(tag="codecave_new_filename_input",
                                   hint="e.g., MYMOD.DAT",
                                   width=200)
                dpg.add_text("Platform-specific naming conventions apply", color=(150, 150, 150))

        # Address in Memory (single, unique)
        dpg.add_text("Address in Memory To Load At")
        with dpg.group(horizontal=True, tag="c_address_in_memory_group"):
            dpg.add_text("0x")
            dpg.add_input_text(tag="c_address_in_memory", hint="80123456",
                               hexadecimal=True,
                               callback=update_calculated_file_address,
                               user_data=current_project_data)

        # Address in File (entire section hidden when creating a new file)
        with dpg.group(tag="codecave_file_address_group", show=True):
            dpg.add_text("Address in File")
            with dpg.group(horizontal=True):
                dpg.add_text("0x")
                dpg.add_input_text(tag="injection_file_address_input",
                                   hint="1000", hexadecimal=True)
                dpg.add_checkbox(label="Auto-Calculate from Offset",
                                 tag="auto_calc_file_address_checkbox",
                                 callback=callback_auto_calculate_file_address_checkbox,
                                 user_data=current_project_data)

        # Region Size
        dpg.add_text("Size of Region")
        with dpg.group(horizontal=True):
            dpg.add_text("0x")
            dpg.add_input_text(tag="size_of_codecave_region", hint="1234", hexadecimal=True)

        for _ in range(5):
            dpg.add_spacer()

        with dpg.group(horizontal=True):
            dpg.add_button(tag="save_codecave",
                           label="Save Current Codecave Details",
                           callback=callback_save_codecave,
                           user_data=current_project_data)
            dpg.add_text("Saved!", tag="codecave_save_indicator",
                        color=(0, 255, 0), show=False)



def CInjectionChangeGameFiles(items):
    dpg.configure_item("target_game_file", items=items)

def ClearGuiCodecaveData():
    global _currently_selected_codecave_name
    global _currently_selected_codecave_index

  # Only clear if items exist
    if dpg.does_item_exist("codecave_name_detail_input"):
        dpg.set_value("codecave_name_detail_input", "")
    if dpg.does_item_exist("c_address_in_memory"):
        dpg.set_value("c_address_in_memory", "")
    if dpg.does_item_exist("injection_file_address_input"):
        dpg.set_value("injection_file_address_input", "")
    if dpg.does_item_exist("size_of_codecave_region"):
        dpg.set_value("size_of_codecave_region", "")
    if dpg.does_item_exist("target_game_file"):
        dpg.set_value("target_game_file", "")
        dpg.configure_item("target_game_file", items=[""])
    if dpg.does_item_exist("C/C++ Files Listbox"):
        dpg.configure_item("C/C++ Files Listbox", items=[])
    if dpg.does_item_exist("auto_calc_file_address_checkbox"):
        dpg.set_value("auto_calc_file_address_checkbox", False)
    if dpg.does_item_exist("injection_file_address_input"):
        dpg.configure_item("injection_file_address_input", enabled=True)

    _currently_selected_codecave_name = None
    _currently_selected_codecave_index = -1
    #print("GUI Codecave Data Cleared.")


def callback_show_add_codecave_popup(sender, app_data, user_data):
    global _new_codecave_name_input_value
    _new_codecave_name_input_value = "" # Clear previous input

    if dpg.does_item_exist("add_codecave_modal"):
        dpg.set_value("new_codecave_name_input", _new_codecave_name_input_value)
        dpg.show_item("add_codecave_modal")
    else:
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        modal_width = 350
        modal_height = 150
        modal_x = (viewport_width - modal_width) // 2
        modal_y = (viewport_height - modal_height) // 2

        with dpg.window(label="Add New Codecave", modal=True, no_close=True, tag="add_codecave_modal",
                        no_move=True, no_resize=True, width=modal_width, height=modal_height, pos=[modal_x, modal_y], show=False):
            dpg.add_text("Enter name for the new codecave:")
            dpg.add_input_text(tag="new_codecave_name_input", default_value=_new_codecave_name_input_value, width=200, hint="New Codecave Name")
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Create", callback=callback_create_codecave_from_popup, user_data=user_data)
                dpg.add_button(label="Cancel", callback=lambda s,a,u: dpg.configure_item("add_codecave_modal", show=False))
        dpg.show_item("add_codecave_modal")


def callback_create_codecave_from_popup(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_codecave_name
    global _currently_selected_codecave_index

    new_codecave_name = dpg.get_value("new_codecave_name_input")

    if not new_codecave_name:
        messagebox.showerror("Error", "Codecave name cannot be empty.")
        return

    if new_codecave_name in current_project_data.GetCurrentBuildVersion().GetCodeCaveNames():
        messagebox.showerror("Error", f"A codecave named '{new_codecave_name}' already exists.")
        return

    new_codecave = Codecave()
    new_codecave.SetName(new_codecave_name)
    
    new_codecave_name = new_codecave.GetName() # Update because it will be sanitized of spaces 
    
    # NEW: Set default aligned address based on platform
    platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
    if platform.upper() in ["PS2", "N64"]:
        new_codecave.SetMemoryAddress("80100000")  # 8-byte aligned
    else:
        new_codecave.SetMemoryAddress("80100000")  # 4-byte aligned (same default works)

    current_project_data.GetCurrentBuildVersion().AddCodeCave(new_codecave)
    print(f"Created new codecave: {new_codecave_name}")

    UpdateCodecavesListbox(current_project_data)

    _currently_selected_codecave_name = new_codecave_name
    _currently_selected_codecave_index = current_project_data.GetCurrentBuildVersion().GetCodeCaveNames().index(new_codecave_name)
    dpg.set_value("codecaves_listbox", new_codecave_name)

    ReloadGuiCodecaveData(current_project_data)

    dpg.configure_item("add_codecave_modal", show=False)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def callback_show_rename_codecave_popup(sender, app_data, current_project_data: ProjectData):
    global _rename_codecave_name_input_value
    global _currently_selected_codecave_name

    if _currently_selected_codecave_index == -1:
        messagebox.showinfo("Info", "No codecave selected to rename.")
        return

    _rename_codecave_name_input_value = _currently_selected_codecave_name

    if dpg.does_item_exist("rename_codecave_modal"):
        dpg.set_value("rename_codecave_name_input", _rename_codecave_name_input_value)
        dpg.show_item("rename_codecave_modal")
    else:
        # Adjusted modal position
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        modal_width = 350
        modal_height = 150
        modal_x = (viewport_width - modal_width) // 2
        modal_y = (viewport_height - modal_height) // 2

        with dpg.window(label="Rename Codecave", modal=True, no_close=True, tag="rename_codecave_modal",
                        no_move=True, no_resize=True, width=modal_width, height=modal_height, pos=[modal_x, modal_y], show=False):
            dpg.add_text(f"Rename '{_currently_selected_codecave_name}':")
            dpg.add_input_text(tag="rename_codecave_name_input", default_value=_rename_codecave_name_input_value, width=200, hint="New Codecave Name")
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Rename", callback=callback_rename_codecave_from_popup, user_data=current_project_data)
                dpg.add_button(label="Cancel", callback=lambda s,a,u: dpg.configure_item("rename_codecave_modal", show=False))
        dpg.show_item("rename_codecave_modal")


def callback_rename_codecave_from_popup(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_codecave_name

    new_name = dpg.get_value("rename_codecave_name_input")
    old_name = _currently_selected_codecave_name

    if not new_name:
        messagebox.showerror("Error", "New codecave name cannot be empty.")
        return

    if new_name == old_name:
        dpg.configure_item("rename_codecave_modal", show=False)
        return

    if new_name in current_project_data.GetCurrentBuildVersion().GetCodeCaveNames():
        messagebox.showerror("Error", f"A codecave named '{new_name}' already exists.")
        return

    selected_codecave_obj = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
    selected_codecave_obj.SetName(new_name)

    _currently_selected_codecave_name = new_name
    UpdateCodecavesListbox(current_project_data) # This will re-sort if names are sorted
    dpg.set_value("codecave_name_detail_input", new_name) # Update the detail input field

    print(f"Codecave renamed from '{old_name}' to '{new_name}'.")
    dpg.configure_item("rename_codecave_modal", show=False)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def callback_add_code_file(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index == -1:
        messagebox.showerror("Error", "Please select or create a codecave first.")
        return

    # Allow multiple file selection
    code_file_paths = filedialog.askopenfilenames(
        title="Choose Code File(s)",
        filetypes=[("Code Files", "*.c;*.cpp;*.asm;*.s"), ("All Files", "*.*")],
        initialdir=os.path.join(current_project_data.GetProjectFolder(), "src")
    )
    
    if not code_file_paths:
        return

    selected_codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]

    added_count = 0
    skipped_count = 0
    invalid_count = 0
    space_skipped_count = 0
    space_skipped_files = []

    for code_file_path in code_file_paths:
        basename = os.path.basename(code_file_path)

        # --- NEW: block filenames with spaces ---
        if any(ch.isspace() for ch in basename):
            print(f"Skipped (spaces in name): {basename}")
            space_skipped_count += 1
            space_skipped_files.append(basename)
            continue

        does_file_already_exist = code_file_path in selected_codecave.GetCodeFilesPaths()
        
        if does_file_already_exist:
            print(f"Skipped (already exists): {basename}")
            skipped_count += 1
        elif IsAValidCodeFile(code_file_path):
            selected_codecave.AddCodeFile(code_file_path)
            print(f"Added code file: {basename}")
            added_count += 1
        else:
            print(f"Skipped (invalid): {basename}")
            invalid_count += 1

    # Update the listbox once after all files are processed
    UpdateCodeFilesListbox(current_project_data)

    # Show summary message
    summary_parts = []
    if added_count > 0:
        summary_parts.append(f"{added_count} file(s) added")
    if skipped_count > 0:
        summary_parts.append(f"{skipped_count} already existed")
    if invalid_count > 0:
        summary_parts.append(f"{invalid_count} invalid")
    if space_skipped_count > 0:
        summary_parts.append(f"{space_skipped_count} skipped (spaces in name)")

    if summary_parts:
        print("Code file add summary: " + "; ".join(summary_parts))

    # Show one messagebox for space issues (bandaid rule)
    if space_skipped_count > 0:
        message = (
            "The following file(s) have spaces in their names and were skipped:\n\n"
            + "\n".join(space_skipped_files)
            + "\n\nSpaces in code filenames are not supported yet.\n"
              "Please rename them (e.g. 'My Code.c' → 'My_Code.c') and add them again."
        )
        messagebox.showerror("Unsupported File Name", message)
    
    if added_count > 0:
        from gui.gui_main_project import trigger_auto_save
        trigger_auto_save()


def callback_remove_selected_code_file(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index == -1:
        messagebox.showerror("Error", "No codecave selected.")
        return

    selected_item_value = dpg.get_value("C/C++ Files Listbox")
    if not selected_item_value:
        messagebox.showinfo("Info", "No C/C++ file selected in the listbox to remove.")
        return

    selected_codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
    code_files_full_paths = selected_codecave.GetCodeFilesPaths()
    code_files_names = [os.path.basename(p) for p in code_files_full_paths]

    try:
        idx_in_displayed_names = code_files_names.index(selected_item_value)
        # Assuming code_files is a list in Codecave class
        selected_codecave.code_files.pop(idx_in_displayed_names)
        UpdateCodeFilesListbox(current_project_data)
        print(f"Removed code file: {selected_item_value}")
    except ValueError:
        messagebox.showerror("Error", f"Could not find '{selected_item_value}' in the current codecave's files.")
    except IndexError:
        messagebox.showerror("Error", "Selected codecave data is out of sync. Please re-select a codecave.")

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

def callback_clear_code_files(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index == -1:
        messagebox.showerror("Error", "No codecave selected to clear files from.")
        return

    if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all C/C++ files for the current codecave?"):
        selected_codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
        selected_codecave.code_files = [] # Assuming code_files is a list
        UpdateCodeFilesListbox(current_project_data)
        print("Cleared all code files for the current codecave.")
        
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

def callback_code_file_selected(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index != -1 and app_data:
        current_codecave_obj = None
        if 0 <= _currently_selected_codecave_index < len(current_project_data.GetCurrentBuildVersion().GetCodeCaves()):
            current_codecave_obj = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]

        if current_codecave_obj:
            full_paths = current_codecave_obj.GetCodeFilesPaths()
            for path in full_paths:
                if os.path.basename(path) == app_data:
                    verbose_print(f"Full path of selected file: {path}")
                    break

def callback_codecave_selected(sender, data, current_project_data: ProjectData):
    global _currently_selected_codecave_name
    global _currently_selected_codecave_index

    selected_display_name = dpg.get_value("codecaves_listbox")

    # Strip [DISABLED] prefix if present
    if selected_display_name.startswith("[DISABLED] "):
        _currently_selected_codecave_name = selected_display_name.replace("[DISABLED] ", "")
    else:
        _currently_selected_codecave_name = selected_display_name

    found_index = -1
    for i, code_cave_name in enumerate(current_project_data.GetCurrentBuildVersion().GetCodeCaveNames()):
        if _currently_selected_codecave_name == code_cave_name:
            found_index = i
            break

    if found_index != -1:
        _currently_selected_codecave_index = found_index
        verbose_print(f"Codecave selected: {_currently_selected_codecave_name} (Index: {_currently_selected_codecave_index})")
        ReloadGuiCodecaveData(current_project_data)
    else:
        print(f"Error: Selected codecave '{_currently_selected_codecave_name}' not found in project data. Clearing GUI.")
        ClearGuiCodecaveData()


def GetGuiCodecaveData(current_project_data: ProjectData):
    global _currently_selected_codecave_index

    temp_codecave = Codecave()

    # --- Name ---
    codecave_name = dpg.get_value("codecave_name_detail_input")
    if not codecave_name:
        messagebox.showerror("Validation Error", "Codecave name cannot be empty.")
        return None
    temp_codecave.SetName(codecave_name)

    # --- Preserve existing code files from currently selected codecave ---
    if _currently_selected_codecave_index != -1:
        current_codecave_obj = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
        temp_codecave.code_files = list(current_codecave_obj.code_files)
    else:
        temp_codecave.code_files = []

    # === Injection type handling (Existing file / New file / Memory Only) ===
    injection_type_text = dpg.get_value("codecave_injection_type_radio")

    # Normalize to internal string values
    if injection_type_text == "Inject into existing file":
        injection_type = "existing_file"
    elif injection_type_text == "Create new file on disk":
        injection_type = "new_file"
    elif injection_type_text == "Memory Only":
        injection_type = "memory_only"
    else:
        # Failsafe – default to existing file
        injection_type = "existing_file"

    temp_codecave.SetInjectionType(injection_type)

    # --- File target based on injection type ---
    if injection_type == "new_file":
        # New file: get new filename from input
        new_filename = dpg.get_value("codecave_new_filename_input")
        if not new_filename or new_filename.strip() == "":
            messagebox.showerror("Validation Error", "New file name cannot be empty when creating a new file.")
            return None
        temp_codecave.SetInjectionFile(new_filename.strip())

    elif injection_type == "existing_file":
        # Existing file: get selected game file from combo
        game_file = dpg.get_value("target_game_file")
        if not game_file:
            messagebox.showerror("Validation Error", "You must select a target game file for this codecave.")
            return None
        temp_codecave.SetInjectionFile(game_file)

    else:
        # Memory Only: no disk file involved
        temp_codecave.SetInjectionFile("")

    # --- Memory address (always required) ---
    memory_address = dpg.get_value("c_address_in_memory")
    if not memory_address:
        messagebox.showerror("Validation Error", "Memory address cannot be empty.")
        return None

    # Validate alignment
    platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
    is_valid, error_msg = validate_address_alignment(memory_address, platform, "codecave")
    if not is_valid:
        show_alignment_error_dialog(memory_address, platform, "codecave")
        return None

    temp_codecave.SetMemoryAddress(memory_address)

    # --- File address handling (only for 'existing_file') ---
    if injection_type == "existing_file":
        auto_calc_enabled = dpg.get_value("auto_calc_file_address_checkbox")
        temp_codecave.SetAutoCalculateInjectionFileAddress(auto_calc_enabled)

        injection_file_address = dpg.get_value("injection_file_address_input")

        if injection_file_address:
            # Ensure 0x prefix
            if not injection_file_address.startswith("0x"):
                injection_file_address = "0x" + injection_file_address
        else:
            # If nothing entered, store empty string
            injection_file_address = ""

        temp_codecave.SetInjectionFileAddress(injection_file_address)

    else:
        # New files and Memory Only codecaves do not need a file address
        temp_codecave.SetAutoCalculateInjectionFileAddress(False)
        temp_codecave.SetInjectionFileAddress("")

    # --- Size of codecave region ---
    size_of_region = dpg.get_value("size_of_codecave_region")
    temp_codecave.SetSize(size_of_region)

    return temp_codecave


def callback_codecave_disabled_checkbox_changed(sender, app_data, user_data):
    """Handle toggling the disabled checkbox for a codecave in the details panel"""
    global _currently_selected_codecave_index
    current_project_data = user_data

    if _currently_selected_codecave_index == -1:
        return

    codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
    codecave_name = codecave.GetName()

    # Checkbox value: True = disabled, False = enabled
    codecave.SetEnabled(not app_data)

    # Update listbox to show visual indicator
    UpdateCodecavesListbox(current_project_data)

    # Restore selection to keep the current codecave selected
    if not codecave.IsEnabled():
        dpg.set_value("codecaves_listbox", f"[DISABLED] {codecave_name}")
    else:
        dpg.set_value("codecaves_listbox", codecave_name)

    # Save project
    from services.project_serializer import ProjectSerializer
    ProjectSerializer.save_project(current_project_data)


def UpdateCodecavesListbox(current_project_data: ProjectData):
    code_caves = current_project_data.GetCurrentBuildVersion().GetCodeCaves()

    # Format names with [DISABLED] prefix for disabled items
    code_cave_display_names = []
    for cc in code_caves:
        if not cc.IsEnabled():
            code_cave_display_names.append(f"[DISABLED] {cc.GetName()}")
        else:
            code_cave_display_names.append(cc.GetName())

    dpg.configure_item("codecaves_listbox", items=code_cave_display_names)

    # Show or hide the "getting started" helper based on whether we have any codecaves
    if not code_caves:
        show_codecave_getting_started_message(current_project_data)
    else:
        hide_codecave_getting_started_message()


def UpdateCodeFilesListbox(current_project_data: ProjectData):
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index != -1:
        selected_codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
        code_files_names = [os.path.basename(f) for f in selected_codecave.GetCodeFilesPaths()]
        dpg.configure_item("C/C++ Files Listbox", items=code_files_names)
    else:
        dpg.configure_item("C/C++ Files Listbox", items=[])


def callback_codecave_injection_file_changed(sender, app_data, current_project_data: ProjectData):
    """Auto-save when injection file dropdown changes"""
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index == -1:
        return

    # Get the selected file from the combo
    selected_file = app_data

    # Update the codecave's injection file
    existing_codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
    existing_codecave.SetInjectionFile(selected_file)

    # Trigger auto-save
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    verbose_print(f"Codecave '{existing_codecave.GetName()}' injection file changed to: {selected_file}")

def _hide_save_indicator_after_delay(indicator_tag):
    """Helper to hide save indicator after 3 seconds"""
    import threading

    def hide_callback():
        if dpg.does_item_exist(indicator_tag):
            dpg.configure_item(indicator_tag, show=False)

    timer = threading.Timer(1.0, hide_callback)
    timer.daemon = True
    timer.start()

def callback_save_codecave(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index == -1:
        messagebox.showerror("Error", "No codecave selected to save.")
        return

    temp_codecave_from_gui = GetGuiCodecaveData(current_project_data)
    if temp_codecave_from_gui is None: # If validation failed
        return

    # The name from the detail input should match the selected codecave's name
    # as the detail input is disabled for direct editing.
    existing_codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]

    # Update only the mutable fields of the existing codecave object
    existing_codecave.SetInjectionFile(temp_codecave_from_gui.GetInjectionFile())
    existing_codecave.SetMemoryAddress(temp_codecave_from_gui.GetMemoryAddress())
    existing_codecave.SetSize(temp_codecave_from_gui.GetSize())
    existing_codecave.SetInjectionFileAddress(temp_codecave_from_gui.GetInjectionFileAddress())
    existing_codecave.SetAutoCalculateInjectionFileAddress(temp_codecave_from_gui.GetAutoCalculateInjectionFileAddress()) # Save the checkbox state

    UpdateCodecavesListbox(current_project_data)

    print(f"Codecave '{existing_codecave.GetName()}' details saved.")

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    # Show "Saved!" indicator
    if dpg.does_item_exist("codecave_save_indicator"):
        dpg.configure_item("codecave_save_indicator", show=True)
        _hide_save_indicator_after_delay("codecave_save_indicator")


def callback_remove_codecave(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_codecave_name
    global _currently_selected_codecave_index

    selected_codecave_name = dpg.get_value("codecaves_listbox")

    if not selected_codecave_name:
        messagebox.showinfo("Info", "No codecave selected to remove.")
        return

    if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove codecave '{selected_codecave_name}'?"):
        codecave_to_remove_index = None
        for i, project_code_cave_name in enumerate(current_project_data.GetCurrentBuildVersion().GetCodeCaveNames()):
            if selected_codecave_name == project_code_cave_name:
                codecave_to_remove_index = i
                break

        if codecave_to_remove_index is not None:
            current_project_data.GetCurrentBuildVersion().code_caves.pop(codecave_to_remove_index)
            UpdateCodecavesListbox(current_project_data)
            ClearGuiCodecaveData() # Clear GUI after removal
            print(f"Removed codecave: {selected_codecave_name}")
        else:
            messagebox.showerror("Error", f"Codecave '{selected_codecave_name}' not found in project data.")
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def ReloadGuiCodecaveData(current_project_data: ProjectData):
    global _currently_selected_codecave_name
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index == -1:
        ClearGuiCodecaveData()
        return

    codecaves = current_project_data.GetCurrentBuildVersion().GetCodeCaves()
    if not (0 <= _currently_selected_codecave_index < len(codecaves)):
        print(f"Error: Invalid codecave index {_currently_selected_codecave_index}. Clearing GUI.")
        ClearGuiCodecaveData()
        return

    selected_codecave = codecaves[_currently_selected_codecave_index]

    dpg.set_value("codecave_name_detail_input", selected_codecave.GetName())

    # Set disabled checkbox state
    is_disabled = not selected_codecave.IsEnabled()
    dpg.set_value("codecave_disabled_checkbox", is_disabled)

    # --- Injection type handling (existing / new file / memory only) ---
    injection_type = selected_codecave.GetInjectionType()

    if injection_type == "new_file":
        dpg.set_value("codecave_injection_type_radio", "Create new file on disk")
        dpg.configure_item("codecave_existing_file_group", show=False)
        dpg.configure_item("codecave_new_file_group", show=True)
        dpg.configure_item("codecave_file_address_group", show=False)

        new_filename = selected_codecave.GetInjectionFile() or ""
        dpg.set_value("codecave_new_filename_input", new_filename)

    elif injection_type == "memory_only":
        dpg.set_value("codecave_injection_type_radio", "Memory Only")
        # No file selection and no file address for memory-only codecaves
        dpg.configure_item("codecave_existing_file_group", show=False)
        dpg.configure_item("codecave_new_file_group", show=False)
        dpg.configure_item("codecave_file_address_group", show=False)

        # Optional: clear file-related widgets so they don't carry stale data
        dpg.set_value("codecave_new_filename_input", "")
        dpg.set_value("target_game_file", "")

    else:
        # Default / existing_file case
        dpg.set_value("codecave_injection_type_radio", "Inject into existing file")
        dpg.configure_item("codecave_existing_file_group", show=True)
        dpg.configure_item("codecave_new_file_group", show=False)
        dpg.configure_item("codecave_file_address_group", show=True)

    # --- Code files list ---
    filenames = [os.path.basename(f) for f in selected_codecave.GetCodeFilesPaths()]
    dpg.configure_item("C/C++ Files Listbox", items=filenames)

    # --- Target game file combo ---
    game_files_for_combo = current_project_data.GetCurrentBuildVersion().GetInjectionFiles()
    
    if game_files_for_combo:
        dpg.configure_item("target_game_file", items=game_files_for_combo)
    else:
        dpg.configure_item("target_game_file", items=[""])
    
    current_injection_file = selected_codecave.GetInjectionFile()
    
    if current_injection_file and current_injection_file not in game_files_for_combo:
        dpg.set_value("target_game_file", "")  # Clear dropdown
        print(
            f"Warning: Codecave '{selected_codecave.GetName()}' references missing file: {current_injection_file}"
        )
    else:
        dpg.set_value("target_game_file", current_injection_file or "")

    # --- Memory address & size (always relevant) ---
    dpg.set_value("c_address_in_memory", selected_codecave.GetMemoryAddress())
    dpg.set_value("size_of_codecave_region", selected_codecave.GetSize())

    # --- File address / auto-calc (only meaningful for existing_file, but safe to keep) ---
    auto_calc_state = selected_codecave.GetAutoCalculateInjectionFileAddress()
    dpg.set_value("auto_calc_file_address_checkbox", auto_calc_state)
    dpg.configure_item("injection_file_address_input", enabled=not auto_calc_state)

    if auto_calc_state:
        update_calculated_file_address(None, None, current_project_data)
        
        # Only auto-calculate using section maps if checkbox is enabled
        current_build = current_project_data.GetCurrentBuildVersion()
        memory_address = selected_codecave.GetMemoryAddress()
        if memory_address:
            mem_addr_int = int(memory_address, 16)
            file_offset = current_build.GetFileOffsetForAddress(
                selected_codecave.GetInjectionFile(),
                mem_addr_int
            )
            
            if file_offset:
                dpg.set_value("injection_file_address_input", f"{file_offset:X}")
    else:
        # Use the manually set file address
        display_offset = selected_codecave.GetInjectionFileAddress()
        dpg.set_value("injection_file_address_input", display_offset)



def update_calculated_file_address(sender, app_data, current_project_data: ProjectData):
    """Calculate file address using section maps (NEW: Multi-section support)"""
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index == -1:
        return

    selected_codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]

    if not selected_codecave.GetAutoCalculateInjectionFileAddress():
        return

    memory_address_str = dpg.get_value("c_address_in_memory")
    
    if not memory_address_str:
        dpg.set_value("injection_file_address_input", "")
        return

    try:
        # Parse memory address
        processed_memory_address_str = memory_address_str.strip()

        # Remove 0x prefix if present
        if processed_memory_address_str.lower().startswith("0x"):
            processed_memory_address_str = processed_memory_address_str[2:]

        # Remove 80 prefix if present (GameCube/Wii addresses)
        if processed_memory_address_str.lower().startswith("80") and len(processed_memory_address_str) > 2:
            processed_memory_address_str = processed_memory_address_str[2:]

        memory_address_int = int(processed_memory_address_str, 16)
        
        # NEW: Use section map to calculate file offset
        current_build = current_project_data.GetCurrentBuildVersion()
        injection_file = selected_codecave.GetInjectionFile()
        
        if not injection_file:
            dpg.set_value("injection_file_address_input", "NO FILE")
            return
        
        # Try section map first
        file_offset = current_build.GetFileOffsetForAddress(injection_file, memory_address_int)
        
        if file_offset is not None:
            # Success! Found in section map
            calculated_hex_string = f"{file_offset:X}"
            dpg.set_value("injection_file_address_input", calculated_hex_string)
            
            # Show section info in console
            section_info = current_build.GetSectionInfoForAddress(injection_file, memory_address_int)
            if section_info:
                print(f"Address 0x{memory_address_int:X} found in {section_info['type']} section")
                print(f"  File offset: 0x{file_offset:X}")
            
        else:
            # Fallback to old offset method
            ram_offset_str = dpg.get_value("File Offset From Ram Input")
            
            if not ram_offset_str:
                dpg.set_value("injection_file_address_input", "NO OFFSET")
                return
            
            ram_offset_int = int(ram_offset_str, 16)
            calculated_file_address_int = memory_address_int - ram_offset_int

            if calculated_file_address_int < 0:
                dpg.set_value("injection_file_address_input", "INVALID")
                return

            calculated_hex_string = f"{calculated_file_address_int:X}"
            dpg.set_value("injection_file_address_input", calculated_hex_string)
            print(f"Using fallback offset calculation (no section map)")

    except ValueError as e:
        dpg.set_value("injection_file_address_input", "INVALID")
        print(f"Error in auto-calculation: {e}")

# --- NEW: Checkbox callback ---
def callback_auto_calculate_file_address_checkbox(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_codecave_index

    if _currently_selected_codecave_index == -1:
        messagebox.showinfo("Info", "No codecave selected. Cannot change auto-calculate setting.")
        dpg.set_value("auto_calc_file_address_checkbox", False) # Uncheck if no codecave selected
        dpg.configure_item("injection_file_address_input", enabled=True)
        return

    selected_codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
    is_checked = app_data # app_data is True if checked, False if unchecked

    selected_codecave.SetAutoCalculateInjectionFileAddress(is_checked) # Store state in codecave object

    # Enable/Disable the input field
    dpg.configure_item("injection_file_address_input", enabled=not is_checked)

    if is_checked:
        update_calculated_file_address(sender, app_data, current_project_data) # Trigger calculation immediately
    else:
        # If unchecked, load the original saved value from the codecave
        display_offset = selected_codecave.GetInjectionFileAddress()
        dpg.set_value("injection_file_address_input", display_offset)
        print("Auto-calculation disabled. Manual input enabled.")
        
def callback_add_ps1_header_codecave(sender, app_data, current_project_data: ProjectData):
    """
    Callback for "Add PS1 Header Codecave" button.
    Imported from template_service.
    """
    from services.template_service import callback_add_ps1_header_codecave as template_callback
    template_callback(sender, app_data, current_project_data)


def update_ps1_codecave_button_visibility(current_project_data: ProjectData):
    """
    Show/hide PS1 header codecave button based on platform.
    Call this when platform changes or project loads.
    """
    
    platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
    is_ps1 = platform == "PS1"
    
    if dpg.does_item_exist("add_ps1_header_codecave_button"):
        dpg.configure_item("add_ps1_header_codecave_button", show=is_ps1)


def callback_codecave_injection_type_changed(sender, app_data, current_project_data: ProjectData):
    """Show/hide appropriate fields based on injection type"""
    global _currently_selected_codecave_index
    
    selected_text = app_data  # e.g. "Inject into existing file", "Create new file on disk", "Memory Only"

    if selected_text == "Create new file on disk":
        injection_type = "new_file"
    elif selected_text == "Memory Only":
        injection_type = "memory_only"
    else:
        injection_type = "existing_file"

    # Show/hide file-related groups
    show_existing_file = (injection_type == "existing_file")
    show_new_file = (injection_type == "new_file")
    show_file_address = (injection_type == "existing_file")  # ONLY for existing-file injections

    dpg.configure_item("codecave_existing_file_group", show=show_existing_file)
    dpg.configure_item("codecave_new_file_group", show=show_new_file)
    dpg.configure_item("codecave_file_address_group", show=show_file_address)
    
    # Update codecave object if one is selected
    if _currently_selected_codecave_index != -1:
        codecave = current_project_data.GetCurrentBuildVersion().GetCodeCaves()[_currently_selected_codecave_index]
        codecave.SetInjectionType(injection_type)

        # Make sure memory-only and new-file don't accidentally carry file-address auto-calc
        if injection_type != "existing_file":
            codecave.SetAutoCalculateInjectionFileAddress(False)
            codecave.SetInjectionFileAddress("")
            if injection_type == "memory_only":
                # Memory-only should not have a disk file associated
                codecave.SetInjectionFile("")

        from gui.gui_main_project import trigger_auto_save
        trigger_auto_save()


def callback_open_debug_string_codecave_finder(sender, app_data, current_project_data: ProjectData):
    """Open Codecave Finder → Debug String tab and auto-scan."""
    from gui.gui_codecave_finder import show_codecave_finder_window, _on_debug_string_scan_clicked

    # Open the Codecave Finder window (re-uses existing window if already created)
    show_codecave_finder_window(sender, app_data, current_project_data)

    # Switch to the Debug String Finder tab if the tab bar exists
    if dpg.does_item_exist("codecave_finder_tab_bar"):
        try:
            # Value is the tag of the tab we want active
            dpg.set_value("codecave_finder_tab_bar", "debug_string_finder_tab")
        except Exception as e:
            print(f"Warning: could not switch codecave finder tab: {e}")

    # Kick off the debug-string scan
    try:
        _on_debug_string_scan_clicked("debug_string_scan_button", None, current_project_data)
    except Exception as e:
        # Fallback: if something goes wrong, just let the user drive it manually
        print(f"Error auto-scanning debug strings: {e}")
        
def show_codecave_getting_started_message(current_project_data: ProjectData):
    """Show a little helper panel when there are no codecaves yet."""
    if dpg.does_item_exist("codecave_getting_started_group"):
        dpg.configure_item("codecave_getting_started_group", show=True)
        return

    # Insert this group above the codecaves listbox inside the C & C++ Injection tab
    with dpg.group(tag="codecave_getting_started_group",
                   parent="C & C++ Injection",
                   before="codecaves_listbox"):
        dpg.add_separator()
        dpg.add_spacer(height=4)
        dpg.add_text("No codecaves yet for this build.", color=(200, 200, 0))
        dpg.add_text(
            "You can automatically find safe codecave regions from debug strings:",
            color=(180, 180, 180),
        )
        dpg.add_spacer(height=4)

        with dpg.group(horizontal=True):
            dpg.add_button(
                tag="find_debug_string_codecave_button",
                label="Find Codecave from Debug Strings",
                callback=callback_open_debug_string_codecave_finder,
                user_data=current_project_data,
                width=280,
                height=26,
            )

        dpg.add_spacer(height=4)
        dpg.add_separator()


def hide_codecave_getting_started_message():
    """Hide the helper panel when at least one codecave exists."""
    if dpg.does_item_exist("codecave_getting_started_group"):
        dpg.configure_item("codecave_getting_started_group", show=False)
