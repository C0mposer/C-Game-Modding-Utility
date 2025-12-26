# gui/gui_project_wizard.py
"""
Project Creation Wizard - Step-by-step guided project setup

Replaces the old create_project flow with a more intuitive wizard interface.
Guides users through:
  1. Naming the project
  2. Choosing platform
  3. Selecting input mode (extract ISO, existing folder, or single file)
  4. Selecting the file/folder

Usage:
    from gui.gui_project_wizard import show_project_wizard
    show_project_wizard()
"""

import dearpygui.dearpygui as dpg
from tkinter import filedialog
from gui import gui_messagebox as messagebox
import os
from typing import Optional

from classes.project_data.project_data import ProjectData
from services.project_serializer import ProjectSerializer
from services.iso_service import ISOService
from services.template_service import TemplateService
from services.ghidra_pattern_service import GhidraPatternService
from gui.gui_loading_indicator import LoadingIndicator
from gui.gui_prereq_prompt import check_and_prompt_prereqs
from functions.verbose_print import verbose_print
from path_helper import get_application_directory

class ProjectWizardState:
    """Holds the state of the wizard"""
    def __init__(self):
        self.project_name: str = ""
        self.platform: str = ""
        self.file_mode: str = ""  # "extract_iso", "existing_folder", "single_file"
        self.selected_file_path: str = ""
        self.extracted_folder: str = ""
        self.current_step: int = 1
        self.total_steps: int = 4

_wizard_state = ProjectWizardState()

def show_project_wizard():
    """Entry point - creates and shows the wizard window"""
    global _wizard_state
    _wizard_state = ProjectWizardState()  # Reset state
    
    # Delete existing windows
    if dpg.does_item_exist("project_wizard_window"):
        dpg.delete_item("project_wizard_window")
    if dpg.does_item_exist("startup_window"):
        dpg.delete_item("startup_window")
    
    # Create wizard window
    with dpg.window(
        label="New Project Wizard",
        tag="project_wizard_window",
        width=700,
        height=500,
        no_move=True,
        no_resize=True,
        no_collapse=True,
        modal=False
    ):
        # Progress indicator at top
        with dpg.group(tag="wizard_progress_group", horizontal=True):
            dpg.add_text("Step 1 of 4", tag="wizard_progress_text")
        
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Content area (will be dynamically updated)
        with dpg.group(tag="wizard_content_group"):
            _render_step_1()
        
        dpg.add_spacer(height=20)
        dpg.add_separator()
        
        # Navigation buttons at bottom
        with dpg.group(tag="wizard_nav_group", horizontal=True):
            dpg.add_button(
                label="Back",
                tag="wizard_back_button",
                callback=_on_back_clicked,
                show=False,
                width=100
            )
            dpg.add_spacer(width=400)
            dpg.add_button(
                label="Cancel",
                tag="wizard_cancel_button",
                callback=_on_cancel_clicked,
                width=100
            )
            dpg.add_button(
                label="Next",
                tag="wizard_next_button",
                callback=_on_next_clicked,
                width=110
            )
    
    dpg.set_primary_window("project_wizard_window", True)

# ==================== STEP RENDERING ====================

def _render_step_1():
    """Step 1: Project Name"""
    global _wizard_state
    
    with dpg.group(parent="wizard_content_group"):
        dpg.add_text("Step 1: Name Your Project", color=(100, 150, 255))
        dpg.add_spacer(height=10)
        
        dpg.add_text("Choose a name for your modding project:")
        dpg.add_spacer(height=5)
        
        dpg.add_input_text(
            tag="wizard_project_name_input",
            hint="e.g., MyAwesomeMod",
            default_value=_wizard_state.project_name,
            width=400
        )
        
        dpg.add_spacer(height=10)
        dpg.add_text(
            "This will create a folder in the 'projects/' directory.",
            color=(150, 150, 150)
        )

