import os
import subprocess
import shutil
from typing import Optional
from pathlib import Path
from classes.project_data.project_data import ProjectData
from typing import Optional, Callable
from functions.print_wrapper import print_error
from functions.verbose_print import verbose_print

import xml.etree.ElementTree as ET

# Add compatibility shim for older Python versions
if not hasattr(ET, 'indent'):
    def indent(tree, space="  ", level=0):
        """Add pretty-printing to XML (backport for Python < 3.9)"""
        i = "\n" + level * space
        if len(tree):
            if not tree.text or not tree.text.strip():
                tree.text = i + space
            if not tree.tail or not tree.tail.strip():
                tree.tail = i
            for elem in tree:
                indent(elem, space, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not tree.tail or not tree.tail.strip()):
                tree.tail = i
    ET.indent = indent

class ISOResult:
    """Represents the result of an ISO operation"""
    def __init__(self, success: bool, message: str = "", output_path: str = ""):
        self.success = success
        self.message = message
        self.output_path = output_path

class ISOService:
    """Handles ISO/ROM extraction and rebuilding for all platforms"""

    def __init__(self, project_data: ProjectData, verbose: bool = False,
                 on_progress: Optional[Callable] = None, on_error: Optional[Callable] = None,
                 tool_dir: Optional[str] = None):
        self.project_data = project_data
        # Use provided tool_dir or fall back to getcwd() for backwards compatibility
        self.tool_dir = tool_dir if tool_dir is not None else os.getcwd()
        self.verbose = verbose
        self.on_progress = on_progress
        self.on_error = on_error

        # Tool paths
        self.tools = {
            'dumpsxiso': os.path.join(self.tool_dir, 'prereq', 'mkpsxiso', 'dumpsxiso.exe'),
            'mkpsxiso': os.path.join(self.tool_dir, 'prereq', 'mkpsxiso', 'mkpsxiso.exe'),
            '7z': os.path.join(self.tool_dir, 'prereq', '7z', '7z.exe'),
            'ps2iso': os.path.join(self.tool_dir, 'prereq', 'PS2ISOTools', 'bin', 'ps2iso.exe'),
            'mkisofs': os.path.join(self.tool_dir, 'prereq', 'mkisofs', 'mkisofs.exe'),
            'gcr': os.path.join(self.tool_dir, 'prereq', 'gcr', 'gcr.exe'),
            'gc_fst': os.path.join(self.tool_dir, 'prereq', 'gc-fst', 'gc_fst.exe'),
            'wit': os.path.join(self.tool_dir, 'prereq', 'wit', 'bin', 'wit.exe'),
            'wwt': os.path.join(self.tool_dir, 'prereq', 'wit', 'bin', 'wwt.exe'),
            'wdf': os.path.join(self.tool_dir, 'prereq', 'wit', 'bin', 'wdf.exe'),
            'dolphintool': os.path.join(self.tool_dir, 'prereq', 'DolphinTool', 'DolphinTool.exe'),
            'xdelta': os.path.join(self.tool_dir, 'prereq', 'xdelta', 'xdelta.exe'),
        }
        
    def _log_progress(self, message: str):
        """Short/normal messages (always printed)."""
        self._log_verbose(message)
        if self.on_progress:
            self.on_progress(message)

    def _log_verbose(self, message: str):
        """Verbose-only messages (printed only if verbose=True)."""
        if self.verbose:
            verbose_print(message)
            if self.on_progress:
                self.on_progress(message)

    def _log_error(self, message: str):
        """Error messages (always printed)."""
        print_error(message)
        if self.on_error:
            self.on_error(message)

    # ==================== BUILD DIRECTORY OPTIMIZATION ====================

    def _prepare_build_directory(self, game_folder: str, temp_build_dir: str) -> bool:
        """
        Prepare build directory optimally:
        - First build: Full copy (unavoidable)
        - Subsequent builds: Build folder already exists, just use it

        Returns: True if successful, False otherwise
        """
        # First build - need full copy
        if not os.path.exists(temp_build_dir):
            self._log_verbose("First build - performing full copy...")
            shutil.copytree(game_folder, temp_build_dir)
            return True

        # Subsequent build - build folder already exists
        self._log_verbose("Incremental build - using existing build folder...")
        return True

    def _copy_injection_files_from_original(self, game_folder: str, temp_build_dir: str, current_build):
        """
        Copy all current injection files from original game folder to build folder.
        This resets them to vanilla state before patching.

        Called BEFORE patching to prepare files, and AFTER build to reset them.
        """
        current_modified = current_build.GetInjectionFiles()

        if not current_modified:
            return

        self._log_verbose(f"Copying {len(current_modified)} injection files from original...")

        for file_name in current_modified:
            # Find file in original game folder
            original_path = current_build.FindFileInGameFolder(file_name)
            if not original_path or not os.path.exists(original_path):
                # File doesn't exist in original (new file) - skip, will be added by _add_xxx_new_files()
                continue

            # Find relative path and target in temp
            rel_path = os.path.relpath(original_path, game_folder)
            target_path = os.path.join(temp_build_dir, rel_path)

            # Copy original to temp (reset to vanilla)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(original_path, target_path)
            self._log_verbose(f"  Copied: {file_name}")

    def _remove_new_files_from_build(self, temp_build_dir: str, current_build):
        """
        Remove all new files (codecaves with IsNewFile) from build folder.
        This ensures the build folder only contains original game files + current injection files.

        Called AFTER ISO build completes to clean up new files.
        """
        new_files_removed = 0

        for codecave in current_build.GetEnabledCodeCaves():
            if codecave.IsNewFile():
                filename = codecave.GetInjectionFile()

                if not filename or filename.strip() == "" or filename.lower() == "none":
                    continue

                filename = filename.strip()

                # Construct path in build folder
                target_file = os.path.join(temp_build_dir, filename)

                # Remove if exists
                if os.path.exists(target_file):
                    try:
                        os.remove(target_file)
                        self._log_verbose(f"  Removed new file: {filename}")
                        new_files_removed += 1
                    except Exception as e:
                        self._log_verbose(f"  Warning: Could not remove {filename}: {e}")

        if new_files_removed > 0:
            self._log_verbose(f"Removed {new_files_removed} new file(s) from build folder")

    # ==================== EXTRACTION ====================

    #! NOT USED YET
    def _dolphin_tool_convert(self, path: str, output_type: str) -> tuple[bool, str, str]:
        """
        Convert RVZ file to ISO format using DolphinTool.
        Returns: (success, iso_path, error_message)
        """
        self._log_verbose(f"Converting ISO to {output_type}: {path}")

        # Get project-specific conversion directory
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()

        basename = os.path.basename(path)
        new_basename = os.path.splitext(basename)[0] + f'{output_type}'
        path = os.path.abspath(path)
        output_path = os.path.join(path, new_basename)
        
        # Convert using DolphinTool
        cmd = [
            self.tools['dolphintool'],
            'convert',
            f'--format={output_type}',
            f'--input={path}',
            f'--output={output_path}'
            f'--block_size=33554432',
            f'--compression=lzma2',
            f'--compression_level=9'
        ]

        self._log_verbose(f"Command: {' '.join(cmd)}")
        self._log_verbose(f"Converting to: {output_path}")
        self._log_verbose("This may take a few minutes...")

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")

            if result.returncode != 0:
                error_msg = f"DolphinTool conversion failed: {result.stderr}"
                self._log_verbose(error_msg)
                return False, "", error_msg

            if not os.path.exists(output_path):
                error_msg = f"Conversion completed but ISO not found at: {output_path}"
                self._log_verbose(error_msg)
                return False, "", error_msg

            self._log_verbose(f"Successfully converted to ISO: {output_path}")
            return True, output_path, ""

        except Exception as e:
            import traceback
            error_msg = f"Conversion error: {str(e)}\n{traceback.format_exc()}"
            self._log_verbose(error_msg)
            return False, "", error_msg
        
    def _convert_rvz_to_iso(self, rvz_path: str) -> tuple[bool, str, str]:
        """
        Convert RVZ file to ISO format using DolphinTool.
        Returns: (success, iso_path, error_message)
        """
        self._log_verbose(f"Converting RVZ to ISO: {rvz_path}")

        # Get project-specific conversion directory
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()

        # Create conversion output directory in .config/conversions/
        conversion_dir = os.path.join(project_folder, '.config', 'conversions', build_name)
        os.makedirs(conversion_dir, exist_ok=True)

        # Generate output ISO path
        rvz_basename = os.path.basename(rvz_path)
        iso_basename = os.path.splitext(rvz_basename)[0] + '.iso'
        output_iso_path = os.path.join(conversion_dir, iso_basename)

        # Check if already converted
        if os.path.exists(output_iso_path):
            self._log_verbose(f"Using existing converted ISO: {output_iso_path}")
            return True, output_iso_path, ""

        # Convert RVZ to ISO using DolphinTool
        rvz_path = os.path.abspath(rvz_path)
        output_iso_path = os.path.abspath(output_iso_path)

        cmd = [
            self.tools['dolphintool'],
            'convert',
            '--format=iso',
            f'--input={rvz_path}',
            f'--output={output_iso_path}'
        ]

        self._log_verbose(f"Command: {' '.join(cmd)}")
        self._log_verbose(f"Converting to: {output_iso_path}")
        self._log_verbose("This may take a few minutes...")

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")

            if result.returncode != 0:
                error_msg = f"DolphinTool conversion failed: {result.stderr}"
                self._log_verbose(error_msg)
                return False, "", error_msg

            if not os.path.exists(output_iso_path):
                error_msg = f"Conversion completed but ISO not found at: {output_iso_path}"
                self._log_verbose(error_msg)
                return False, "", error_msg

            self._log_verbose(f"RVZ successfully converted to ISO: {output_iso_path}")
            return True, output_iso_path, ""

        except Exception as e:
            import traceback
            error_msg = f"Conversion error: {str(e)}\n{traceback.format_exc()}"
            self._log_verbose(error_msg)
            return False, "", error_msg
        
    def _convert_ciso_to_iso(self, ciso_path: str) -> tuple[bool, str, str]:
        """
        Convert CISO file to ISO format using WIT (direct copy method).
        This is needed for GameCube because gc-fst can't read CISO directly.
        Returns: (success, iso_path, error_message)
        """
        self._log_verbose(f"Converting CISO to ISO: {ciso_path}")

        # Get project-specific conversion directory
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()

        # Create conversion output directory in .config/conversions/
        conversion_dir = os.path.join(project_folder, '.config', 'conversions', build_name)
        os.makedirs(conversion_dir, exist_ok=True)

        # Generate paths
        ciso_basename = os.path.basename(ciso_path)
        iso_basename = os.path.splitext(ciso_basename)[0] + '.iso'
        output_iso_path = os.path.join(conversion_dir, iso_basename)

        # Check if already converted
        if os.path.exists(output_iso_path):
            self._log_verbose(f"Using existing converted ISO: {output_iso_path}")
            return True, output_iso_path, ""

        ciso_path = os.path.abspath(ciso_path)
        output_iso_path = os.path.abspath(output_iso_path)

        try:
            self._log_verbose("Converting CISO to ISO format...")
            
            # Try direct copy first (simpler and might work)
            cmd = [
                self.tools['wit'],
                'copy',
                ciso_path,
                output_iso_path,
                '--iso',
                '--raw'
            ]

            self._log_verbose(f"Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")

            if result.returncode != 0:
                error_msg = f"WIT copy failed: {result.stderr}"
                self._log_verbose(error_msg)
                return False, "", error_msg

            if not os.path.exists(output_iso_path):
                error_msg = f"Conversion completed but ISO not found at: {output_iso_path}"
                self._log_verbose(error_msg)
                return False, "", error_msg

            self._log_verbose(f"CISO successfully converted to ISO: {output_iso_path}")
            self._log_verbose("IM LOSING IT "+ output_iso_path)
            return True, output_iso_path, ""

        except Exception as e:
            import traceback
            error_msg = f"Conversion error: {str(e)}\n{traceback.format_exc()}"
            self._log_verbose(error_msg)
            return False, "", error_msg

    def extract_iso(self, iso_path: str, output_dir: str) -> ISOResult:
        """
        Extract ISO based on current platform.
        Automatically detects platform from project data.
        """
        platform = self.project_data.GetCurrentBuildVersion().GetPlatform()
        
        if platform == "PS1":
            return self._extract_ps1(iso_path, output_dir)
        elif platform == "PS2":
            return self._extract_ps2(iso_path, output_dir)
        elif platform == "Gamecube":
            return self._extract_gamecube(iso_path, output_dir)
        elif platform == "Wii":
            return self._extract_wii(iso_path, output_dir)
        elif platform == "N64":
            return ISOResult(True, "N64 ROMs don't need extraction", iso_path)
        else:
            return ISOResult(False, f"Unsupported platform: {platform}")
    
    def _extract_ps1(self, iso_path: str, output_dir: str) -> ISOResult:
        """Extract PS1 BIN/CUE using dumpsxiso"""
        self._log_progress(f"Extracting PS1 BIN: {iso_path}")
        
        # UPDATED: Use build-specific output directory
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()
        
        # Modify output_dir to be build-specific
        project_folder = self.project_data.GetProjectFolder()
        output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert paths to absolute paths
        iso_path = os.path.abspath(iso_path)
        output_dir = os.path.abspath(output_dir)
        
        # Determine where to save the XML file (build-specific)
        xml_output_path = os.path.join(project_folder, '.config', 'output', f'psxbuild_{build_name}.xml')
        
        # Ensure the directory for XML exists
        os.makedirs(os.path.dirname(xml_output_path), exist_ok=True)
        
        # Build extraction command with -s flag to generate XML
        cmd = [
            self.tools['dumpsxiso'],
            iso_path,
            '-x', output_dir,
            '-s', xml_output_path
        ]
        
        self._log_verbose(f"Command: {' '.join(cmd)}")
        self._log_verbose(f"Build-specific output: {output_dir}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.tool_dir
            )
            
            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")
            
            if result.returncode != 0:
                return ISOResult(False, f"Extraction failed: {result.stderr}")
            
            if not os.path.exists(xml_output_path):
                self._log_verbose(f"  Warning: XML file not created at {xml_output_path}")
            else:
                self._log_progress(f"Build XML created: {xml_output_path}")

                # Check if this was a multi-bin game (source path ends with .cue and has multiple bins)
                source_path = current_build.GetSourcePath()
                is_multibin = False

                if source_path and source_path.lower().endswith('.cue'):
                    from services.binmerge_service import BinmergeService
                    bin_count = BinmergeService.parse_cue_file(source_path)
                    is_multibin = (bin_count > 1)

                # Only clean XML if this was a multi-bin game where we extracted only Track 01
                if is_multibin:
                    self._log_verbose(f"Multi-bin game detected - cleaning XML to remove audio file references...")
                    self._clean_ps1_xml_audio_references(xml_output_path, output_dir)
                else:
                    self._log_verbose(f"Single-bin game - no XML cleaning needed")

            self._log_progress(f"PS1 BIN extracted to: {output_dir}")
            return ISOResult(True, "PS1 BIN extracted successfully", output_dir)
            
        except Exception as e:
            import traceback
            return ISOResult(False, f"Extraction error: {str(e)}\n{traceback.format_exc()}")
    
    def _extract_ps2(self, iso_path: str, output_dir: str) -> ISOResult:
        """Extract PS2 ISO using 7-Zip"""
        self._log_progress(f"Extracting PS2 ISO: {iso_path}")
        
        os.makedirs(output_dir, exist_ok=True)
        iso_path = os.path.abspath(iso_path)
        output_dir = os.path.abspath(output_dir)
        
        cmd = [
            self.tools['7z'],
            'x',
            iso_path,
            f'-o{output_dir}',
            '-y'
        ]
        
        self._log_verbose(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.tool_dir
            )
            
            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")
            
            if result.returncode != 0:
                return ISOResult(False, f"Extraction failed: {result.stderr}")
            
            self._log_progress(f" PS2 ISO extracted to: {output_dir}")
            return ISOResult(True, "PS2 ISO extracted successfully", output_dir)
            
        except Exception as e:
            import traceback
            return ISOResult(False, f"Extraction error: {str(e)}\n{traceback.format_exc()}")
    
    def _extract_gamecube(self, iso_path: str, output_dir: str, disc_format: str = "iso") -> ISOResult:
        """Extract GameCube ISO using gc-fst (supports .iso, .nkit.iso, .gcm, .rvz, and .ciso)"""
        self._log_progress(f"Extracting GameCube ISO: {iso_path}")

        current_build = self.project_data.GetCurrentBuildVersion()

        # Check if this is an RVZ file that needs conversion
        if iso_path.lower().endswith('.rvz'):
            self._log_verbose("Detected RVZ format - converting to ISO first")
            success, converted_iso_path, error_msg = self._convert_rvz_to_iso(iso_path)
            
            if not success:
                return ISOResult(False, f"RVZ conversion failed: {error_msg}")
            
            # Use the converted ISO for extraction
            iso_path = converted_iso_path
            self._log_verbose(f"Using converted ISO: {iso_path}")
            
            # Update project source path to use converted ISO
            current_build.SetSourcePath(converted_iso_path)
            self._log_verbose(f"Updated project to use converted ISO for future builds")

        # Check if this is a CISO file that needs conversion
        if iso_path.lower().endswith('.ciso'):
            self._log_verbose("Detected CISO format - converting to ISO first")
            success, converted_iso_path, error_msg = self._convert_ciso_to_iso(iso_path)
            
            if not success:
                return ISOResult(False, f"CISO conversion failed: {error_msg}")
            
            # Use the converted ISO for extraction
            iso_path = converted_iso_path
            self._log_verbose(f"Using converted ISO: {iso_path}")
            
            # Update project source path to use converted ISO
            current_build.SetSourcePath(converted_iso_path)
            self._log_verbose(f"Updated project to use converted ISO for future builds")

        # Get build-specific output directory
        build_name = current_build.GetBuildName()
        project_folder = self.project_data.GetProjectFolder()

        # Override output_dir to be build-specific
        output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)
        os.makedirs(output_dir, exist_ok=True)

        iso_path = os.path.abspath(iso_path)
        output_dir = os.path.abspath(output_dir)

        # gc-fst extracts to a 'root' subdirectory automatically
        root_dir = os.path.join(output_dir, 'root')

        cmd = [
            self.tools['gc_fst'],
            'extract',
            iso_path
        ]

        self._log_verbose(f"Command: {' '.join(cmd)}")
        self._log_verbose(f"Build-specific output: {output_dir}")
        self._log_verbose(f"Note: GameCube files will be extracted to: {root_dir}")

        try:
            # gc-fst extracts to current working directory, so we need to run it from output_dir
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=output_dir
            )

            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")

            if result.returncode != 0:
                return ISOResult(False, f"Extraction failed: {result.stderr}")

            if not os.path.exists(root_dir):
                return ISOResult(False, f"Extraction completed but 'root' folder not found at: {root_dir}")

            self._log_progress(f"GameCube ISO extracted to: {output_dir}")
            self._log_verbose(f"  Files are in: {root_dir}")

            # Return the output_dir (parent of root), not root_dir itself
            # The game folder will be set separately to handle the root subdirectory
            self._log_verbose("PLEASE " + output_dir)
            return ISOResult(True, "GameCube ISO extracted successfully", output_dir)

        except Exception as e:
            import traceback
            return ISOResult(False, f"Extraction error: {str(e)}\n{traceback.format_exc()}")
        
        
    def _extract_wii(self, iso_path: str, output_dir: str) -> ISOResult:
        # Spports .iso, .nkit.iso, .wbfs, .ciso, and .rvz
        self._log_progress(f"Extracting Wii ISO/WBFS: {iso_path}")
        
        disk_format = "iso" # Assume ISO

        # Check if this is an RVZ file that needs conversion
        if iso_path.lower().endswith('.rvz'):
            self._log_verbose("Detected RVZ format - converting to ISO first...")
            success, converted_iso_path, error_msg = self._convert_rvz_to_iso(iso_path)
            if not success:
                return ISOResult(False, f"RVZ conversion failed: {error_msg}")
            # Use the converted ISO for extraction
            iso_path = converted_iso_path
            self._log_verbose(f"Using converted ISO: {iso_path}")
            
            
        # Get build-specific output directory
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()
        project_folder = self.project_data.GetProjectFolder()

        # Override output_dir to be build-specific
        output_dir = os.path.join(project_folder, '.config', 'game_files', build_name)
        
        # WIT doesn't like extracting to existing directories, so remove it first if it exists
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
                self._log_verbose(f"Removed existing extraction directory")
            except Exception as e:
                return ISOResult(False, f"Could not remove existing directory: {str(e)}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        iso_path = os.path.abspath(iso_path)
        output_dir = os.path.abspath(output_dir)
        
        wit_tool = self.tools['wit']
        
        # WIT extracts directly to the specified directory
        cmd = [
            wit_tool,
            'extract',
            iso_path,
            output_dir,
            '--psel=DATA',  # Only extract game data, not UPDATE partition
            '--overwrite'   # Allow overwriting if directory exists
        ]
        
        self._log_verbose(f"Command: {' '.join(cmd)}")
        self._log_verbose(f"Build-specific output: {output_dir}")
        self._log_verbose(f"Note: Wii files will be extracted to: {output_dir}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.tool_dir
            )
            
            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")
            
            if result.returncode != 0:
                return ISOResult(False, f"Extraction failed: {result.stderr}")
            
            # Verify extraction worked by checking if files exist
            if not os.path.exists(output_dir) or len(os.listdir(output_dir)) == 0:
                return ISOResult(False, f"Extraction completed but no files found in: {output_dir}")
            
            self._log_progress(f"Wii ISO/WBFS extracted to: {output_dir}")
            
            return ISOResult(True, "Wii ISO/WBFS extracted successfully", output_dir)
            
        except Exception as e:
            import traceback
            return ISOResult(False, f"Extraction error: {str(e)}\n{traceback.format_exc()}")
    
    # ==================== REBUILDING ====================
    
    def rebuild_iso(self) -> ISOResult:
        platform = self.project_data.GetCurrentBuildVersion().GetPlatform()
        
        if platform == "PS1":
            return self._rebuild_ps1()
        elif platform == "PS2":
            return self._rebuild_ps2()
        elif platform == "Gamecube":
            # Check output format preference
            output_format = self.project_data.GetCurrentBuildVersion().GetOutputFormat()
            if not output_format:
                output_format = "iso"  # Default to ISO
            if output_format in ["ciso"]:
                return self._rebuild_gamecube_with_wit(output_format)
            else:
                return self._rebuild_gamecube()
        elif platform == "Wii":
            # Check output format preference
            output_format = self.project_data.GetCurrentBuildVersion().GetOutputFormat()
            if not output_format:
                output_format = "iso"  # Default to ISO
            
            return self._rebuild_wii(output_format)
        elif platform == "N64":
            return self._rebuild_n64()
        else:
            return ISOResult(False, f"Unsupported platform: {platform}")
    
    def _rebuild_ps1(self) -> ISOResult:
        """Rebuild PS1 BIN/CUE using mkpsxiso"""
        self._log_progress("Rebuilding PS1 BIN/CUE...")
        
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()
        
        build_dir = os.path.join(project_folder, 'build')
        os.makedirs(build_dir, exist_ok=True)
        
        # Use build-specific local game files
        local_game_files = current_build.GetGameFolder()

        if not local_game_files or not os.path.exists(local_game_files):
            return ISOResult(False, 
                f"Game folder not found for build '{build_name}'\n\n"
                f"Path: {local_game_files}\n\n"
                "Please extract or select the PS1 folder first.")
        
        self._log_verbose(f"Building from: {local_game_files}")
        
        # Show if this is a shared build
        if local_game_files and 'game_files' in local_game_files:
            folder_build_name = os.path.basename(local_game_files)
            if folder_build_name != build_name:
                self._log_verbose(f"  (Sharing game files from build: {folder_build_name})")
        
        # Use build-specific XML
        xml_path = os.path.join(project_folder, '.config', 'output', f'psxbuild_{build_name}.xml')
        
        # CRITICAL: XML must exist from extraction - never generate it manually
        if not os.path.exists(xml_path):
            return ISOResult(False,
                f"PS1 build XML not found: {xml_path}\n\n"
                "This file should have been created during ISO extraction.\n\n"
                "Please re-extract the PS1 BIN/CUE to generate the proper XML file.\n\n"
                "The XML cannot be generated manually because it requires:\n"
                "• Exact file ordering from the original disc\n"
                "• Dummy sector information for proper spacing\n"
                "• Correct file type attributes (data/mixed/audio)\n"
                "• Proper timestamps and metadata")
        
        self._log_verbose(f"Using XML: {xml_path}")
        
        # Validate XML has proper structure
        if not self._validate_ps1_xml(xml_path):
            return ISOResult(False,
                "PS1 build XML is invalid or incomplete.\n\n"
                "Please re-extract the PS1 BIN/CUE to regenerate the XML.")
        
        # Rest of the function continues as before...
        xml_path = os.path.abspath(xml_path)
        project_folder = os.path.abspath(project_folder)
        local_game_files = os.path.abspath(local_game_files)
        mkpsxiso_path = os.path.abspath(self.tools['mkpsxiso'])
        
        if not os.path.exists(mkpsxiso_path):
            return ISOResult(False, f"mkpsxiso not found at: {mkpsxiso_path}")
        
        self._log_verbose("Updating XML file paths to use local game files...")
        
        if not self._update_ps1_xml_for_local_files(xml_path, local_game_files):
            return ISOResult(False, "Failed to update XML paths")
        
        # Build command
        cmd = [
            mkpsxiso_path,
            '-y',
            xml_path
        ]
        
        self._log_verbose(f"Command: {' '.join(cmd)}")
        self._log_verbose(f"Working directory: {project_folder}")
        
        try:
            self._log_verbose("\nStarting mkpsxiso...")
            
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_folder,
                timeout=60
            )
            
            self._log_verbose(f"mkpsxiso completed with return code: {result.returncode}")

            # Always show mkpsxiso output for debugging
            if result.stdout:
                self._log_verbose(f"\n=== mkpsxiso stdout ===")
                self._log_verbose(result.stdout)
                self._log_verbose("======================\n")
            if result.stderr:
                self._log_verbose(f"\n=== mkpsxiso stderr ===")
                self._log_verbose(result.stderr)
                self._log_verbose("======================\n")

            if result.returncode != 0:
                return ISOResult(False, f"Rebuild failed (code {result.returncode}):\n{result.stderr}")
            
            # Rename output files
            bin_src = os.path.join(project_folder, 'mkpsxiso.bin')
            cue_src = os.path.join(project_folder, 'mkpsxiso.cue')
            bin_dst = os.path.join(build_dir, f'ModdedGame_{build_name}.bin')
            cue_dst = os.path.join(build_dir, f'ModdedGame_{build_name}.cue')
            
            self._log_verbose(f"\nLooking for output files:")
            self._log_verbose(f"  BIN: {bin_src} (exists: {os.path.exists(bin_src)})")
            self._log_verbose(f"  CUE: {cue_src} (exists: {os.path.exists(cue_src)})")
            
            if not os.path.exists(bin_src):
                files_in_folder = os.listdir(project_folder)
                self._log_verbose(f"Files in project folder: {files_in_folder}")
                return ISOResult(False, f"mkpsxiso did not create output BIN file.\n\nCheck stdout/stderr above for errors.")
            
            # Remove old files if they exist
            if os.path.exists(bin_dst):
                os.remove(bin_dst)
            if os.path.exists(cue_dst):
                os.remove(cue_dst)
            
            # Rename new files (with build name)
            os.rename(bin_src, bin_dst)
            if os.path.exists(cue_src):
                os.rename(cue_src, cue_dst)

                # Update .cue file contents to point to renamed .bin file instead of mkpsxiso.bin
                try:
                    with open(cue_dst, 'r', encoding='utf-8', errors='ignore') as f:
                        cue_content = f.read()

                    new_bin_filename = os.path.basename(bin_dst)
                    cue_content = cue_content.replace('mkpsxiso.bin', new_bin_filename)
                    cue_content = cue_content.replace('MKPSXISO.BIN', new_bin_filename)

                    with open(cue_dst, 'w', encoding='utf-8') as f:
                        f.write(cue_content)

                    self._log_verbose(f"  Updated .cue file to reference {new_bin_filename}")
                except Exception as e:
                    self._log_verbose(f"  Warning: Could not update .cue file {e}")

            # NOTE: Multi-bin CUE creation disabled due to timing issues
            # Multi-bin CUE files require correct INDEX positions for each track
            # When mkpsxiso rebuilds Track 01, the size may change slightly, which
            # causes all the INDEX positions for audio tracks (Track 02+) to be incorrect
            # This leads to CD-ROM timing errors in emulators like DuckStation
            #
            # For now, we only output the single modded BIN file
            # Users can load just this BIN (without music) or use other methods to add audio
            source_path = current_build.GetSourcePath()
            if source_path and source_path.lower().endswith('.cue'):
                from services.binmerge_service import BinmergeService
                bin_count = BinmergeService.parse_cue_file(source_path)

                if bin_count > 1:
                    self._log_verbose(f"\n  Note: Original game had {bin_count} tracks (data + {bin_count-1} audio)")
                    self._log_progress(f"  Output: Single modded BIN file (Track 01 data only)")
                    self._log_verbose(f"  Audio tracks not included to avoid timing issues")

            self._log_progress(f" PS1 BIN/CUE rebuilt: build/ModdedGame_{build_name}.bin/cue")
            return ISOResult(True, f"PS1 BIN/CUE rebuilt successfully for build '{build_name}'", bin_dst)
            
        except subprocess.TimeoutExpired:
            return ISOResult(False, 
                "mkpsxiso timed out after 60 seconds.\n\n"
                "Possible causes:\n"
                "- XML file has incorrect paths\n"
                "- mkpsxiso waiting for input\n"
                "- Error in XML structure\n\n"
                "Try running mkpsxiso manually to see the error.")
        except Exception as e:
            import traceback
            return ISOResult(False, f"Rebuild error: {str(e)}\n{traceback.format_exc()}")

    def _clean_ps1_xml_audio_references(self, xml_path: str, extracted_dir: str) -> bool:
        """
        Remove references to files that don't actually exist in the extracted directory.
        This is necessary when extracting only Track 01 from multi-bin PS1 games,
        as the XML references audio files that are in separate tracks (Track 02+).

        The XML 'source' attribute points to where dumpsxiso extracted files,
        so we simply check if each file's source path actually exists on disk.

        Also removes audio track elements (Track 02+) since we only have Track 01 (data track).
        """
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(xml_path)
            root = tree.getroot()

            removed_files_count = 0
            removed_tracks_count = 0

            # Find all file elements
            for file_elem in list(root.iter('file')):  # Use list() to avoid modification during iteration
                filename = file_elem.get('name', '')
                source = file_elem.get('source', '')

                if not filename:
                    continue

                # The 'source' attribute tells us where dumpsxiso put the file
                # If the file doesn't exist at that location, it's a reference to an audio track
                if source:
                    file_exists = os.path.exists(source)
                else:
                    # No source attribute - shouldn't happen with dumpsxiso, but handle it
                    file_exists = os.path.exists(os.path.join(extracted_dir, filename))

                if not file_exists:
                    # File doesn't exist - remove it from XML
                    # Find the parent element
                    parent = None
                    for p in root.iter():
                        children = list(p)
                        if file_elem in children:
                            parent = p
                            break

                    if parent is not None:
                        parent.remove(file_elem)
                        removed_files_count += 1
                        self._log_verbose(f"  Removed missing file from XML: {filename}")

            # Remove audio track elements (Track 02+)
            # These are <track type="audio"> elements that dumpsxiso creates for embedded XA audio
            # We ALWAYS remove these because mkpsxiso only supports single-track (data) output
            for track_elem in list(root.iter('track')):
                track_type = track_elem.get('type', '')
                track_id = track_elem.get('trackid', '')

                # Remove ALL audio tracks (type="audio"), regardless of whether files exist
                # Track 01 is the data track (type="data"), which we keep
                # mkpsxiso cannot create multi-track images, so audio tracks must be removed
                if track_type == 'audio':
                    # Remove this audio track element
                    parent = None
                    for p in root.iter():
                        children = list(p)
                        if track_elem in children:
                            parent = p
                            break

                    if parent is not None:
                        parent.remove(track_elem)
                        removed_tracks_count += 1
                        self._log_verbose(f"  Removed audio track {track_id} from XML (mkpsxiso single-track limitation)")

            total_removed = removed_files_count + removed_tracks_count

            if total_removed > 0:
                # Save the cleaned XML
                # IMPORTANT: Preserve element order by not reformatting
                # Use method='xml' to maintain original formatting as much as possible
                tree.write(xml_path, encoding='utf-8', xml_declaration=True, method='xml')
                self._log_verbose(f"   Cleaned XML: Removed {removed_files_count} file(s) and {removed_tracks_count} audio track(s)")
                self._log_verbose(f"    (These are audio files/tracks not present in Track 01 data track)")

            return True

        except Exception as e:
            self._log_verbose(f"  Warning: Failed to clean XML file references: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail the extraction if XML cleaning fails
            return False

    def _update_ps1_xml_for_local_files(self, xml_path: str, local_game_files: str) -> bool:
        """Update XML file to use local game files directory with proper structure"""
        try:
            import xml.etree.ElementTree as ET
            
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            project_folder = self.project_data.GetProjectFolder()
            current_build = self.project_data.GetCurrentBuildVersion()
            
            # FIX: Patched files are in build/ directory, not project root
            build_dir = os.path.join(project_folder, 'build')
            
            # Convert to absolute path
            local_game_files = os.path.abspath(local_game_files)
            
            self._log_verbose(f"Updating XML paths...")
            self._log_verbose(f"  Local game files: {local_game_files}")
            self._log_verbose(f"  Build directory: {build_dir}")
            
            # Helper function to get directory path from XML tree
            def get_dir_path_from_parent(file_elem):
                """Walk up the XML tree to build the directory path"""
                path_parts = []
                parent = file_elem
                
                # Walk up to find all parent <dir> elements
                while True:
                    found_parent = None
                    for elem in root.iter():
                        if parent in list(elem):
                            found_parent = elem
                            break
                    
                    if found_parent is None or found_parent.tag == 'directory_tree':
                        break
                    
                    if found_parent.tag == 'dir':
                        dir_name = found_parent.get('name')
                        if dir_name:
                            path_parts.insert(0, dir_name)
                    
                    parent = found_parent
                
                return os.path.join(*path_parts) if path_parts else ''
            
            updated_files = 0
            patched_files = 0
            
            # Update license file path (if present)
            track = root.find('.//track')
            if track is not None:
                license_elem = track.find('license')
                if license_elem is not None and 'file' in license_elem.attrib:
                    license_file = os.path.join(local_game_files, 'license_data.dat')
                    if os.path.exists(license_file):
                        license_elem.attrib['file'] = license_file
                        self._log_verbose(f"  Updated license file")
            
            # Process all file elements
            for file_elem in root.iter('file'):
                filename = file_elem.get('name')
                
                if not filename:
                    continue
                
                # Skip license_data.dat - handled separately
                if filename.lower() == 'license_data.dat':
                    continue
                
                # Check if patched version exists
                base_filename = os.path.basename(filename)
                # FIX: Look in build/ directory for patched files
                patched_path = os.path.abspath(os.path.join(build_dir, f"patched_{base_filename}"))
                
                if os.path.exists(patched_path):
                    # Use patched version
                    file_elem.set('source', patched_path)
                    patched_files += 1
                    self._log_verbose(f"  PATCHED: {filename}")
                else:
                    # Use original from local_game_files
                    # Get directory path from XML structure
                    dir_path = get_dir_path_from_parent(file_elem)
                    
                    if dir_path:
                        new_source = os.path.abspath(os.path.join(local_game_files, dir_path, filename))
                    else:
                        new_source = os.path.abspath(os.path.join(local_game_files, filename))
                    
                    # Verify file exists before updating XML
                    if os.path.exists(new_source):
                        file_elem.set('source', new_source)
                        updated_files += 1
                    else:
                        # File doesn't exist - this shouldn't happen if XML was cleaned properly
                        self._log_verbose(f"  WARNING: File not found: {os.path.join(dir_path, filename) if dir_path else filename}")
                        self._log_verbose(f"      Expected path: {new_source}")
                        self._log_verbose(f"      This file will be skipped in the build")
                        # Remove this file element from XML to prevent mkpsxiso errors
                        parent = None
                        for p in root.iter():
                            children = list(p)
                            if file_elem in children:
                                parent = p
                                break
                        if parent is not None:
                            parent.remove(file_elem)
                            self._log_verbose(f"      Removed from XML to prevent build errors")
            
            # Add new files
            self._add_ps1_new_files_to_xml(root, local_game_files)
            
            # Save updated XML
            tree.write(xml_path, encoding='utf-8', xml_declaration=True)
            self._log_verbose(f"\nUpdated {updated_files} files, {patched_files} patched")
            
            return True
            
        except Exception as e:
            self._log_verbose(f" Failed to update XML: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _rebuild_ps2(self) -> ISOResult:
        """Rebuild PS2 ISO using ps2iso (Ps2IsoTools)"""
        self._log_progress("Rebuilding PS2 ISO...")

        current_build = self.project_data.GetCurrentBuildVersion()
        project_folder = self.project_data.GetProjectFolder()
        source_dir = current_build.GetGameFolder()
        build_name = current_build.GetBuildName()

        build_dir = os.path.join(project_folder, 'build')
        os.makedirs(build_dir, exist_ok=True)

        output_iso = os.path.join(build_dir, f'ModdedGame_{build_name}.iso')

        # Delete existing ISO (ps2iso will create new one)
        if os.path.exists(output_iso):
            try:
                self._log_verbose(f"Existing ISO found, deleting: {output_iso}")
                os.remove(output_iso)
            except Exception as e:
                return ISOResult(False, f"Could not remove existing ISO:\n{e}")
        
        if not source_dir or not os.path.exists(source_dir):
            return ISOResult(False, f"Source folder not found: {source_dir}")

        self._log_verbose(f"Source folder: {source_dir}")

        # Use persistent build directory for optimization
        temp_build_dir = os.path.join(project_folder, '.config', 'output', 'iso_build', build_name)

        self._log_verbose(f"Preparing build folder: {temp_build_dir}")

        # Smart copy: full copy on first build, use existing on subsequent builds
        if not self._prepare_build_directory(source_dir, temp_build_dir):
            return ISOResult(False, "Failed to prepare build directory")

        # Copy injection files from original to reset them to vanilla before patching
        self._copy_injection_files_from_original(source_dir, temp_build_dir, current_build)

        main_exe = current_build.GetMainExecutable()
        if not main_exe:
            return ISOResult(False, "Main executable not set")

        build_files_dir = os.path.join(project_folder, 'build')
        patched_exe = os.path.join(build_files_dir, f"patched_{main_exe}")

        if not os.path.exists(patched_exe):
            return ISOResult(False, f"Patched executable not found: {patched_exe}")

        target_exe = os.path.join(temp_build_dir, main_exe)

        try:
            self._log_verbose(f"Replacing {main_exe} with patched version...")
            if os.path.exists(target_exe):
                os.remove(target_exe)
            shutil.copyfile(patched_exe, target_exe)
            self._log_verbose(f"  Patched executable copied to build folder")
        except Exception as e:
            return ISOResult(False, f"Could not replace executable: {str(e)}")
        
        self._copy_ps2_new_files_to_build(temp_build_dir)

        cmd = [
            self.tools['ps2iso'],
            'build',
            temp_build_dir,
            output_iso,
            '--volume-label', 'Modded_Game'
        ]

        self._log_verbose(f"Command: {' '.join(cmd)}")

        try:
            self._log_verbose("\nStarting ps2iso...")
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd(),
                timeout=300
            )

            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")

            if result.returncode != 0:
                return ISOResult(False, f"ps2iso failed with return code {result.returncode}. Check output above.")

            if not os.path.exists(output_iso):
                return ISOResult(False, "ISO file was not created. Check ps2iso output above.")

            # Reset injection files back to vanilla for next build
            self._log_verbose("Resetting injection files to vanilla...")
            self._copy_injection_files_from_original(source_dir, temp_build_dir, current_build)

            # Remove new files from build folder
            self._log_verbose("Removing new files from build folder...")
            self._remove_new_files_from_build(temp_build_dir, current_build)

            # Keep temp_build_dir persistent for faster subsequent builds
            self._log_verbose(f" Build folder kept for optimization: {temp_build_dir}")

            self._log_progress(f" PS2 ISO rebuilt: ModdedGame.iso")
            return ISOResult(True, f"PS2 ISO rebuilt successfully for build '{build_name}'", output_iso)

        except subprocess.TimeoutExpired:
            return ISOResult(False, "ps2iso timed out after 5 minutes.")
        except Exception as e:
            import traceback
            return ISOResult(False, f"Rebuild error: {str(e)}\n{traceback.format_exc()}")



    
    def _rebuild_gamecube(self) -> ISOResult:
        """Rebuild GameCube ISO using gc-fst"""
        self._log_verbose("\n" + "=" * 60)
        self._log_verbose("GAMECUBE ISO REBUILD")
        self._log_verbose("=" * 60)
        
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()
        
        build_dir = os.path.join(project_folder, 'build')
        os.makedirs(build_dir, exist_ok=True)
        
        # Get the game folder (which should point to the 'root' directory)
        game_folder = current_build.GetGameFolder()
        
        self._log_verbose(f"\n[DEBUG] game_folder from project: {game_folder}")
        self._log_verbose(f"[DEBUG] game_folder exists: {os.path.exists(game_folder) if game_folder else 'None'}")
        
        if not game_folder or not os.path.exists(game_folder):
            # Try to find it in the expected location
            expected_root = os.path.join(project_folder, '.config', 'game_files', build_name, 'root')
            self._log_verbose(f"[DEBUG] Trying expected location: {expected_root}")
            self._log_verbose(f"[DEBUG] Expected location exists: {os.path.exists(expected_root)}")
            
            if os.path.exists(expected_root):
                self._log_verbose(f"  Found files at expected location: {expected_root}")
                game_folder = expected_root
                current_build.SetGameFolder(game_folder)
            else:
                return ISOResult(False, 
                    f"Game files not found!\n\n"
                    f"game_folder was: {current_build.GetGameFolder()}\n"
                    f"Also checked: {expected_root}\n\n"
                    "Please extract the GameCube ISO first.")
        
        self._log_verbose(f"Building from: {game_folder}")
        
        # List what's actually in game_folder
        if os.path.exists(game_folder):
            files = os.listdir(game_folder)
            self._log_verbose(f"  Files in game_folder: {len(files)} items")
            self._log_verbose(f"  First 5 items: {files[:5]}")

        # Use persistent build directory for optimization
        temp_build_dir = os.path.join(project_folder, '.config', 'output', 'iso_build', build_name)
        temp_root = os.path.join(temp_build_dir, 'root')

        self._log_verbose(f"Preparing build folder: {temp_build_dir}")
        self._log_verbose(f"Root directory: {temp_root}")

        # Smart copy: full copy on first build, use existing on subsequent builds
        # GameCube needs the 'root' subdirectory structure for gc-fst
        if not self._prepare_build_directory(game_folder, temp_root):
            return ISOResult(False, "Failed to prepare build directory")

        # Copy injection files from original to reset them to vanilla before patching
        self._copy_injection_files_from_original(game_folder, temp_root, current_build)

        # Copy patched files
        main_exe = current_build.GetMainExecutable()
        if not main_exe:
            return ISOResult(False, "Main executable not set")
        
        build_files_dir = os.path.join(project_folder, 'build')
        patched_main_exe = os.path.join(build_files_dir, f"patched_{main_exe}")
        
        if not os.path.exists(patched_main_exe):
            return ISOResult(False, 
                f"Patched executable not found!\n\n"
                f"Expected: {patched_main_exe}\n\n"
                "The patching step may have failed.")
        
        # Determine target path in temp build
        if main_exe.lower() == "start.dol":
            target_exe = os.path.join(temp_root, '&&SystemData', 'Start.dol')
        elif main_exe.lower() == "main.dol":
            target_exe = os.path.join(temp_root, 'main.dol')
        else:
            # Find the file in the game folder structure
            original_exe_path = current_build.FindFileInGameFolder(main_exe)
            if original_exe_path:
                # game_folder is already pointing to 'root', so get relative path from there
                relative_path = os.path.relpath(original_exe_path, game_folder)
                target_exe = os.path.join(temp_root, relative_path)
            else:
                return ISOResult(False, f"Could not determine path for {main_exe}")
        
        try:
            self._log_verbose(f"\nCopying patched {main_exe}...")
            self._log_verbose(f"  FROM: {patched_main_exe}")
            self._log_verbose(f"  TO: {target_exe}")
            
            os.makedirs(os.path.dirname(target_exe), exist_ok=True)
            if os.path.exists(target_exe):
                os.remove(target_exe)
            shutil.copyfile(patched_main_exe, target_exe)
            self._log_verbose(f"  Patched executable copied")
        except Exception as e:
            return ISOResult(False, f"Could not copy patched executable: {str(e)}")
        
        # Copy other patched injection files
        injection_files = current_build.GetInjectionFiles()
        
        for file_name in injection_files:
            if file_name == main_exe:
                continue
            
            base_filename = os.path.basename(file_name)
            patched_file = os.path.join(build_files_dir, f"patched_{base_filename}")
            
            if not os.path.exists(patched_file):
                continue
            
            # Find original file location
            original_file_path = current_build.FindFileInGameFolder(file_name)
            if not original_file_path:
                self._log_verbose(f"  Warning: Could not find original location for {file_name}")
                continue
            
            # Calculate relative path from game_folder (which is already 'root')
            relative_path = os.path.relpath(original_file_path, game_folder)
            target_file = os.path.join(temp_root, relative_path)
            
            try:
                self._log_progress(f"Inserting patched {file_name}...")
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                if os.path.exists(target_file):
                    os.remove(target_file)
                shutil.copyfile(patched_file, target_file)
                self._log_verbose(f"  Copied to: {relative_path}")
            except Exception as e:
                self._log_verbose(f"  Warning: Could not copy {file_name}: {str(e)}")
        
        # Add new files
        self._add_gamecube_new_files(temp_root, current_build, build_files_dir)
        
        # Build ISO
        output_iso = os.path.join(build_dir, f'ModdedGame_{build_name}.iso')
        
        if os.path.exists(output_iso):
            try:
                os.remove(output_iso)
            except PermissionError:
                return ISOResult(False, 
                    "Cannot remove old ISO!\n\n"
                    "The file may be open in another program.")
        
        gc_fst_path = self.tools['gc_fst']
        if not os.path.exists(gc_fst_path):
            return ISOResult(False, f"gc-fst tool not found: {gc_fst_path}")
        
        self._log_progress(f"\nBuilding ISO with gc-fst...")
        self._log_verbose(f"  gc-fst tool: {gc_fst_path}")
        self._log_verbose(f"  Root folder: {temp_root}")
        self._log_verbose(f"  Output ISO: {output_iso}")
        self._log_verbose(f"  Working directory: {temp_build_dir}")
        
        # Convert to absolute paths
        temp_root_abs = os.path.abspath(temp_root)
        output_iso_abs = os.path.abspath(output_iso)
        
        self._log_verbose(f"  Root folder (abs): {temp_root_abs}")
        self._log_verbose(f"  Output ISO (abs): {output_iso_abs}")
        
        cmd = [
            gc_fst_path,
            'rebuild',
            temp_root_abs,
            output_iso_abs
        ]
        
        self._log_verbose(f"  Command: {' '.join(cmd)}")
        self._log_verbose(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd(),  # Run from main directory, not temp_build_dir
                timeout=300
            )
            
            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
                self._log_verbose(f"gc-fst output: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")
                self._log_verbose(f"gc-fst errors: {result.stderr}")
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown error"
                # Don't clean up temp folder on error so we can inspect it
                return ISOResult(False, 
                    f"gc-fst rebuild failed (exit code {result.returncode}):\n\n{error_msg}\n\n"
                    f"Temp folder preserved for inspection: {temp_build_dir}")
            
            if not os.path.exists(output_iso):
                return ISOResult(False, 
                    f"ISO file was not created by gc-fst.\n\n"
                    f"Temp folder preserved for inspection: {temp_build_dir}")

            # Reset injection files back to vanilla for next build
            self._log_verbose("Resetting injection files to vanilla...")
            self._copy_injection_files_from_original(game_folder, temp_root, current_build)

            # Remove new files from build folder
            self._log_verbose("Removing new files from build folder...")
            self._remove_new_files_from_build(temp_root, current_build)

            # Keep temp_build_dir persistent for faster subsequent builds
            self._log_verbose(f" Build folder kept for optimization: {temp_build_dir}")

            final_size = os.path.getsize(output_iso)

            output_format = self.project_data.GetCurrentBuildVersion().GetOutputFormat()
            output_iso_no_ext, ext = os.path.splitext(output_iso)

            if output_format == "gcm":
                os.rename(output_iso, output_iso_no_ext+".gcm")

            self._log_progress(f"\nISO created:")
            self._log_progress(f"  Size: {final_size:,} bytes ({final_size / (1024*1024):.2f} MB)")

            self._log_verbose("\n" + "=" * 60)
            self._log_progress("GAMECUBE ISO BUILD COMPLETE")
            self._log_verbose("=" * 60)
            self._log_progress(f"\nOutput: {output_iso}")

            return ISOResult(True, "GameCube ISO rebuilt successfully", output_iso)
            
        except subprocess.TimeoutExpired:
            return ISOResult(False, f"gc-fst timed out after 5 minutes.\n\nTemp folder: {temp_build_dir}")
        except Exception as e:
            import traceback
            return ISOResult(False, f"Rebuild error: {str(e)}\n{traceback.format_exc()}\n\nTemp folder: {temp_build_dir}")
        
    def _rebuild_gamecube_with_wit(self, output_format: str = "iso") -> ISOResult:
        """Rebuild GameCube image using two-step process: gc-fst -> ISO, then WIT -> format"""
        self._log_verbose("\n" + "=" * 60)
        self._log_progress(f"GAMECUBE {output_format.upper()} REBUILD")
        self._log_verbose("=" * 60)
        
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()
        
        build_dir = os.path.join(project_folder, 'build')
        os.makedirs(build_dir, exist_ok=True)
        
        # Get the game folder (which should point to the 'root' directory)
        game_folder = current_build.GetGameFolder()
        
        if not game_folder or not os.path.exists(game_folder):
            expected_root = os.path.join(project_folder, '.config', 'game_files', build_name, 'root')
            if os.path.exists(expected_root):
                game_folder = expected_root
                current_build.SetGameFolder(game_folder)
            else:
                return ISOResult(False, 
                    f"Game files not found!\n\n"
                    f"Please extract the GameCube ISO first.")
        
        self._log_verbose(f"Building from: {game_folder}")

        # Use persistent build directory for optimization (same as _rebuild_gamecube)
        temp_build_dir = os.path.join(project_folder, '.config', 'output', 'iso_build', build_name)
        temp_root = os.path.join(temp_build_dir, 'root')

        self._log_verbose(f"Preparing build folder: {temp_build_dir}")
        self._log_verbose(f"Root directory: {temp_root}")

        # Smart copy: full copy on first build, use existing on subsequent builds
        if not self._prepare_build_directory(game_folder, temp_root):
            return ISOResult(False, "Failed to prepare build directory")

        # Copy injection files from original to reset them to vanilla before patching
        self._copy_injection_files_from_original(game_folder, temp_root, current_build)
        
        # Copy patched files (same logic as _rebuild_gamecube)
        main_exe = current_build.GetMainExecutable()
        if not main_exe:
            return ISOResult(False, "Main executable not set")
        
        build_files_dir = os.path.join(project_folder, 'build')
        patched_main_exe = os.path.join(build_files_dir, f"patched_{main_exe}")
        
        if not os.path.exists(patched_main_exe):
            return ISOResult(False, 
                f"Patched executable not found!\n\n"
                f"Expected: {patched_main_exe}\n\n"
                "The patching step may have failed.")
        
        # Determine target path
        if main_exe.lower() == "start.dol":
            target_exe = os.path.join(temp_root, '&&SystemData', 'Start.dol')
        elif main_exe.lower() == "main.dol":
            target_exe = os.path.join(temp_root, 'main.dol')
        else:
            original_exe_path = current_build.FindFileInGameFolder(main_exe)
            if original_exe_path:
                relative_path = os.path.relpath(original_exe_path, game_folder)
                target_exe = os.path.join(temp_root, relative_path)
            else:
                return ISOResult(False, f"Could not determine path for {main_exe}")
        
        try:
            self._log_verbose(f"\nCopying patched {main_exe}...")
            os.makedirs(os.path.dirname(target_exe), exist_ok=True)
            if os.path.exists(target_exe):
                os.remove(target_exe)
            shutil.copyfile(patched_main_exe, target_exe)
            self._log_verbose(f"  Patched executable copied")
        except Exception as e:
            return ISOResult(False, f"Could not copy patched executable: {str(e)}")
        
        # Copy other patched injection files
        injection_files = current_build.GetInjectionFiles()
        for file_name in injection_files:
            if file_name == main_exe:
                continue
            
            base_filename = os.path.basename(file_name)
            patched_file = os.path.join(build_files_dir, f"patched_{base_filename}")
            
            if not os.path.exists(patched_file):
                continue
            
            original_file_path = current_build.FindFileInGameFolder(file_name)
            if not original_file_path:
                self._log_verbose(f"  Warning: Could not find original location for {file_name}")
                continue
            
            relative_path = os.path.relpath(original_file_path, game_folder)
            target_file = os.path.join(temp_root, relative_path)
            
            try:
                self._log_progress(f"Inserting patched {file_name}...")
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                if os.path.exists(target_file):
                    os.remove(target_file)
                shutil.copyfile(patched_file, target_file)
                self._log_verbose(f"  Copied to: {relative_path}")
            except Exception as e:
                self._log_verbose(f"  Warning: Could not copy {file_name}: {str(e)}")
        
        # Add new files
        self._add_gamecube_new_files(temp_root, current_build, build_files_dir)
        
        # STEP 1: Build temporary ISO with gc-fst
        self._log_progress(f"\nStep 1/2: Building temporary ISO with gc-fst...")
        
        temp_iso_path = os.path.join(temp_build_dir, 'temp_build.iso')
        temp_root_abs = os.path.abspath(temp_root)
        temp_iso_abs = os.path.abspath(temp_iso_path)
        
        gc_fst_path = self.tools['gc_fst']
        if not os.path.exists(gc_fst_path):
            return ISOResult(False, f"gc-fst tool not found: {gc_fst_path}")
        
        cmd_gcfst = [
            gc_fst_path,
            'rebuild',
            temp_root_abs,
            temp_iso_abs
        ]
        
        self._log_verbose(f"gc-fst command: {' '.join(cmd_gcfst)}")
        
        try:
            result = subprocess.run(
                cmd_gcfst,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd(),
                timeout=300
            )
            
            if result.stdout:
                self._log_verbose(f"gc-fst stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"gc-fst stderr: {result.stderr}")
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown error"
                return ISOResult(False, 
                    f"gc-fst rebuild failed (exit code {result.returncode}):\n\n{error_msg}\n\n"
                    f"Temp folder preserved for inspection: {temp_build_dir}")
            
            if not os.path.exists(temp_iso_path):
                return ISOResult(False, 
                    f"Temporary ISO was not created by gc-fst.\n\n"
                    f"Temp folder preserved for inspection: {temp_build_dir}")
            
            self._log_verbose(f"  Temporary ISO created: {os.path.getsize(temp_iso_path):,} bytes")
            
        except subprocess.TimeoutExpired:
            return ISOResult(False, f"gc-fst timed out after 5 minutes.\n\nTemp folder: {temp_build_dir}")
        except Exception as e:
            import traceback
            return ISOResult(False, f"gc-fst error: {str(e)}\n{traceback.format_exc()}\n\nTemp folder: {temp_build_dir}")
        
        # STEP 2: Convert ISO to desired format using WIT
        self._log_verbose(f"\nStep 2/2: Converting ISO to {output_format.upper()} with WIT...")
        
        output_file = os.path.join(build_dir, f'ModdedGame_{build_name}.{output_format}')
        output_file_abs = os.path.abspath(output_file)
        
        # Remove old output file if exists
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except PermissionError:
                return ISOResult(False, 
                    "Cannot remove old file!\n\n"
                    "The file may be open in another program.")
        
        wit_path = self.tools['wit']
        if not os.path.exists(wit_path):
            return ISOResult(False, f"WIT tool not found: {wit_path}")
        
        # Build WIT command based on format
        if output_format == "ciso":
            cmd_wit = [
                wit_path,
                'copy',
                temp_iso_abs,
                output_file_abs,
                '--ciso'
            ]
        elif output_format == "gcn":
            cmd_wit = [
                wit_path,
                'copy',
                temp_iso_abs,
                output_file_abs
                # WIT will detect .gcn extension automatically
            ]
        else:  # Should not reach here, but handle it
            return ISOResult(False, f"Invalid format for WIT conversion: {output_format}")
        
        self._log_verbose(f"WIT command: {' '.join(cmd_wit)}")
        
        try:
            result = subprocess.run(
                cmd_wit,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.tool_dir,
                timeout=300
            )
            
            if result.stdout:
                self._log_verbose(f"WIT stdout: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"WIT stderr: {result.stderr}")
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown error"
                # Don't clean up on error
                return ISOResult(False, 
                    f"WIT conversion failed (exit code {result.returncode}):\n\n{error_msg}\n\n"
                    f"Temp folder preserved for inspection: {temp_build_dir}")
            
            if not os.path.exists(output_file):
                return ISOResult(False, 
                    f"{output_format.upper()} file was not created by WIT.\n\n"
                    f"Temp folder preserved for inspection: {temp_build_dir}")
            
            self._log_progress(f"  {output_format.upper()} created: {os.path.getsize(output_file):,} bytes")
            
        except subprocess.TimeoutExpired:
            return ISOResult(False, f"WIT timed out after 5 minutes.\n\nTemp folder: {temp_build_dir}")
        except Exception as e:
            import traceback
            return ISOResult(False, f"WIT error: {str(e)}\n{traceback.format_exc()}\n\nTemp folder: {temp_build_dir}")
        
        # Clean up temp ISO (but keep build folder for faster subsequent builds)
        try:
            # Delete temp ISO
            if os.path.exists(temp_iso_path):
                os.remove(temp_iso_path)
                self._log_verbose("Deleted temporary ISO")
        except Exception as e:
            self._log_verbose(f"Warning: Could not delete temporary ISO: {e}")

        # Reset injection files back to vanilla for next build
        self._log_verbose("Resetting injection files to vanilla...")
        self._copy_injection_files_from_original(game_folder, temp_root, current_build)

        # Remove new files from build folder
        self._log_verbose("Removing new files from build folder...")
        self._remove_new_files_from_build(temp_root, current_build)

        # Keep temp_build_dir persistent for faster subsequent builds
        self._log_verbose(f" Build folder kept for optimization: {temp_build_dir}")
        
        final_size = os.path.getsize(output_file)
        self._log_progress(f"\n{output_format.upper()} created:")
        self._log_progress(f"  Size: {final_size:,} bytes ({final_size / (1024*1024):.2f} MB)")
        
        self._log_verbose("\n" + "=" * 60)
        self._log_progress(f"GAMECUBE {output_format.upper()} BUILD COMPLETE")
        self._log_verbose("=" * 60)
        self._log_progress(f"\nOutput: {output_file}")
        
        return ISOResult(True, f"GameCube {output_format.upper()} rebuilt successfully", output_file)
    
    def _add_gamecube_new_files(self, temp_root: str, current_build, build_files_dir: str):
        """Add new files to GameCube build folder"""
        self._log_progress(f"\n[Adding New Files]")
        
        project_folder = self.project_data.GetProjectFolder()
        bin_output_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')
        
        new_files_added = 0
        
        for codecave in current_build.GetEnabledCodeCaves():
            if codecave.IsNewFile():
                filename = codecave.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping codecave '{codecave.GetName()}' - invalid filename")
                    continue
                
                filename = filename.strip()
                
                # For new files, use the compiled binary from bin_output_dir
                bin_file = os.path.join(bin_output_dir, f"{codecave.GetName()}.bin")
                
                if not os.path.exists(bin_file):
                    self._log_verbose(f"  Warning: Binary not found for codecave '{codecave.GetName()}'")
                    self._log_verbose(f"    Expected: {bin_file}")
                    continue
                
                # Determine target path in temp_root
                # filename might have path separators
                target_path = os.path.join(temp_root, filename.replace('\\', '/'))
                
                try:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copyfile(bin_file, target_path)
                    new_files_added += 1
                    self._log_verbose(f"  Added: {filename}")
                    self._log_verbose(f"    From: {bin_file}")
                    self._log_verbose(f"    To: {target_path}")
                    self._log_verbose(f"    Size: {os.path.getsize(bin_file)} bytes")
                except Exception as e:
                    self._log_verbose(f"  Error adding {filename}: {e}")
        
        for hook in current_build.GetEnabledHooks():
            if hook.IsNewFile():
                filename = hook.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping hook '{hook.GetName()}' - invalid filename")
                    continue
                
                filename = filename.strip()
                
                # For new files, use the compiled binary from bin_output_dir
                bin_file = os.path.join(bin_output_dir, f"{hook.GetName()}.bin")
                
                if not os.path.exists(bin_file):
                    self._log_verbose(f"  Warning: Binary not found for hook '{hook.GetName()}'")
                    self._log_verbose(f"    Expected: {bin_file}")
                    continue
                
                target_path = os.path.join(temp_root, filename.replace('\\', '/'))
                
                try:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copyfile(bin_file, target_path)
                    new_files_added += 1
                    self._log_verbose(f"  Added: {filename}")
                    self._log_verbose(f"    From: {bin_file}")
                    self._log_verbose(f"    To: {target_path}")
                    self._log_verbose(f"    Size: {os.path.getsize(bin_file)} bytes")
                except Exception as e:
                    self._log_verbose(f"  Error adding {filename}: {e}")
        
        for patch in current_build.GetEnabledBinaryPatches():
            if patch.IsNewFile():
                filename = patch.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping patch '{patch.GetName()}' - invalid filename")
                    continue
                
                filename = filename.strip()
                
                # For new files, use the compiled binary from bin_output_dir
                bin_file = os.path.join(bin_output_dir, f"{patch.GetName()}.bin")
                
                if not os.path.exists(bin_file):
                    self._log_verbose(f"  Warning: Binary not found for patch '{patch.GetName()}'")
                    self._log_verbose(f"    Expected: {bin_file}")
                    continue
                
                target_path = os.path.join(temp_root, filename.replace('\\', '/'))
                
                try:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copyfile(bin_file, target_path)
                    new_files_added += 1
                    self._log_verbose(f"  Added: {filename}")
                    self._log_verbose(f"    From: {bin_file}")
                    self._log_verbose(f"    To: {target_path}")
                    self._log_verbose(f"    Size: {os.path.getsize(bin_file)} bytes")
                except Exception as e:
                    self._log_verbose(f"  Error adding {filename}: {e}")
        
        if new_files_added == 0:
            self._log_progress("  No new files to add")
        else:
            self._log_verbose(f"\n  Total new files added: {new_files_added}")
    
    def _rebuild_wii(self, disc_format: str = "iso") -> ISOResult:
        """Rebuild Wii ISO using WIT"""
        self._log_verbose("\n" + "=" * 60)
        self._log_progress("WII ISO REBUILD")
        self._log_verbose("=" * 60)
        
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        build_name = current_build.GetBuildName()
        
        build_dir = os.path.join(project_folder, 'build')
        os.makedirs(build_dir, exist_ok=True)
        
        # Get the game folder
        game_folder = current_build.GetGameFolder()
        
        self._log_verbose(f"\n[DEBUG] game_folder from project: {game_folder}")
        self._log_verbose(f"[DEBUG] game_folder exists: {os.path.exists(game_folder) if game_folder else 'None'}")
        
        if not game_folder or not os.path.exists(game_folder):
            # Try to find it in the expected location
            expected_location = os.path.join(project_folder, '.config', 'game_files', build_name)
            self._log_verbose(f"[DEBUG] Trying expected location: {expected_location}")
            self._log_verbose(f"[DEBUG] Expected location exists: {os.path.exists(expected_location)}")
            
            if os.path.exists(expected_location):
                self._log_verbose(f"  Found files at expected location: {expected_location}")
                game_folder = expected_location
                current_build.SetGameFolder(game_folder)
            else:
                return ISOResult(False, 
                    f"Game files not found!\n\n"
                    f"game_folder was: {current_build.GetGameFolder()}\n"
                    f"Also checked: {expected_location}\n\n"
                    "Please extract the Wii ISO first.")
        
        self._log_verbose(f"Building from: {game_folder}")
        
        # List what's actually in game_folder
        if os.path.exists(game_folder):
            files = os.listdir(game_folder)
            self._log_verbose(f"  Files in game_folder: {len(files)} items")
            self._log_verbose(f"  First 5 items: {files[:5]}")

        # Use persistent build directory for optimization
        temp_build_dir = os.path.join(project_folder, '.config', 'output', 'iso_build', build_name)

        self._log_verbose(f"Preparing build folder: {temp_build_dir}")

        # Smart copy: full copy on first build, use existing on subsequent builds
        if not self._prepare_build_directory(game_folder, temp_build_dir):
            return ISOResult(False, "Failed to prepare build directory")

        # Copy injection files from original to reset them to vanilla before patching
        self._copy_injection_files_from_original(game_folder, temp_build_dir, current_build)

        # Copy patched files
        main_exe = current_build.GetMainExecutable()
        if not main_exe:
            return ISOResult(False, "Main executable not set")
        
        build_files_dir = os.path.join(project_folder, 'build')
        patched_main_exe = os.path.join(build_files_dir, f"patched_{main_exe}")
        
        if not os.path.exists(patched_main_exe):
            return ISOResult(False, 
                f"Patched executable not found!\n\n"
                f"Expected: {patched_main_exe}\n\n"
                "The patching step may have failed.")
        
        # Wii executables are typically in sys/ folder
        # Determine target path in temp build
        if main_exe.lower() == "main.dol":
            target_exe = os.path.join(temp_build_dir, 'sys', 'main.dol')
        else:
            # Find the file in the game folder structure
            original_exe_path = current_build.FindFileInGameFolder(main_exe)
            if original_exe_path:
                relative_path = os.path.relpath(original_exe_path, game_folder)
                target_exe = os.path.join(temp_build_dir, relative_path)
            else:
                return ISOResult(False, f"Could not determine path for {main_exe}")
        
        try:
            self._log_verbose(f"\nCopying patched {main_exe}...")
            self._log_verbose(f"  FROM: {patched_main_exe}")
            self._log_verbose(f"  TO: {target_exe}")
            
            os.makedirs(os.path.dirname(target_exe), exist_ok=True)
            if os.path.exists(target_exe):
                os.remove(target_exe)
            shutil.copyfile(patched_main_exe, target_exe)
            self._log_verbose(f"  Patched executable copied")
        except Exception as e:
            return ISOResult(False, f"Could not copy patched executable: {str(e)}")
        
        # Copy other patched injection files
        injection_files = current_build.GetInjectionFiles()
        
        for file_name in injection_files:
            if file_name == main_exe:
                continue
            
            base_filename = os.path.basename(file_name)
            patched_file = os.path.join(build_files_dir, f"patched_{base_filename}")
            
            if not os.path.exists(patched_file):
                continue
            
            # Find original file location
            original_file_path = current_build.FindFileInGameFolder(file_name)
            if not original_file_path:
                self._log_verbose(f"  Warning: Could not find original location for {file_name}")
                continue
            
            # Calculate relative path from game_folder
            relative_path = os.path.relpath(original_file_path, game_folder)
            target_file = os.path.join(temp_build_dir, relative_path)
            
            try:
                self._log_progress(f"Inserting patched {file_name}...")
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                if os.path.exists(target_file):
                    os.remove(target_file)
                shutil.copyfile(patched_file, target_file)
                self._log_verbose(f"  Copied to: {relative_path}")
            except Exception as e:
                self._log_verbose(f"  Warning: Could not copy {file_name}: {str(e)}")
        
        # Add new files
        self._add_wii_new_files(temp_build_dir, current_build, build_files_dir)
        
        # Build ISO with WIT
        output_iso = os.path.join(build_dir, f'ModdedGame_{build_name}.{disc_format}')
        
        if os.path.exists(output_iso):
            try:
                os.remove(output_iso)
            except PermissionError:
                return ISOResult(False, 
                    "Cannot remove old ISO!\n\n"
                    "The file may be open in another program.")
        
        wit_path = self.tools['wit']
        wwt_path = self.tools['wwt']
        wdf_path = self.tools['wdf']
        if not os.path.exists(wit_path):
            return ISOResult(False, f"WIT tool not found: {wit_path}")
        
        self._log_progress(f"\nBuilding ISO with WIT...")
        #print(f"  WIT tool: {wit_path}")
        #print(f"  Source folder: {temp_build_dir}")
        #print(f"  Output ISO: {output_iso}")
        
        # Convert to absolute paths
        temp_build_dir_abs = os.path.abspath(temp_build_dir)
        output_iso_abs = os.path.abspath(output_iso)
        
        #print(f"  Source folder (abs): {temp_build_dir_abs}")
        #print(f"  Output ISO (abs): {output_iso_abs}")
        

        cmd = [
            wit_path,
            'copy',
            temp_build_dir_abs,
            output_iso_abs
        ]
        
        #print(f"  Command: {' '.join(cmd)}")
        self._log_verbose(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.tool_dir,
                timeout=300
            )
            
            if result.stdout:
                self._log_verbose(f"stdout: {result.stdout}")
                self._log_verbose(f"WIT output: {result.stdout}")
            if result.stderr:
                self._log_verbose(f"stderr: {result.stderr}")
                self._log_verbose(f"WIT errors: {result.stderr}")
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown error"
                # Don't clean up temp folder on error so we can inspect it
                return ISOResult(False, 
                    f"WIT rebuild failed (exit code {result.returncode}):\n\n{error_msg}\n\n"
                    f"Temp folder preserved for inspection: {temp_build_dir}")
            
            if not os.path.exists(output_iso):
                return ISOResult(False, 
                    f"ISO file was not created by WIT.\n\n"
                    f"Temp folder preserved for inspection: {temp_build_dir}")

            # Reset injection files back to vanilla for next build
            self._log_verbose("Resetting injection files to vanilla...")
            self._copy_injection_files_from_original(game_folder, temp_build_dir, current_build)

            # Remove new files from build folder
            self._log_verbose("Removing new files from build folder...")
            self._remove_new_files_from_build(temp_build_dir, current_build)

            # Keep temp_build_dir persistent for faster subsequent builds
            self._log_verbose(f" Build folder kept for optimization: {temp_build_dir}")

            final_size = os.path.getsize(output_iso)
            self._log_progress(f"\nISO created:")
            self._log_progress(f"  Size: {final_size:,} bytes ({final_size / (1024*1024):.2f} MB)")

            self._log_verbose("\n" + "=" * 60)
            self._log_progress("WII ISO BUILD COMPLETE")
            self._log_verbose("=" * 60)
            self._log_progress(f"\nOutput: {output_iso}")

            return ISOResult(True, "Wii ISO rebuilt successfully", output_iso)
            
        except subprocess.TimeoutExpired:
            return ISOResult(False, f"WIT timed out after 5 minutes.\n\nTemp folder: {temp_build_dir}")
        except Exception as e:
            import traceback
            return ISOResult(False, f"Rebuild error: {str(e)}\n{traceback.format_exc()}\n\nTemp folder: {temp_build_dir}")
        
    def _add_wii_new_files(self, temp_build_dir: str, current_build, build_files_dir: str):
        """Add new files to Wii build folder"""
        self._log_progress(f"\n[Adding New Files]")
        
        project_folder = self.project_data.GetProjectFolder()
        bin_output_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')
        
        new_files_added = 0
        
        for codecave in current_build.GetEnabledCodeCaves():
            if codecave.IsNewFile():
                filename = codecave.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping codecave '{codecave.GetName()}' - invalid filename")
                    continue
                
                filename = filename.strip()
                
                # For new files, use the compiled binary from bin_output_dir
                bin_file = os.path.join(bin_output_dir, f"{codecave.GetName()}.bin")
                
                if not os.path.exists(bin_file):
                    self._log_verbose(f"  Warning: Binary not found for codecave '{codecave.GetName()}'")
                    self._log_verbose(f"    Expected: {bin_file}")
                    continue
                
                # Determine target path in temp_build_dir
                # filename might have path separators
                target_path = os.path.join(temp_build_dir, filename.replace('\\', '/'))
                
                try:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copyfile(bin_file, target_path)
                    new_files_added += 1
                    self._log_verbose(f"  Added: {filename}")
                    self._log_verbose(f"    From: {bin_file}")
                    self._log_verbose(f"    To: {target_path}")
                    self._log_verbose(f"    Size: {os.path.getsize(bin_file)} bytes")
                except Exception as e:
                    self._log_verbose(f"  Error adding {filename}: {e}")
        
        for hook in current_build.GetEnabledHooks():
            if hook.IsNewFile():
                filename = hook.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping hook '{hook.GetName()}' - invalid filename")
                    continue
                
                filename = filename.strip()
                
                # For new files, use the compiled binary from bin_output_dir
                bin_file = os.path.join(bin_output_dir, f"{hook.GetName()}.bin")
                
                if not os.path.exists(bin_file):
                    self._log_verbose(f"  Warning: Binary not found for hook '{hook.GetName()}'")
                    self._log_verbose(f"    Expected: {bin_file}")
                    continue
                
                target_path = os.path.join(temp_build_dir, filename.replace('\\', '/'))
                
                try:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copyfile(bin_file, target_path)
                    new_files_added += 1
                    self._log_verbose(f"  Added: {filename}")
                    self._log_verbose(f"    From: {bin_file}")
                    self._log_verbose(f"    To: {target_path}")
                    self._log_verbose(f"    Size: {os.path.getsize(bin_file)} bytes")
                except Exception as e:
                    self._log_verbose(f"  Error adding {filename}: {e}")
        
        for patch in current_build.GetEnabledBinaryPatches():
            if patch.IsNewFile():
                filename = patch.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping patch '{patch.GetName()}' - invalid filename")
                    continue
                
                filename = filename.strip()
                
                # For new files, use the compiled binary from bin_output_dir
                bin_file = os.path.join(bin_output_dir, f"{patch.GetName()}.bin")
                
                if not os.path.exists(bin_file):
                    self._log_verbose(f"  Warning: Binary not found for patch '{patch.GetName()}'")
                    self._log_verbose(f"    Expected: {bin_file}")
                    continue
                
                target_path = os.path.join(temp_build_dir, filename.replace('\\', '/'))
                
                try:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copyfile(bin_file, target_path)
                    new_files_added += 1
                    self._log_verbose(f"  Added: {filename}")
                    self._log_verbose(f"    From: {bin_file}")
                    self._log_verbose(f"    To: {target_path}")
                    self._log_verbose(f"    Size: {os.path.getsize(bin_file)} bytes")
                except Exception as e:
                    self._log_verbose(f"  Error adding {filename}: {e}")
        
        if new_files_added == 0:
            self._log_progress("  No new files to add")
        else:
            self._log_verbose(f"\n  Total new files added: {new_files_added}")
    
    def _rebuild_n64(self) -> ISOResult:
        """N64 ROM doesn't need rebuilding, just checksum fix"""
        self._log_verbose("N64 ROM ready (checksum should be fixed separately)")
        
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        main_exe = current_build.GetMainExecutable()
        
        if not main_exe:
            return ISOResult(False, "Main executable not set")
        
        patched_rom = os.path.join(project_folder, f"patched_{main_exe}")
        
        if not os.path.exists(patched_rom):
            return ISOResult(False, f"Patched ROM not found: {patched_rom}")
        
        self._log_verbose(" Note: N64 checksum needs to be fixed manually")
        
        return ISOResult(True, "N64 ROM ready (fix checksum with n64crc)", patched_rom)
    
    # ==================== PATCHING ====================
    
    def patch_executable(self) -> ISOResult:
        """Patch all injection files with compiled binary sections"""
        self._log_progress("Patching game files...")

        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()

        # Create build directory
        build_dir = os.path.join(project_folder, 'build')
        os.makedirs(build_dir, exist_ok=True)

        bin_output_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')

        injection_files = current_build.GetInjectionFiles()

        if not injection_files:
            return ISOResult(False, "No injection files set")

        self._log_progress(f"Found {len(injection_files)} file(s) to patch")
        
        patched_files = []

        for file_name in injection_files:
            self._log_progress(f"Patching: {file_name}")
            self._log_verbose(f"\n{'='*60}")
            self._log_verbose(f"Patching: {file_name}")
            self._log_verbose(f"{'='*60}")
            original_file_path = current_build.FindFileInGameFolder(file_name)
            self._log_verbose(f"test {original_file_path}")

            if not original_file_path or not os.path.exists(original_file_path):
                self._log_error(f"Could not find {file_name} in game folder, skipping")
                continue

            self._log_verbose(f"Original file: {original_file_path}")
            self._log_verbose(f"Size: {os.path.getsize(original_file_path)} bytes")
            
            # Extract just the filename without directory path for patched file naming
            base_filename = os.path.basename(file_name)
            patched_file_path = os.path.join(build_dir, f"patched_{base_filename}")
            
            try:
                with open(original_file_path, 'rb') as f:
                    file_data = bytearray(f.read())
                
                patches_applied = 0
                
                for codecave in current_build.GetEnabledCodeCaves():
                    # Skip memory-only codecaves when patching
                    if codecave.IsMemoryOnly():
                        continue

                    target_file = codecave.GetInjectionFile()
                    if target_file != file_name:
                        continue
                    
                    bin_file = os.path.join(bin_output_dir, f"{codecave.GetName()}.bin")
                    
                    if not os.path.exists(bin_file):
                        self._log_verbose(f" Warning: Binary not found for codecave '{codecave.GetName()}'")
                        continue
                    
                    with open(bin_file, 'rb') as f:
                        patch_data = f.read()
                    
                    file_address = codecave.GetInjectionFileAddress()
                    memory_address = int(codecave.GetMemoryAddress(), 16)
                    # file_address = current_build.GetFileOffsetForAddress(
                    #     codecave.GetInjectionFile(),
                    #     memory_address
                    # )

                    if file_address is None:
                        self._log_error(f"Could not find file offset for codecave '{codecave.GetName()}' at 0x{memory_address:X}")
                        continue
                    
                    if not file_address or file_address == "None" or file_address == "":
                        self._log_verbose(f" Warning: No injection file address set for codecave '{codecave.GetName()}'. Skipping.")
                        continue
                    
                    try:
                        if isinstance(file_address, str):
                            if file_address.startswith('0x') or file_address.startswith('0X'):
                                file_address = file_address[2:]
                            file_address = int(file_address, 16)
                        elif isinstance(file_address, int):
                            pass
                        else:
                            self._log_verbose(f" Warning: Invalid address type for codecave '{codecave.GetName()}': {type(file_address)}. Skipping.")
                            continue
                    except ValueError:
                        self._log_verbose(f" Warning: Invalid address format for codecave '{codecave.GetName()}': '{file_address}'. Skipping.")
                        continue
                    
                    if file_address < 0 or file_address >= len(file_data):
                        self._log_verbose(f" Warning: Address 0x{file_address:X} out of bounds for codecave '{codecave.GetName()}'. Skipping.")
                        continue
                    
                    if file_address + len(patch_data) > len(file_data):
                        self._log_verbose(f" Warning: Patch for codecave '{codecave.GetName()}' would overflow file. Skipping.")
                        continue
                    
                    file_data[file_address:file_address + len(patch_data)] = patch_data
                    patches_applied += 1
                    self._log_verbose(f"  Patched codecave '{codecave.GetName()}' at 0x{file_address:X} ({len(patch_data)} bytes)")
                
                for hook in current_build.GetEnabledHooks():
                    target_file = hook.GetInjectionFile()
                    if target_file != file_name:
                        continue
                    
                    bin_file = os.path.join(bin_output_dir, f"{hook.GetName()}.bin")
                    
                    if not os.path.exists(bin_file):
                        self._log_verbose(f" Warning: Binary not found for hook '{hook.GetName()}'")
                        continue
                    
                    with open(bin_file, 'rb') as f:
                        patch_data = f.read()
                    
                    file_address = hook.GetInjectionFileAddress()
                    memory_address = int(codecave.GetMemoryAddress(), 16)
                    # file_address = current_build.GetFileOffsetForAddress(
                    #     hook.GetInjectionFile(),
                    #     memory_address
                    # )

                    if file_address is None:
                        self._log_error(f"Could not find file offset for hook '{hook.GetName()}' at 0x{memory_address:X}")
                        continue
                    
                    if not file_address or file_address == "None" or file_address == "":
                        self._log_verbose(f" Warning: No injection file address set for hook '{hook.GetName()}'. Skipping.")
                        continue
                    
                    try:
                        if isinstance(file_address, str):
                            if file_address.startswith('0x') or file_address.startswith('0X'):
                                file_address = file_address[2:]
                            file_address = int(file_address, 16)
                        elif isinstance(file_address, int):
                            pass
                        else:
                            self._log_verbose(f" Warning: Invalid address type for hook '{hook.GetName()}'. Skipping.")
                            continue
                    except ValueError:
                        self._log_verbose(f" Warning: Invalid address format for hook '{hook.GetName()}': '{file_address}'. Skipping.")
                        continue
                    
                    if file_address < 0 or file_address >= len(file_data):
                        self._log_verbose(f" Warning: Address 0x{file_address:X} out of bounds for hook '{hook.GetName()}'. Skipping.")
                        continue
                    
                    if file_address + len(patch_data) > len(file_data):
                        self._log_verbose(f" Warning: Patch for hook '{hook.GetName()}' would overflow file. Skipping.")
                        continue
                    
                    file_data[file_address:file_address + len(patch_data)] = patch_data
                    patches_applied += 1
                    self._log_verbose(f"  Patched hook '{hook.GetName()}' at 0x{file_address:X} ({len(patch_data)} bytes)")
                
                for patch in current_build.GetEnabledBinaryPatches():
                    target_file = patch.GetInjectionFile()
                    if target_file != file_name:
                        continue
                    
                    bin_file = os.path.join(bin_output_dir, f"{patch.GetName()}.bin")
                    
                    if not os.path.exists(bin_file):
                        self._log_verbose(f" Warning: Binary not found for patch '{patch.GetName()}'")
                        continue
                    
                    with open(bin_file, 'rb') as f:
                        patch_data = f.read()
                    
                    file_address = patch.GetInjectionFileAddress()
                    
                    if not file_address or file_address == "None" or file_address == "":
                        self._log_verbose(f" Warning: No injection file address set for patch '{patch.GetName()}'. Skipping.")
                        continue
                    
                    try:
                        if isinstance(file_address, str):
                            if file_address.startswith('0x') or file_address.startswith('0X'):
                                file_address = file_address[2:]
                            file_address = int(file_address, 16)
                        elif isinstance(file_address, int):
                            pass
                        else:
                            self._log_verbose(f" Warning: Invalid address type for patch '{patch.GetName()}'. Skipping.")
                            continue
                    except ValueError:
                        self._log_verbose(f" Warning: Invalid address format for patch '{patch.GetName()}': '{file_address}'. Skipping.")
                        continue
                    
                    if file_address < 0 or file_address >= len(file_data):
                        self._log_verbose(f" Warning: Address out of bounds for patch '{patch.GetName()}'. Skipping.")
                        continue
                    
                    if file_address + len(patch_data) > len(file_data):
                        self._log_verbose(f" Warning: Patch '{patch.GetName()}' would overflow file. Skipping.")
                        continue
                    
                    file_data[file_address:file_address + len(patch_data)] = patch_data
                    patches_applied += 1
                    self._log_verbose(f"  Patched binary patch '{patch.GetName()}' at 0x{file_address:X} ({len(patch_data)} bytes)")
                
                with open(patched_file_path, 'wb') as f:
                    f.write(file_data)
                
                if patches_applied > 0:
                    self._log_verbose(f" Patched file created: build/patched_{base_filename}")
                    self._log_verbose(f"  Applied {patches_applied} patch(es)")
                    patched_files.append(file_name)
                else:
                    self._log_verbose(f" No patches applied to {file_name}")
                    patched_files.append(file_name)
                
            except Exception as e:
                import traceback
                self._log_verbose(f" Error patching {file_name}: {str(e)}")
                traceback.print_exc()
                continue
        
        if not patched_files:
            return ISOResult(False, "No files were successfully patched!")
        
        self._log_verbose(f"\n{'='*60}")
        self._log_progress(f" Patching complete!")
        self._log_verbose(f"  Patched {len(patched_files)}/{len(injection_files)} file(s)")
        self._log_verbose(f"{'='*60}")
        
        return ISOResult(True, "Files patched successfully", f"{len(patched_files)} files patched")
    
    # ==================== FULL BUILD ====================
    
    def full_build(self) -> ISOResult:
        self._log_progress("=" * 60)
        self._log_progress("STARTING FULL BUILD")
        self._log_progress("=" * 60)

        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        self._log_progress(f"Platform: {platform}")

        is_single_file = current_build.IsSingleFileMode()
        if is_single_file:
            self._log_verbose(f"\n SINGLE FILE MODE ENABLED")
            self._log_verbose(f"  ISO rebuilding will be skipped")

        # Setup source path BEFORE patching (so external files can be found)
        source_path = current_build.GetSourcePath()

        if not source_path:
            from tkinter import filedialog, messagebox

            if platform in ["Gamecube", "Wii"]:
                messagebox.showinfo(
                    "ISO Required for Extraction",
                    f"{platform} extraction requires the original ISO file.\nPlease select it."
                )
                source_path = filedialog.askopenfilename(
                    title=f"Choose {platform} ISO File",
                    filetypes=[("ISO Images", "*.iso;*.gcm;*.nkit.iso;*.rvz;*.wfbs" if platform == "Gamecube" else "*.iso;*.wbfs"), ("All Files", "*.*")]
                )
            else:
                source_path = current_build.GetGameFolder()

            if not source_path:
                return ISOResult(False, "No source path available for building")

            current_build.SetSourcePath(source_path)

        self._log_verbose(f"\nUsing source: {source_path}")

        # Patch
        self._log_progress("\n[1/3] Patching executable with compiled code...")
        patch_result = self.patch_executable()
        if not patch_result.success:
            return patch_result

        if is_single_file:
            main_exe = current_build.GetMainExecutable()
            project_folder = self.project_data.GetProjectFolder()

            build_dir = os.path.join(project_folder, 'build')

            patched_file = os.path.join(build_dir, f"patched_{main_exe}")

            self._log_progress("\n" + "=" * 60)
            self._log_progress(" SINGLE FILE BUILD COMPLETE")
            self._log_progress("=" * 60)
            self._log_progress(f"\nPatched file: {patched_file}")
            self._log_progress("\n ISO rebuilding skipped (single file mode)")

            return ISOResult(True, f"Single file patched successfully!\n\nOutput: patched_{main_exe}", patched_file)

        # For GameCube/Wii, we no longer need the ISO after extraction
        # The rebuild works directly from the extracted files

        self._log_progress(f"\n[2/3] Rebuilding {platform} ISO...")
        rebuild_result = self.rebuild_iso()

        self._log_progress("\n" + "=" * 60)
        if rebuild_result.success:
            self._log_progress(" FULL BUILD COMPLETE")
        else:
            self._log_progress(" BUILD FAILED")
        self._log_progress("=" * 60)

        return rebuild_result

    def _add_ps1_new_files_to_xml(self, root, local_game_files: str):
        """Add new files to PS1 XML structure"""
        import xml.etree.ElementTree as ET
        
        current_build = self.project_data.GetCurrentBuildVersion()
        project_folder = self.project_data.GetProjectFolder()
        bin_output_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')
        
        dir_tree = root.find('.//directory_tree')
        if dir_tree is None:
            return
        
        new_files = []
        
        for codecave in current_build.GetEnabledCodeCaves():
            if codecave.IsNewFile():
                filename = codecave.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping codecave '{codecave.GetName()}' - invalid filename: {filename}")
                    continue
                
                filename = filename.strip()
                bin_file = os.path.join(bin_output_dir, f"{codecave.GetName()}.bin")
                
                if os.path.exists(bin_file):
                    dest_path = os.path.join(local_game_files, filename)
                    try:
                        shutil.copyfile(bin_file, dest_path)
                        new_files.append(filename)
                        self._log_verbose(f"  Prepared new file: {filename}")
                    except Exception as e:
                        self._log_verbose(f"  Error copying {filename}: {e}")
        
        for hook in current_build.GetEnabledHooks():
            if hook.IsNewFile():
                filename = hook.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping hook '{hook.GetName()}' - invalid filename: {filename}")
                    continue
                
                filename = filename.strip()
                bin_file = os.path.join(bin_output_dir, f"{hook.GetName()}.bin")
                
                if os.path.exists(bin_file):
                    dest_path = os.path.join(local_game_files, filename)
                    try:
                        shutil.copyfile(bin_file, dest_path)
                        new_files.append(filename)
                        self._log_verbose(f"  Prepared new file: {filename}")
                    except Exception as e:
                        self._log_verbose(f"  Error copying {filename}: {e}")
        
        for patch in current_build.GetEnabledBinaryPatches():
            if patch.IsNewFile():
                filename = patch.GetInjectionFile()
                
                if not filename or filename.strip() == "" or filename.lower() == "none":
                    self._log_verbose(f"  Warning: Skipping patch '{patch.GetName()}' - invalid filename: {filename}")
                    continue
                
                filename = filename.strip()
                bin_file = os.path.join(bin_output_dir, f"{patch.GetName()}.bin")
                
                if os.path.exists(bin_file):
                    dest_path = os.path.join(local_game_files, filename)
                    try:
                        shutil.copyfile(bin_file, dest_path)
                        new_files.append(filename)
                        self._log_verbose(f"  Prepared new file: {filename}")
                    except Exception as e:
                        self._log_verbose(f"  Error copying {filename}: {e}")
        
        # CLEANUP: Remove orphaned files from XML (files that were added in previous builds but are no longer referenced)
        # We mark files we add with added_by_tool="true" to distinguish them from original template files
        files_to_remove = []
        for existing_file in dir_tree.findall('.//file'):  # Search all files recursively
            # Only consider files that WE added (marked with added_by_tool attribute)
            if existing_file.attrib.get('added_by_tool') == 'true':
                existing_filename = existing_file.attrib.get('name')

                # Remove if no longer in the current new_files list
                if existing_filename and existing_filename not in new_files:
                    files_to_remove.append(existing_file)
                    self._log_verbose(f"  Removing orphaned file from XML: {existing_filename}")

        # Remove orphaned files
        for file_elem in files_to_remove:
            # Find the parent and remove from it
            for parent in dir_tree.iter():
                if file_elem in list(parent):
                    parent.remove(file_elem)
                    break

        # Add new files to XML
        for filename in new_files:
            file_already_exists = False

            for existing_file in dir_tree.findall('.//file'):
                if existing_file.attrib.get('name') == filename:
                    file_already_exists = True
                    self._log_verbose(f"  Skipping {filename} - already in XML")
                    break

            if not file_already_exists:
                file_elem = ET.SubElement(dir_tree, 'file')
                file_elem.attrib['name'] = filename
                file_elem.attrib['source'] = os.path.join(local_game_files, filename)
                file_elem.attrib['type'] = 'data'
                file_elem.attrib['added_by_tool'] = 'true'  # Mark as tool-added for cleanup tracking
                self._log_verbose(f"  Added new file to PS1 ISO: {filename}")
            
    def _copy_ps2_new_files_to_build(self, temp_build_dir: str):
        """Copy new files to PS2 build folder"""
        current_build = self.project_data.GetCurrentBuildVersion()
        project_folder = self.project_data.GetProjectFolder()
        bin_output_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')
        
        for codecave in current_build.GetEnabledCodeCaves():
            if codecave.IsNewFile():
                filename = codecave.GetInjectionFile()
                bin_file = os.path.join(bin_output_dir, f"{codecave.GetName()}.bin")
                
                if os.path.exists(bin_file):
                    dest_path = os.path.join(temp_build_dir, filename)
                    shutil.copyfile(bin_file, dest_path)
                    self._log_verbose(f"  Added new file to PS2 build: {filename}")
                    
    def _inject_gamecube_new_files(self, modded_iso: str, current_build):
        """Inject new files into GameCube ISO"""
        project_folder = self.project_data.GetProjectFolder()
        bin_output_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')
        gcr_path = self.tools['gcr']
        
        self._log_verbose(f"\n[Adding New Files to GameCube ISO]")
        
        new_files = []
        
        for codecave in current_build.GetEnabledCodeCaves():
            if codecave.IsNewFile():
                filename = codecave.GetInjectionFile()
                bin_file = os.path.join(bin_output_dir, f"{codecave.GetName()}.bin")
                new_files.append((filename, bin_file))
        
        for filename, bin_file in new_files:
            if not os.path.exists(bin_file):
                self._log_verbose(f"  Warning: {bin_file} not found")
                continue
            
            gcr_path_str = f"root/{filename}"
            
            add_cmd = [
                gcr_path,
                modded_iso,
                gcr_path_str,
                'a',
                bin_file
            ]
            
            self._log_verbose(f"Adding: {filename}")
            
            try:
                result = subprocess.run(
                    add_cmd,
                    shell=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=60
                )
                
                if result.returncode == 0:
                    self._log_verbose(f"  Added successfully")
                else:
                    self._log_verbose(f"  Failed: {result.stderr}")
            except Exception as e:
                self._log_verbose(f"  Error: {str(e)}")

    def _generate_ps1_xml_from_folder(self, game_folder: str, xml_output_path: str) -> bool:
        """Generate a complete PS1 build XML from an existing folder structure"""
        try:
            import xml.etree.ElementTree as ET
            
            self._log_verbose(f"Generating PS1 build XML from folder: {game_folder}")
            
            root = ET.Element('iso_project')
            root.attrib['image_name'] = 'mkpsxiso.bin'
            root.attrib['cue_sheet'] = 'mkpsxiso.cue'
            
            track = ET.SubElement(root, 'track')
            track.attrib['type'] = 'data'
            
            game_folder_abs = os.path.abspath(game_folder)
            
            identifiers = ET.SubElement(track, 'identifiers')
            
            system_cnf_path = os.path.join(game_folder_abs, 'SYSTEM.CNF')
            volume_id = 'MODDED_GAME'
            
            if os.path.exists(system_cnf_path):
                try:
                    with open(system_cnf_path, 'r') as f:
                        for line in f:
                            if line.startswith('BOOT'):
                                parts = line.split('\\')
                                if len(parts) > 1:
                                    volume_id = parts[1].split(';')[0].replace('_', '-')
                                break
                except Exception as e:
                    self._log_verbose(f"  Could not read SYSTEM.CNF: {e}")
            
            identifiers.attrib['system'] = 'PLAYSTATION'
            identifiers.attrib['application'] = 'PLAYSTATION'
            identifiers.attrib['volume'] = volume_id
            identifiers.attrib['publisher'] = 'HOMEBREW'
            identifiers.attrib['creation_date'] = '1996022919020100-19'
            
            self._log_verbose(f"  Volume ID: {volume_id}")
            
            license_file = os.path.join(game_folder_abs, 'license_data.dat')
            if os.path.exists(license_file):
                license_elem = ET.SubElement(track, 'license')
                license_elem.attrib['file'] = license_file
                self._log_verbose(f"  Added license file: license_data.dat")
            else:
                self._log_verbose(f"  No license_data.dat found (will be auto-generated by mkpsxiso)")
            
            default_attrs = ET.SubElement(track, 'default_attributes')
            default_attrs.attrib['gmt_offs'] = '-15'
            default_attrs.attrib['xa_attrib'] = '0'
            default_attrs.attrib['xa_perm'] = '1365'
            default_attrs.attrib['xa_gid'] = '0'
            default_attrs.attrib['xa_uid'] = '0'
            
            dir_tree = ET.SubElement(track, 'directory_tree')
            dir_tree.attrib['gmt_offs'] = '-19'
            
            root_files = []
            root_dirs = []
            
            for item in os.listdir(game_folder_abs):
                item_path = os.path.join(game_folder_abs, item)
                
                if item.lower() == 'license_data.dat':
                    continue
                
                if os.path.isfile(item_path):
                    root_files.append((item, item_path))
                elif os.path.isdir(item_path):
                    root_dirs.append((item, item_path))
            
            root_files.sort(key=lambda x: (x[0] != 'SYSTEM.CNF', x[0]))
            
            for filename, filepath in root_files:
                file_elem = ET.SubElement(dir_tree, 'file')
                file_elem.attrib['name'] = filename
                file_elem.attrib['source'] = filepath
                file_elem.attrib['type'] = 'data'
                self._log_verbose(f"  Added file: {filename}")
            
            for dirname, dirpath in sorted(root_dirs):
                self._add_directory_to_xml(dir_tree, dirname, dirpath)
            
            os.makedirs(os.path.dirname(xml_output_path), exist_ok=True)
            
            tree = ET.ElementTree(root)
            ET.indent(tree, space="    ")
            tree.write(xml_output_path, encoding='utf-8', xml_declaration=True)
            
            self._log_verbose(f"Generated XML: {xml_output_path}")
            return True
            
        except Exception as e:
            self._log_verbose(f"Failed to generate XML: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def _validate_ps1_xml(self, xml_path: str) -> bool:
        """Validate that PS1 XML has proper structure from dumpsxiso"""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Check for directory_tree
            dir_tree = root.find('.//directory_tree')
            if dir_tree is None:
                self._log_verbose("XML missing directory_tree")
                return False
            
            # Check if any files exist
            files = dir_tree.findall('.//file')
            if not files:
                self._log_verbose("XML has no files")
                return False
            
            self._log_verbose(f" XML validation passed ({len(files)} files found)")
            return True
            
        except Exception as e:
            self._log_verbose(f"XML validation failed: {e}")
            return False

    def _add_directory_to_xml(self, parent_elem, dir_name: str, dir_path: str):
        """Recursively add a directory and its contents to XML"""
        import xml.etree.ElementTree as ET
        
        dir_elem = ET.SubElement(parent_elem, 'dir')
        dir_elem.attrib['name'] = dir_name
        
        self._log_verbose(f"  Added directory: {dir_name}/")
        
        files = []
        subdirs = []
        
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            
            if os.path.isfile(item_path):
                files.append((item, item_path))
            elif os.path.isdir(item_path):
                subdirs.append((item, item_path))
        
        for filename, filepath in sorted(files):
            file_elem = ET.SubElement(dir_elem, 'file')
            file_elem.attrib['name'] = filename
            file_elem.attrib['source'] = filepath
            file_elem.attrib['type'] = 'data'
            self._log_verbose(f"    {dir_name}/{filename}")
        
        for subdir_name, subdir_path in sorted(subdirs):
            self._add_directory_to_xml(dir_elem, subdir_name, subdir_path)
            
            
    def _handle_external_files(self, current_build) -> ISOResult:
        """
        Process external files separately (not part of ISO rebuild).
        These files should be patched and saved to project folder.
        """
        project_folder = self.project_data.GetProjectFolder()
        external_files = []
        
        # Find all external files
        for filename in current_build.GetInjectionFiles():
            if current_build.GetInjectionFileType(filename) == "external":
                external_files.append(filename)
        
        if not external_files:
            return ISOResult(True, "No external files to process")
        
        self._log_verbose(f"\nProcessing {len(external_files)} external file(s) separately...")
        
        for filename in external_files:
            patched_file = os.path.join(project_folder, f"patched_{filename}")
            
            if not os.path.exists(patched_file):
                self._log_verbose(f"  Warning: No patched version of external file '{filename}'")
                continue
            
            self._log_verbose(f"  External file ready: patched_{filename}")
            self._log_verbose(f"    (This file must be manually re-packed into game data)")
        
        return ISOResult(True, f"Processed {len(external_files)} external file(s)")

    # ==================== XDELTA PATCH GENERATION ====================

    def _get_file_format(self, file_path: str) -> str:
        """
        Get the format of a file from its extension.

        Args:
            file_path: Path to the file

        Returns:
            Format string: 'iso', 'ciso', 'wbfs', 'gcm', 'bin', or 'unknown'
        """
        ext = os.path.splitext(file_path)[1].lower()
        format_map = {
            '.iso': 'iso',
            '.ciso': 'ciso',
            '.wbfs': 'wbfs',
            '.gcm': 'gcm',
            '.bin': 'bin',
            '.rvz': 'rvz',  # Dolphin compressed format
            '.nkit': 'nkit'  # NKit format
        }
        return format_map.get(ext, 'unknown')

    def generate_xdelta_patch(self, original_file: Optional[str] = None) -> ISOResult:
        """
        Generate an xdelta patch comparing the original file to the modded file.

        Args:
            original_file: Path to the original file. If None, will try to auto-detect from source_path.
                          For folder-based projects, this must be provided by the user.

        Returns:
            ISOResult with success status and patch file path
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        project_folder = self.project_data.GetProjectFolder()
        build_name = current_build.GetBuildName()

        # Determine if this is single file mode or ISO mode
        is_single_file = current_build.IsSingleFileMode()

        # Find the modded file
        if is_single_file:
            # Single file mode - look for patched_{filename} in build/
            single_file_path = current_build.GetSingleFilePath()
            if not single_file_path:
                return ISOResult(False, "No single file path set in project")

            filename = os.path.basename(single_file_path)
            build_dir = os.path.join(project_folder, 'build')
            modded_file = os.path.join(build_dir, f"patched_{filename}")

            if not os.path.exists(modded_file):
                return ISOResult(False, f"Modded file not found: {modded_file}")
        else:
            # ISO mode - look for output ISO/BIN in build/ folder
            build_dir = os.path.join(project_folder, 'build')
            platform = current_build.GetPlatform()

            # Different platforms have different output naming conventions
            modded_file = None

            if platform == "PS1":
                # PS1 outputs as build/ModdedGame_{build_name}.bin
                modded_file = os.path.join(build_dir, f"ModdedGame_{build_name}.bin")
            elif platform == "PS2":
                # PS2 outputs as build/ModdedGame_{build_name}.iso
                modded_file = os.path.join(build_dir, f"ModdedGame_{build_name}.iso")
            elif platform in ["Gamecube", "Wii"]:
                # Get the actual output format from build settings
                output_format = current_build.GetOutputFormat()

                # Default to ISO if not set
                if not output_format:
                    output_format = "iso"

                # Normalize format to lowercase for extension
                ext = output_format.lower()

                # GC/Wii output as build/ModdedGame_{build_name}.{format}
                modded_file = os.path.join(build_dir, f"ModdedGame_{build_name}.{ext}")
            elif platform == "N64":
                # N64 outputs as patched_{filename} in project folder (not build/)
                main_exe = current_build.GetMainExecutable()
                if main_exe:
                    modded_file = os.path.join(project_folder, f"patched_{main_exe}")


            if not modded_file or not os.path.exists(modded_file):
                return ISOResult(False, f"Please build ISO before generating xdelta patch!\n\nExpected file: {modded_file if modded_file else 'unknown path'}")


        # Determine the original file
        if original_file is None:
            # For single file mode, use the single_file_path
            if is_single_file:
                original_file = current_build.GetSingleFilePath()
                if not original_file:
                    return ISOResult(False, "No single file path set. Please select the original file.")
            else:
                # For ISO mode, use source_path
                source_path = current_build.GetSourcePath()

                if not source_path:
                    return ISOResult(False, "No source path set. Please select the original file.")

                # Check if source_path is a directory (folder extraction case)
                if os.path.isdir(source_path):
                    return ISOResult(False, "Project was created from extracted folder. Please select the original ISO/file.")

                # Check if source_path exists
                if not os.path.exists(source_path):
                    return ISOResult(False, f"Original file not found: {source_path}. Please select the original file.")

                original_file = source_path

        # Validate original file exists
        if not os.path.exists(original_file):
            return ISOResult(False, f"Original file not found: {original_file}")

        # Detect formats
        original_format = self._get_file_format(original_file)
        modded_format = self._get_file_format(modded_file)

        # Warning if formats don't match
        format_warning = ""
        if platform in ["Gamecube", "Wii"] and original_format != modded_format:
            format_warning = (
                f"\nWARNING: Format mismatch detected!\n"
                f"  Original file format: {original_format.upper()}\n"
                f"  Built file format:    {modded_format.upper()}\n"
                f"  This patch will ONLY work with {modded_format.upper()} files.\n"
                f"  Users with {original_format.upper()} files will need to convert to {modded_format.upper()} first.\n"
            )

        # Generate output patch filename
        modded_basename = os.path.basename(modded_file)
        modded_name_no_ext = os.path.splitext(modded_basename)[0]
        build_dir = os.path.join(project_folder, "build")
        patch_file = os.path.join(build_dir, f"{modded_name_no_ext}.xdelta")

        self._log_verbose(f"\nGenerating xdelta patch...")
        self._log_verbose(f"  Original: {original_file} ({original_format.upper()})")
        self._log_verbose(f"  Modified: {modded_file} ({modded_format.upper()})")
        self._log_verbose(f"  Patch:    {patch_file}")

        # Show format warning if formats don't match
        if format_warning:
            self._log_verbose(format_warning)

        # Build xdelta command
        cmd = [
            self.tools['xdelta'],
            '-S', 'none',
            '-f',
            '-s', original_file,
            modded_file,
            patch_file
        ]

        self._log_verbose(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.tool_dir,
                timeout=300  # 5 minute timeout for large files
            )

            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return ISOResult(False, f"xdelta failed: {error_msg}")

            if not os.path.exists(patch_file):
                return ISOResult(False, "Patch generation completed but patch file not found")

            # Get patch file size for reporting
            patch_size = os.path.getsize(patch_file)
            patch_size_mb = patch_size / (1024 * 1024)

            self._log_verbose(f"\n✓ Patch generated successfully!")
            self._log_verbose(f"  File: {patch_file}")
            self._log_progress(f"  Size: {patch_size_mb:.2f} MB")

            # Build success message with format information
            success_msg = f"Patch created: {os.path.basename(patch_file)}"
            if platform in ["Gamecube", "Wii"]:
                success_msg += f" (for {modded_format.upper()} format)"
                if original_format != modded_format:
                    success_msg += f"\nNote: Original was {original_format.upper()}, patch is for {modded_format.upper()}"

            return ISOResult(True, success_msg, patch_file)

        except subprocess.TimeoutExpired:
            return ISOResult(False, "xdelta patch generation timed out (> 5 minutes)")
        except Exception as e:
            return ISOResult(False, f"Error generating patch: {str(e)}")
