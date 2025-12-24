import dearpygui.dearpygui as dpg
from dpg.widget_themes import *
from classes.project_data.project_data import *
from classes.injection_targets.hook import *
from functions.helper_funcs import *
from gui.gui_loading_indicator import LoadingIndicator
import os
from functions.verbose_print import verbose_print
from functions.alignment_validator import *

from tkinter import messagebox
from tkinter import filedialog

_currently_selected_hook_name = None
_currently_selected_hook_index = -1

# Global state variables for popup input fields
_new_hook_name_input_value = ""
_rename_hook_name_input_value = ""


def CreateASMInjectionGui(current_project_data: ProjectData):
    with dpg.tab(label="Hook Injection", tag="hook_injection_tab"):

        dpg.add_text("Hooks:")
        dpg.add_listbox(items=[], tag="hooks_listbox", callback=callback_hook_selected, user_data=current_project_data, num_items=5)

        # Right-click context menu for the listbox
        with dpg.popup(parent="hooks_listbox", mousebutton=dpg.mvMouseButton_Right):
            dpg.add_menu_item(label="Rename Hook", callback=callback_show_rename_hook_popup, user_data=current_project_data)

        # Buttons related to managing the list of hooks
        with dpg.group(horizontal=True):
            dpg.add_button(tag="add_new_hook_button", label="Add New Hook", callback=callback_show_add_hook_popup, user_data=current_project_data)
            dpg.add_button(tag="remove_selected_hook_button", label="Remove Selected Hook", callback=callback_remove_hook, user_data=current_project_data)
            dpg.add_button(tag="import_multipatch_button", label="Import Multi-Patch", callback=callback_import_multipatch, user_data=current_project_data)
            dpg.add_button(tag="auto_detect_hook_button", label="Auto-Detect Hook", callback=callback_auto_detect_hook, user_data=current_project_data)
            # Apply colored theme to the auto-detect button
            with dpg.theme() as auto_detect_theme:
                with dpg.theme_component(dpg.mvButton):
                    # Green/cyan color to indicate it's a helpful feature
                    dpg.add_theme_color(dpg.mvThemeCol_Button, (40, 120, 80), category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (50, 150, 100), category=dpg.mvThemeCat_Core)
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (30, 100, 60), category=dpg.mvThemeCat_Core)
                    # Make it slightly larger
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 6, category=dpg.mvThemeCat_Core)
            
            dpg.bind_item_theme("auto_detect_hook_button", auto_detect_theme)

        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Rest of the existing GUI code...
        # (Keep all the existing detail fields)
        
        dpg.add_text("Hook Name")
        with dpg.group(horizontal=True):
            # Hook Name
            dpg.add_input_text(tag="hook_name_detail_input", hint="Name of selected hook", enabled=False)
            # Disabled checkbox
            dpg.add_checkbox(label="Disabled", tag="hook_disabled_checkbox",
                            callback=callback_hook_disabled_checkbox_changed,
                            user_data=current_project_data)
            with dpg.tooltip("hook_disabled_checkbox", delay=1):
                dpg.add_text("This temporarily removes it from compilation/building")

        # ASM files Listbox
        dpg.add_text(f"ASM Files")
        dpg.add_listbox([], tag="hook_asm_files_listbox", callback=callback_asm_file_selected, user_data=current_project_data, num_items=6)

        # ASM Files button
        with dpg.group(horizontal=True):
            dpg.add_button(tag="add_hook_asm_file_button", label="Add ASM Files", callback=callback_add_asm_file, user_data=current_project_data)
            dpg.add_button(label="Remove Selected ASM File", tag="remove_selected_hook_asm_file_button", callback=callback_remove_selected_asm_file, user_data=current_project_data)
            dpg.add_button(label="Clear ASM Files List", tag="clear_hook_asm_files_button", callback=callback_clear_asm_files, user_data=current_project_data)

        # Choose Injection File
        dpg.add_text("Game File to Inject Into")
        dpg.add_combo(("",), tag="hook_target_game_file",
                     callback=callback_hook_injection_file_changed,
                     user_data=current_project_data)

        # In Game Memory Address
        dpg.add_text("Address in Memory To Inject Into")
        with dpg.group(horizontal=True, tag="hook_address_in_memory_group"):
            dpg.add_text("0x")
            dpg.add_input_text(tag="hook_address_in_memory", hint="80123456", hexadecimal=True,
                               callback=update_calculated_file_address, user_data=current_project_data)

        # Address in File
        dpg.add_text("Address in File")
        with dpg.group(horizontal=True):
            dpg.add_text("0x")
            dpg.add_input_text(tag="hook_injection_file_address_input", hint="1000", hexadecimal=True)
            dpg.add_checkbox(label="Auto-Calculate from Offset", tag="hook_auto_calc_file_address_checkbox",
                             callback=callback_auto_calculate_file_address_checkbox, user_data=current_project_data)

        # Region Size
        dpg.add_text("Size of Region")
        with dpg.group(horizontal=True):
            dpg.add_text("0x")
            dpg.add_input_text(tag="hook_size_of_region", hint="1234", hexadecimal=True)

        for _ in range(5):
            dpg.add_spacer()

        with dpg.group(horizontal=True):
            dpg.add_button(tag="save_hook_details_button", label="Save Current Hook Details", callback=callback_save_hook, user_data=current_project_data)
            dpg.add_text("Saved!", tag="hook_save_indicator",
                        color=(0, 255, 0), show=False)


def HookInjectionChangeGameFiles(items):
    dpg.configure_item("hook_target_game_file", items=items) # Unique tag