def _render_step_2():
    """Step 2: Platform Selection"""
    global _wizard_state
    
    with dpg.group(parent="wizard_content_group"):
        dpg.add_text("Step 2: Choose Platform", color=(100, 150, 255))
        dpg.add_spacer(height=10)
        
        dpg.add_text("Select the gaming platform you're modding:")
        dpg.add_spacer(height=10)
        
        # Platform buttons in a grid
        platforms = [
            ("PS1", "PlayStation 1", ""),
            ("PS2", "PlayStation 2", ""),
            ("Gamecube", "Nintendo GameCube", ""),
            ("Wii", "Nintendo Wii", ""),
            ("N64", "Nintendo 64", "")
        ]
        
        for i, (platform_id, platform_name, icon) in enumerate(platforms):
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label=f"{icon} {platform_name}",
                    width=300,
                    height=50,
                    callback=lambda s, a, u: _on_platform_selected(u),
                    user_data=platform_id
                )
                
                # Show checkmark if selected
                if _wizard_state.platform == platform_id:
                    dpg.add_text("Selected", color=(100, 255, 100))
            
            if i < len(platforms) - 1:
                dpg.add_spacer(height=5)

def _render_step_3():
    """Step 3: File Mode Selection"""
    global _wizard_state
    
    with dpg.group(parent="wizard_content_group"):
        dpg.add_text("Step 3: Choose Input Mode", color=(100, 150, 255))
        dpg.add_spacer(height=10)
        
        dpg.add_text(f"Platform: {_wizard_state.platform}", color=(150, 150, 150))
        dpg.add_spacer(height=10)
        
        dpg.add_text("How do you want to provide the game files?")
        dpg.add_spacer(height=10)
        
        # Different options based on platform
        if _wizard_state.platform in ["PS1", "PS2", "Gamecube", "Wii"]:
            # Option 1: Extract ISO
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Extract ISO File",
                    width=300,
                    height=50,
                    callback=lambda: _on_file_mode_selected("extract_iso")
                )
                if _wizard_state.file_mode == "extract_iso":
                    dpg.add_text("Selected", color=(100, 255, 100))
            
            dpg.add_text("   Extract game files from an ISO/BIN image", 
                        color=(150, 150, 150))
            dpg.add_spacer(height=10)
            
            # Option 2: Use existing folder
            if _wizard_state.platform in ["PS2", "Gamecube", "Wii"]:
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Use Extracted Folder",
                        width=300,
                        height=50,
                        callback=lambda: _on_file_mode_selected("existing_folder")
                    )
                    if _wizard_state.file_mode == "existing_folder":
                        dpg.add_text("Selected", color=(100, 255, 100))
                
                dpg.add_text("   Use game files you've already extracted", 
                            color=(150, 150, 150))
                dpg.add_spacer(height=10)
        
        # Option 3: Single file (available for all platforms)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Single File (No ISO)",
                width=300,
                height=50,
                callback=lambda: _on_file_mode_selected("single_file")
            )
            if _wizard_state.file_mode == "single_file":
                dpg.add_text("Selected", color=(100, 255, 100))
        
        dpg.add_text("   Modify a single game file/executable (skip ISO rebuilding)", 
                    color=(150, 150, 150))

def _render_step_4():
    """Step 4: File Selection"""
    global _wizard_state
    
    with dpg.group(parent="wizard_content_group"):
        dpg.add_text("Step 4: Select File/Folder", color=(100, 150, 255))
        dpg.add_spacer(height=10)
        
        dpg.add_text(f"Platform: {_wizard_state.platform}", color=(150, 150, 150))
        dpg.add_text(f"Mode: {_get_file_mode_display()}", color=(150, 150, 150))
        dpg.add_spacer(height=10)
        
        if _wizard_state.file_mode == "extract_iso":
            dpg.add_text("Click 'Browse' to select the ISO/BIN file to extract:")
            dpg.add_spacer(height=5)

            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag="wizard_file_path_input",
                    default_value=_wizard_state.selected_file_path,
                    width=500,
                    readonly=True
                )
                dpg.add_button(
                    label="Browse...",
                    callback=_on_browse_iso_clicked
                )

            # Add hint for PS1 multi-bin games
            if _wizard_state.platform == "PS1":
                dpg.add_spacer(height=5)
                dpg.add_text("Tip: For multi-bin PS1 games, select the .cue file", color=(150, 150, 150), wrap=600)
        
        elif _wizard_state.file_mode == "existing_folder":
            dpg.add_text("Click 'Browse' to select the extracted game folder:")
            dpg.add_spacer(height=5)
            
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag="wizard_file_path_input",
                    default_value=_wizard_state.selected_file_path,
                    width=500,
                    readonly=True
                )
                dpg.add_button(
                    label="Browse...",
                    callback=_on_browse_folder_clicked
                )
        
        elif _wizard_state.file_mode == "single_file":
            dpg.add_text("Click 'Browse' to select the game executable:")
            dpg.add_spacer(height=5)
            
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag="wizard_file_path_input",
                    default_value=_wizard_state.selected_file_path,
                    width=500,
                    readonly=True
                )
                dpg.add_button(
                    label="Browse...",
                    callback=_on_browse_single_file_clicked
                )
        
        # Show selected file info
        if _wizard_state.selected_file_path:
            dpg.add_spacer(height=10)
            dpg.add_text("Selected:", color=(100, 255, 100))
            dpg.add_text(f"  {os.path.basename(_wizard_state.selected_file_path)}")
            
            if os.path.exists(_wizard_state.selected_file_path):
                if os.path.isfile(_wizard_state.selected_file_path):
                    size_mb = os.path.getsize(_wizard_state.selected_file_path) / (1024 * 1024)
                    dpg.add_text(f"  Size: {size_mb:.1f} MB", color=(150, 150, 150))

