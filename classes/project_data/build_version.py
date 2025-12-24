import os
import sys
from typing import Optional
from typing import List, Dict, Optional, Tuple

from functions.helper_funcs import *
from functions.print_wrapper import *
from classes.injection_targets.code_cave import Codecave
from classes.injection_targets.hook import Hook
from classes.injection_targets.binary_patch import BinaryPatch
from classes.exteneded_base_classes.file_path import FilePathStr
from classes.injection_targets.multipatch_asm import MultiPatchASM
from functions.verbose_print import verbose_print
from services.section_parser_service import SectionParserService, SectionInfo

class BuildVersion:
    def __init__(self):
        self.build_name: str = None
        self.platform: str = None
        self.injection_files: list[str] = list()
        self.injection_file_offsets = {}
        self.section_maps: Dict[str, List[SectionInfo]] = {}
        self.injection_file_types: dict[str, str] = {}  # Maps filename to "disk" or "external"
        self.external_file_full_paths: dict[str, str] = {}
        self.extracted_game_folder: str = None
        self.main_executable: str = None
        self.code_files: list[str] = list()
        self.source_path: str = None
        self.symbols_file: str = None
        self.compiler_flags: str = "-O2"  # Default flag
        self.debug_mode: bool = False  # Debug build mode (-O0, better debugging)
        self.code_caves: list[Codecave] = list()
        self.hooks: list[Hook] = list()
        self.binary_patches: list[BinaryPatch] = list()
        
        self.multi_patches: list[MultiPatchASM] = list()
        
        self.is_single_file_mode: bool = False
        self.single_file_path: str = None  # Path to the single file being modified
        
    
    def SetBuildName(self, name: str):
        # Replace " " with "_", and make uppercase
        safe_name = SanitizeNameNoSpaces(name)
        self.build_name = safe_name.upper()
    def GetBuildName(self) -> str:
        return self.build_name
    
    def SetPlatform(self, platform: str):
        self.platform = platform
    def GetPlatform(self) -> str:
        return self.platform
    
    def IsPlatformPS1(self):
        if self.platform == "PS1":
            return True
        else:
            return False
    def IsPlatformPS2(self):
        if self.platform == "PS2":
            return True
        else:
            return False
    def IsPlatformGameCube(self):
        if self.platform == "Gamecube":
            return True
        else:
            return False
    def IsPlatformWii(self):
        if self.platform == "Wii":
            return True
        else:
            return False
    def IsPlatformN64(self):
        if self.platform == "N64":
            return True
        else:
            return False

    def GetInjectionFiles(self):
        return self.injection_files

    def AddInjectionFile(self, file_path: str):
        """Add a file to the injection list with automatic type determination"""
        game_folder = self.GetGameFolder()
        abs_file_path = os.path.abspath(file_path)
        filename = os.path.basename(abs_file_path)

        # 1. Automatic Type Determination
        file_type = "external"  # Default to external
        
        # OVERRIDE: Main executable is ALWAYS a disk file
        if filename == self.GetMainExecutable():
            file_type = "disk"
        elif game_folder:
            abs_game_folder = os.path.abspath(game_folder)
            
            try:
                # Check if file is inside game folder
                common_path = os.path.commonpath([abs_game_folder, abs_file_path])
                
                if os.path.normcase(common_path) == os.path.normcase(abs_game_folder):
                    file_type = "disk"
                else:
                    file_type = "external"
                    
            except ValueError:
                # Different drives or no common path
                file_type = "external"
        else:
            # No game folder set yet - check if it's in a common game extraction location
            # This handles the case where main executable is added before game folder is set
            game_related_paths = [".config/game_files", "extracted_games", "extracted", "game_files"]
            
            for path_indicator in game_related_paths:
                if path_indicator in abs_file_path.replace('\\', '/'):
                    file_type = "disk"
                    break
        
        # 2. Remove duplicates
        if filename in self.injection_files:
            self.injection_files.remove(filename)
            if filename in self.injection_file_offsets:
                del self.injection_file_offsets[filename]
            if filename in self.injection_file_types:
                del self.injection_file_types[filename]
            if filename in self.external_file_full_paths:
                del self.external_file_full_paths[filename]

        # 3. Add the file
        self.injection_files.append(filename)
        
        # 4. Store the determined type
        self.injection_file_types[filename] = file_type
        
        # 5. Store the path if external
        if file_type == "external":
            self.external_file_full_paths[filename] = abs_file_path
        
        # 6. Initialize offset
        if filename not in self.injection_file_offsets:
            self.injection_file_offsets[filename] = 0

        # Print condensed message for main executable, verbose for others
        if filename == self.GetMainExecutable():
            print(f"Added {filename} as disk file")
        else:
            verbose_print(f"Added '{filename}' as {file_type} file")

    def _determine_file_type(self, file_path: str) -> str:
        # No game folder set yet - assume disk (normal case)
        if not self.extracted_game_folder:
            return "disk"
        
        try:
            # Normalize paths
            file_abs = os.path.abspath(file_path)
            game_folder_abs = os.path.abspath(self.extracted_game_folder)
            
            # Check if file is inside game folder
            if file_abs.startswith(game_folder_abs + os.sep) or os.path.dirname(file_abs) == game_folder_abs:
                return "disk"
            
            # Check if it's in common game file storage locations
            # (even if not in the current game folder, might be in local copy)
            game_related_paths = [".config/game_files", "extracted_games", "extracted", "game_files"]
            for path_indicator in game_related_paths:
                if path_indicator in file_abs:
                    return "disk"
            
            # File is truly external - not in game folder or any common extraction location
            return "external"
            
        except Exception as e:
            print(f" Warning: Could not determine file type for {file_path}: {e}")
            return "disk"  # Default to disk on error

    def GetInjectionFileType(self, filename: str) -> str:
        return self.injection_file_types.get(filename, "disk")  # Default to "disk"

    def SetInjectionFileType(self, filename: str, file_type: str):
        """Manually set file type (for loading from save file)"""
        if file_type in ["disk", "external"]:
            self.injection_file_types[filename] = file_type
        else:
            print(f" Warning: Invalid file type '{file_type}', using 'disk'")
            self.injection_file_types[filename] = "disk"

    def RemoveInjectionFile(self, file_name):
        if file_name in self.injection_files:
            self.injection_files.remove(file_name)
        if file_name in self.injection_file_offsets:
            del self.injection_file_offsets[file_name]
        if file_name in self.injection_file_types:
            del self.injection_file_types[file_name]
        
        if file_name in self.external_file_full_paths:
            del self.external_file_full_paths[file_name]
            
    def BuildSectionMapForFile(self, filename: str) -> bool:
        """
        Build section map for an executable file.
        Returns True on success, False if sections couldn't be parsed.
        """
        # Find the file path
        file_path = self.FindFileInGameFolder(filename)
        
        if not file_path or not os.path.exists(file_path):
            print(f"Could not find {filename} to build section map")
            return False
        
        platform = self.GetPlatform()
        
        # Parse sections
        sections = SectionParserService.parse_executable_sections(file_path, platform)
        
        if not sections:
            print(f"No sections found for {filename}")
            return False
        
        # Store section map
        self.section_maps[filename] = sections

        print(f"Built section map for {filename}: {len(sections)} sections")
        for section in sections:
            verbose_print(f"    {section}")

        return True
        
    def GetFileOffsetForAddress(self, filename: str, memory_address: int) -> Optional[int]:
        """
        Get the file offset for a specific memory address.
        Uses section map for accurate offset calculation.
        Returns file offset, or None if address not in any section.
        """
        # Try section map first
        if filename in self.section_maps:
            sections = self.section_maps[filename]
            file_offset = SectionParserService.calculate_file_offset(sections, memory_address)
            
            if file_offset is not None:
                return file_offset
            
            # Address not in any section
            print(f"Address 0x{memory_address:X} not found in any section of {filename}")
            section = SectionParserService.find_section_for_address(sections, memory_address)
            if section:
                print(f"    Closest section: {section}")
            return None
        
        # Fallback to old single-offset method
        offset_str = self.GetInjectionFileOffset(filename)
        if offset_str:
            try:
                offset = int(offset_str, 16)

                # Strip 0x80 prefix from memory address if present (PS1/GameCube/Wii)
                if memory_address >= 0x80000000:
                    memory_address = memory_address & 0x00FFFFFF

                return memory_address - offset
            except ValueError:
                pass
        
        print(f"No section map or offset available for {filename}")
        return None
    
    def GetSectionInfoForAddress(self, filename: str, memory_address: int) -> Optional[Dict]:
        """Get section information for a memory address"""
        if filename not in self.section_maps:
            return None
        
        section = SectionParserService.find_section_for_address(
            self.section_maps[filename],
            memory_address
        )
        
        if section:
            return {
                'type': section.section_type,
                'mem_start': section.mem_start,
                'mem_end': section.mem_end,
                'file_offset': section.file_offset,
                'size': section.size,
                'offset_diff': section.offset_diff
            }
        
        return None
    def ValidateMemoryAddress(self, filename: str, memory_address: int) -> Tuple[bool, str]:
        if filename not in self.section_maps:
            return True, "No section map available (using fallback offset)"
        
        section = SectionParserService.find_section_for_address(
            self.section_maps[filename],
            memory_address
        )
        
        if section:
            return True, f"Address in {section.section_type} section"
        else:
            return False, f"Address 0x{memory_address:X} is not in any valid section"
        
    def AddInjectionFileOffset(self, file_offset_from_ram, file_name):
        if file_name:
            self.injection_file_offsets[file_name] = file_offset_from_ram

    def SetInjectionFileOffset(self, file_name, offset_value):
        if file_name in self.injection_files: # Ensure the file exists in our list
            self.injection_file_offsets[file_name] = offset_value
            verbose_print(f"Offset for {file_name} set to: {offset_value}")
        else:
            print(f"Error: File '{file_name}' not found in injection list to set offset.")
            
    def GetInjectionFileOffset(self, file_name):
        return self.injection_file_offsets.get(file_name, "")
    def PopInjectionFileOffset(self):
        offset_removed = self.injection_file_offsets.pop()
        print_dark_grey(f"Removed {offset_removed} from injection file offsets")
        
    def SetMainExecutable(self, filename: str):
        """Set the main executable file"""
        self.main_executable = filename
        
        # If main executable isn't in injection files yet, add it
        if filename not in self.injection_files:
            # If we have the game folder, construct full path
            if self.extracted_game_folder:
                file_path = os.path.join(self.extracted_game_folder, filename)
                self.AddInjectionFile(file_path)
            else:
                # No game folder yet - add with pending classification
                self.injection_files.append(filename)
                self.injection_file_types[filename] = "pending"
                verbose_print(f" Added {filename} as pending file (will classify after game folder is set)")
    def GetMainExecutable(self):
        return self.main_executable
    
    
    def GetMainExecutableFullPath(self):
        """Get the full absolute path to the main executable"""
        if not self.main_executable or not self.extracted_game_folder:
            return None
        return os.path.join(self.extracted_game_folder, self.main_executable)

    def GetMainExecutableDirectory(self):
        """Get the directory containing the main executable"""
        if not self.main_executable or not self.extracted_game_folder:
            return None
        full_path = self.GetMainExecutableFullPath()
        return os.path.dirname(full_path)
    
    def GetCodeFilesPaths(self):
        return self.code_files
    def GetCodeFilesNames(self):
        code_files_no_path = list()
        for file in self.code_files:
            code_files_no_path.append(GetFileNameFromPath(file))
        return code_files_no_path
    
    def AddCodeFile(self, file_path: str):
        self.code_files.append(file_path)
    def PopCodeFile(self):
        file_removed = self.code_files.pop()
        print_dark_grey(f"Removed {file_removed} from code files")
    
    def SetGameFolder(self, file_path):
        self.extracted_game_folder = file_path
    def GetGameFolder(self):
        return self.extracted_game_folder
    
    def GetSymbolsFile(self) -> str:
        return self.symbols_file if hasattr(self, 'symbols_file') else f"{self.build_name}.txt"

    def SetSymbolsFile(self, filename: str):
        self.symbols_file = filename
    
    def AddCodeCave(self, code_cave):
        self.code_caves.append(code_cave)
    def GetCodeCaves(self):
        return self.code_caves
    def GetEnabledCodeCaves(self):
        """Get only enabled codecaves"""
        return [cc for cc in self.code_caves if cc.IsEnabled()]
    def GetCodeCaveNames(self):
        code_cave_names = []

        for code_cave in self.code_caves:
            code_cave_names.append(code_cave.GetName())
        return code_cave_names
    
    def AddHook(self, hook):
        self.hooks.append(hook)
    def GetHooks(self):
        return self.hooks
    def GetEnabledHooks(self):
        """Get only enabled hooks"""
        return [h for h in self.hooks if h.IsEnabled()]
    def GetHookNames(self):
        hook_names = []

        for hook in self.hooks:
            hook_names.append(hook.GetName())
        return hook_names
        
        for code_cave in self.code_caves:
            code_cave_names.append(code_cave.GetName())
        return code_cave_names
        
    def AddBinaryPatch(self, patch):
        self.binary_patches.append(patch)
    def GetBinaryPatches(self):
        return self.binary_patches
    def GetEnabledBinaryPatches(self):
        """Get only enabled binary patches"""
        return [p for p in self.binary_patches if p.IsEnabled()]
    def GetBinaryPatchNames(self):
        patch_names = []

        for patch in self.binary_patches:
            patch_names.append(patch.GetName())
        return patch_names
    
    def AddMultiPatch(self, multipatch):
        self.multi_patches.append(multipatch)

    def GetMultiPatches(self):
        return self.multi_patches

    def GetMultiPatchNames(self):
        return [mp.GetName() for mp in self.multi_patches]
    
    def SetSourcePath(self, path: str):
        """Set the source path (original ISO for GC/Wii, or extracted folder for PS1/PS2)"""
        self.source_path = path
    
    def GetSourcePath(self):
        """Get the source path for building"""
        return self.source_path
    
    def GetCompilerFlags(self) -> str:
        """Get compiler flags for this build version"""
        return self.compiler_flags if hasattr(self, 'compiler_flags') else "-O2"
    
    def SetCompilerFlags(self, flags: str):
        """Set compiler flags for this build version"""
        self.compiler_flags = flags

    def IsDebugMode(self) -> bool:
        """Check if debug build mode is enabled (-O0 for better debugging)"""
        return self.debug_mode if hasattr(self, 'debug_mode') else False

    def SetDebugMode(self, enabled: bool):
        """
        Enable or disable debug build mode.

        When enabled, compiles with -O0 (no optimization) for accurate
        C-to-assembly line mapping and better variable inspection.
        """
        self.debug_mode = enabled

    def IsSingleFileMode(self) -> bool:
        """Check if this build version is in single file mode"""
        return self.is_single_file_mode if hasattr(self, 'is_single_file_mode') else False

    def SetSingleFileMode(self, enabled: bool):
        """Enable or disable single file mode"""
        self.is_single_file_mode = enabled
        
    def GetSingleFilePath(self) -> str:
        """Get the path to the single file being modified"""
        return self.single_file_path if hasattr(self, 'single_file_path') else None

    def SetSingleFilePath(self, path: str):
        """Set the path to the single file being modified"""
        self.single_file_path = path    

    def GetOutputFormat(self) -> str:
        """Get output format preference (iso, gcn, ciso, wbfs)"""
        return getattr(self, 'output_format', 'iso')

    def SetOutputFormat(self, format: str):
        """Set output format preference"""
        self.output_format = format.lower()

    def SearchForMainExecutableInGameFolder(self):
        """Search for main executable, including recursive search for GameCube/Wii"""
        matching_file = None
        game_folder = self.GetGameFolder()
        
        if not game_folder or not os.path.exists(game_folder):
            verbose_print("No game folder set or folder doesn't exist")
            return None

        verbose_print(f"Searching for executable in: {game_folder}")

        # Check if this is GameCube/Wii (they extract to root/ subfolder with various structures)
        if self.IsPlatformGameCube() or self.IsPlatformWii():
            verbose_print("Platform is GameCube/Wii - searching recursively...")

            # Recursively search for main.dol or start.dol (case-insensitive)
            try:
                for root, dirs, files in os.walk(game_folder):
                    for filename in files:
                        filename_lower = filename.lower()
                        if filename_lower == "main.dol" or filename_lower == "start.dol":
                            # Found it! Return just the actual filename (preserving case)
                            verbose_print(f"Found GC/Wii executable: {filename} in {root}")
                            return filename  # Just return "Start.dol" or "main.dol"

                verbose_print("No main.dol or start.dol found in any subdirectory")
            except Exception as e:
                verbose_print(f"Error during recursive search: {e}")
                import traceback
                traceback.print_exc()
        else:
            # PS1/PS2 - check base folder only
            try:
                for filename in os.listdir(game_folder):
                    if filename.startswith("SCUS") or filename.startswith("SCES") or \
                    filename.startswith("SLUS") or filename.startswith("SLES") or \
                    filename.startswith("SCPS") or filename.startswith("SLPS"):
                        verbose_print(f"Found potential PS1/PS2 executable: {filename}")
                        matching_file = filename
                        return matching_file
            except Exception as e:
                verbose_print(f"Error listing folder: {e}")

        verbose_print("No executable found")
        return matching_file

    def FindFileInGameFolder(self, filename: str) -> Optional[str]:     
        file_type = self.GetInjectionFileType(filename)

        # 1. Handle External Files (Use Stored Absolute Path)
        if file_type == "external":
            if filename in self.external_file_full_paths:
                full_path = self.external_file_full_paths[filename]
                
                # Check if the stored path is still valid
                if os.path.exists(full_path):
                    return full_path
                else:
                    print(f"Stored external file path no longer exists for '{filename}': {full_path}")
            # If external, but not found in the map, proceed to general search (fallback)
            
        # 2. Handle Disk Files (Search within Game Folder)
        if file_type == "disk":
            game_folder = self.GetGameFolder()
            if not game_folder:
                print(f"Error: Game folder not set for disk file '{filename}'.")
                return None

            # Check in the root of the game folder (build-specific now)
            path_in_game_folder = os.path.join(game_folder, filename)
            if os.path.exists(path_in_game_folder):
                return path_in_game_folder
            
            # Recursively search the game folder for the file (e.g., if in subdirectory)
            for root, _, files in os.walk(game_folder):
                if filename in files:
                    return os.path.join(root, filename)

        # 3. General Fallback (For files with missing or unknown type)
        source_path = self.GetSourcePath()
        if source_path and os.path.isdir(source_path):
            # Recursively search the project's source path
            for root, _, files in os.walk(source_path):
                if filename in files:
                    return os.path.join(root, filename)

        # File not found
        print(f"File '{filename}' not found in any expected location.")
        return None


    
    def GetLocalGameFilesPath(self) -> Optional[str]:
        if not hasattr(self, 'build_name') or not self.build_name:
            return None
        
        if self.extracted_game_folder:
            config_index = self.extracted_game_folder.find('.config')
            if config_index != -1:
                project_folder = self.extracted_game_folder[:config_index].rstrip(os.sep)
                return os.path.join(project_folder, '.config', 'game_files', self.build_name)
        
        return None

    def SetLocalGameFilesPath(self, project_folder: str):
        if not self.build_name:
            return None
        
        local_path = os.path.join(project_folder, '.config', 'game_files', self.build_name)
        os.makedirs(local_path, exist_ok=True)
        self.SetGameFolder(local_path)
        return local_path

    def CopyGameFilesToLocal(self, source_folder: str, project_folder: str) -> bool:
        import shutil
        
        if not self.build_name:
            print(" Error: Build name not set, cannot determine local path")
            return False
        
        # Build-specific local path
        local_path = os.path.join(project_folder, '.config', 'game_files', self.build_name)
        
        try:
            # Remove old copy if exists
            if os.path.exists(local_path):
                print(f"Removing old game files copy for build '{self.build_name}'...")
                shutil.rmtree(local_path)
            
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Copy entire folder
            verbose_print(f"Copying game files from: {source_folder}")
            verbose_print(f"                     to: {local_path}")
            shutil.copytree(source_folder, local_path)
            
            # Count items copied
            item_count = sum(1 for _ in os.walk(local_path))
            verbose_print(f"Copied {item_count} directories with files for build '{self.build_name}'")
            return True
            
        except Exception as e:
            print(f"Failed to copy game files: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
    # classes/project_data/build_version.py - Add new method

    def AutoSetFileOffsetForPlatform(self):
        if not self.main_executable:
            return False
        
        platform = self.GetPlatform()
        
        if platform == "PS1":
            # PS1 always uses F800 for SCUS/SCES/SLUS/SLES files
            main_exe_upper = self.main_executable.upper()
            is_ps1_exe = any(main_exe_upper.startswith(prefix) for prefix in 
                            ["SCUS", "SCES", "SLUS", "SLES", "SCPS", "SLPS"])
            
            if is_ps1_exe:
                self.SetInjectionFileOffset(self.main_executable, "F800")
                verbose_print(f"Auto-set PS1 file offset: 0xF800 (fixed offset, no section map)")
                # DO NOT build section map for PS1
                return True

        elif platform == "PS2":
            # Build section map for PS2
            if self.BuildSectionMapForFile(self.main_executable):
                # Use the first section's offset as the default display value
                if self.main_executable in self.section_maps:
                    first_section = self.section_maps[self.main_executable][0]
                    offset = first_section.offset_diff
                    self.SetInjectionFileOffset(self.main_executable, f"{offset:X}")
                    verbose_print(f"Auto-set PS2 file offset: 0x{offset:X} (from first section)")
                    return True

        elif platform in ["Gamecube", "Wii"]:
            # Build section map for GC/Wii
            if self.BuildSectionMapForFile(self.main_executable):
                # Use the first text section's offset
                if self.main_executable in self.section_maps:
                    text_sections = [s for s in self.section_maps[self.main_executable]
                                    if s.section_type == "text"]
                    if text_sections:
                        offset = text_sections[0].offset_diff
                        self.SetInjectionFileOffset(self.main_executable, f"{offset:X}")
                        verbose_print(f"Auto-set {platform} file offset: 0x{offset:X} (from first text section)")
                        return True
        
        return False
    
    def _calculate_ps2_offset(self) -> Optional[str]:
        """Calculate PS2 ELF offset using ee-objdump. First checks if section map is already cached."""
        if not self.main_executable:
            return None

        # Check if section map already exists (avoid running objdump again)
        if self.main_executable in self.section_maps:
            sections = self.section_maps[self.main_executable]
            if sections:
                offset = sections[0].offset_diff
                verbose_print(f" Using cached section map for PS2 offset: 0x{offset:X}")
                return f"{offset:X}"

        # No cached section map - run objdump
        # Find the executable file
        exe_path = self.FindFileInGameFolder(self.main_executable)
        if not exe_path or not os.path.exists(exe_path):
            return None

        import subprocess
        tool_dir = os.getcwd()
        objdump_path = os.path.join(tool_dir, "prereq", "PS2ee", "bin", "ee-objdump.exe")

        if not os.path.exists(objdump_path):
            print(f" Warning: ee-objdump not found at {objdump_path}")
            return None

        try:
            result = subprocess.run(
                [objdump_path, exe_path, "-x"],
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tool_dir,
                timeout=10
            )
            
            if "Idx Name" not in result.stdout:
                return None
            
            # Parse the first section
            lines = result.stdout.split("Idx Name")[1].split("\n")
            objdump_section_0 = None
            for line in lines[1:]:
                if line.strip() and not line.startswith("Idx"):
                    objdump_section_0 = line
                    break
            
            if not objdump_section_0:
                return None
            
            objdump_section_0_list = objdump_section_0.split()
            
            if len(objdump_section_0_list) >= 7:
                vma = int(objdump_section_0_list[3], base=16)
                file_off = int(objdump_section_0_list[5], base=16)
                offset = vma - file_off
            elif len(objdump_section_0_list) >= 6:
                vma = int(objdump_section_0_list[3], base=16)
                file_off = int(objdump_section_0_list[4], base=16)
                offset = vma - file_off
            else:
                return None
            
            return f"{offset:X}"
            
        except Exception as e:
            print(f" Could not calculate PS2 offset: {e}")
            return None

    def _calculate_gamecube_wii_offset(self) -> Optional[str]:
        """Calculate GameCube/Wii DOL offset using doltool. First checks if section map is already cached."""
        if not self.main_executable:
            return None

        # Check if section map already exists (avoid running doltool again)
        if self.main_executable in self.section_maps:
            sections = self.section_maps[self.main_executable]
            # Find first text section (GameCube/Wii uses first text section)
            text_sections = [s for s in sections if s.section_type == "text"]
            if text_sections:
                offset = text_sections[0].offset_diff
                verbose_print(f" Using cached section map for GC/Wii offset: 0x{offset:X}")
                return f"{offset:X}"

        # No cached section map - run doltool
        # Find the executable file
        exe_path = self.FindFileInGameFolder(self.main_executable)
        if not exe_path or not os.path.exists(exe_path):
            return None

        import subprocess
        tool_dir = os.getcwd()
        doltool_path = os.path.join(tool_dir, "prereq", "doltool", "doltool.exe")

        if not os.path.exists(doltool_path):
            print(f" Warning: doltool not found at {doltool_path}")
            return None

        try:
            result = subprocess.run(
                [doltool_path, "-i", exe_path],
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tool_dir,
                timeout=10
            )
            
            if "Text Section  1" not in result.stdout:
                return None
            
            # Parse Text Section 1
            doltool_section_1 = result.stdout.split("Text Section  1:")[1]
            doltool_section_1_list = doltool_section_1.split()
            
            disk_area = int(doltool_section_1_list[0].split('=')[1], base=16)
            memory_area_str = doltool_section_1_list[1].split('=')[1]
            
            # Remove 0x80 prefix if present
            if memory_area_str.lower().startswith("0x80"):
                memory_area_str = "0x" + memory_area_str[4:]
            elif memory_area_str.lower().startswith("80"):
                memory_area_str = "0x" + memory_area_str[2:]
            
            memory_area = int(memory_area_str, base=16)
            offset = memory_area - disk_area
            
            return f"{offset:X}"
            
        except Exception as e:
            print(f" Could not calculate GC/Wii offset: {e}")
            return None