def ClearGuiHookData():
    global _currently_selected_hook_name
    global _currently_selected_hook_index

# Only clear if items exist
    if dpg.does_item_exist("hook_name_detail_input"):
        dpg.set_value("hook_name_detail_input", "")
    if dpg.does_item_exist("hook_address_in_memory"):
        dpg.set_value("hook_address_in_memory", "")
    if dpg.does_item_exist("hook_injection_file_address_input"):
        dpg.set_value("hook_injection_file_address_input", "")
    if dpg.does_item_exist("hook_size_of_region"):
        dpg.set_value("hook_size_of_region", "")
    if dpg.does_item_exist("hook_target_game_file"):
        dpg.set_value("hook_target_game_file", "")
        dpg.configure_item("hook_target_game_file", items=[""])
    if dpg.does_item_exist("hook_asm_files_listbox"):
        dpg.configure_item("hook_asm_files_listbox", items=[])
    if dpg.does_item_exist("hook_auto_calc_file_address_checkbox"):
        dpg.set_value("hook_auto_calc_file_address_checkbox", False)
    if dpg.does_item_exist("hook_injection_file_address_input"):
        dpg.configure_item("hook_injection_file_address_input", enabled=True)

    _currently_selected_hook_name = None
    _currently_selected_hook_index = -1
    verbose_print("GUI Hook Data Cleared.")


# --- Callbacks for "Add New Hook" Popup ---
def callback_show_add_hook_popup(sender, app_data, user_data):
    global _new_hook_name_input_value
    _new_hook_name_input_value = "" # Clear previous input

    if dpg.does_item_exist("add_hook_modal"): # Unique tag
        dpg.set_value("new_hook_name_input", _new_hook_name_input_value)
        dpg.show_item("add_hook_modal")
    else:
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        modal_width = 350
        modal_height = 150
        modal_x = (viewport_width - modal_width) // 2
        modal_y = (viewport_height - modal_height) // 2

        with dpg.window(label="Add New Hook", modal=True, no_close=True, tag="add_hook_modal", # Unique tag
                        no_move=True, no_resize=True, width=modal_width, height=modal_height, pos=[modal_x, modal_y], show=False):
            dpg.add_text("Enter name for the new hook:")
            dpg.add_input_text(tag="new_hook_name_input", default_value=_new_hook_name_input_value, width=200, hint="New Hook Name") # Unique tag
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Create", callback=callback_create_hook_from_popup, user_data=user_data)
                dpg.add_button(label="Cancel", callback=lambda s,a,u: dpg.configure_item("add_hook_modal", show=False))
        dpg.show_item("add_hook_modal")