# ==================== NAVIGATION ====================

def _update_wizard_ui():
    """Update the wizard UI for the current step"""
    global _wizard_state
    
    # Update progress text
    dpg.set_value("wizard_progress_text", 
                  f"Step {_wizard_state.current_step} of {_wizard_state.total_steps}")
    
    # Update back button visibility
    dpg.configure_item("wizard_back_button", show=(_wizard_state.current_step > 1))
    
    # Update next button text
    if _wizard_state.current_step == _wizard_state.total_steps:
        dpg.set_item_label("wizard_next_button", "Create Project")
    else:
        dpg.set_item_label("wizard_next_button", "Next")
    
    # Clear and re-render content
    if dpg.does_item_exist("wizard_content_group"):
        dpg.delete_item("wizard_content_group")
    
    with dpg.group(tag="wizard_content_group", before="wizard_nav_group"):
        if _wizard_state.current_step == 1:
            _render_step_1()
        elif _wizard_state.current_step == 2:
            _render_step_2()
        elif _wizard_state.current_step == 3:
            _render_step_3()
        elif _wizard_state.current_step == 4:
            _render_step_4()

def _on_next_clicked():
    """Handle Next button click"""
    global _wizard_state
    
    # Validate current step
    if not _validate_current_step():
        return
    
    # Save data from current step
    if _wizard_state.current_step == 1:
        _wizard_state.project_name = dpg.get_value("wizard_project_name_input")
    
    # Last step - create project
    if _wizard_state.current_step == _wizard_state.total_steps:
        _create_project()
        return
    
    # Move to next step
    _wizard_state.current_step += 1
    _update_wizard_ui()

def _on_back_clicked():
    """Handle Back button click"""
    global _wizard_state
    
    if _wizard_state.current_step > 1:
        _wizard_state.current_step -= 1
        _update_wizard_ui()

def _on_cancel_clicked():
    """Handle Cancel button click"""
    from gui.gui_startup_window import InitMainWindow
    
    response = messagebox.askyesno(
        "Cancel Project Creation",
        "Are you sure you want to cancel?\n\nAll progress will be lost."
    )
    
    if response:
        dpg.delete_item("project_wizard_window")
        InitMainWindow()
        dpg.set_primary_window("startup_window", True)

# ==================== VALIDATION ====================

def _validate_current_step() -> bool:
    """Validate the current step before proceeding"""
    global _wizard_state
    
    if _wizard_state.current_step == 1:
        # Validate project name
        name = dpg.get_value("wizard_project_name_input").strip()
        if not name:
            messagebox.showerror("Invalid Name", "Please enter a project name.")
            return False
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(c in name for c in invalid_chars):
            messagebox.showerror("Invalid Name", 
                "Project name contains invalid characters.\n\n" +
                "Avoid: / \\ : * ? \" < > |")
            return False
        
        # Check if project already exists
        project_path = os.path.join("projects", name)
        if os.path.exists(project_path):
            response = messagebox.askyesno("Project Exists",
                f"A project named '{name}' already exists.\n\n" +
                "Do you want to overwrite it?")
            if not response:
                return False
        
        return True
    
    elif _wizard_state.current_step == 2:
        # Validate platform selection
        if not _wizard_state.platform:
            messagebox.showerror("No Platform", "Please select a platform.")
            return False
        return True
    
    elif _wizard_state.current_step == 3:
        # Validate file mode selection
        if not _wizard_state.file_mode:
            messagebox.showerror("No Mode", "Please select an input mode.")
            return False
        return True
    
    elif _wizard_state.current_step == 4:
        # Validate file/folder selection
        if not _wizard_state.selected_file_path:
            messagebox.showerror("No File", "Please select a file or folder.")
            return False
        
        if not os.path.exists(_wizard_state.selected_file_path):
            messagebox.showerror("File Not Found", 
                "The selected file or folder no longer exists.")
            return False
        
        return True
    
    return True

