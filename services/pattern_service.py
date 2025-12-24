import os
from typing import Optional, Dict, List, Tuple, Union
from classes.project_data.project_data import ProjectData
from classes.injection_targets.hook import Hook
from functions.verbose_print import verbose_print

class PatternMatch:
    """Represents a found pattern match"""
    def __init__(self, pattern_name: str, file_offset: int, memory_address: int, 
                 hook_offset: int, asm_template: str):
        self.pattern_name = pattern_name
        self.file_offset = file_offset
        self.memory_address = memory_address
        self.hook_offset = hook_offset
        self.asm_template = asm_template


class FlexiblePattern:
    """
    Represents a pattern with potential gaps/wildcards.
    Pattern is defined as a list of tuples:
    - ("bytes", b'\\x00\\x01\\x02') - Match these exact bytes
    - ("skip", 8) - Skip 8 bytes (don't care what's there)
    """
    def __init__(self, segments: List[Tuple[str, Union[bytes, int]]]):
        self.segments = segments
    
    def match(self, data: bytes, start_pos: int = 0) -> Optional[int]:
        """
        Try to match this pattern starting at start_pos in data.
        Returns the starting position if match found, None otherwise.
        """
        pos = start_pos
        
        for segment_type, segment_value in self.segments:
            if segment_type == "bytes":
                # Check if we have enough data left
                if pos + len(segment_value) > len(data):
                    return None
                
                # Check if bytes match
                if data[pos:pos + len(segment_value)] != segment_value:
                    return None
                
                pos += len(segment_value)
            
            elif segment_type == "skip":
                # Skip the specified number of bytes
                pos += segment_value
                
                # Check if we went past the end
                if pos > len(data):
                    return None
        
        return start_pos
    
    def search(self, data: bytes) -> Optional[int]:
        """
        Search for this pattern in data.
        Returns the position where the pattern starts, or None if not found.
        """
        # We need to search byte by byte since we have variable sections
        # Start with the first segment to optimize
        if not self.segments or self.segments[0][0] != "bytes":
            return None
        
        first_bytes = self.segments[0][1]
        search_pos = 0
        
        while True:
            # Find the next occurrence of the first byte sequence
            try:
                search_pos = data.index(first_bytes, search_pos)
            except ValueError:
                return None  # Not found
            
            # Try to match the full pattern from this position
            if self.match(data, search_pos) is not None:
                return search_pos
            
            # Move to next position
            search_pos += 1
    
    def total_length(self) -> int:
        """Calculate the total length of the pattern including skips"""
        total = 0
        for segment_type, segment_value in self.segments:
            if segment_type == "bytes":
                total += len(segment_value)
            elif segment_type == "skip":
                total += segment_value
        return total


