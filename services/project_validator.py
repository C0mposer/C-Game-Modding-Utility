import os
import sys
import tkinter as tk
from tkinter import messagebox, filedialog
from classes.project_data.project_data import ProjectData
from classes.project_data.build_version import BuildVersion
from functions.verbose_print import verbose_print


def _is_cli_mode() -> bool:
    """
    Check if running in CLI mode (modtool.py).
    Returns True if running from command line, False if GUI mode.
    """
    return any('modtool.py' in arg for arg in sys.argv)


def _show_missing_game_files_dialog(title: str, message: str) -> str:
    """
    Custom 3-button dialog for missing game files.
    Returns 'extract', 'select', or 'cancel'
    """
    result = {'choice': 'cancel'}

    # Create hidden root if needed
    root = tk.Tk()
    root.withdraw()

    # Create dialog
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.resizable(False, False)

    # Message
    tk.Label(dialog, text=message, padx=20, pady=20, justify=tk.LEFT).pack()

    # Buttons frame
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=(0, 20))

    def on_extract():
        result['choice'] = 'extract'
        dialog.destroy()
        root.destroy()

    def on_select():
        result['choice'] = 'select'
        dialog.destroy()
        root.destroy()

    def on_cancel():
        result['choice'] = 'cancel'
        dialog.destroy()
        root.destroy()

    tk.Button(button_frame, text="Select ISO", command=on_extract, width=15).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Select Folder", command=on_select, width=15).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Cancel", command=on_cancel, width=15).pack(side=tk.LEFT, padx=5)

    # Center dialog
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'+{x}+{y}')

    dialog.grab_set()
    dialog.wait_window()

    return result['choice']