# ==================== CALLBACKS ====================

def _on_platform_selected(platform: str):
    """Handle platform selection"""
    global _wizard_state

    # Check prerequisites when platform is selected
    tool_dir = get_application_directory()

    if not check_and_prompt_prereqs(tool_dir, platform, None):
        # User cancelled download - don't change platform selection
        return

    _wizard_state.platform = platform
    _update_wizard_ui()

def _on_file_mode_selected(mode: str):
    """Handle file mode selection"""
    global _wizard_state
    _wizard_state.file_mode = mode
    _update_wizard_ui()

def _on_browse_iso_clicked():
    """Browse for ISO file"""
    global _wizard_state
    
    # Platform-specific file types
    if _wizard_state.platform == "PS1":
        filetypes = [("PS1 Images", "*.bin;*.cue"), ("All Files", "*.*")]
        title = "Choose PS1 BIN/CUE File (use .cue for multi-bin games)"
    elif _wizard_state.platform == "PS2":
        filetypes = [("PS2 ISO", "*.iso"), ("All Files", "*.*")]
        title = "Choose PS2 ISO File"
    elif _wizard_state.platform == "Gamecube":
        filetypes = [("GameCube Images", "*.iso;*.gcm;*.nkit.iso;*.iso;*.rvz"), ("All Files", "*.*")]
        title = "Choose GameCube ISO/RVZ File"
    elif _wizard_state.platform == "Wii":
        filetypes = [("Wii Images", "*.iso;*.wbfs;*.nkit.iso;*.rvz"), ("All Files", "*.*")]
        title = "Choose Wii ISO/WBFS/RVZ File"
    else:
        filetypes = [("All Files", "*.*")]
        title = "Choose ISO File"
    
    file_path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    
    if file_path:
        _wizard_state.selected_file_path = file_path
        dpg.set_value("wizard_file_path_input", file_path)

def _on_browse_folder_clicked():
    """Browse for extracted folder"""
    global _wizard_state
    
    folder_path = filedialog.askdirectory(
        title=f"Choose Extracted {_wizard_state.platform} Folder"
    )
    
    if folder_path:
        _wizard_state.selected_file_path = folder_path
        dpg.set_value("wizard_file_path_input", folder_path)

def _on_browse_single_file_clicked():
    """Browse for single executable file"""
    global _wizard_state
    
    # Platform-specific file types
    if _wizard_state.platform == "PS1":
        filetypes = [("PS1 Executables", "SCUS*;SCES*;SLUS*;SLES*"), ("All Files", "*.*")]
    elif _wizard_state.platform == "PS2":
        filetypes = [("PS2 Executables", "SCUS*;SCES*"), ("ELF Files", "*.elf"), ("All Files", "*.*")]
    elif _wizard_state.platform in ["Gamecube", "Wii"]:
        filetypes = [("DOL Files", "*.dol"), ("All Files", "*.*")]
    elif _wizard_state.platform == "N64":
        filetypes = [("N64 ROMs", "*.n64;*.z64;*.v64"), ("All Files", "*.*")]
    else:
        filetypes = [("All Files", "*.*")]
    
    file_path = filedialog.askopenfilename(
        title=f"Choose {_wizard_state.platform} Executable",
        filetypes=filetypes
    )
    
    if file_path:
        _wizard_state.selected_file_path = file_path
        dpg.set_value("wizard_file_path_input", file_path)

# ==================== PROJECT CREATION ====================