def callback_create_hook_from_popup(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_hook_name
    global _currently_selected_hook_index

    new_hook_name = dpg.get_value("new_hook_name_input")

    if not new_hook_name:
        messagebox.showerror("Error", "Hook name cannot be empty.")
        return

    if new_hook_name in current_project_data.GetCurrentBuildVersion().GetHookNames():
        messagebox.showerror("Error", f"A hook named '{new_hook_name}' already exists.")
        return

    new_hook = Hook()
    new_hook.SetName(new_hook_name)
    
    new_hook_name = new_hook.GetName() # Update because it will be sanitized of spaces 
    
    # NEW: Set default aligned address based on platform
    platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
    if platform.upper() in ["PS2", "N64"]:
        new_hook.SetMemoryAddress("80100000")  # 8-byte aligned
    else:
        new_hook.SetMemoryAddress("80100000")  # 4-byte aligned

    current_project_data.GetCurrentBuildVersion().AddHook(new_hook)
    print(f"Created new hook: {new_hook_name}")

    UpdateHooksListbox(current_project_data)

    _currently_selected_hook_name = new_hook_name
    _currently_selected_hook_index = current_project_data.GetCurrentBuildVersion().GetHookNames().index(new_hook_name)
    dpg.set_value("hooks_listbox", new_hook_name)

    ReloadGuiHookData(current_project_data)

    dpg.configure_item("add_hook_modal", show=False)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


# --- Callbacks for "Rename Hook" Popup ---
def callback_show_rename_hook_popup(sender, app_data, current_project_data: ProjectData):
    global _rename_hook_name_input_value
    global _currently_selected_hook_name

    if _currently_selected_hook_index == -1:
        messagebox.showinfo("Info", "No hook selected to rename.")
        return

    _rename_hook_name_input_value = _currently_selected_hook_name

    if dpg.does_item_exist("rename_hook_modal"): # Unique tag
        dpg.set_value("rename_hook_name_input", _rename_hook_name_input_value)
        dpg.show_item("rename_hook_modal")
    else:
        # Adjusted modal position
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        modal_width = 350
        modal_height = 150
        modal_x = (viewport_width - modal_width) // 2
        modal_y = (viewport_height - modal_height) // 2

        with dpg.window(label="Rename Hook", modal=True, no_close=True, tag="rename_hook_modal", # Unique tag
                        no_move=True, no_resize=True, width=modal_width, height=modal_height, pos=[modal_x, modal_y], show=False):
            dpg.add_text(f"Rename '{_currently_selected_hook_name}':")
            dpg.add_input_text(tag="rename_hook_name_input", default_value=_rename_hook_name_input_value, width=200, hint="New Hook Name") # Unique tag
            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Rename", callback=callback_rename_hook_from_popup, user_data=current_project_data)
                dpg.add_button(label="Cancel", callback=lambda s,a,u: dpg.configure_item("rename_hook_modal", show=False))
        dpg.show_item("rename_hook_modal")


def callback_rename_hook_from_popup(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_hook_name

    new_name = dpg.get_value("rename_hook_name_input")
    old_name = _currently_selected_hook_name

    if not new_name:
        messagebox.showerror("Error", "New hook name cannot be empty.")
        return

    if new_name == old_name:
        dpg.configure_item("rename_hook_modal", show=False)
        return

    if new_name in current_project_data.GetCurrentBuildVersion().GetHookNames():
        messagebox.showerror("Error", f"A hook named '{new_name}' already exists.")
        return

    selected_hook_obj = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]
    selected_hook_obj.SetName(new_name)

    _currently_selected_hook_name = new_name
    UpdateHooksListbox(current_project_data)
    dpg.set_value("hook_name_detail_input", new_name)

    print(f"Hook renamed from '{old_name}' to '{new_name}'.")
    dpg.configure_item("rename_hook_modal", show=False)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def callback_add_asm_file(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_hook_index

    if _currently_selected_hook_index == -1:
        messagebox.showerror("Error", "Please select or create a hook first.")
        return

    # Allow multiple file selection
    code_file_paths = filedialog.askopenfilenames(
        title="Choose ASM File(s)",
        filetypes=[("Assembly Files", "*.s;*.asm"), ("All Files", "*.*")],
        initialdir=os.path.join(current_project_data.GetProjectFolder(), "asm")
    )
    
    if not code_file_paths:
        return

    selected_hook = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]

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

        does_file_already_exist = code_file_path in selected_hook.GetCodeFilesPaths()
        
        if does_file_already_exist:
            print(f"Skipped (already exists): {basename}")
            skipped_count += 1
        elif IsAValidASMFile(code_file_path):
            selected_hook.AddCodeFile(code_file_path)
            print(f"Added ASM file: {basename}")
            added_count += 1
        else:
            print(f"Skipped (invalid): {basename}")
            invalid_count += 1

    # Update the listbox once after all files are processed
    UpdateASMFilesListbox(current_project_data)

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
        print("ASM file add summary: " + "; ".join(summary_parts))

    # Show one messagebox for space issues
    if space_skipped_count > 0:
        message = (
            "The following ASM file(s) have spaces in their names and were skipped:\n\n"
            + "\n".join(space_skipped_files)
            + "\n\nSpaces in ASM filenames are not supported yet.\n"
              "Please rename them (e.g. 'My Hook.s' → 'My_Hook.s') and add them again."
        )
        messagebox.showerror("Unsupported File Name", message)

    if added_count > 0:
        from gui.gui_main_project import trigger_auto_save
        trigger_auto_save()



def callback_remove_selected_asm_file(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_hook_index

    if _currently_selected_hook_index == -1:
        messagebox.showerror("Error", "No hook selected.")
        return

    selected_item_value = dpg.get_value("hook_asm_files_listbox") # Unique tag
    if not selected_item_value:
        messagebox.showinfo("Info", "No ASM file selected in the listbox to remove.")
        return

    selected_hook = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]
    code_files_full_paths = selected_hook.GetCodeFilesPaths()
    code_files_names = [os.path.basename(p) for p in code_files_full_paths]

    try:
        idx_in_displayed_names = code_files_names.index(selected_item_value)
        selected_hook.code_files.pop(idx_in_displayed_names)
        UpdateASMFilesListbox(current_project_data)
        print(f"Removed ASM file: {selected_item_value}")
    except ValueError:
        messagebox.showerror("Error", f"Could not find '{selected_item_value}' in the current hook's files.")
    except IndexError:
        messagebox.showerror("Error", "Selected hook data is out of sync. Please re-select a hook.")
        
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

def callback_clear_asm_files(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_hook_index

    if _currently_selected_hook_index == -1:
        messagebox.showerror("Error", "No hook selected to clear files from.")
        return

    if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all ASM files for the current hook?"):
        selected_hook = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]
        selected_hook.code_files = []
        UpdateASMFilesListbox(current_project_data)
        print("Cleared all ASM files for the current hook.")
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

def callback_asm_file_selected(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_hook_index

    if _currently_selected_hook_index != -1 and app_data:
        current_hook_obj = None
        if 0 <= _currently_selected_hook_index < len(current_project_data.GetCurrentBuildVersion().GetHooks()):
            current_hook_obj = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]

        if current_hook_obj:
            full_paths = current_hook_obj.GetCodeFilesPaths()
            for path in full_paths:
                if os.path.basename(path) == app_data:
                    verbose_print(f"Full path of selected file: {path}")
                    break

def callback_hook_selected(sender, data, current_project_data: ProjectData):
    global _currently_selected_hook_name
    global _currently_selected_hook_index

    selected_value = dpg.get_value("hooks_listbox")
    
    # Check if it's a multi-patch (has suffix)
    if selected_value.endswith(" (Multi-Patch)"):
        # Extract the actual multi-patch name
        multipatch_name = selected_value.replace(" (Multi-Patch)", "")
        
        # Show multi-patch info (read-only)
        show_multipatch_info(multipatch_name, current_project_data)
        
        # Clear hook selection
        _currently_selected_hook_name = None
        _currently_selected_hook_index = -1
        return
    
    # It's a regular hook
    # Strip [DISABLED] prefix if present
    if selected_value.startswith("[DISABLED] "):
        _currently_selected_hook_name = selected_value.replace("[DISABLED] ", "")
    else:
        _currently_selected_hook_name = selected_value

    found_index = -1
    for i, hook_name in enumerate(current_project_data.GetCurrentBuildVersion().GetHookNames()):
        if _currently_selected_hook_name == hook_name:
            found_index = i
            break

    if found_index != -1:
        _currently_selected_hook_index = found_index
        verbose_print(f"Hook selected: {_currently_selected_hook_name} (Index: {_currently_selected_hook_index})")
        ReloadGuiHookData(current_project_data)
    else:
        print(f"Error: Selected hook '{_currently_selected_hook_name}' not found in project data. Clearing GUI.")
        ClearGuiHookData()

def GetGuiHookData(current_project_data: ProjectData):
    global _currently_selected_hook_index

    temp_hook = Hook()

    hook_name = dpg.get_value("hook_name_detail_input")
    if not hook_name:
        messagebox.showerror("Validation Error", "Hook name cannot be empty.")
        return None
    temp_hook.SetName(hook_name)

    if _currently_selected_hook_index != -1:
        current_hook_obj = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]
        temp_hook.code_files = list(current_hook_obj.code_files)
    else:
        temp_hook.code_files = []

    game_file = dpg.get_value("hook_target_game_file") # Unique tag
    temp_hook.SetInjectionFile(game_file)

    memory_address = dpg.get_value("hook_address_in_memory")
    if not memory_address:
        messagebox.showerror("Validation Error", "Memory address cannot be empty.")
        return None
    
    # NEW: Validate alignment
    platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
    is_valid, error_msg = validate_address_alignment(memory_address, platform, "hook")
    if not is_valid:
        show_alignment_error_dialog(memory_address, platform, "hook")
        return None
    
    temp_hook.SetMemoryAddress(memory_address)
    
    temp_hook.SetMemoryAddress(memory_address)

    auto_calc_enabled = dpg.get_value("hook_auto_calc_file_address_checkbox") # Unique tag
    temp_hook.SetAutoCalculateInjectionFileAddress(auto_calc_enabled)

    if auto_calc_enabled:
        injection_file_address = dpg.get_value("hook_injection_file_address_input") # Unique tag
        if injection_file_address and not injection_file_address.startswith("0x"):
            injection_file_address = "0x" + injection_file_address
    else:
        injection_file_address = dpg.get_value("hook_injection_file_address_input") # Unique tag
        if injection_file_address and not injection_file_address.startswith("0x"):
            injection_file_address = "0x" + injection_file_address
        elif not injection_file_address:
            injection_file_address = ""

    temp_hook.SetInjectionFileAddress(injection_file_address)

    size_of_region = dpg.get_value("hook_size_of_region") # Unique tag
    temp_hook.SetSize(size_of_region)

    return temp_hook