class ProjectValidator:
    """Validates project file paths and prompts user to locate missing files"""

    @staticmethod
    def validate_and_fix_project(project_data: ProjectData) -> bool:
        """
        Validate all build versions in project and prompt user to fix missing files.
        Returns True if validation passed or user fixed issues, False if user cancelled.

        In CLI mode (modtool.py), skips prompts and prints warnings for missing files.
        """
        # CLI mode - skip all prompts, just check and warn about missing files
        if _is_cli_mode():
            for build_version in project_data.build_versions:
                build_name = build_version.GetBuildName()

                # Check if files are missing (without prompting)
                if build_version.IsSingleFileMode():
                    single_file_path = build_version.GetSingleFilePath()
                    if not single_file_path or not os.path.exists(single_file_path):
                        print(f"Warning: Build '{build_name}' has missing game file (skipping validation)", file=sys.stderr)
                else:
                    game_folder = build_version.GetGameFolder()
                    if not game_folder or not os.path.exists(game_folder):
                        print(f"Warning: Build '{build_name}' has missing game files (skipping validation)", file=sys.stderr)

            # Still create .config directories if needed
            full_project_path = project_data.GetProjectFolder()
            config_dir = os.path.join(full_project_path, ".config")
            if not os.path.exists(config_dir):
                os.makedirs(f"{full_project_path}/.config/output", exist_ok=True)
                os.makedirs(f"{full_project_path}/.config/output/object_files", exist_ok=True)
                os.makedirs(f"{full_project_path}/.config/output/memory_map", exist_ok=True)

            return True

        # GUI mode - continue with prompts
        print("\n[Validating Project Files]")

        # Track already processed game folders to avoid asking for duplicates
        processed_folders = {}  # Maps game_folder path -> build_name that provided it

        for build_version in project_data.build_versions:
            if not ProjectValidator._validate_build_version(build_version, project_data, processed_folders):
                return False  # User cancelled

            # Check if .config exists. If not, create
            full_project_path = project_data.GetProjectFolder()
            config_dir = os.path.join(full_project_path, ".config")

            verbose_print("Checking if .config folder exists")
            if not os.path.exists(config_dir):
                verbose_print("Creating .config folder")
                os.makedirs(f"{full_project_path}/.config/output")
                os.makedirs(f"{full_project_path}/.config/output/object_files")
                # os.makedirs(f"{full_project_path}/.config/output/elf_files") # Probably not needed?
                #os.makedirs(f"{full_project_path}/.config/output/final_bins") # Probably not needed?
                os.makedirs(f"{full_project_path}/.config/output/memory_map")

        verbose_print(" Project validation complete\n")
        return True

    @staticmethod
    def _validate_build_version(build_version: BuildVersion, project_data: ProjectData, processed_folders: dict) -> bool:
        """Validate a single build version. Returns False if user cancels."""
        build_name = build_version.GetBuildName()
        #print(f"\nValidating build: {build_name}")

        # Check single file mode
        if build_version.IsSingleFileMode():
            return ProjectValidator._validate_single_file_mode(build_version, build_name)
        else:
            return ProjectValidator._validate_extracted_mode(build_version, build_name, project_data, processed_folders)

    @staticmethod
    def _validate_single_file_mode(build_version: BuildVersion, build_name: str) -> bool:
        """Validate single file mode - check if the single file exists"""
        single_file_path = build_version.GetSingleFilePath()

        if not single_file_path:
            print(f"  Warning: Build '{build_name}' is in single file mode but has no file path set")
            return True  # Not necessarily an error, user might set it up later

        if os.path.exists(single_file_path):
            print(f"   Single file exists: {single_file_path}")
            return True

        # File is missing - prompt user
        print(f"  Single file not found: {single_file_path}")

        response = messagebox.askyesno(
            "Missing Single File",
            f"The game file for build version \"{build_name}\" could not be found:\n\n"
            f"{single_file_path}\n\n"
            f"Would you like to locate this file?"
        )

        if not response:
            return True  # User chose not to fix, that's okay

        # Prompt user to select the file
        new_file_path = filedialog.askopenfilename(
            title=f"Locate Single File for '{build_name}'",
            filetypes=[("All Files", "*.*")]
        )

        if not new_file_path:
            print(f"  User cancelled file selection")
            return True  # User cancelled, but don't block loading

        # Update the path
        build_version.SetSingleFilePath(new_file_path)
        print(f"   Updated single file path: {new_file_path}")
        return True

    @staticmethod
    def _validate_extracted_mode(build_version: BuildVersion, build_name: str, project_data: ProjectData, processed_folders: dict) -> bool:
        """Validate extracted game folder mode"""
        game_folder = build_version.GetGameFolder()
        platform = build_version.GetPlatform()

        if not game_folder:
            print(f"  Warning: Build '{build_name}' has no extracted game folder set")
            return True  # Not necessarily an error

        # Normalize path for comparison
        normalized_folder = os.path.normpath(game_folder) if game_folder else None

        # Check if this folder was already processed by another build
        if normalized_folder and normalized_folder in processed_folders:
            source_build = processed_folders[normalized_folder]
            print(f"   Using game folder from build '{source_build}': {game_folder}")
            return True

        if os.path.exists(game_folder) and os.path.isdir(game_folder):
            #print(f"   Extracted game folder exists: {game_folder}")
            # Mark this folder as processed
            if normalized_folder:
                processed_folders[normalized_folder] = build_name
            return True

        # Folder is missing - prompt user
        print(f"  Extracted game folder not found: {game_folder}")

        # Different prompts based on platform
        if platform == "PS1":
            result = ProjectValidator._prompt_ps1_extraction(build_version, build_name, project_data)
        else:
            result = ProjectValidator._prompt_folder_selection(build_version, build_name, platform, project_data)

        # If user provided a new folder, mark it as processed
        if result:
            new_folder = build_version.GetGameFolder()
            if new_folder:
                normalized_new = os.path.normpath(new_folder)
                processed_folders[normalized_new] = build_name

        return result

    @staticmethod
    def _prompt_ps1_extraction(build_version: BuildVersion, build_name: str, project_data: ProjectData) -> bool:
        """Prompt user to extract PS1 BIN (must extract to generate XML, can't use existing folder)"""
        response = messagebox.askyesno(
            "Missing PS1 Game Files",
            f"The game files for build version \"{build_name}\" could not be found.\n\n"
            f"PS1 projects require extracting from a BIN/CUE file to generate the required XML.\n\n"
            f"Would you like to extract from a BIN/CUE file now?"
        )

        if not response:
            return True  # User chose to skip

        # Extract from BIN/CUE
        return ProjectValidator._extract_ps1_bin(build_version, build_name, project_data)

    @staticmethod
    def _extract_ps1_bin(build_version: BuildVersion, build_name: str, project_data: ProjectData) -> bool:
        """Extract PS1 BIN/CUE file"""
        original_file_path = filedialog.askopenfilename(
            title=f"Choose PS1 BIN/CUE File for '{build_name}' (use .cue for multi-bin games)",
            filetypes=[("PS1 Images", "*.bin;*.cue"), ("All Files", "*.*")]
        )

        if not original_file_path:
            print(f"  User cancelled BIN selection")
            return True

        # Handle multi-bin games with binmerge
        from services.binmerge_service import BinmergeService
        print(f"\nProcessing PS1 file: {os.path.basename(original_file_path)}")
        success, bin_to_extract, message = BinmergeService.process_ps1_file(original_file_path)

        if not success:
            messagebox.showerror("Error", f"Failed to process PS1 file:\n\n{message}")
            return True  # Don't block project loading

        print(f" {message}")

        # Import here to avoid circular dependencies
        from services.iso_service import ISOService

        project_folder = project_data.GetProjectFolder()
        output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)

        print(f"  Extracting PS1 BIN to: {output_dir}")

        # Create ISO service and extract
        iso_service = ISOService(project_data, verbose=False)
        result = iso_service.extract_iso(bin_to_extract, output_dir)

        if result.success:
            # Update paths
            build_version.SetGameFolder(output_dir)
            build_version.SetSourcePath(original_file_path)  # Use original file path (CUE or BIN)

            # Search for main executable
            main_exe = build_version.SearchForMainExecutableInGameFolder()
            if main_exe:
                build_version.SetMainExecutable(main_exe)

            print(f"   PS1 BIN extracted successfully")

            # Save the project to persist the updated paths
            from services.project_serializer import ProjectSerializer
            project_path = os.path.join(project_folder, f"{project_data.GetProjectName()}.modproj")
            ProjectSerializer.save_project(project_data, project_path)

            messagebox.showinfo(
                "Extraction Complete",
                f"PS1 BIN extracted successfully for build '{build_name}'"
            )
            return True
        else:
            print(f"  Extraction failed: {result.message}")
            messagebox.showerror(
                "Extraction Failed",
                f"Failed to extract PS1 BIN:\n{result.message}"
            )
            return True  # Don't block project loading

    @staticmethod
    def _select_extracted_folder(build_version: BuildVersion, build_name: str, project_data: ProjectData = None) -> bool:
        """Select an already extracted game folder"""
        folder_path = filedialog.askdirectory(
            title=f"Select Extracted Game Folder for '{build_name}'"
        )

        if not folder_path:
            print(f"  User cancelled folder selection")
            return True

        # Update the path
        build_version.SetGameFolder(folder_path)

        # Search for main executable
        main_exe = build_version.SearchForMainExecutableInGameFolder()
        if main_exe:
            build_version.SetMainExecutable(main_exe)

        print(f"   Updated game folder: {folder_path}")

        # Save the project to persist the updated paths
        if project_data:
            from services.project_serializer import ProjectSerializer
            project_folder = project_data.GetProjectFolder()
            project_path = os.path.join(project_folder, f"{project_data.GetProjectName()}.modproj")
            ProjectSerializer.save_project(project_data, project_path)

        return True

    @staticmethod
    def _extract_iso(build_version: BuildVersion, build_name: str, platform: str, project_data: ProjectData) -> bool:
        """Extract ISO file for PS2/GC/Wii platforms"""
        # Determine file types based on platform
        if platform == "PS2":
            filetypes = [("PS2 ISO", "*.iso"), ("All Files", "*.*")]
        elif platform == "GameCube":
            filetypes = [("GameCube ISO", "*.iso;*.gcm"), ("All Files", "*.*")]
        elif platform == "Wii":
            filetypes = [("Wii ISO", "*.iso;*.wbfs"), ("All Files", "*.*")]
        else:
            filetypes = [("ISO Files", "*.iso"), ("All Files", "*.*")]

        iso_path = filedialog.askopenfilename(
            title=f"Choose {platform} ISO for '{build_name}'",
            filetypes=filetypes
        )

        if not iso_path:
            print(f"  User cancelled ISO selection")
            return True

        # Import here to avoid circular dependencies
        from services.iso_service import ISOService
        from gui.gui_loading_indicator import LoadingIndicator

        # Extract to game_files/{build_name} automatically (same as main callbacks)
        project_folder = project_data.GetProjectFolder()
        output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)

        print(f"  Extracting {platform} ISO to: {output_dir}")

        # Show loading indicator
        LoadingIndicator.show(f"Extracting {platform} ISO...")

        try:
            # Create ISO service and extract
            iso_service = ISOService(project_data, verbose=False)
            result = iso_service.extract_iso(iso_path, output_dir)

            if result.success:
                # Update paths
                build_version.SetGameFolder(output_dir)
                build_version.SetSourcePath(iso_path)  # Set source path to ISO

                # Search for main executable
                main_exe = build_version.SearchForMainExecutableInGameFolder()
                if main_exe:
                    build_version.SetMainExecutable(main_exe)

                print(f"   ISO extracted successfully")

                # Save the project to persist the updated paths
                from services.project_serializer import ProjectSerializer
                project_path = os.path.join(project_folder, f"{project_data.GetProjectName()}.modproj")
                ProjectSerializer.save_project(project_data, project_path)

                LoadingIndicator.hide()

                messagebox.showinfo(
                    "Extraction Complete",
                    f"ISO extracted successfully for build '{build_name}'"
                )
                return True
            else:
                print(f"  Extraction failed: {result.message}")
                LoadingIndicator.hide()
                messagebox.showerror(
                    "Extraction Failed",
                    f"Failed to extract ISO:\n{result.message}"
                )
                return True  # Don't block project loading
        except Exception as e:
            LoadingIndicator.hide()
            messagebox.showerror(
                "Extraction Error",
                f"An error occurred during extraction:\n{str(e)}"
            )
            return True  # Don't block project loading

    @staticmethod
    def _prompt_folder_selection(build_version: BuildVersion, build_name: str, platform: str, project_data: ProjectData = None) -> bool:
        """Prompt user to extract ISO or select folder for non-PS1 platforms"""
        # Get expected ISO name or game_id
        source_path = build_version.GetSourcePath()
        main_executable = build_version.GetMainExecutable()

        # Build dialog message
        message = f"The game files for build version \"{build_name}\" ({platform}) could not be found."

        # Show expected ISO if available
        if source_path:
            expected_iso = os.path.basename(source_path)
            message += f"\n\nThis build version expects: {expected_iso}"
        # Otherwise show game_id (main executable name) if available
        elif main_executable:
            message += f"\n\nThis build version expects: {main_executable}"

        message += "\n\nWhat would you like to do?"

        response = _show_missing_game_files_dialog(
            "Missing Game Files",
            message
        )

        if response == 'cancel':
            return True  # User chose to skip

        if response == 'extract':
            # Extract from ISO
            return ProjectValidator._extract_iso(build_version, build_name, platform, project_data)
        elif response == 'select':
            # Select existing folder
            return ProjectValidator._select_extracted_folder(build_version, build_name, project_data)
        else:
            return True