def _create_project():
    """Create the project with the wizard settings"""
    global _wizard_state

    LoadingIndicator.show("Creating project...")

    # Import verbose checking
    from functions.verbose_print import is_verbose

    # Print condensed header for normal mode
    if not is_verbose:
        print("\nCreating Project:")

    def create_async():
        try:
            # Create project data
            project_data = ProjectData()
            project_data.SetProjectName(_wizard_state.project_name)
            project_data.SetDefaultNewProjectData()
            project_data.SetProjectFolder(_wizard_state.project_name)

            # Set platform
            current_build = project_data.GetCurrentBuildVersion()
            current_build.SetPlatform(_wizard_state.platform)
            
            if current_build.platform == "PS2":
                current_build.compiler_flags = "-O2 -fsingle-precision-constant"  # Default flags for PS2. Always use floats if PS2. Might need to change, because unsure if double support is needed, but
                                                                                  # The problem is it tries to link to libraries like fptodp, dpadd, dptofp, etc.
            # Handle file/folder based on mode
            if _wizard_state.file_mode == "extract_iso":
                _handle_iso_extraction(project_data)
            elif _wizard_state.file_mode == "existing_folder":
                _handle_existing_folder(project_data)
            elif _wizard_state.file_mode == "single_file":
                _handle_single_file(project_data)

            # Scan for OS library function patterns (PS1/PS2 only)
            if _wizard_state.platform in ["PS1", "PS2"]:
                #_scan_for_ghidra_patterns(project_data)
                pass

            # Save project
            save_success = ProjectSerializer.save_project(project_data)

            # Add to recent projects immediately
            if save_success:
                try:
                    from services.recent_projects_service import RecentProjectsService

                    project_name = project_data.GetProjectName()
                    project_folder = project_data.GetProjectFolder()
                    platform = project_data.GetCurrentBuildVersion().GetPlatform()

                    # Calculate file path (same logic as save_project)
                    project_file_path = os.path.join(project_folder, f"{project_name}{ProjectSerializer.PROJECT_FILE_EXTENSION}")

                    RecentProjectsService.add_recent_project(project_file_path, project_name, platform)
                except Exception as e:
                    print(f"Warning: Failed to add new project to recent list: {e}")

            # Print condensed completion message for normal mode
            if not is_verbose:
                print("Project Saved")
            
            # Update UI on main thread - THIS is the key part
            def update_ui():
                LoadingIndicator.hide()
                
                # Close wizard
                dpg.delete_item("project_wizard_window")
                
                # Open project
                from gui.gui_main_project import InitMainProjectWindowWithData
                InitMainProjectWindowWithData(project_data)
                
                # Show PS1 template prompt AFTER success message, with delay
                if _wizard_state.platform == "PS1":
                    def show_template_delayed():
                        import time
                        time.sleep(0.1)
                        from services.template_service import show_ps1_template_prompt
                        show_ps1_template_prompt(project_data)
                    
                    import threading
                    threading.Thread(target=show_template_delayed, daemon=True).start()
            
            # Schedule UI update on next frame
            dpg.split_frame(delay=1)
            dpg.set_frame_callback(dpg.get_frame_count() + 1, update_ui)
            
        except Exception as ex:
            # Capture the exception immediately before creating nested functions
            import traceback
            error_msg = str(ex)
            error_trace = traceback.format_exc()
            
            def hide_and_error():
                LoadingIndicator.hide()
                messagebox.showerror("Error", 
                    f"Failed to create project:\n\n{error_msg}\n\n{error_trace}")
                print(f"Failed to create project:\n\n{error_msg}\n\n{error_trace}")
            
            # Schedule error handling on next frame
            dpg.split_frame(delay=1)
            dpg.set_frame_callback(dpg.get_frame_count() + 1, hide_and_error)
    
    import threading
    thread = threading.Thread(target=create_async, daemon=True)
    thread.start()