def callback_hook_disabled_checkbox_changed(sender, app_data, user_data):
    """Handle toggling the disabled checkbox for a hook in the details panel"""
    global _currently_selected_hook_index
    current_project_data = user_data

    if _currently_selected_hook_index == -1:
        return

    # Use ALL hooks (not just permanent) since _currently_selected_hook_index is based on all hooks
    all_hooks = current_project_data.GetCurrentBuildVersion().GetHooks()

    if _currently_selected_hook_index < len(all_hooks):
        hook = all_hooks[_currently_selected_hook_index]
        hook_name = hook.GetName()

        # Checkbox value: True = disabled, False = enabled
        hook.SetEnabled(not app_data)

        # Determine display name with/without [DISABLED] prefix
        if not hook.IsEnabled():
            display_name = f"[DISABLED] {hook_name}"
        else:
            display_name = hook_name

        # Update listbox with preserved selection
        UpdateHooksListbox(current_project_data, preserve_selection=display_name)

        # Save project
        from services.project_serializer import ProjectSerializer
        ProjectSerializer.save_project(current_project_data)


def UpdateHooksListbox(current_project_data: ProjectData, preserve_selection: str = None):
    # Only show permanent hooks (exclude auto-generated)
    all_hooks = current_project_data.GetCurrentBuildVersion().GetHooks()
    permanent_hooks = [h for h in all_hooks if not h.IsTemporary()]

    # Format names with [DISABLED] prefix for disabled items
    permanent_hook_display_names = []
    for h in permanent_hooks:
        if not h.IsEnabled():
            permanent_hook_display_names.append(f"[DISABLED] {h.GetName()}")
        else:
            permanent_hook_display_names.append(h.GetName())

    multipatch_names = [f"{name} (Multi-Patch)" for name in current_project_data.GetCurrentBuildVersion().GetMultiPatchNames()]

    # Combine hooks and multi-patches (multi-patches shown with suffix)
    all_items = permanent_hook_display_names + multipatch_names

    dpg.configure_item("hooks_listbox", items=all_items)

    # Restore selection if specified
    if preserve_selection and preserve_selection in all_items:
        dpg.set_value("hooks_listbox", preserve_selection)

    # Show/hide getting started message
    if not all_items:
        show_hook_getting_started_message(current_project_data)
    else:
        hide_hook_getting_started_message()


def UpdateASMFilesListbox(current_project_data: ProjectData):
    global _currently_selected_hook_index

    if _currently_selected_hook_index != -1:
        selected_hook = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]
        code_files_names = [os.path.basename(f) for f in selected_hook.GetCodeFilesPaths()]
        dpg.configure_item("hook_asm_files_listbox", items=code_files_names) # Unique tag
    else:
        dpg.configure_item("hook_asm_files_listbox", items=[]) # Unique tag


def callback_hook_injection_file_changed(sender, app_data, current_project_data: ProjectData):
    """Auto-save when injection file dropdown changes"""
    global _currently_selected_hook_index

    if _currently_selected_hook_index == -1:
        return

    # Get the selected file from the combo
    selected_file = app_data

    # Update the hook's injection file
    existing_hook = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]
    existing_hook.SetInjectionFile(selected_file)

    # Trigger auto-save
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    verbose_print(f"Hook '{existing_hook.GetName()}' injection file changed to: {selected_file}")