class PatternService:
    """Handles automatic pattern detection in game executables"""
    
    # PS1 Patterns - DrawOTag variants (every frame hook)
    PS1_PATTERNS = {
        "DrawOTag_v1": {
            "bytes": b'\x09\xf8\x40\x00\x21\x38\x00\x00\x14\x00\xbf\x8f\x10\x00\xb0\x8f\x18\x00\xbd\x27\x08\x00\xe0\x03\x00\x00\x00\x00\xe0\xff\xbd\x27\x18\x00\xb2\xaf',
            "hook_offset": 0x14,
            "description": "DrawOTag (Every Frame Hook) - Variant 1",
            "asm_template": ".set noreorder\n# Replacing DrawOTag jr ra\nj ModMain\n\n"
        },
        "DrawOTag_v2": {
            "bytes": b'\x09\xf8\x40\x00\x21\x38\x00\x00\x14\x00\xbf\x8f\x10\x00\xb0\x8f\x08\x00\xe0\x03\x18\x00\xbd\x27\xe0\xff\xbd\x27\x18\x00\xb2\xaf',
            "hook_offset": 0x10,
            "description": "DrawOTag (Every Frame Hook) - Variant 2",
            "asm_template": ".set noreorder\n# Replacing DrawOTag jr ra\nj ModMain\n\n"
        },
        "DrawOTag_v3": {
            "bytes": b'\x00\x00\x00\x00\x09\xf8\x40\x00\x21\x38\x00\x00\x14\x00\xbf\x8f\x10\x00\xb0\x8f\x18\x00\xbd\x27\x08\x00\xe0\x03\x00\x00\x00\x00',
            "hook_offset": 0x18,
            "description": "DrawOTag (Every Frame Hook) - Variant 3",
            "asm_template": ".set noreorder\n# Replacing DrawOTag jr ra\nj ModMain\n\n"
        },
        "DrawOTag_v4": {
            "bytes": b'\x00\x00\x00\x00\x09\xf8\x40\x00\x21\x30\x00\x00\x14\x00\xbf\x8f\x10\x00\xb0\x8f\x18\x00\xbd\x27\x08\x00\xe0\x03\x00\x00\x00\x00',
            "hook_offset": 0x18,
            "description": "DrawOTag (Every Frame Hook) - Variant 4",
            "asm_template": ".set noreorder\n# Replacing DrawOTag jr ra\nj ModMain\n\n"
        }
    }
    
    # PS2 Patterns - Various system functions (every frame hooks)
    PS2_PATTERNS = {
        "sceSifSendCmd": {
            "bytes": b'\x2d\x10\xc0\x00\x2d\x18\xe0\x00\x2d\x58\x00\x01\xf0\xff\xbd\x27\x2d\x50\x20\x01\x2d\x30\xa0\x00\x00\x00\xbf\xff\x2d\x38\x40\x00\x2d\x40\x60\x00\x2d\x48\x60\x01',
            "hook_offset": 0x28,
            "description": "sceSifSendCmd (Every Frame Hook)",
            "asm_template": ".set noreorder\n# Replacing sceSifSendCmd jr ra\njal ModMain\n",
            "return_type": "int",
            "original_function": "sceSifSendCmd"
        },
        "scePad2Read": {
            "bytes": b'\x2d\x20\x40\x02\x34\x03\x03\x24\x02\x00\x04\x92\x18\x18\x23\x02',
            "hook_offset": 0x48,
            "description": "scePad2Read (Every Frame Hook)",
            "asm_template": ".set noreorder\n# Replacing scePad2Read jr ra\njal ModMain\n",
            "return_type": "int",
            "original_function": "scePad2Read"
        },
        "scePadRead": {
            "bytes": b'\x2d\x38\x80\x00\x70\x00\x03\x24\x1c\x00\x04\x24\x18\x18\xe3\x70\x18\x20\xa4\x00',
            "hook_offset": 0x74,
            "description": "scePadRead (Every Frame Hook)",
            "asm_template": ".set noreorder\n# Replacing scePadRead jr ra\njal ModMain\n",
            "return_type": "int",
            "original_function": "scePadRead"
        }
    }
    
    # GameCube Patterns
    GAMECUBE_PATTERNS = {
        "VIWaitForRetrace": {
            "bytes": b'\x93\xe1\x00\x44\x89\x03\x00\x2c\xa0\x03\x00\x0e\x55\x1f\x28\x34\xa1\x03\x00\x16\x7c\x1f\x01\xd6\x81\x63\x00\x20\x81\x43\x00\x30\xa1\x83\x00\x0a\x55\x08\x08\x34\x7c\x08\x02\x14\x7c\x0a\x02\x14\x2c\x0b\x00\x00\x90\x04\x00\x00',
            "hook_offset": -0x10,
            "description": "VIWaitForRetrace (Every Frame Hook)",
            "asm_template": "# Replacing VIWaitForRetrace blr\nb ModMain\n"
        },
        "VISetNextFrameBuffer": {
            "bytes": b'\x7c\x08\x02\xa6\x3c\x80\x80\x2f\x90\x01\x00\x04\x94\x21\xff\xe8\x93\xe1\x00\x14\x3b\xe4\xfa\xa8\x93\xc1\x00\x10\x3b\xc3\x00\x00',
            "hook_offset": 0x68,
            "description": "VISetNextFrameBuffer (Every Frame Hook). (Cannot Use With Gecko)",
            "asm_template": "# Replacing VISetNextFrameBuffer blr\nb ModMain\n"
        },
        "OSSleepThread": {
            "bytes": b'\x90\xa4\x02\xe0\x80\x65\x02\xe4\x90\x85\x02\xe4\x28\x03\x00\x00\x90\x64\x02\xe4',
            "hook_offset": 0x5C,
            "description": "OSSleepThread (Every Frame Hook)",
            "asm_template": "# Replacing OSSleepThread blr\nb ModMain\n"
        },
    }
    
    # Wii Patterns
    WII_PATTERNS = {
        "OSSleepThread": {
            "bytes": b'\x90\xa4\x02\xe0\x80\x65\x02\xe4\x90\x85\x02\xe4\x2c\x03\x00\x00\x90\x64\x02\xe4',
            "hook_offset": 0x5C,
            "description": "OSSleepThread (Every Frame Hook)",
            "asm_template": "# Replacing OSSleepThread blr\nb ModMain\n"
        },
        "GXSetDrawDone": {
            "pattern": FlexiblePattern([
                ("bytes", b'\x3b\xe0\x00\x00\x3c\x60\xcc\x01\x93\xe3\x80\x00\x93\xe3\x80\x00\x93\xe3\x80\x00\x93\xe3\x80\x00\x93\xe3\x80\x00\x93\xe3\x80\x00\x93\xe3\x80\x00\x93\xe3\x80\x00'),
                ("skip", 16),
                ("bytes", b'\x80\x01\x00\x14\x83\xe1\x00\x0c\x83\xc1\x00\x08\x7c\x08\x03\xa6\x38\x21\x00\x10\x4e\x80\x00\x20'),
            ]),
            "hook_offset": 0x4C,
            "description": "GXSetDrawDone (Every Frame Hook)",
            "asm_template": "# Replacing GXSetDrawDone blr\nb ModMain\n"
        },
        "GXFlush": {
            "pattern": FlexiblePattern([
                ("bytes", b'\x38\x00\x00\x00\x3c\x60\xcc\x01\x90\x03\x80\x00\x90\x03\x80\x00\x90\x03\x80\x00\x90\x03\x80\x00\x90\x03\x80\x00\x90\x03\x80\x00\x90\x03\x80\x00\x90\x03\x80\x00'),
                ("skip", 4),
                ("bytes", b'\x80\x01\x00\x14\x7c\x08\x03\xa6\x38\x21\x00\x10\x4e\x80\x00\x20'),
            ]),
            "hook_offset": 0x38,
            "description": "GXFlush (Every Frame Hook)",
            "asm_template": "# Replacing GXFlush blr\nb ModMain\n"
        },
        "VIWaitForRetrace": {
            "pattern": FlexiblePattern([
                ("bytes", b'\x94\x21\xff\xf0\x7c\x08\x02\xa6\x90\x01\x00\x14\x93\xe1\x00\x0c\x93\xc1\x00\x08'),
                ("skip", 4),
                ("bytes", b'\x7c\x7f\x1b\x78'),
                ("skip", 16),
                ("bytes", b'\x7c\x1e\x00\x40'),
                ("skip", 4),
                ("bytes", b'\x7f\xe3\xfb\x78'),
                ("skip", 4),
                ("bytes", b'\x80\x01\x00\x14\x83\xe1\x00\x0c\x83\xc1\x00\x08\x7c\x08\x03\xa6\x38\x21\x00\x10\x4e\x80\x00\x20'),
            ]),
            "hook_offset": 0x50,
            "description": "VIWaitForRetrace (Every Frame Hook)",
            "asm_template": "# Replacing VIWaitForRetrace blr\nb ModMain\n"
        }
    }

    # OSReport Patterns (for library function detection, not hooks)
    OSREPORT_PATTERNS = {
        "Gamecube": b'\x7c\x08\x02\xa6\x90\x01\x00\x04\x94\x21\xff\x88\x40\x86\x00\x24\xd8\x21\x00\x28\xd8\x41\x00\x30',
        "Wii": b'\x94\x21\xff\x80\x7c\x08\x02\xa6\x90\x01\x00\x84\x93\xe1\x00\x7c\x40\x86\x00\x24\xd8\x21\x00\x28\xd8\x41\x00\x30\xd8\x61\x00\x38\xd8\x81\x00\x40\xd8\xa1\x00\x48\xd8\xc1\x00\x50\xd8\xe1\x00\x58\xd9\x01\x00\x60'
    }
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
    
    def _search_pattern(self, exe_data: bytes, pattern_info: Dict) -> Optional[int]:
        """
        Search for a pattern in executable data.
        Handles both simple byte patterns and flexible patterns.
        Returns file offset if found, None otherwise.
        """
        # Check if this is a flexible pattern
        if "pattern" in pattern_info:
            flexible_pattern = pattern_info["pattern"]
            return flexible_pattern.search(exe_data)
        
        # Simple byte pattern
        elif "bytes" in pattern_info:
            pattern_bytes = pattern_info["bytes"]
            if pattern_bytes in exe_data:
                return exe_data.index(pattern_bytes)
        
        return None
    
    def _get_pattern_length(self, pattern_info: Dict) -> int:
        """Get the length of a pattern (for calculating hook offset)"""
        if "pattern" in pattern_info:
            return pattern_info["pattern"].total_length()
        elif "bytes" in pattern_info:
            return len(pattern_info["bytes"])
        return 0
    
    def find_hook_patterns(self) -> List[PatternMatch]:
        """
        Search for known hook patterns in the main executable.
        Returns a list of all found patterns.
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        
        # Validate tools before proceeding
        tools_valid, error_msg = self.validate_tools(platform)
        if not tools_valid:
            print(f" Tool validation failed: {error_msg}")
            print("  Continuing with fallback offset values...")
        
        # Get main executable path
        main_exe = current_build.GetMainExecutable()
        if not main_exe:
            return []
        
        if current_build.IsSingleFileMode():
            exe_path = current_build.GetSingleFilePath()
            if not exe_path or not os.path.exists(exe_path):
                print(f" Single file not found: {exe_path}")
                return []
        else:
            # For PS1, use local copy
            if platform == "PS1":
                project_folder = self.project_data.GetProjectFolder()
                local_game_files = os.path.join(project_folder, ".config", "game_files")
                exe_path = None
                
                for root, dirs, files in os.walk(local_game_files):
                    if main_exe in files:
                        exe_path = os.path.join(root, main_exe)
                        break
            else:
                exe_path = current_build.FindFileInGameFolder(main_exe)
        
        if not exe_path or not os.path.exists(exe_path):
            print(f" Executable not found: {main_exe}")
            return []
        
        print(f"Scanning executable: {exe_path}")
        
        # Get file offset (for PS2/GC/Wii)
        file_offset = self._get_file_offset(platform, exe_path)
        
        # Select patterns based on platform
        patterns = self._get_patterns_for_platform(platform)
        
        if not patterns:
            print(f" No patterns defined for platform: {platform}")
            return []
        
        # Read executable
        try:
            with open(exe_path, 'rb') as f:
                exe_data = f.read()
        except Exception as e:
            print(f" Could not read executable: {e}")
            return []
        
        print(f"Searching {len(patterns)} pattern(s)...")
        
        # Search for patterns
        matches = []
        for pattern_name, pattern_info in patterns.items():
            file_offset_match = self._search_pattern(exe_data, pattern_info)
            
            if file_offset_match is not None:
                hook_file_offset = file_offset_match + pattern_info["hook_offset"]
                
                # Calculate memory address
                memory_address = self._calculate_memory_address(
                    platform, 
                    hook_file_offset, 
                    file_offset
                )
                
                match = PatternMatch(
                    pattern_name=pattern_info["description"],
                    file_offset=hook_file_offset,
                    memory_address=memory_address,
                    hook_offset=file_offset,
                    asm_template=pattern_info["asm_template"]
                )
                
                matches.append(match)
                print(f" Found pattern: {pattern_info['description']}")
                print(f"  File offset: 0x{hook_file_offset:X}")
                print(f"  Memory address: 0x{memory_address:X}")

                # For PS2 hooks, extract the JAL target and add symbol
                verbose_print(f"  DEBUG: Platform={platform}, pattern_name={pattern_name}")
                if platform == "PS2" and pattern_name in ["sceSifSendCmd", "scePad2Read", "scePadRead"]:
                    verbose_print(f"  DEBUG: PS2 hook detected, extracting JAL target...")

                    # Read the opcode at the pattern match location
                    original_func_addr = self._extract_jal_target_address(
                        exe_data,
                        hook_file_offset,
                        memory_address
                    )

                    verbose_print(f"  DEBUG: Extracted address: {hex(original_func_addr) if original_func_addr else 'None'}")

                    if original_func_addr:
                        # Add symbol for the original function
                        symbol_name = f"_{pattern_name}"  # e.g., "_sceSifSendCmd"
                        verbose_print(f"  DEBUG: Calling _add_symbol_to_file with {symbol_name}")
                        symbol_added = self._add_symbol_to_file(symbol_name, original_func_addr)

                        if symbol_added:
                            print(f"  Added symbol: {symbol_name} = 0x{original_func_addr:X}")
                        else:
                            print(f"  Symbol {symbol_name} already exists in symbols file")

                        # Update main.c template if hook needs return value
                        if "return_type" in pattern_info and "original_function" in pattern_info:
                            verbose_print(f"  DEBUG: Generating return value template...")
                            from services.template_service import TemplateService
                            template_service = TemplateService(self.project_data)
                            template_created = template_service.setup_ps2_hook_with_return_value(
                                pattern_info["original_function"],
                                pattern_info["return_type"]
                            )
                            if template_created:
                                print(f"  Updated main.c with return value template")
                            else:
                                verbose_print(f"  DEBUG: Template not created (main.c already customized)")
                    else:
                        print(f"  Warning: Could not extract JAL target address for {pattern_name}")

        if not matches:
            print(" No patterns found in executable")
        
        return matches
    
    def _get_patterns_for_platform(self, platform: str) -> Dict:
        """Get pattern dictionary for platform"""
        if platform == "PS1":
            return self.PS1_PATTERNS
        elif platform == "PS2":
            return self.PS2_PATTERNS
        elif platform == "Gamecube":
            return self.GAMECUBE_PATTERNS
        elif platform == "Wii":
            return self.WII_PATTERNS
        else:
            return {}
    
    def _get_file_offset(self, platform: str, exe_path: str) -> int:
        """
        Calculate the file offset for PS2/GC/Wii executables.
        This is the difference between file address and memory address.
        """
        if platform == "PS1":
            return 0x8000F800
        elif platform == "PS2":
            return self._find_ps2_offset(exe_path)
        elif platform in ["Gamecube", "Wii"]:
            return self._find_gamecube_wii_offset(exe_path)
        return 0

    def _find_ps2_offset(self, exe_path: str) -> int:
        """
        Find PS2 ELF offset using ee-objdump.
        Returns the difference between memory address and file offset.
        First checks if section map is already cached.
        """
        # Check if section map already exists (avoid running objdump again)
        current_build = self.project_data.GetCurrentBuildVersion()
        main_exe = current_build.GetMainExecutable()

        if main_exe and main_exe in current_build.section_maps:
            sections = current_build.section_maps[main_exe]
            if sections:
                offset = sections[0].offset_diff
                print(f" Using cached section map for PS2 offset: 0x{offset:X}")
                return offset

        # No cached section map - run objdump
        import subprocess

        tool_dir = os.getcwd()
        objdump_path = os.path.join(tool_dir, "prereq", "PS2ee", "bin", "ee-objdump.exe")

        print(f"Looking for ee-objdump at: {objdump_path}")
        print(f"Exists: {os.path.exists(objdump_path)}")

        if not os.path.exists(objdump_path):
            print(f" Warning: ee-objdump not found at {objdump_path}")
            return 0x100000

        try:
            print(f"Running ee-objdump on: {exe_path}")
            
            result = subprocess.run(
                [objdump_path, exe_path, "-x"],
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tool_dir,
                timeout=10
            )
            
            print(f"ee-objdump return code: {result.returncode}")
            
            if result.stderr:
                print(f"ee-objdump stderr: {result.stderr}")
            
            if "Idx Name" not in result.stdout:
                print(f" Warning: Could not parse objdump output")
                print(f"  Output preview: {result.stdout[:500]}")
                return 0x100000
            
            lines = result.stdout.split("Idx Name")[1].split("\n")
            print(f"Lines after 'Idx Name': {lines[:5]}")
            
            objdump_section_0 = None
            for line in lines[1:]:
                if line.strip() and not line.startswith("Idx"):
                    objdump_section_0 = line
                    break
            
            if not objdump_section_0:
                print(" Warning: Could not find section 0")
                return 0x100000
            
            objdump_section_0_list = objdump_section_0.split()
            
            print(f"  PS2 objdump section 0: {objdump_section_0_list}")
            
            if len(objdump_section_0_list) >= 7:
                vma = int(objdump_section_0_list[3], base=16)
                file_off = int(objdump_section_0_list[5], base=16)
                offset = vma - file_off
            elif len(objdump_section_0_list) >= 6:
                vma = int(objdump_section_0_list[3], base=16)
                file_off = int(objdump_section_0_list[4], base=16)
                offset = vma - file_off
            else:
                print(f" Warning: Unknown ELF format (section list length: {len(objdump_section_0_list)})")
                print(f"  Section list: {objdump_section_0_list}")
                return 0x100000
            
            print(f" PS2 offset calculated: 0x{offset:X} (VMA: 0x{vma:X}, File: 0x{file_off:X})")
            return offset
            
        except subprocess.TimeoutExpired:
            print(" Warning: ee-objdump timed out")
            return 0x100000
        except Exception as e:
            print(f" Warning: Failed to calculate PS2 offset: {e}")
            import traceback
            traceback.print_exc()
            return 0x100000

    def _find_gamecube_wii_offset(self, exe_path: str) -> int:
        """
        Find GameCube/Wii DOL offset using doltool.
        Returns the difference between memory address and file offset.
        First checks if section map is already cached.
        """
        # Check if section map already exists (avoid running doltool again)
        current_build = self.project_data.GetCurrentBuildVersion()
        main_exe = current_build.GetMainExecutable()

        if main_exe and main_exe in current_build.section_maps:
            sections = current_build.section_maps[main_exe]
            # Find first text section (GameCube/Wii uses first text section)
            text_sections = [s for s in sections if s.section_type == "text"]
            if text_sections:
                offset = text_sections[0].offset_diff
                print(f" Using cached section map for GC/Wii offset: 0x{offset:X}")
                return offset

        # No cached section map - run doltool
        import subprocess

        tool_dir = os.getcwd()
        doltool_path = os.path.join(tool_dir, "prereq", "doltool", "doltool.exe")

        if not os.path.exists(doltool_path):
            print(f" Warning: doltool not found at {doltool_path}")
            return 0x3000

        try:
            result = subprocess.run(
                [doltool_path, "-i", exe_path],
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tool_dir
            )
            
            if "Text Section  1" not in result.stdout:
                print(f" Warning: Could not parse doltool output")
                print(f"  stderr: {result.stderr}")
                return 0x3000
            
            doltool_section_1 = result.stdout.split("Text Section  1:")[1]
            doltool_section_1_list = doltool_section_1.split()

            verbose_print(f"  GC/Wii doltool section: {doltool_section_1_list}")

            disk_area = int(doltool_section_1_list[0].split('=')[1], base=16)
            memory_area_str = doltool_section_1_list[1].split('=')[1]

            if memory_area_str.lower().startswith("0x80"):
                memory_area_str = "0x" + memory_area_str[4:]
            elif memory_area_str.lower().startswith("80"):
                memory_area_str = "0x" + memory_area_str[2:]

            memory_area = int(memory_area_str, base=16)
            offset = memory_area - disk_area

            verbose_print(f" GC/Wii offset calculated: 0x{offset:X} (Mem: 0x{memory_area:X}, Disk: 0x{disk_area:X})")
            return offset
            
        except Exception as e:
            print(f" Warning: Failed to calculate GC/Wii offset: {e}")
            import traceback
            traceback.print_exc()
            return 0x3000
    
    def _calculate_memory_address(self, platform: str, file_offset: int, base_offset: int) -> int:
        """Calculate the in-memory address from file offset"""
        if platform == "PS1":
            return base_offset + file_offset
        elif platform == "PS2":
            return base_offset + file_offset
        elif platform in ["Gamecube", "Wii"]:
            return 0x80000000 + base_offset + file_offset
        return file_offset

    def _extract_jal_target_address(self, exe_data: bytes, file_offset: int, memory_address: int) -> Optional[int]:
        """
        Extract the target address from a JAL opcode.

        MIPS JAL format: 0x0cXXXXXX where XXXXXX is the 26-bit target (in words)
        PS2 uses little endian byte order.

        Args:
            exe_data: Executable binary data
            file_offset: File offset where the JAL instruction is located
            memory_address: Memory address of the JAL instruction

        Returns:
            Target address, or None if not a valid JAL opcode
        """
        # Read 4-byte opcode at file offset
        if file_offset + 4 > len(exe_data):
            verbose_print(f"  DEBUG: file_offset {file_offset} + 4 > exe_data length")
            return None

        opcode_bytes = exe_data[file_offset:file_offset + 4]
        verbose_print(f"  DEBUG: Opcode bytes at 0x{file_offset:X}: {opcode_bytes.hex()}")

        # PS2 is little endian
        opcode = int.from_bytes(opcode_bytes, byteorder='little', signed=False)
        verbose_print(f"  DEBUG: Opcode value: 0x{opcode:08X}")

        # Verify it's a JAL instruction (opcode starts with 0x0c)
        opcode_type = (opcode >> 26) & 0x3F
        verbose_print(f"  DEBUG: Opcode type: 0x{opcode_type:02X} (should be 0x03 for JAL)")

        if opcode_type != 0x03:  # 0x03 is JAL in MIPS
            return None

        # Extract 26-bit target field
        target_field = opcode & 0x03FFFFFF
        verbose_print(f"  DEBUG: Target field: 0x{target_field:07X}")

        # Convert from words to bytes (multiply by 4)
        target_bytes = target_field << 2
        verbose_print(f"  DEBUG: Target bytes: 0x{target_bytes:08X}")

        # JAL uses upper 4 bits of (PC + 4)
        pc_upper = (memory_address + 4) & 0xF0000000
        verbose_print(f"  DEBUG: PC upper bits: 0x{pc_upper:08X}")

        # Combine to get full 32-bit address
        target_address = pc_upper | target_bytes
        verbose_print(f"  DEBUG: Final target address: 0x{target_address:08X}")

        return target_address

    def _add_symbol_to_file(self, symbol_name: str, address: int) -> bool:
        """
        Add a symbol to the current build's symbols file.

        Args:
            symbol_name: Name of the symbol (e.g., "_sceSifSendCmd")
            address: Memory address of the symbol

        Returns:
            True if symbol was added, False if already exists or error
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        project_folder = self.project_data.GetProjectFolder()

        symbols_file = current_build.GetSymbolsFile()
        symbols_path = os.path.join(project_folder, "symbols", symbols_file)

        verbose_print(f"  DEBUG: Symbols file path: {symbols_path}")
        verbose_print(f"  DEBUG: Adding symbol {symbol_name} = 0x{address:X}")

        try:
            # Check if file exists and read content
            if os.path.exists(symbols_path):
                with open(symbols_path, 'r') as f:
                    content = f.read()

                # Don't duplicate
                if symbol_name in content:
                    verbose_print(f"  Symbol {symbol_name} already exists in symbols file")
                    return False

                # Append to file
                with open(symbols_path, 'a') as f:
                    if content and not content.endswith('\n'):
                        f.write('\n')
                    f.write(f"{symbol_name} = 0x{address:X};\n")

                verbose_print(f"  Added symbol to existing file: {symbol_name} = 0x{address:X}")
            else:
                # Create new file
                verbose_print(f"  Symbols file doesn't exist, creating: {symbols_path}")
                os.makedirs(os.path.dirname(symbols_path), exist_ok=True)
                with open(symbols_path, 'w') as f:
                    f.write(f"/* Symbols file for build version */\n")
                    f.write(f"{symbol_name} = 0x{address:X};\n")

                verbose_print(f"  Created new symbols file with: {symbol_name} = 0x{address:X}")

            return True

        except Exception as e:
            print(f" ERROR adding symbol {symbol_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_hook_from_pattern(self, pattern_match: PatternMatch, hook_name: str = "AutoHook") -> Hook:
        """
        Create a Hook object from a pattern match.
        Now uses section maps if available.
        """
        hook = Hook()
        hook.SetName(hook_name)
        
        hook.SetMemoryAddress(f"{pattern_match.memory_address:X}")
        
        # Create ASM file
        project_folder = self.project_data.GetProjectFolder()
        asm_dir = os.path.join(project_folder, "asm")
        os.makedirs(asm_dir, exist_ok=True)
        
        asm_file_path = os.path.join(asm_dir, f"{hook_name}.s")
        
        with open(asm_file_path, 'w') as f:
            f.write(pattern_match.asm_template)
        print(f" Created ASM file: asm/{hook_name}.s")
        
        hook.AddCodeFile(asm_file_path)
        
        # Use section map if available
        current_build = self.project_data.GetCurrentBuildVersion()
        main_exe = current_build.GetMainExecutable()
        
        if main_exe:
            file_offset = current_build.GetFileOffsetForAddress(main_exe, pattern_match.memory_address)
            
            if file_offset is not None:
                hook.SetInjectionFileAddress(f"{file_offset:X}")
                hook.SetAutoCalculateInjectionFileAddress(True)
                print(f"  File offset: 0x{file_offset:X} (from section map)")
            else:
                hook.SetInjectionFileAddress(f"{pattern_match.file_offset:X}")
                hook.SetAutoCalculateInjectionFileAddress(False)
                print(f"  File offset: 0x{pattern_match.file_offset:X} (from pattern scan)")
        else:
            hook.SetInjectionFileAddress(f"{pattern_match.file_offset:X}")
            hook.SetAutoCalculateInjectionFileAddress(False)
        
        return hook
    
    def validate_tools(self, platform: str) -> Tuple[bool, str]:
        """
        Validate that required tools are available for the platform.
        Returns (success, error_message)
        """
        tool_dir = os.getcwd()
        
        if platform == "PS2":
            objdump_path = os.path.join(tool_dir, "prereq", "PS2ee", "bin", "ee-objdump.exe")
            if not os.path.exists(objdump_path):
                return False, (
                    "PS2 toolchain not found!\n\n"
                    f"Expected: {objdump_path}\n\n"
                    "Please ensure the PS2 toolchain is installed in prereq/PS2ee/"
                )
        
        elif platform in ["Gamecube", "Wii"]:
            doltool_path = os.path.join(tool_dir, "prereq", "doltool", "doltool.exe")
            if not os.path.exists(doltool_path):
                return False, (
                    "DOL tool not found!\n\n"
                    f"Expected: {doltool_path}\n\n"
                    "Please ensure doltool is installed in prereq/doltool/"
                )

        return True, ""


    def find_osreport(self) -> Optional[int]:
        """
        Search for OSReport function in GameCube/Wii executables.
        Returns the memory address if found, None otherwise.
        Only works for GameCube and Wii platforms.
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()

        # Only for GameCube and Wii
        if platform not in ["Gamecube", "Wii"]:
            return None

        # Get main executable
        main_exe = current_build.GetMainExecutable()
        if not main_exe:
            return None

        # Find executable (may be in subdirectory)
        exe_path = current_build.FindFileInGameFolder(main_exe)
        if not exe_path or not os.path.exists(exe_path):
            print(f"  Executable not found: {main_exe}")
            return None

        # Read executable
        try:
            with open(exe_path, 'rb') as f:
                exe_data = f.read()
            verbose_print(f"  Scanning {len(exe_data)} bytes in {main_exe}")
        except Exception as e:
            verbose_print(f"  Error reading executable: {e}")
            return None

        # Get the pattern for this platform
        pattern_bytes = self.OSREPORT_PATTERNS.get(platform)
        if not pattern_bytes:
            verbose_print(f"  No OSReport pattern defined for {platform}")
            return None

        verbose_print(f"  Looking for {len(pattern_bytes)}-byte pattern...")

        # Search for pattern
        if pattern_bytes not in exe_data:
            verbose_print(f"  OSReport pattern not found")
            return None

        file_offset_match = exe_data.index(pattern_bytes)

        # Calculate memory address
        base_offset = self._get_file_offset(platform, exe_path)
        memory_address = self._calculate_memory_address(platform, file_offset_match, base_offset)

        verbose_print(f"  Found OSReport:")
        verbose_print(f"  File offset: 0x{file_offset_match:X}")
        verbose_print(f"  Memory address: 0x{memory_address:X}")

        return memory_address

    def setup_osreport(self) -> bool:
        """
        Find OSReport, add it to symbols file, create osreport.h header,
        and update main.c to use it.
        Returns True if OSReport was found and set up, False otherwise.
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        project_folder = self.project_data.GetProjectFolder()

        # Only for GameCube and Wii
        if platform not in ["Gamecube", "Wii"]:
            return False

        # Find OSReport
        osreport_address = self.find_osreport()
        if not osreport_address:
            verbose_print("  OSReport pattern not found")
            return False

        # Add to symbols file
        build_name = current_build.GetBuildName()
        symbols_file = current_build.GetSymbolsFile()
        symbols_path = os.path.join(project_folder, "symbols", symbols_file)

        # Check if OSReport already exists in symbols
        if os.path.exists(symbols_path):
            with open(symbols_path, 'r') as f:
                content = f.read()
                if 'OSReport' in content:
                    verbose_print("  OSReport already in symbols file")
                else:
                    # Append OSReport to symbols file
                    with open(symbols_path, 'a') as f:
                        if content and not content.endswith('\n'):
                            f.write('\n')
                        f.write(f"OSReport = 0x{osreport_address:X};\n")
                    verbose_print(f"  Added OSReport to {symbols_file}")
        else:
            # Create symbols file with OSReport
            os.makedirs(os.path.dirname(symbols_path), exist_ok=True)
            with open(symbols_path, 'w') as f:
                f.write(f"OSReport = 0x{osreport_address:X};\n")
            verbose_print(f"  Created {symbols_file} with OSReport")

        # Create osreport.h header file
        osreport_h_path = os.path.join(project_folder, "include", "osreport.h")
        if not os.path.exists(osreport_h_path):
            os.makedirs(os.path.dirname(osreport_h_path), exist_ok=True)
            with open(osreport_h_path, 'w') as f:
                f.write("""#ifndef OSREPORT_H
#define OSREPORT_H

// GameCube/Wii Debug Print Function
// Outputs to the console in Dolphin emulator
void OSReport(const char* format, ...);

#endif // OSREPORT_H
""")
            verbose_print(f"  Created: include/osreport.h")

        # Only update main.c if it contains the default template code
        main_c_path = os.path.join(project_folder, "src", "main.c")
        if os.path.exists(main_c_path):
            with open(main_c_path, "r") as f:
                current_content = f.read()

            # Check if main.c still has default content (user hasn't customized it)
            is_default = "// Your code here" in current_content or current_content.strip() == ""

            if is_default:
                with open(main_c_path, 'w') as f:
                    f.write("""#include <types.h>
#include <symbols.h>
#include <osreport.h>

void ModMain(void) {
    OSReport("Hello World!\\n");

    return;
}

""")
                verbose_print(f"  Updated: src/main.c (Hello World)")
            else:
                print(f"  Skipped: src/main.c (already customized)")

        return True