def _handle_iso_extraction(project_data: ProjectData):
    """Handle ISO extraction during project creation"""
    current_build = project_data.GetCurrentBuildVersion()
    project_folder = project_data.GetProjectFolder()
    build_name = current_build.GetBuildName()
    platform = current_build.GetPlatform()

    output_dir = os.path.join(project_folder, ".config", "game_files", build_name)

    # For PS1, handle multi-bin games with binmerge
    file_to_extract = _wizard_state.selected_file_path
    original_source_path = _wizard_state.selected_file_path  # Preserve original file path for source_path

    if platform == "PS1":
        from services.binmerge_service import BinmergeService
        print(f"\nProcessing PS1 file: {os.path.basename(file_to_extract)}")
        success, bin_path, message = BinmergeService.process_ps1_file(file_to_extract)

        if not success:
            raise Exception(f"Failed to process PS1 file: {message}")

        print(f"{message}")
        file_to_extract = bin_path  # Extract the data track BIN, but keep original_source_path for rebuilding

    # Extract ISO
    iso_service = ISOService(project_data, verbose=False)
    result = iso_service.extract_iso(file_to_extract, output_dir)
    
    if not result.success:
        raise Exception(f"ISO extraction failed: {result.message}")
    
    # Set paths - handle GameCube/Wii subdirectories
    platform = current_build.GetPlatform()
    game_folder = output_dir  # Default

    if platform == "Gamecube":
        # For GameCube, gc-fst creates a 'root' subdirectory with all the files
        root_subdir = os.path.join(output_dir, 'root')
        if os.path.exists(root_subdir):
            game_folder = root_subdir
            verbose_print(f"  Using GameCube 'root' subdirectory: {game_folder}")
    elif platform == "Wii":
        # For Wii, Dolphin extraction creates a 'DATA' subdirectory with all the files
        data_subdir = os.path.join(output_dir, 'DATA')
        if os.path.exists(data_subdir):
            game_folder = data_subdir
            verbose_print(f"  Using Wii 'DATA' subdirectory: {game_folder}")

    current_build.SetGameFolder(game_folder)

    current_build.SetSourcePath(original_source_path)  # Use original file path (CUE or BIN)
    
    # Find and set main executable
    main_exe = current_build.SearchForMainExecutableInGameFolder()
    if main_exe:
        current_build.SetMainExecutable(main_exe)
        current_build.AddInjectionFile(main_exe)
        current_build.AutoSetFileOffsetForPlatform()

        # Try to find and setup OSReport for GameCube/Wii Hello World
        platform = current_build.GetPlatform()
        if platform in ["Gamecube", "Wii"]:
            verbose_print("Searching for OSReport pattern...")
            from services.pattern_service import PatternService
            pattern_service = PatternService(project_data)
            if pattern_service.setup_osreport():
                verbose_print(" OSReport setup complete")
            else:
                verbose_print(" OSReport pattern not found or not applicable")

        # Setup PS2 _print syscall for Hello World
        if platform == "PS2":
            verbose_print("Setting up PS2 _print syscall...")
            from services.template_service import TemplateService
            template_service = TemplateService(project_data)
            if template_service.setup_ps2_print_syscall():
                verbose_print(" PS2 _print syscall setup complete")
            else:
                verbose_print(" PS2 _print syscall setup failed")

    # Download box art
    from services.game_boxart_service import GameBoxartService
    GameBoxartService.download_boxart(project_data)


def _handle_existing_folder(project_data: ProjectData):
    """Handle existing folder during project creation"""
    current_build = project_data.GetCurrentBuildVersion()
    project_folder = project_data.GetProjectFolder()
    build_name = current_build.GetBuildName()
    platform = current_build.GetPlatform()

    # Copy to build-specific folder for PS1
    if platform == "PS1":
        if not current_build.CopyGameFilesToLocal(_wizard_state.selected_file_path, project_folder):
            raise Exception("Failed to copy game files to project")

        # Use the build-specific local copy
        local_copy_path = os.path.join(project_folder, '.config', 'game_files', build_name)
        current_build.SetGameFolder(local_copy_path)
    else:
        # For GameCube/Wii, check for subdirectories ('root' for GameCube, 'DATA' for Wii)
        game_folder = _wizard_state.selected_file_path  # Default to user selection

        if platform in ["Gamecube", "Wii"]:
            # Check for Wii 'DATA' folder first (Dolphin extraction format)
            data_subdir = os.path.join(_wizard_state.selected_file_path, 'DATA')
            if os.path.exists(data_subdir) and os.path.isdir(data_subdir):
                game_folder = data_subdir
                print(f"  Detected 'DATA' subdirectory (Wii Dolphin extraction), using: {game_folder}")
            else:
                # Check for GameCube 'root' folder (wit/gc-fst extraction format)
                root_subdir = os.path.join(_wizard_state.selected_file_path, 'root')
                if os.path.exists(root_subdir) and os.path.isdir(root_subdir):
                    game_folder = root_subdir
                    print(f"  Detected 'root' subdirectory (GameCube extraction), using: {game_folder}")

        current_build.SetGameFolder(game_folder)

    # Set source path (original location)
    current_build.SetSourcePath(_wizard_state.selected_file_path)
    
    # Find and set main executable
    main_exe = current_build.SearchForMainExecutableInGameFolder()
    if main_exe:
        current_build.SetMainExecutable(main_exe)
        current_build.AddInjectionFile(main_exe)
        current_build.AutoSetFileOffsetForPlatform()

        # Try to find and setup OSReport for GameCube/Wii Hello World
        if platform in ["Gamecube", "Wii"]:
            print("Searching for OSReport pattern...")
            from services.pattern_service import PatternService
            pattern_service = PatternService(project_data)
            if pattern_service.setup_osreport():
                print(" OSReport setup complete")
            else:
                print(" OSReport pattern not found or not applicable")

        # Setup PS2 _print syscall for Hello World
        if platform == "PS2":
            verbose_print("Setting up PS2 _print syscall...")
            from services.template_service import TemplateService
            template_service = TemplateService(project_data)
            if template_service.setup_ps2_print_syscall():
                verbose_print(" PS2 _print syscall setup complete")
            else:
                verbose_print(" PS2 _print syscall setup failed")

    # Download box art
    from services.game_boxart_service import GameBoxartService
    GameBoxartService.download_boxart(project_data)