def _hide_save_indicator_after_delay(indicator_tag):
    """Helper to hide save indicator after 3 seconds"""
    import threading

    def hide_callback():
        if dpg.does_item_exist(indicator_tag):
            dpg.configure_item(indicator_tag, show=False)

    timer = threading.Timer(1.0, hide_callback)
    timer.daemon = True
    timer.start()

def callback_save_hook(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_hook_index

    if _currently_selected_hook_index == -1:
        messagebox.showerror("Error", "No hook selected to save.")
        return

    temp_hook_from_gui = GetGuiHookData(current_project_data)
    if temp_hook_from_gui is None:
        return

    existing_hook = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]

    existing_hook.SetInjectionFile(temp_hook_from_gui.GetInjectionFile())
    existing_hook.SetMemoryAddress(temp_hook_from_gui.GetMemoryAddress())
    existing_hook.SetSize(temp_hook_from_gui.GetSize())
    existing_hook.SetInjectionFileAddress(temp_hook_from_gui.GetInjectionFileAddress())
    existing_hook.SetAutoCalculateInjectionFileAddress(temp_hook_from_gui.GetAutoCalculateInjectionFileAddress())

    UpdateHooksListbox(current_project_data)
    print(f"Hook '{existing_hook.GetName()}' details saved.")

    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

    # Show "Saved!" indicator
    if dpg.does_item_exist("hook_save_indicator"):
        dpg.configure_item("hook_save_indicator", show=True)
        _hide_save_indicator_after_delay("hook_save_indicator")


def callback_remove_hook(sender, button_data, current_project_data: ProjectData):
    global _currently_selected_hook_name
    global _currently_selected_hook_index

    selected_value = dpg.get_value("hooks_listbox")

    if not selected_value:
        messagebox.showinfo("Info", "No hook or multi-patch selected to remove.")
        return

    # Check if it's a multi-patch
    if selected_value.endswith(" (Multi-Patch)"):
        multipatch_name = selected_value.replace(" (Multi-Patch)", "")
        
        if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove multi-patch '{multipatch_name}'?"):
            # Find and remove the multi-patch
            multipatches = current_project_data.GetCurrentBuildVersion().GetMultiPatches()
            multipatch_to_remove = None
            
            for mp in multipatches:
                if mp.GetName() == multipatch_name:
                    multipatch_to_remove = mp
                    break
            
            if multipatch_to_remove:
                current_project_data.GetCurrentBuildVersion().multi_patches.remove(multipatch_to_remove)
                UpdateHooksListbox(current_project_data)
                ClearGuiHookData()
                print(f"Removed multi-patch: {multipatch_name}")
                
                from gui.gui_main_project import trigger_auto_save
                trigger_auto_save()
            else:
                messagebox.showerror("Error", f"Multi-patch '{multipatch_name}' not found in project data.")
        return

    # It's a regular hook
    selected_hook_name = selected_value

    if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove hook '{selected_hook_name}'?"):
        hook_to_remove_index = None
        for i, project_hook_name in enumerate(current_project_data.GetCurrentBuildVersion().GetHookNames()):
            if selected_hook_name == project_hook_name:
                hook_to_remove_index = i
                break

        if hook_to_remove_index is not None:
            current_project_data.GetCurrentBuildVersion().hooks.pop(hook_to_remove_index)
            UpdateHooksListbox(current_project_data)
            ClearGuiHookData()
            print(f"Removed hook: {selected_hook_name}")
        else:
            messagebox.showerror("Error", f"Hook '{selected_hook_name}' not found in project data.")
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def ReloadGuiHookData(current_project_data: ProjectData):
    global _currently_selected_hook_name
    global _currently_selected_hook_index

    if _currently_selected_hook_index == -1:
        ClearGuiHookData()
        return

    hooks = current_project_data.GetCurrentBuildVersion().GetHooks()
    if not (0 <= _currently_selected_hook_index < len(hooks)):
        print(f"Error: Invalid hook index {_currently_selected_hook_index}. Clearing GUI.")
        ClearGuiHookData()
        return

    selected_hook = hooks[_currently_selected_hook_index]

    dpg.set_value("hook_name_detail_input", selected_hook.GetName())

    filenames = [os.path.basename(f) for f in selected_hook.GetCodeFilesPaths()]
    dpg.configure_item("hook_asm_files_listbox", items=filenames)

    game_files_for_combo = current_project_data.GetCurrentBuildVersion().GetInjectionFiles()
    
    if game_files_for_combo:
        dpg.configure_item("hook_target_game_file", items=game_files_for_combo)
    else:
        dpg.configure_item("hook_target_game_file", items=[""])
    
    current_injection_file = selected_hook.GetInjectionFile()
    
    if current_injection_file and current_injection_file not in game_files_for_combo:
        dpg.set_value("hook_target_game_file", "")
        print(f"Warning: Hook '{selected_hook.GetName()}' references missing file: {current_injection_file}")
    else:
        dpg.set_value("hook_target_game_file", current_injection_file or "")

    dpg.set_value("hook_address_in_memory", selected_hook.GetMemoryAddress())
    dpg.set_value("hook_size_of_region", selected_hook.GetSize())

    # Set disabled checkbox state (checkbox True = disabled)
    is_disabled = not selected_hook.IsEnabled()
    dpg.set_value("hook_disabled_checkbox", is_disabled)

    auto_calc_state = selected_hook.GetAutoCalculateInjectionFileAddress()
    dpg.set_value("hook_auto_calc_file_address_checkbox", auto_calc_state)
    dpg.configure_item("hook_injection_file_address_input", enabled=not auto_calc_state)

    if auto_calc_state:
        update_calculated_file_address(None, None, current_project_data)
    else:
        display_offset = selected_hook.GetInjectionFileAddress()
        dpg.set_value("hook_injection_file_address_input", display_offset)
        
        current_build = current_project_data.GetCurrentBuildVersion()
        memory_address = selected_hook.GetMemoryAddress()
        if memory_address:
            mem_addr_int = int(memory_address, 16)
            file_offset = current_build.GetFileOffsetForAddress(
                selected_hook.GetInjectionFile(),
                mem_addr_int
            )
            
            if file_offset:
                dpg.set_value("injection_file_address_input", f"{file_offset:X}")
                # # Optional: Show section info
                # section_info = current_build.GetSectionInfoForAddress(
                #     selected_hook.GetInjectionFile(),
                #     mem_addr_int
                # )
                # if section_info:
                #     print(f"  In {section_info['type']} section (0x{section_info['mem_start']:X} - 0x{section_info['mem_end']:X})")

    verbose_print(f"GUI Reloaded for Hook: {selected_hook.GetName()}")


