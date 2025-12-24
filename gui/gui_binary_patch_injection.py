import dearpygui.dearpygui as dpg
from dpg.widget_themes import *
from classes.project_data.project_data import *
from classes.injection_targets.binary_patch import * # Changed to binary_patch
from functions.helper_funcs import *
import os
from functions.verbose_print import verbose_print

from tkinter import messagebox
from tkinter import filedialog

_currently_selected_binary_patch_name = None
_currently_selected_binary_patch_index = -1

# Global state variables for popup input fields
_new_binary_patch_name_input_value = ""
_rename_binary_patch_name_input_value = ""


def CreateBinaryFileInjectionGui(current_project_data: ProjectData):
    with dpg.tab(label="Binary Patch Injection", tag="binary_patch_injection_tab"): # Unique tab tag

        dpg.add_text("Binary Patches:") # Changed text
        dpg.add_listbox(items=[], tag="binary_patches_listbox", callback=callback_binary_patch_selected, user_data=current_project_data, num_items=5) # Unique tag and callback

        # Right-click context menu for the listbox
        with dpg.popup(parent="binary_patches_listbox", mousebutton=dpg.mvMouseButton_Right): # Unique parent
            dpg.add_menu_item(label="Rename Binary Patch", callback=callback_show_rename_binary_patch_popup, user_data=current_project_data) # Changed label and callback

        # Buttons related to managing the list of binary patches
        with dpg.group(horizontal=True):
            dpg.add_button(tag="add_new_binary_patch_button", label="Add New Binary Patch", callback=callback_show_add_binary_patch_popup, user_data=current_project_data) # Unique tag, label, callback
            dpg.add_button(tag="remove_selected_binary_patch_button", label="Remove Selected Binary Patch", callback=callback_remove_binary_patch, user_data=current_project_data) # Unique tag, label, callback

        dpg.add_separator()
        dpg.add_spacer(height=10) # Visual separation

        # --- Binary Patch Details Section (below the listbox and its controls) ---
        dpg.add_text("Binary Patch Name") # Changed text
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag="binary_patch_name_detail_input", hint="Name of selected binary patch", enabled=False) # Unique tag and hint
            dpg.add_checkbox(label="Disabled", tag="binary_patch_disabled_checkbox",
                            callback=callback_binary_patch_disabled_checkbox_changed,
                            user_data=current_project_data)
            with dpg.tooltip("binary_patch_disabled_checkbox", delay=1):
                dpg.add_text("This temporarily removes it from compilation/building")
            # Binary Patch Name

        # Binary files Listbox
        dpg.add_text(f"Binary Files") # Changed text
        dpg.add_listbox([], tag="binary_patch_files_listbox", callback=callback_binary_file_selected, user_data=current_project_data, num_items=6) # Unique tag and callback

        # Binary Files button
        with dpg.group(horizontal=True):
            dpg.add_button(tag="add_binary_patch_file_button", label="Add Binary File", callback=callback_add_binary_file, user_data=current_project_data) # Unique tag, label, callback
            dpg.add_button(label="Remove Selected Binary File", tag="remove_selected_binary_patch_file_button", callback=callback_remove_selected_binary_file, user_data=current_project_data) # Unique tag, label, callback
            dpg.add_button(label="Clear Binary Files List", tag="clear_binary_patch_files_button", callback=callback_clear_binary_files, user_data=current_project_data) # Unique tag and callback

        # Choose Injection File
        dpg.add_text("Game File to Inject Into")
        dpg.add_combo(("",), tag="binary_patch_target_game_file",
                     callback=callback_binary_patch_injection_file_changed,
                     user_data=current_project_data) # Unique tag

        # In Game Memory Address
        dpg.add_text("Address in Memory To Inject Into")
        with dpg.group(horizontal=True, tag="binary_patch_address_in_memory_group"): # Unique tag
            dpg.add_text("0x")
            dpg.add_input_text(tag="binary_patch_address_in_memory", hint="80123456", hexadecimal=True, # Unique tag
                               callback=update_calculated_file_address, user_data=current_project_data)

        # Address in File
        dpg.add_text("Address in File")
        with dpg.group(horizontal=True):
            dpg.add_text("0x")
            dpg.add_input_text(tag="binary_patch_injection_file_address_input", hint="1000", hexadecimal=True) # Unique tag
            dpg.add_checkbox(label="Auto-Calculate from Offset", tag="binary_patch_auto_calc_file_address_checkbox", # Unique tag
                             callback=callback_auto_calculate_file_address_checkbox, user_data=current_project_data)

        ##Optional options (figure out way to make this clear)

        # Region Size
        dpg.add_text("Size of Region")
        with dpg.group(horizontal=True):
            dpg.add_text("0x")
            dpg.add_input_text(tag="binary_patch_size_of_region", hint="1234", hexadecimal=True) # Unique tag

        for _ in range(5):
            dpg.add_spacer()

        with dpg.group(horizontal=True):
            dpg.add_button(tag="save_binary_patch_details_button", label="Save Current Binary Patch Details", callback=callback_save_binary_patch, user_data=current_project_data)
            dpg.add_text("Saved!", tag="binary_patch_save_indicator",
                        color=(0, 255, 0), show=False) # Unique tag


