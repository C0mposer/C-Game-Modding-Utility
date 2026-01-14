import dearpygui.dearpygui as dpg
from dpg.widget_themes import *

from classes.project_data.project_data import *
from gui.gui_main_project_callbacks import *

def CreateGameFilesGui(current_project_data):
    # Check if in single file mode
    current_build = current_project_data.GetCurrentBuildVersion()
    is_single_file = current_build.IsSingleFileMode()

    if is_single_file:
        dpg.add_text("Single File Mode - Modifying one file only", color=(100, 150, 255))
        dpg.add_text("DF = Disk File (from game folder)  |  EF = External File (from outside)",
                     color=(150, 150, 150))
    else:
        dpg.add_text("Choose files from the game that you want to modify.")
        dpg.add_text("DF = Disk File (from game folder)  |  EF = External File (from outside)",
                     color=(150, 150, 150))

    with dpg.group(horizontal=False):
        # Game files listbox
        dpg.add_listbox(
            tag="game_files_listbox",
            items=_get_formatted_file_list(current_project_data),
            callback=callback_game_file_selected,
            user_data=current_project_data,
            num_items=8,
            width=-1
        )

    with dpg.group(horizontal=True):
        # Only show "Add New File" button if project is not a single file project
        if not is_single_file:
            dpg.add_button(label="Add New File", tag="Add New File",
                          callback=callback_add_file_to_inject_into,
                          user_data=current_project_data)
        else:
            # Show disabled button if sinlge file
            dpg.add_button(label="Add New File", tag="Add New File",
                          enabled=False)
            with dpg.tooltip("Add New File"):
                dpg.add_text("Cannot add files in Single File Mode", color=(255, 150, 150))
                dpg.add_text("This project is configured to modify only one file",
                           color=(150, 150, 150))

        dpg.add_button(label="Delete Selected File", tag="Delete Selected File To Inject Into",
                      callback=callback_delete_selected_file_to_inject_into,
                      user_data=current_project_data,
                      enabled=not is_single_file)  # Disable delete in single file mode

    dpg.add_separator()
    dpg.add_spacer(height=10)
    
    # Section Map
    dpg.add_text("File Sections / Offset", tag="section_info_header")
    
    # Container for section map
    with dpg.group(tag="section_info_container"):
        dpg.add_text("Select a file to view section information", color=(150, 150, 150))


def _get_formatted_file_list(current_project_data: ProjectData) -> list:
    current_build = current_project_data.GetCurrentBuildVersion()
    formatted_items = []
    main_exe = current_build.GetMainExecutable()
    
    for filename in current_build.GetInjectionFiles():
        file_type = current_build.GetInjectionFileType(filename)
        
        # Determine indicator
        if file_type == "disk":
            prefix = "[DF]"
        else:  # external
            prefix = "[EF]"
        
        # Add (Main) if it's the main executable (scus, main.dol, etc)
        if filename == main_exe:
            formatted_items.append(f"{prefix} {filename} (Main)")
        else:
            formatted_items.append(f"{prefix} {filename}")
    
    return formatted_items


def _get_filename_from_formatted(formatted_string: str) -> str:
    # Remove the prefix [DF] or [EF]
    without_prefix = formatted_string.split("] ", 1)[-1]
    
    # Remove (Main) suffix
    filename = without_prefix.replace(" (Main)", "").strip()
    
    return filename


def _update_game_files_listbox(current_project_data: ProjectData):
    if dpg.does_item_exist("game_files_listbox"):
        formatted_items = _get_formatted_file_list(current_project_data)
        dpg.configure_item("game_files_listbox", items=formatted_items)
        
        # Clear
        dpg.set_value("game_files_listbox", "")


def callback_game_file_selected(sender, app_data, current_project_data: ProjectData):
    if not app_data:
        return
    
    # Extract actual filename
    filename = _get_filename_from_formatted(app_data)
    
    # Store selected filename
    global _selected_game_file
    _selected_game_file = filename
    
    # Get file type and section info
    current_build = current_project_data.GetCurrentBuildVersion()
    file_type = current_build.GetInjectionFileType(filename)
    
    # Display section information 
    _update_section_display(current_project_data, filename, file_type)