def update_calculated_file_address(sender, app_data, current_project_data: ProjectData):
    """Calculate file address using section maps (NEW: Multi-section support)"""
    global _currently_selected_hook_index

    if _currently_selected_hook_index == -1:
        return

    selected_hook = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]

    if not selected_hook.GetAutoCalculateInjectionFileAddress():
        return

    memory_address_str = dpg.get_value("hook_address_in_memory")
    
    if not memory_address_str:
        dpg.set_value("hook_injection_file_address_input", "")
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
        injection_file = selected_hook.GetInjectionFile()
        
        if not injection_file:
            dpg.set_value("hook_injection_file_address_input", "NO FILE")
            return
        
        # Try section map first
        file_offset = current_build.GetFileOffsetForAddress(injection_file, memory_address_int)
        
        if file_offset is not None:
            # Success! Found in section map
            calculated_hex_string = f"{file_offset:X}"
            dpg.set_value("hook_injection_file_address_input", calculated_hex_string)
            
            # Show section info in console
            section_info = current_build.GetSectionInfoForAddress(injection_file, memory_address_int)
            if section_info:
                print(f"Address 0x{memory_address_int:X} found in {section_info['type']} section")
                print(f"  File offset: 0x{file_offset:X}")
            
        else:
            # Fallback to old offset method
            ram_offset_str = dpg.get_value("File Offset From Ram Input")
            
            if not ram_offset_str:
                dpg.set_value("hook_injection_file_address_input", "NO OFFSET")
                return
            
            ram_offset_int = int(ram_offset_str, 16)
            calculated_file_address_int = memory_address_int - ram_offset_int

            if calculated_file_address_int < 0:
                dpg.set_value("hook_injection_file_address_input", "INVALID")
                return

            calculated_hex_string = f"{calculated_file_address_int:X}"
            dpg.set_value("hook_injection_file_address_input", calculated_hex_string)
            print(f"Using fallback offset calculation (no section map)")

    except ValueError as e:
        dpg.set_value("hook_injection_file_address_input", "INVALID")
        print(f"Error in auto-calculation: {e}")

def callback_auto_calculate_file_address_checkbox(sender, app_data, current_project_data: ProjectData):
    global _currently_selected_hook_index

    if _currently_selected_hook_index == -1:
        messagebox.showinfo("Info", "No hook selected. Cannot change auto-calculate setting.")
        dpg.set_value("hook_auto_calc_file_address_checkbox", False) # Unique tag
        dpg.configure_item("hook_injection_file_address_input", enabled=True) # Unique tag
        return

    selected_hook = current_project_data.GetCurrentBuildVersion().GetHooks()[_currently_selected_hook_index]
    is_checked = app_data

    selected_hook.SetAutoCalculateInjectionFileAddress(is_checked)

    dpg.configure_item("hook_injection_file_address_input", enabled=not is_checked) # Unique tag

    if is_checked:
        update_calculated_file_address(sender, app_data, current_project_data)
    else:
        display_offset = selected_hook.GetInjectionFileAddress()
        dpg.set_value("hook_injection_file_address_input", display_offset) # Unique tag
        print("Auto-calculation disabled. Manual input enabled.")
        
        
def callback_auto_detect_hook(sender, app_data, current_project_data: ProjectData):
    """Auto-detect common hook patterns in the game executable"""
    from services.pattern_service import PatternService
    from tkinter import messagebox
    
    # Check if main executable is set
    current_build = current_project_data.GetCurrentBuildVersion()
    if not current_build.GetMainExecutable():
        messagebox.showerror("Error", "No main executable set. Please select game files first.")
        return
    
    # Validate tools first
    pattern_service = PatternService(current_project_data)
    platform = current_build.GetPlatform()
    tools_valid, error_msg = pattern_service.validate_tools(platform)
    
    if not tools_valid:
        response = messagebox.askyesno(
            "Missing Tools",
            f"{error_msg}\n\nContinue with fallback offset calculation?\n"
            "(Results may be inaccurate)"
        )
        if not response:
            return
    
    print("Starting hook pattern detection...")
    
    try:
        # Run synchronously - threading with DPG can cause issues
        matches = pattern_service.find_hook_patterns()
        
        if not matches:
            messagebox.showinfo(
                "No Patterns Found",
                "Could not automatically detect any known hook patterns.\n\n"
                "This might mean:\n"
                "• The game uses uncommon functions\n"
                "• The executable is compressed/encrypted\n"
                "• Manual hook placement is needed"
            )
            return
        
        print(f"Found {len(matches)} pattern(s)")
        
        # Show pattern selection dialog
        show_pattern_selection_dialog(matches, current_project_data)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error during pattern detection:\n{error_details}")
        messagebox.showerror("Error", f"Pattern detection failed: {str(e)}\n\n{error_details}")