def BinaryPatchInjectionChangeGameFiles(items): # Changed function name
    dpg.configure_item("binary_patch_target_game_file", items=items) # Unique tag

def ClearGuiBinaryPatchData(): # Changed function name
    global _currently_selected_binary_patch_name
    global _currently_selected_binary_patch_index

    # Only clear if items exist
    if dpg.does_item_exist("binary_patch_name_detail_input"):
        dpg.set_value("binary_patch_name_detail_input", "")
    if dpg.does_item_exist("binary_patch_address_in_memory"):
        dpg.set_value("binary_patch_address_in_memory", "")
    if dpg.does_item_exist("binary_patch_injection_file_address_input"):
        dpg.set_value("binary_patch_injection_file_address_input", "")
    if dpg.does_item_exist("binary_patch_size_of_region"):
        dpg.set_value("binary_patch_size_of_region", "")
    if dpg.does_item_exist("binary_patch_target_game_file"):
        dpg.set_value("binary_patch_target_game_file", "")
        dpg.configure_item("binary_patch_target_game_file", items=[""])
    if dpg.does_item_exist("binary_patch_files_listbox"):
        dpg.configure_item("binary_patch_files_listbox", items=[])
    if dpg.does_item_exist("binary_patch_auto_calc_file_address_checkbox"):
        dpg.set_value("binary_patch_auto_calc_file_address_checkbox", False)
    if dpg.does_item_exist("binary_patch_injection_file_address_input"):
        dpg.configure_item("binary_patch_injection_file_address_input", enabled=True)

    _currently_selected_binary_patch_name = None
    _currently_selected_binary_patch_index = -1
    verbose_print("GUI Binary Patch Data Cleared.") # Changed print statement


# --- Callbacks for "Add New Binary Patch" Popup ---
def callback_show_add_binary_patch_popup(sender, app_data, user_data): # Changed function name
    global _new_binary_patch_name_input_value
    _new_binary_patch_name_input_value = "" # Clear previous input

    if dpg.does_item_exist("add_binary_patch_modal"): # Unique tag
        dpg.set_value("new_binary_patch_name_input", _new_binary_patch_name_input_value) # Unique tag
        dpg.show_item("add_binary_patch_modal") # Unique tag
    else:
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        modal_width = 350
        modal_height = 150
        modal_x = (viewport_width - modal_width) // 2
        modal_y = (viewport_height - modal_height) // 2

        with dpg.window(label="Add New Binary Patch", modal=True, no_close=True, tag="add_binary_patch_modal", # Unique label and tag
                        no_move=True, no_resize=True, width=modal_width, height=modal_height, pos=[modal_x, modal_y], show=False):
            dpg.add_text("Enter name for the new binary patch:") # Changed text
            dpg.add_input_text(tag="new_binary_patch_name_input", default_value=_new_binary_patch_name_input_value, width=200, hint="New Binary Patch Name") # Unique tag and hint
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Create", callback=callback_create_binary_patch_from_popup, user_data=user_data) # Changed callback
                dpg.add_button(label="Cancel", callback=lambda s,a,u: dpg.configure_item("add_binary_patch_modal", show=False)) # Unique tag
        dpg.show_item("add_binary_patch_modal") # Unique tag