def _update_section_display(current_project_data: ProjectData, filename: str, file_type: str):
    current_build = current_project_data.GetCurrentBuildVersion()
    
    # Clear
    if dpg.does_item_exist("section_info_container"):
        dpg.delete_item("section_info_container", children_only=True)
    else:
        with dpg.group(tag="section_info_container", before="save_offset_button"):
            pass
    
    # Check if sections exist (Some games have really weird outputs from objdump, which may make a section map not be saved correctly)
    has_sections = filename in current_build.section_maps
    
    if has_sections:
        sections = current_build.section_maps[filename]
        
        # Display
        with dpg.group(parent="section_info_container"):
            dpg.add_text(f"File: {filename} ({file_type})", color=(100, 200, 255))
            dpg.add_text(f"Sections: {len(sections)}", color=(150, 150, 150))
            dpg.add_spacer(height=5)
            
            # Table for sections
            with dpg.table(header_row=True, borders_innerH=True, borders_outerH=True,
                          borders_innerV=True, borders_outerV=True, row_background=True,
                          scrollY=True, height=200):
                # Columns
                dpg.add_table_column(label="Type", width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(label="Memory Range", width_fixed=True, init_width_or_weight=180)
                dpg.add_table_column(label="File Offset", width_fixed=True, init_width_or_weight=100)
                dpg.add_table_column(label="Size", width_fixed=True, init_width_or_weight=100)
                dpg.add_table_column(label="Offset Diff", width_fixed=True, init_width_or_weight=100)
                
                # Rows
                for i, section in enumerate(sections):
                    with dpg.table_row():
                        # Type
                        type_color = _get_section_type_color(section.section_type)
                        dpg.add_text(section.section_type.upper(), color=type_color)
                        
                        # Memory Range
                        dpg.add_text(f"0x{section.mem_start:X} - 0x{section.mem_end:X}")
                        
                        # File Offset
                        dpg.add_text(f"0x{section.file_offset:X}")
                        
                        # Size
                        dpg.add_text(f"0x{section.size:X}")
                        
                        # Offset Diff
                        dpg.add_text(f"0x{section.offset_diff:X}")
            
            dpg.add_spacer(height=10)
            dpg.add_text("Offset calculated automatically from sections", 
                        color=(100, 255, 100), tag="section_auto_calc_note")
    
    else:
        # Check if this file type should even have sections
        platform = current_build.GetPlatform()
        could_have_sections = _is_file_supported_for_sections(filename, platform)
        
        # Fallback: Hard-coded offset
        with dpg.group(parent="section_info_container"):
            dpg.add_text(f"File: {filename} ({file_type})", color=(100, 200, 255))
            
            if could_have_sections:
                dpg.add_text("Section map not built yet", color=(255, 200, 100))
                dpg.add_spacer(height=5)
                dpg.add_button(
                    label="Build Section Map",
                    callback=callback_build_section_map_for_file,
                    user_data=(current_project_data, filename)
                )
                dpg.add_spacer(height=10)
            else:
                dpg.add_text("No section map available - using single offset", color=(150, 150, 150))
            
            dpg.add_spacer(height=10)
            
            # Single offset input
            dpg.add_text("Enter file offset from RAM")
            with dpg.group(horizontal=True):
                dpg.add_text("0x")
                offset = current_build.GetInjectionFileOffset(filename)
                dpg.add_input_text(
                    tag="File Offset From Ram Input", 
                    hint="123", 
                    hexadecimal=True, 
                    default_value=offset if offset else "",
                    width=200
                )
            
            dpg.add_spacer(height=5)
            dpg.add_button(
                label="Save Offset", 
                tag="save_offset_button",
                callback=callback_save_offset, 
                user_data=current_project_data
            )


def _get_section_type_color(section_type: str) -> tuple:
    color_map = {
        "text": (100, 255, 100), 
        "data": (255, 200, 100),
        "rodata": (100, 200, 255),
        "bss": (255, 100, 255),
        "unknown": (150, 150, 150)
    }
    return color_map.get(section_type.lower(), (255, 255, 255))


def callback_add_file_to_inject_into(sender, app_data, current_project_data: ProjectData):
    #print("Add Game File button clicked")
    
    game_file_path = filedialog.askopenfilename(
        title="Choose Target Game File",
        initialdir=current_project_data.GetCurrentBuildVersion().GetGameFolder()
    )
    
    if not game_file_path:
        verbose_print("File selection cancelled.")
        return

    # Automatically determine file type
    current_project_data.GetCurrentBuildVersion().AddInjectionFile(game_file_path)
    
    # Auto-build section map for supported file types
    filename = os.path.basename(game_file_path)
    _auto_build_section_map_if_supported(current_project_data, filename, game_file_path)

    # Update the listbox
    _update_game_files_listbox(current_project_data)

    # Update other GUI elements
    CInjectionChangeGameFiles(current_project_data.GetCurrentBuildVersion().GetInjectionFiles())
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()


def callback_delete_selected_file_to_inject_into(sender, app_data, current_project_data: ProjectData):
    global _selected_game_file
    
    if not _selected_game_file:
        messagebox.showinfo("No Selection", "Please select a file from the list first.")
        return
    
    # Ask for confirmation
    response = messagebox.askyesno(
        "Delete Game File",
        f"Remove '{_selected_game_file}' from injection list?\n\n"
        f"This will also clear file references in codecaves, hooks, and patches."
    )
    
    if not response:
        return
    
    print(f"Deleting: {_selected_game_file}")
    
    # Clear file references in all injection targets
    _clear_file_references_in_targets(current_project_data, _selected_game_file)
    
    # Remove the file from target game files
    current_project_data.GetCurrentBuildVersion().RemoveInjectionFile(_selected_game_file)
    
    # Update listbox
    _update_game_files_listbox(current_project_data)
    
    # Clear selection
    _selected_game_file = None
    
    # Clear section display
    if dpg.does_item_exist("section_info_container"):
        dpg.delete_item("section_info_container", children_only=True)
        with dpg.group(parent="section_info_container"):
            dpg.add_text("Select a file to view section information", color=(150, 150, 150))
    
    # Update other GUI elements
    CInjectionChangeGameFiles(current_project_data.GetCurrentBuildVersion().GetInjectionFiles())
    
    # Update codecave/hook/patch GUIs
    from gui.gui_c_injection import ReloadGuiCodecaveData
    from gui.gui_asm_injection import ReloadGuiHookData
    from gui.gui_binary_patch_injection import ReloadGuiBinaryPatchData
    
    ReloadGuiCodecaveData(current_project_data)
    ReloadGuiHookData(current_project_data)
    ReloadGuiBinaryPatchData(current_project_data)
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

def _clear_file_references_in_targets(current_project_data: ProjectData, file_name: str):
    current_build = current_project_data.GetCurrentBuildVersion()
    
    cleared_count = 0
    
    # Clear from codecaves
    for codecave in current_build.GetCodeCaves():
        if codecave.GetInjectionFile() == file_name:
            codecave.SetInjectionFile("")
            codecave.SetInjectionFileAddress("")
            cleared_count += 1
            verbose_print(f"  Cleared file reference from codecave: {codecave.GetName()}")
    
    # Clear from hooks
    for hook in current_build.GetHooks():
        if hook.GetInjectionFile() == file_name:
            hook.SetInjectionFile("")
            hook.SetInjectionFileAddress("")
            cleared_count += 1
            verbose_print(f"  Cleared file reference from hook: {hook.GetName()}")
    
    # Clear from binary patches
    for patch in current_build.GetBinaryPatches():
        if patch.GetInjectionFile() == file_name:
            patch.SetInjectionFile("")
            patch.SetInjectionFileAddress("")
            cleared_count += 1
            verbose_print(f"  Cleared file reference from patch: {patch.GetName()}")
    
    if cleared_count > 0:
        verbose_print(f"Cleared {cleared_count} reference(s) to '{file_name}'")
    else:
        verbose_print(f"  No references to '{file_name}' found")

def listbox_selection_callback(sender, selected_file_name, current_project_data: ProjectData):
    verbose_print(f"Listbox selection changed. Selected: {selected_file_name}")
    if selected_file_name:
        # Get the offset
        offset = current_project_data.GetCurrentBuildVersion().GetInjectionFileOffset(selected_file_name)
        # Update the input text field
        dpg.set_value("File Offset From Ram Input", offset)
    else:
        dpg.set_value("File Offset From Ram Input", "")
        
def callback_save_offset(sender, app_data, current_project_data: ProjectData):
    global _selected_game_file
    
    if not _selected_game_file:
        messagebox.showinfo("No Selection", "Please select a file first.")
        return
    
    offset_value = dpg.get_value("File Offset From Ram Input")
    
    if not offset_value:
        messagebox.showinfo("No Offset", "Please enter an offset value.")
        return
    
    # Save the offset
    current_project_data.GetCurrentBuildVersion().SetInjectionFileOffset(_selected_game_file, offset_value)
    
    print(f"Saved offset 0x{offset_value} for {_selected_game_file}")
    
    from gui.gui_main_project import trigger_auto_save
    trigger_auto_save()

# Global to track selected file
_selected_game_file = None

def reset_game_files_state():
    global _selected_game_file
    _selected_game_file = None

def _auto_build_section_map_if_supported(current_project_data: ProjectData, filename: str, file_path: str):
    current_build = current_project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()
    
    # Check if section map already exists
    if filename in current_build.section_maps:
        verbose_print(f"  Section map already exists for {filename}")
        return
    
    # Determine if file is supported
    is_supported = False
    file_lower = filename.lower()
    
    # GameCube/Wii DOL files
    if file_lower.endswith('.dol') and platform in ["Gamecube", "Wii"]:
        is_supported = True
        verbose_print(f"  Detected {platform} DOL file: {filename}")
    
    # PS2 ELF files (Maybe include any extension eventually, because I think some ps2 games might have elfs, with a different extension? Need to do more research on this)
    elif file_lower.endswith('.elf') and platform == "PS2":
        is_supported = True
        verbose_print(f"  Detected PS2 ELF file: {filename}")
    
    # PS1 executables (I don't think there are any tools that can parse PS1 exe's in the same way, since they really are stripped to the bone of anything other than a header, and the raw data.)
    elif platform == "PS1":
        filename_upper = filename.upper()
        ps1_prefixes = ["SCUS", "SCES", "SLUS", "SLES", "SCPS", "SLPS"]
        if any(filename_upper.startswith(prefix) for prefix in ps1_prefixes):
            # PS1 detected, but we don't build section maps for it
            verbose_print(f"  Detected PS1 executable: {filename}, no section map")
            return
    
    if not is_supported:
        return
    
    # Build section map
    verbose_print(f"  Building section map for {filename}...")
    success = current_build.BuildSectionMapForFile(filename)
    
    if success:
        section_count = len(current_build.section_maps[filename])
        verbose_print(f"  Built section map: {section_count} section(s)")
    else:
        verbose_print(f"  Failed to build section map")


def _is_file_supported_for_sections(filename: str, platform: str) -> bool:
    file_lower = filename.lower()
    filename_upper = filename.upper()
    
    # GameCube/Wii DOL files
    if file_lower.endswith('.dol') and platform in ["Gamecube", "Wii"]:
        return True
    
    # PS2 ELF files
    if platform == "PS2":
        ps2_prefixes = ["SCUS", "SCES", "SLUS", "SLES"] # My current hack for allowing some other files that may not end in elf
        if file_lower.endswith('.elf') or any(filename_upper.startswith(prefix) for prefix in ps2_prefixes):
            return True
    
    return False

def callback_build_section_map_for_file(sender, app_data, user_data):
    current_project_data, filename = user_data
    current_build = current_project_data.GetCurrentBuildVersion()
    
    print(f"\nBuilding section map for: {filename}")
    
    # Build the section map
    success = current_build.BuildSectionMapForFile(filename)
    
    if success:
        from gui import gui_messagebox as messagebox
        
        # Get section count
        section_count = len(current_build.section_maps.get(filename, []))
        
        messagebox.showinfo("Section Map Built", f"File offsets will now be calculated automatically from memory addresses.")
        
        verbose_print(f"Built section map: {section_count} section(s)")
        
        # Refresh
        _update_section_display(current_project_data, filename, 
                               current_build.GetInjectionFileType(filename))
        
        # Trigger auto-save
        from gui.gui_main_project import trigger_auto_save
        trigger_auto_save()
    else:
        from gui import gui_messagebox as messagebox
        
        messagebox.showerror(
            "Section Map Failed", f"Could not build section map for {filename}.\n\n")
        
        verbose_print(f"Failed to build section map for {filename}")