def show_pattern_selection_dialog(matches, current_project_data: ProjectData):
    """Show dialog to select which pattern to use"""
    from services.pattern_service import PatternService
    from tkinter import messagebox
    
    if dpg.does_item_exist("pattern_selection_modal"):
        dpg.delete_item("pattern_selection_modal")
    
    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()
    modal_width = 800
    modal_height = 500
    modal_x = (viewport_width - modal_width) // 2
    modal_y = (viewport_height - modal_height) // 2
    
    with dpg.window(
        label="Auto-Detected Hook Patterns",
        modal=True,
        tag="pattern_selection_modal",
        no_move=True,
        no_resize=True,
        width=modal_width,
        height=modal_height,
        pos=[modal_x, modal_y]
    ):
        dpg.add_text(f"Found {len(matches)} hook pattern(s):")
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Create a table of patterns
        with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True,
                      borders_innerV=True, borders_outerV=True, row_background=True):
            dpg.add_table_column(label="Pattern", init_width_or_weight=3)
            dpg.add_table_column(label="Memory Address")
            dpg.add_table_column(label="File Offset")
            dpg.add_table_column(label="Select", init_width_or_weight=1)
            
            for i, match in enumerate(matches):
                with dpg.table_row():
                    dpg.add_text(match.pattern_name)
                    dpg.add_text(f"0x{match.memory_address:X}")
                    dpg.add_text(f"0x{match.file_offset:X}")
                    dpg.add_button(
                        label="Use Hook",
                        callback=callback_use_pattern,
                        user_data=(match, current_project_data)
                    )
                    dpg.bind_item_theme(dpg.last_item(), "add_as_cave_theme") # Purple
        
        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Cancel",
                callback=lambda: dpg.delete_item("pattern_selection_modal")
            )
            dpg.add_text("   Tip: Use the first pattern found for most reliable results", color=(150, 150, 150))


def callback_use_pattern(sender, app_data, user_data):
    """Use the selected pattern to create a hook"""
    global _currently_selected_hook_name
    global _currently_selected_hook_index
    from services.pattern_service import PatternService
    from tkinter import messagebox
    
    pattern_match, current_project_data = user_data
    
    print(f"Using pattern: {pattern_match.pattern_name}")
    
    # Check if hook already exists
    existing_hooks = current_project_data.GetCurrentBuildVersion().GetHookNames()

    build_name = current_project_data.GetCurrentBuildVersion().GetBuildName()
    
    hook_name = f"AutoHook_{build_name}"
    counter = 1
    while hook_name in existing_hooks:
        hook_name = f"AutoHook_{build_name}_{counter}"
        counter += 1
    
    print(f"Creating hook: {hook_name}")
    
    # Create hook from pattern
    pattern_service = PatternService(current_project_data)
    new_hook = pattern_service.create_hook_from_pattern(pattern_match, hook_name)
    
    # Set the injection file (main executable)
    main_exe = current_project_data.GetCurrentBuildVersion().GetMainExecutable()
    new_hook.SetInjectionFile(main_exe)
    
    # Add to project
    current_project_data.GetCurrentBuildVersion().AddHook(new_hook)
    print(f"Hook added to project: {hook_name}")
    
    # Update GUI
    UpdateHooksListbox(current_project_data)
    
    # Select the new hook
    _currently_selected_hook_name = hook_name
    _currently_selected_hook_index = current_project_data.GetCurrentBuildVersion().GetHookNames().index(hook_name)
    dpg.set_value("hooks_listbox", hook_name)
    
    ReloadGuiHookData(current_project_data)
    
    # Close modal
    if dpg.does_item_exist("pattern_selection_modal"):
        dpg.delete_item("pattern_selection_modal")
    
    # Show success message
    messagebox.showinfo(
        "Hook Created",
        f"Successfully created hook '{hook_name}'!\n\n"
        f"ASM File: asm/{hook_name}.s\n\n"
        f"Default behavior is jumping/branching to ModMain().\n"
        f"Edit {hook_name}.s for different behavior."
    )
    
    print(f" Created auto-detected hook: {hook_name}")
    print(f"  Pattern: {pattern_match.pattern_name}")
    print(f"  Memory: 0x{pattern_match.memory_address:X}")
    print(f"  File: 0x{pattern_match.file_offset:X}")
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()
    
def show_hook_getting_started_message(current_project_data: ProjectData):
    """Show a helpful message when no hooks exist"""
    if dpg.does_item_exist("hook_getting_started_group"):
        return  # Already showing
    
    with dpg.group(tag="hook_getting_started_group", parent="hook_injection_tab", before="hooks_listbox"):
        dpg.add_spacer(height=5)
        with dpg.group():
            dpg.add_text("No hooks yet for this build", color=(200, 200, 0))
            dpg.add_text("Auto-detect will find common every frame hook points", 
                        color=(150, 150, 150))
            dpg.add_button(
                label="Auto-Detect Hook",
                callback=callback_auto_detect_hook,
                user_data=current_project_data,
                width=280,
                height=26,
            )
        dpg.add_spacer(height=5)


