import os
import re
from typing import List, Tuple, Optional
from classes.project_data.project_data import ProjectData
from classes.injection_targets.hook import Hook
from functions.verbose_print import verbose_print

class ASMPatch:
    def __init__(self, memory_address: str, file_target: Optional[str], file_offset: Optional[str], asm_code: str, line_number: int):
        self.memory_address = memory_address
        self.file_target = file_target
        self.file_offset = file_offset  # Optional explicit file offset
        self.asm_code = asm_code
        self.line_number = line_number


class ASMParserService: 
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
    
    def _strip_comments(self, line: str) -> str:
        # Remove # comments
        if '#' in line:
            line = line.split('#')[0]
        # Remove ; comments
        if ';' in line:
            line = line.split(';')[0]
        return line.strip()
    
    def parse_multipatch_asm(self, asm_file_path: str) -> List[ASMPatch]:
        """
        Parse a multi-patch ASM file and extract individual patches.
        
        Format:
            .memaddr 0x80123456
            .file SCUS.elf          # Optional - explicit file, defaults to main exe
            .fileaddr 0x1000        # Optional - explicit file address, defaults to automatically calculate from section map or manual file offset
            nop
            
        Example:
            .memaddr 0x80111222
            li $a0, 0x69
            li $a1, 0x420
        """
        if not os.path.exists(asm_file_path):
            print(f" ASM file not found: {asm_file_path}")
            return []
        
        patches = []
        
        with open(asm_file_path, 'r') as f:
            lines = f.readlines()
        
        current_memaddr = None
        current_file = None
        current_fileaddr = None
        current_code_lines = []
        patch_start_line = 0
        
        for line_num, line in enumerate(lines, 1):
            original_line = line
            stripped = line.strip()
            
            # Skip empty lines and pure comment lines
            if not stripped or stripped.startswith('#') or stripped.startswith(';'):
                # If we're collecting code, keep comments
                if current_memaddr and stripped.startswith(('#', ';')):
                    current_code_lines.append(original_line)
                continue
            
            # Remove inline comments for directive parsing
            stripped_no_comments = self._strip_comments(stripped)
            
            if stripped_no_comments.lower().startswith('.memaddr'):
                # Save previous patch if exists
                if current_memaddr and current_code_lines:
                    code = ''.join(current_code_lines).strip()
                    if code:  # Only create patch if there's actual code
                        patches.append(ASMPatch(
                            memory_address=current_memaddr,
                            file_target=current_file,
                            file_offset=current_fileaddr,
                            asm_code=code,
                            line_number=patch_start_line
                        ))
                
                # New patch
                parts = stripped_no_comments.split(maxsplit=1)
                if len(parts) < 2:
                    print(f" Warning: Invalid .memaddr directive at line {line_num}")
                    continue
                
                current_memaddr = parts[1].strip()
                current_file = None  
                current_fileaddr = None  
                current_code_lines = []
                patch_start_line = line_num
            
            # Check .fileaddr BEFORE .file 
            elif stripped_no_comments.lower().startswith('.fileaddr'):
                parts = stripped_no_comments.split(maxsplit=1)
                if len(parts) < 2:
                    print(f" Warning: Invalid .fileaddr directive at line {line_num}")
                    continue
                current_fileaddr = parts[1].strip()
                print(f"  DEBUG: Set fileaddr to '{current_fileaddr}' at line {line_num}")
            
            elif stripped_no_comments.lower().startswith('.file'):
                parts = stripped_no_comments.split(maxsplit=1)
                if len(parts) < 2:
                    print(f" Warning: Invalid .file directive at line {line_num}")
                    continue
                current_file = parts[1].strip()
                print(f"  DEBUG: Set file to '{current_file}' at line {line_num}")
            
            else:
                # The actual ASM code
                if current_memaddr:
                    current_code_lines.append(original_line)
                else:
                    print(f" Warning: ASM code before .memaddr directive at line {line_num}")
        
        # The last patch
        if current_memaddr and current_code_lines:
            code = ''.join(current_code_lines).strip()
            if code:
                patches.append(ASMPatch(
                    memory_address=current_memaddr,
                    file_target=current_file,
                    file_offset=current_fileaddr,
                    asm_code=code,
                    line_number=patch_start_line
                ))
        
        return patches
    
    def create_hooks_from_multipatch(self, asm_file_path: str, base_name: str = "MultiPatch") -> List[Hook]:
        patches = self.parse_multipatch_asm(asm_file_path)
        
        if not patches:
            print(f" No patches found in {asm_file_path}")
            return []
        
        print(f" Found {len(patches)} patch(es) in multi-patch file")
        
        hooks = []
        project_folder = self.project_data.GetProjectFolder()
        
        # Put generated files in a hidden subfolder
        generated_dir = os.path.join(project_folder, "asm", ".generated", base_name)
        os.makedirs(generated_dir, exist_ok=True)
        
        # Get main executable if not specified
        main_exe = self.project_data.GetCurrentBuildVersion().GetMainExecutable()
        current_build = self.project_data.GetCurrentBuildVersion()
        
        if not main_exe:
            print(" Warning: No main executable set - cannot determine default file target")
        
        for i, patch in enumerate(patches, 1):
            # Generate unique hook name internally
            hook_name = f"{base_name}_patch_{i}"
            
            # Create individual ASM file in hidden folder
            individual_asm_path = os.path.join(generated_dir, f"{hook_name}.s")
            with open(individual_asm_path, 'w') as f:
                f.write(f"# Auto-generated from multi-patch: {base_name}\n")
                f.write(f"# Original location: line {patch.line_number}\n")
                f.write(f"# Memory address: {patch.memory_address}\n")
                if patch.file_target:
                    f.write(f"# Target file: {patch.file_target}\n")
                else:
                    f.write(f"# Target file: {main_exe} (default)\n")
                if patch.file_offset:
                    f.write(f"# Explicit file address: {patch.file_offset}\n")
                f.write("\n")
                f.write(patch.asm_code)
                f.write("\n")
            
            print(f"   Generated: {hook_name}.s (hidden)")
            
            # Create Hook object
            hook = Hook()
            hook.SetName(hook_name)
            hook.SetTemporary(True)
            
            # Remove 0x prefix
            clean_mem_addr = patch.memory_address.replace('0x', '').replace('0X', '').strip()
            hook.SetMemoryAddress(clean_mem_addr)
            hook.AddCodeFile(individual_asm_path)
            
            # Determine injection file before file offset logic
            # Use main exe if no .file directive was specified
            injection_file = patch.file_target if patch.file_target else main_exe
            
            if not injection_file:
                print(f"    Warning: No injection file for {hook_name} - skipping")
                continue
            
            hook.SetInjectionFile(injection_file)
            
            #  It tries to find the file address in this order:
            # 1. Explicit .fileaddr
            # 2. Section map
            # 3. Single offset (if not section map available, or on PS1)
            
            if patch.file_offset:
                # Priority 1: Explicit file address provided
                clean_file_addr = patch.file_offset.replace('0x', '').replace('0X', '').strip()
                hook.SetInjectionFileAddress(clean_file_addr)
                hook.SetAutoCalculateInjectionFileAddress(False)
                print(f"    Using explicit file address: 0x{clean_file_addr} for {injection_file}")
            else:
                # Try to calculate file offset
                try:
                    # Parse memory address
                    mem_addr_str = clean_mem_addr
                    if mem_addr_str.startswith('80'):
                        mem_addr_str = mem_addr_str[2:]
                    
                    mem_addr_int = int(mem_addr_str, 16)
                    
                    # Try section map
                    file_offset = current_build.GetFileOffsetForAddress(injection_file, mem_addr_int)
                    
                    if file_offset is not None:
                        hook.SetInjectionFileAddress(f"{file_offset:X}")
                        hook.SetAutoCalculateInjectionFileAddress(True)
                        print(f"    File offset: 0x{file_offset:X} (from section map)")
                    else:
                        # Fallback to single offset
                        file_offset_from_ram = current_build.GetInjectionFileOffset(injection_file)
                        
                        if file_offset_from_ram and file_offset_from_ram != "":
                            ram_offset_int = int(file_offset_from_ram, 16)
                            file_addr = mem_addr_int - ram_offset_int
                            
                            hook.SetInjectionFileAddress(f"{file_addr:X}")
                            hook.SetAutoCalculateInjectionFileAddress(True)
                            print(f"    File offset: 0x{file_addr:X} (from single offset)")
                        else:
                            # No offset available
                            print(f"     Warning: No section map or file offset for {injection_file}")
                            hook.SetAutoCalculateInjectionFileAddress(False)
                            
                except Exception as e:
                    print(f"     Could not calculate file offset: {e}")
                    import traceback
                    traceback.print_exc()
                    hook.SetAutoCalculateInjectionFileAddress(False)
            
            hooks.append(hook)
            print(f"   Created internal hook: {hook_name} @ 0x{clean_mem_addr} → {injection_file}")
        
        return hooks
    
    def is_multipatch_file(self, asm_file_path: str) -> bool:
        """
        Check if an ASM file is a multi-patch file by looking for .memaddr text
        """
        if not os.path.exists(asm_file_path):
            return False
        
        try:
            with open(asm_file_path, 'r') as f:
                content = f.read()
            
            # Check for at least one instance of .memaddr
            return '.memaddr' in content.lower()
        except:
            return False