def callback_create_binary_patch_from_popup(sender, app_data, current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_name
    global _currently_selected_binary_patch_index

    new_binary_patch_name = dpg.get_value("new_binary_patch_name_input") # Unique tag

    if not new_binary_patch_name:
        messagebox.showerror("Error", "Binary Patch name cannot be empty.") # Changed text
        return

    if new_binary_patch_name in current_project_data.GetCurrentBuildVersion().GetBinaryPatchNames(): # Assuming GetBinaryPatchNames exists
        messagebox.showerror("Error", f"A binary patch named '{new_binary_patch_name}' already exists.") # Changed text
        return

    new_binary_patch = BinaryPatch() # Changed class instantiation
    new_binary_patch.SetName(new_binary_patch_name)
    
    new_binary_patch_name = new_binary_patch.GetName() # Update because it will be sanitized of spaces 

    current_project_data.GetCurrentBuildVersion().AddBinaryPatch(new_binary_patch) # Assuming AddBinaryPatch exists
    print(f"Created new binary patch: {new_binary_patch_name}") # Changed print statement

    UpdateBinaryPatchesListbox(current_project_data) # Changed function call

    _currently_selected_binary_patch_name = new_binary_patch_name
    _currently_selected_binary_patch_index = current_project_data.GetCurrentBuildVersion().GetBinaryPatchNames().index(new_binary_patch_name)
    dpg.set_value("binary_patches_listbox", new_binary_patch_name) # Unique tag

    ReloadGuiBinaryPatchData(current_project_data) # Changed function call

    dpg.configure_item("add_binary_patch_modal", show=False) # Unique tag
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


# --- Callbacks for "Rename Binary Patch" Popup ---
def callback_show_rename_binary_patch_popup(sender, app_data, current_project_data: ProjectData): # Changed function name
    global _rename_binary_patch_name_input_value
    global _currently_selected_binary_patch_name

    if _currently_selected_binary_patch_index == -1:
        messagebox.showinfo("Info", "No binary patch selected to rename.") # Changed text
        return

    _rename_binary_patch_name_input_value = _currently_selected_binary_patch_name

    if dpg.does_item_exist("rename_binary_patch_modal"): # Unique tag
        dpg.set_value("rename_binary_patch_name_input", _rename_binary_patch_name_input_value) # Unique tag
        dpg.show_item("rename_binary_patch_modal") # Unique tag
    else:
        # Adjusted modal position
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        modal_width = 350
        modal_height = 150
        modal_x = (viewport_width - modal_width) // 2
        modal_y = (viewport_height - modal_height) // 2

        with dpg.window(label="Rename Binary Patch", modal=True, no_close=True, tag="rename_binary_patch_modal", # Unique label and tag
                        no_move=True, no_resize=True, width=modal_width, height=modal_height, pos=[modal_x, modal_y], show=False):
            dpg.add_text(f"Rename '{_currently_selected_binary_patch_name}':") # Changed text
            dpg.add_input_text(tag="rename_binary_patch_name_input", default_value=_rename_binary_patch_name_input_value, width=200, hint="New Binary Patch Name") # Unique tag and hint
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Rename", callback=callback_rename_binary_patch_from_popup, user_data=current_project_data) # Changed callback
                dpg.add_button(label="Cancel", callback=lambda s,a,u: dpg.configure_item("rename_binary_patch_modal", show=False)) # Unique tag
        dpg.show_item("rename_binary_patch_modal") # Unique tag


def callback_rename_binary_patch_from_popup(sender, app_data, current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_name

    new_name = dpg.get_value("rename_binary_patch_name_input") # Unique tag
    old_name = _currently_selected_binary_patch_name

    if not new_name:
        messagebox.showerror("Error", "New binary patch name cannot be empty.") # Changed text
        return

    if new_name == old_name:
        dpg.configure_item("rename_binary_patch_modal", show=False) # Unique tag
        return

    if new_name in current_project_data.GetCurrentBuildVersion().GetBinaryPatchNames(): # Assuming GetBinaryPatchNames exists
        messagebox.showerror("Error", f"A binary patch named '{new_name}' already exists.") # Changed text
        return

    selected_binary_patch_obj = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index] # Assuming GetBinaryPatches exists
    selected_binary_patch_obj.SetName(new_name)

    _currently_selected_binary_patch_name = new_name
    UpdateBinaryPatchesListbox(current_project_data) # Changed function call
    dpg.set_value("binary_patch_name_detail_input", new_name) # Unique tag

    print(f"Binary Patch renamed from '{old_name}' to '{new_name}'.") # Changed print statement
    dpg.configure_item("rename_binary_patch_modal", show=False) # Unique tag
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def callback_add_binary_file(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index == -1:
        messagebox.showerror("Error", "Please select or create a binary patch first.")
        return

    # UPDATED: Allow any file type for binary patches
    code_file_path = filedialog.askopenfilename(
        title="Choose Binary File", 
        filetypes=[
            ("Binary Files", "*.bin"),
            ("All Files", "*.*")
        ], 
        initialdir=current_project_data.GetProjectFolder()
    )
    
    if not code_file_path:
        return

    selected_binary_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index]

    does_file_already_exist = code_file_path in selected_binary_patch.GetCodeFilesPaths()
    
    if not does_file_already_exist:
        selected_binary_patch.AddBinaryFile(code_file_path)  # This method exists in BinaryPatch
        UpdateBinaryFilesListbox(current_project_data)
        print(f"Added binary file: {os.path.basename(code_file_path)}")
    else:
        messagebox.showinfo("Info", "File already exists in this binary patch's list.")
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def callback_remove_selected_binary_file(sender, button_data, current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index == -1:
        messagebox.showerror("Error", "No binary patch selected.") # Changed text
        return

    selected_item_value = dpg.get_value("binary_patch_files_listbox") # Unique tag
    if not selected_item_value:
        messagebox.showinfo("Info", "No binary file selected in the listbox to remove.") # Changed text
        return

    selected_binary_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index] # Assuming GetBinaryPatches exists
    code_files_full_paths = selected_binary_patch.GetCodeFilesPaths()
    code_files_names = [os.path.basename(p) for p in code_files_full_paths]

    try:
        idx_in_displayed_names = code_files_names.index(selected_item_value)
        selected_binary_patch.code_files.pop(idx_in_displayed_names) # Assuming code_files is a list (inherited)
        UpdateBinaryFilesListbox(current_project_data) # Changed function call
        print(f"Removed binary file: {selected_item_value}") # Changed print statement
    except ValueError:
        messagebox.showerror("Error", f"Could not find '{selected_item_value}' in the current binary patch's files.") # Changed text
    except IndexError:
        messagebox.showerror("Error", "Selected binary patch data is out of sync. Please re-select a binary patch.") # Changed text
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

def callback_clear_binary_files(sender, button_data, current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index == -1:
        messagebox.showerror("Error", "No binary patch selected to clear files from.") # Changed text
        return

    if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all binary files for the current binary patch?"): # Changed text
        selected_binary_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index] # Assuming GetBinaryPatches exists
        selected_binary_patch.code_files = [] # Assuming code_files is a list
        UpdateBinaryFilesListbox(current_project_data) # Changed function call
        print("Cleared all binary files for the current binary patch.") # Changed print statement
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

def callback_binary_file_selected(sender, app_data, current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index != -1 and app_data:
        current_binary_patch_obj = None
        if 0 <= _currently_selected_binary_patch_index < len(current_project_data.GetCurrentBuildVersion().GetBinaryPatches()): # Assuming GetBinaryPatches exists
            current_binary_patch_obj = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index]

        if current_binary_patch_obj:
            full_paths = current_binary_patch_obj.GetCodeFilesPaths()
            for path in full_paths:
                if os.path.basename(path) == app_data:
                    verbose_print(f"Full path of selected file: {path}")
                    break

def callback_binary_patch_selected(sender, data, current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_name
    global _currently_selected_binary_patch_index

    selected_display_name = dpg.get_value("binary_patches_listbox") # Unique tag

    # Strip [DISABLED] prefix if present
    if selected_display_name.startswith("[DISABLED] "):
        _currently_selected_binary_patch_name = selected_display_name.replace("[DISABLED] ", "")
    else:
        _currently_selected_binary_patch_name = selected_display_name

    found_index = -1
    for i, binary_patch_name in enumerate(current_project_data.GetCurrentBuildVersion().GetBinaryPatchNames()): # Assuming GetBinaryPatchNames exists
        if _currently_selected_binary_patch_name == binary_patch_name:
            found_index = i
            break

    if found_index != -1:
        _currently_selected_binary_patch_index = found_index
        verbose_print(f"Binary Patch selected: {_currently_selected_binary_patch_name} (Index: {_currently_selected_binary_patch_index})") # Changed print statement
        ReloadGuiBinaryPatchData(current_project_data) # Changed function call
    else:
        print(f"Error: Selected binary patch '{_currently_selected_binary_patch_name}' not found in project data. Clearing GUI.") # Changed print statement
        ClearGuiBinaryPatchData() # Changed function call


def GetGuiBinaryPatchData(current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_index

    temp_binary_patch = BinaryPatch() # Changed class instantiation

    binary_patch_name = dpg.get_value("binary_patch_name_detail_input") # Unique tag
    if not binary_patch_name: # Check for empty string
        messagebox.showerror("Validation Error", "Binary Patch name cannot be empty.") # Changed text
        return None
    temp_binary_patch.SetName(binary_patch_name)

    if _currently_selected_binary_patch_index != -1:
        current_binary_patch_obj = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index] # Assuming GetBinaryPatches exists
        temp_binary_patch.code_files = list(current_binary_patch_obj.code_files)
    else:
        temp_binary_patch.code_files = []

    game_file = dpg.get_value("binary_patch_target_game_file") # Unique tag
    temp_binary_patch.SetInjectionFile(game_file)

    memory_address = dpg.get_value("binary_patch_address_in_memory") # Unique tag
    if not memory_address:
        messagebox.showerror("Validation Error", "Memory address cannot be empty.")
        return None
    temp_binary_patch.SetMemoryAddress(memory_address)

    auto_calc_enabled = dpg.get_value("binary_patch_auto_calc_file_address_checkbox") # Unique tag
    temp_binary_patch.SetAutoCalculateInjectionFileAddress(auto_calc_enabled)

    if auto_calc_enabled:
        injection_file_address = dpg.get_value("binary_patch_injection_file_address_input") # Unique tag
        if injection_file_address and not injection_file_address.startswith("0x"):
            injection_file_address = "0x" + injection_file_address
    else:
        injection_file_address = dpg.get_value("binary_patch_injection_file_address_input") # Unique tag
        if injection_file_address and not injection_file_address.startswith("0x"):
            injection_file_address = "0x" + injection_file_address
        elif not injection_file_address:
            injection_file_address = ""

    temp_binary_patch.SetInjectionFileAddress(injection_file_address)

    size_of_region = dpg.get_value("binary_patch_size_of_region") # Unique tag
    temp_binary_patch.SetSize(size_of_region)

    return temp_binary_patch


def callback_binary_patch_disabled_checkbox_changed(sender, app_data, user_data):
    """Handle toggling the disabled checkbox for a binary patch"""
    global _currently_selected_binary_patch_index
    current_project_data = user_data

    if _currently_selected_binary_patch_index == -1:
        return

    binary_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index]
    binary_patch_name = binary_patch.GetName()

    # Checkbox value: True = disabled, False = enabled
    binary_patch.SetEnabled(not app_data)

    # Update listbox to show [DISABLED] prefix
    UpdateBinaryPatchesListbox(current_project_data)

    # Restore selection to keep the current binary patch selected
    if not binary_patch.IsEnabled():
        dpg.set_value("binary_patches_listbox", f"[DISABLED] {binary_patch_name}")
    else:
        dpg.set_value("binary_patches_listbox", binary_patch_name)

    # Save project
    from services.project_serializer import ProjectSerializer
    ProjectSerializer.save_project(current_project_data)


def UpdateBinaryPatchesListbox(current_project_data: ProjectData): # Changed function name
    binary_patches = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()
    binary_patch_display_names = []
    for p in binary_patches:
        if not p.IsEnabled():
            binary_patch_display_names.append(f"[DISABLED] {p.GetName()}")
        else:
            binary_patch_display_names.append(p.GetName())
    dpg.configure_item("binary_patches_listbox", items=binary_patch_display_names) # Unique tag


def UpdateBinaryFilesListbox(current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index != -1:
        selected_binary_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index] # Assuming GetBinaryPatches exists
        code_files_names = [os.path.basename(f) for f in selected_binary_patch.GetCodeFilesPaths()]
        dpg.configure_item("binary_patch_files_listbox", items=code_files_names) # Unique tag
    else:
        dpg.configure_item("binary_patch_files_listbox", items=[]) # Unique tag


def callback_binary_patch_injection_file_changed(sender, app_data, current_project_data: ProjectData):
    """Auto-save when injection file dropdown changes"""
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index == -1:
        return

    # Get the selected file from the combo
    selected_file = app_data

    # Update the binary patch's injection file
    existing_binary_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index]
    existing_binary_patch.SetInjectionFile(selected_file)

    # Trigger auto-save
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    verbose_print(f"Binary Patch '{existing_binary_patch.GetName()}' injection file changed to: {selected_file}")