def hide_hook_getting_started_message():
    """Hide the getting started message"""
    if dpg.does_item_exist("hook_getting_started_group"):
        dpg.delete_item("hook_getting_started_group")


def callback_import_multipatch(sender, app_data, current_project_data: ProjectData):
    """Import a multi-patch ASM file reference (doesn't create hooks until compilation)"""
    from services.asm_parser_service import ASMParserService
    from tkinter import messagebox, filedialog
    from classes.injection_targets.multipatch_asm import MultiPatchASM
    
    # Choose ASM file
    asm_file = filedialog.askopenfilename(
        title="Choose Multi-Patch ASM File",
        filetypes=[("Assembly Files", "*.s;*.asm"), ("All Files", "*.*")],
        initialdir=os.path.join(current_project_data.GetProjectFolder(), "asm")
    )
    
    if not asm_file:
        return
    
    # Check if it's actually a multi-patch file
    parser = ASMParserService(current_project_data)
    if not parser.is_multipatch_file(asm_file):
        messagebox.showwarning(
            "Not a Multi-Patch File",
            "This file doesn't contain any .memaddr directives.\n\n"
            "Multi-patch files should use the format:\n"
            ".memaddr 0x80123456\n"
            ".file SCUS.elf  # optional\n"
            ".fileaddr 0x1234  # optional\n"
            "nop\n"
            "\n"
            ".memaddr 0x80111222\n"
            "li $a0, 0x69"
        )
        return
    
    # Get base name from file
    base_name = os.path.splitext(os.path.basename(asm_file))[0]
    
    # Check if already imported
    existing_names = current_project_data.GetCurrentBuildVersion().GetMultiPatchNames()
    if base_name in existing_names:
        messagebox.showwarning(
            "Already Imported",
            f"Multi-patch '{base_name}' is already in the project.\n\n"
            f"To update it, just edit the .asm file - changes will be\n"
            f"automatically detected on next compilation."
        )
        return
    
    # Quick validation - try parsing
    try:
        patches = parser.parse_multipatch_asm(asm_file)
        if not patches:
            messagebox.showerror("Parse Failed", "Could not parse any patches from the file.")
            return
        
        print(f"Validated multi-patch file: {len(patches)} patch(es) found")
    except Exception as e:
        messagebox.showerror("Parse Failed", f"Error parsing file:\n\n{str(e)}")
        return
    
    # Create multi-patch reference
    multipatch = MultiPatchASM()
    multipatch.SetName(base_name)
    multipatch.SetFilePath(asm_file)
    
    # Add to project
    current_project_data.GetCurrentBuildVersion().AddMultiPatch(multipatch)
    
    # Update GUI
    UpdateHooksListbox(current_project_data)
    
    # Trigger auto-save
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()
    
    # Show success message
    messagebox.showinfo(
        "Multi-Patch Added",
        f"Successfully added multi-patch '{base_name}'!\n\n"
        f"• File: {os.path.basename(asm_file)}\n"
        f"• Patches: {len(patches)}\n\n"
        f"The file will be re-scanned on every compilation.\n"
        f"Edit the .asm file to add/remove/modify patches."
    )
    
    print(f"Added multi-patch: {base_name} ({len(patches)} patches)")
    
def show_multipatch_info(multipatch_name: str, current_project_data: ProjectData):
    """Show read-only info about a multi-patch"""
    from services.asm_parser_service import ASMParserService
    
    # Clear regular hook data
    ClearGuiHookData()
    
    # Find the multi-patch
    multipatches = current_project_data.GetCurrentBuildVersion().GetMultiPatches()
    multipatch = None
    for mp in multipatches:
        if mp.GetName() == multipatch_name:
            multipatch = mp
            break
    
    if not multipatch:
        print(f"Error: Multi-patch '{multipatch_name}' not found")
        return
    
    # Set the name field (read-only)
    dpg.set_value("hook_name_detail_input", f"{multipatch_name} (Multi-Patch)")
    
    # Parse the file to get info
    parser = ASMParserService(current_project_data)
    asm_file_path = multipatch.GetFilePath()
    
    if not os.path.exists(asm_file_path):
        dpg.configure_item("hook_asm_files_listbox", items=[f"ERROR: File not found: {asm_file_path}"])
        print(f"Warning: Multi-patch file not found: {asm_file_path}")
        return
    
    try:
        patches = parser.parse_multipatch_asm(asm_file_path)
        
        # Show file path in ASM files listbox
        file_display = [f"File: {os.path.basename(asm_file_path)}"]
        
        # Add patch info
        for i, patch in enumerate(patches, 1):
            target = patch.file_target if patch.file_target else "(main exe)"
            file_addr = f", file: {patch.file_offset}" if patch.file_offset else ""
            file_display.append(f"  Patch {i}: {patch.memory_address} -> {target}{file_addr}")
        
        dpg.configure_item("hook_asm_files_listbox", items=file_display)
        
        # Show message in target game file
        dpg.set_value("hook_target_game_file", f"{len(patches)} patch(es) - edit .asm file to modify")
        
        # Show info message
        dpg.set_value("hook_address_in_memory", "Multi-Patch")
        dpg.set_value("hook_injection_file_address_input", "Dynamic")
        dpg.set_value("hook_size_of_region", "Auto")
        
        print(f"Multi-patch info: {multipatch_name} ({len(patches)} patches)")
        
    except Exception as e:
        dpg.configure_item("hook_asm_files_listbox", items=[f"ERROR: {str(e)}"])
        print(f"Error parsing multi-patch: {e}")