def _handle_single_file(project_data: ProjectData):
    """Handle single file mode during project creation"""
    current_build = project_data.GetCurrentBuildVersion()
    
    filename = os.path.basename(_wizard_state.selected_file_path)
    file_dir = os.path.dirname(_wizard_state.selected_file_path)
    
    # Enable single file mode
    current_build.SetSingleFileMode(True)
    current_build.SetSingleFilePath(_wizard_state.selected_file_path)
    
    # Set paths
    current_build.SetGameFolder(file_dir)
    current_build.SetMainExecutable(filename)
    current_build.AddInjectionFile(filename)
    current_build.AutoSetFileOffsetForPlatform()

    # Download box art
    from services.game_boxart_service import GameBoxartService
    GameBoxartService.download_boxart(project_data)


def _scan_for_ghidra_patterns(project_data: ProjectData):
    """Scan main executable for OS library function patterns and add to symbols file"""
    current_build = project_data.GetCurrentBuildVersion()
    platform = current_build.GetPlatform()

    # Only scan PS1/PS2
    if platform not in ["PS1", "PS2"]:
        return

    # Get main executable path
    main_exe = current_build.GetMainExecutable()
    if not main_exe:
        print("No main executable found, skipping Ghidra pattern scan")
        return

    # Build full path to executable
    game_folder = current_build.GetGameFolder()
    if not game_folder:
        print("No game folder set, skipping Ghidra pattern scan")
        return

    exe_path = os.path.join(game_folder, main_exe)
    if not os.path.exists(exe_path):
        print(f"Executable not found at {exe_path}, skipping Ghidra pattern scan")
        return

    print(f"\nScanning {main_exe} for OS library function patterns...")

    # Scan for patterns
    try:
        service = GhidraPatternService()
        symbols = service.scan_executable(platform, exe_path)

        if symbols:
            print(f"Found {len(symbols)} OS library functions")

            # Get build-specific symbols file path
            project_folder = project_data.GetProjectFolder()
            build_name = current_build.GetBuildName()
            symbols_dir = os.path.join(project_folder, "symbols")
            symbols_file_name = f"{build_name}.txt"
            symbols_file = os.path.join(symbols_dir, symbols_file_name)

            # Add symbols to file
            service.add_symbols_to_file(symbols_file, symbols)

            # Generate/update unified header file with build-specific section
            include_dir = os.path.join(project_folder, "include")
            header_file = os.path.join(include_dir, "library_symbols.h")
            service.generate_header_file(header_file, symbols, build_name)

            # Update build version to use this symbols file
            current_build.SetSymbolsFile(symbols_file_name)
        else:
            print("No OS library function patterns found")

    except Exception as e:
        print(f"Error scanning for Ghidra patterns: {e}")
        import traceback
        traceback.print_exc()


# ==================== HELPER FUNCTIONS ====================

def _get_file_mode_display() -> str:
    """Get display text for current file mode"""
    mode_map = {
        "extract_iso": "Extract ISO File",
        "existing_folder": "Use Extracted Folder",
        "single_file": "Single File (No ISO)"
    }
    return mode_map.get(_wizard_state.file_mode, "Unknown")