def _hide_save_indicator_after_delay(indicator_tag):
    """Helper to hide save indicator after 3 seconds"""
    import threading

    def hide_callback():
        if dpg.does_item_exist(indicator_tag):
            dpg.configure_item(indicator_tag, show=False)

    timer = threading.Timer(1.0, hide_callback)
    timer.daemon = True
    timer.start()

def callback_save_binary_patch(sender, button_data, current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index == -1:
        messagebox.showerror("Error", "No binary patch selected to save.") # Changed text
        return

    temp_binary_patch_from_gui = GetGuiBinaryPatchData(current_project_data) # Changed function call
    if temp_binary_patch_from_gui is None:
        return

    existing_binary_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index] # Assuming GetBinaryPatches exists

    existing_binary_patch.SetInjectionFile(temp_binary_patch_from_gui.GetInjectionFile())
    existing_binary_patch.SetMemoryAddress(temp_binary_patch_from_gui.GetMemoryAddress())
    existing_binary_patch.SetSize(temp_binary_patch_from_gui.GetSize())
    existing_binary_patch.SetInjectionFileAddress(temp_binary_patch_from_gui.GetInjectionFileAddress())
    existing_binary_patch.SetAutoCalculateInjectionFileAddress(temp_binary_patch_from_gui.GetAutoCalculateInjectionFileAddress())

    UpdateBinaryPatchesListbox(current_project_data) # Changed function call

    print(f"Binary Patch '{existing_binary_patch.GetName()}' details saved.") # Changed print statement

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    # Show "Saved!" indicator
    if dpg.does_item_exist("binary_patch_save_indicator"):
        dpg.configure_item("binary_patch_save_indicator", show=True)
        _hide_save_indicator_after_delay("binary_patch_save_indicator")


def callback_remove_binary_patch(sender, button_data, current_project_data: ProjectData): # Changed function name
    global _currently_selected_binary_patch_name
    global _currently_selected_binary_patch_index

    selected_binary_patch_name = dpg.get_value("binary_patches_listbox") # Unique tag

    if not selected_binary_patch_name:
        messagebox.showinfo("Info", "No binary patch selected to remove.") # Changed text
        return

    if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove binary patch '{selected_binary_patch_name}'?"): # Changed text
        binary_patch_to_remove_index = None
        for i, project_binary_patch_name in enumerate(current_project_data.GetCurrentBuildVersion().GetBinaryPatchNames()): # Assuming GetBinaryPatchNames exists
            if selected_binary_patch_name == project_binary_patch_name:
                binary_patch_to_remove_index = i
                break

        if binary_patch_to_remove_index is not None:
            current_project_data.GetCurrentBuildVersion().binary_patches.pop(binary_patch_to_remove_index) # Assuming binary_patches is the list in BuildVersion
            UpdateBinaryPatchesListbox(current_project_data) # Changed function call
            ClearGuiBinaryPatchData() # Changed function call
            print(f"Removed binary patch: {selected_binary_patch_name}") # Changed print statement
        else:
            messagebox.showerror("Error", f"Binary Patch '{selected_binary_patch_name}' not found in project data.") # Changed text
        
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def ReloadGuiBinaryPatchData(current_project_data: ProjectData):
    global _currently_selected_binary_patch_name
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index == -1:
        ClearGuiBinaryPatchData()
        return

    binary_patches = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()
    if not (0 <= _currently_selected_binary_patch_index < len(binary_patches)):
        print(f"Error: Invalid binary patch index {_currently_selected_binary_patch_index}. Clearing GUI.")
        ClearGuiBinaryPatchData()
        return

    selected_binary_patch = binary_patches[_currently_selected_binary_patch_index]

    dpg.set_value("binary_patch_name_detail_input", selected_binary_patch.GetName())

    filenames = [os.path.basename(f) for f in selected_binary_patch.GetCodeFilesPaths()]
    dpg.configure_item("binary_patch_files_listbox", items=filenames)

    game_files_for_combo = current_project_data.GetCurrentBuildVersion().GetInjectionFiles()
    
    if game_files_for_combo:
        dpg.configure_item("binary_patch_target_game_file", items=game_files_for_combo)
    else:
        dpg.configure_item("binary_patch_target_game_file", items=[""])
    
    current_injection_file = selected_binary_patch.GetInjectionFile()
    
    if current_injection_file and current_injection_file not in game_files_for_combo:
        dpg.set_value("binary_patch_target_game_file", "")
        print(f"Warning: Binary patch '{selected_binary_patch.GetName()}' references missing file: {current_injection_file}")
    else:
        dpg.set_value("binary_patch_target_game_file", current_injection_file or "")

    dpg.set_value("binary_patch_address_in_memory", selected_binary_patch.GetMemoryAddress())
    dpg.set_value("binary_patch_size_of_region", selected_binary_patch.GetSize())

    # Set disabled checkbox state (checkbox True = disabled)
    is_disabled = not selected_binary_patch.IsEnabled()
    dpg.set_value("binary_patch_disabled_checkbox", is_disabled)

    auto_calc_state = selected_binary_patch.GetAutoCalculateInjectionFileAddress()
    dpg.set_value("binary_patch_auto_calc_file_address_checkbox", auto_calc_state)
    dpg.configure_item("binary_patch_injection_file_address_input", enabled=not auto_calc_state)

    if auto_calc_state:
        update_calculated_file_address(None, None, current_project_data)
    else:
        display_offset = selected_binary_patch.GetInjectionFileAddress()
        dpg.set_value("binary_patch_injection_file_address_input", display_offset)

    verbose_print(f"GUI Reloaded for Binary Patch: {selected_binary_patch.GetName()}")


def update_calculated_file_address(sender, app_data, current_project_data: ProjectData):
    """Calculate file address using section maps (NEW: Multi-section support)"""
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index == -1:
        return

    selected_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index]

    if not selected_patch.GetAutoCalculateInjectionFileAddress():
        return

    memory_address_str = dpg.get_value("binary_patch_address_in_memory")
    
    if not memory_address_str:
        dpg.set_value("binary_patch_injection_file_address_input", "")
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
        injection_file = selected_patch.GetInjectionFile()
        
        if not injection_file:
            dpg.set_value("binary_patch_injection_file_address_input", "NO FILE")
            return
        
        # Try section map first
        file_offset = current_build.GetFileOffsetForAddress(injection_file, memory_address_int)
        
        if file_offset is not None:
            # Success! Found in section map
            calculated_hex_string = f"{file_offset:X}"
            dpg.set_value("binary_patch_injection_file_address_input", calculated_hex_string)
            
            # Show section info in console
            section_info = current_build.GetSectionInfoForAddress(injection_file, memory_address_int)
            if section_info:
                print(f"Address 0x{memory_address_int:X} found in {section_info['type']} section")
                print(f"  File offset: 0x{file_offset:X}")
            
        else:
            # Fallback to old offset method
            ram_offset_str = dpg.get_value("File Offset From Ram Input")
            
            if not ram_offset_str:
                dpg.set_value("binary_patch_injection_file_address_input", "NO OFFSET")
                return
            
            ram_offset_int = int(ram_offset_str, 16)
            calculated_file_address_int = memory_address_int - ram_offset_int

            if calculated_file_address_int < 0:
                dpg.set_value("binary_patch_injection_file_address_input", "INVALID")
                return

            calculated_hex_string = f"{calculated_file_address_int:X}"
            dpg.set_value("binary_patch_injection_file_address_input", calculated_hex_string)
            print(f"Using fallback offset calculation (no section map)")

    except ValueError as e:
        dpg.set_value("binary_patch_injection_file_address_input", "INVALID")
        print(f"Error in auto-calculation: {e}")

def callback_auto_calculate_file_address_checkbox(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_binary_patch_index

    if _currently_selected_binary_patch_index == -1:
        messagebox.showinfo("Info", "No binary patch selected. Cannot change auto-calculate setting.") # Changed text
        dpg.set_value("binary_patch_auto_calc_file_address_checkbox", False) # Unique tag
        dpg.configure_item("binary_patch_injection_file_address_input", enabled=True) # Unique tag
        return

    selected_binary_patch = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()[_currently_selected_binary_patch_index] # Assuming GetBinaryPatches exists
    is_checked = app_data

    selected_binary_patch.SetAutoCalculateInjectionFileAddress(is_checked)

    dpg.configure_item("binary_patch_injection_file_address_input", enabled=not is_checked) # Unique tag

    if is_checked:
        update_calculated_file_address(sender, app_data, current_project_data)
    else:
        display_offset = selected_binary_patch.GetInjectionFileAddress()
        dpg.set_value("binary_patch_injection_file_address_input", display_offset) # Unique tag
        print("Auto-calculation disabled. Manual input enabled.")