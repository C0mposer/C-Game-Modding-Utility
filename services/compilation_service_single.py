# services/compilation_service.py

import os
import re
import subprocess
import json
from typing import List, Tuple, Optional, Callable, Dict
from pathlib import Path
from classes.project_data.project_data import ProjectData
from classes.mod_builder import ModBuilder
from classes.injection_targets.hook import Hook
from functions.print_wrapper import *
from functions.verbose_print import verbose_print

class BuildCache:
    """Manages build cache for incremental compilation"""

    def __init__(self, cache_path: str):
        self.cache_path = cache_path
        self.data = self._load_cache()

    def _load_cache(self) -> dict:
        """Load existing cache or return empty cache"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except:
                return self._empty_cache()
        return self._empty_cache()

    def _empty_cache(self) -> dict:
        return {
            "last_compiler_flags": "",
            "last_platform": "",
            "last_build_name": "",
            "last_build_index": -1,
            "last_include_dir_mtime": 0.0,
            "files": {}
        }

    def save(self):
        """Save cache to disk"""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def clear(self):
        """Clear cache (for Clean builds)"""
        self.data = self._empty_cache()
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)

    def get_file_info(self, source_path: str) -> Optional[dict]:
        """Get cached info for a source file"""
        return self.data.get("files", {}).get(source_path)

    def set_file_info(self, source_path: str, source_mtime: float, obj_file: str, obj_mtime: float):
        """Update cached info for a source file"""
        if "files" not in self.data:
            self.data["files"] = {}
        self.data["files"][source_path] = {
            "source_mtime": source_mtime,
            "obj_file": obj_file,
            "obj_mtime": obj_mtime
        }

    def build_config_changed(self, compiler_flags: str, platform: str, build_name: str, build_index: int) -> bool:
        """Check if build configuration changed since last build"""
        return (
            self.data.get("last_compiler_flags") != compiler_flags or
            self.data.get("last_platform") != platform or
            self.data.get("last_build_name") != build_name or
            self.data.get("last_build_index") != build_index
        )

    def update_build_config(self, compiler_flags: str, platform: str, build_name: str, build_index: int):
        """Update build configuration in cache"""
        self.data["last_compiler_flags"] = compiler_flags
        self.data["last_platform"] = platform
        self.data["last_build_name"] = build_name
        self.data["last_build_index"] = build_index

    def get_newest_include_mtime(self, include_dir: str) -> float:
        """Get the newest modification time of any file in include directory"""
        if not os.path.exists(include_dir):
            return 0.0

        newest_mtime = 0.0
        for root, _, files in os.walk(include_dir):
            for file in files:
                if file.endswith(('.h', '.hpp')):
                    file_path = os.path.join(root, file)
                    mtime = os.path.getmtime(file_path)
                    newest_mtime = max(newest_mtime, mtime)

        return newest_mtime

    def include_dir_changed(self, include_dir: str) -> bool:
        """Check if any header file changed since last build"""
        current_mtime = self.get_newest_include_mtime(include_dir)
        last_mtime = self.data.get("last_include_dir_mtime", 0.0)

        if current_mtime > last_mtime:
            # Update cached include dir mtime
            self.data["last_include_dir_mtime"] = current_mtime
            return True
        return False

class CompilationResult:
    """Represents the result of a compilation operation"""
    def __init__(self, success: bool, message: str = "", details: str = ""):
        self.success = success
        self.message = message
        self.details = details
        self.object_files: List[str] = []
        self.linker_overflow_errors: List[Dict[str, str]] = []  # List of {section: str, overflow_bytes: str}

class AutoHookInfo:
    """Information about an auto-detected hook from C code"""
    def __init__(self, hook_type: str, memory_address: str, function_name: str, 
                 source_file: str, line_number: int, target_file: Optional[str] = None,
                 explicit_file_addr: Optional[str] = None):  # NEW parameter
        self.hook_type = hook_type  # "J_HOOK", "JAL_HOOK", "B_HOOK", "BL_HOOK"
        self.memory_address = memory_address
        self.function_name = function_name
        self.source_file = source_file
        self.line_number = line_number
        self.target_file = target_file  # Optional: specific game file to inject into
        self.explicit_file_addr = explicit_file_addr  # NEW: explicit file address
        
class CompilationService:
    """Handles all compilation and linking operations with auto-hook support"""
    
    # Hook type to ASM instruction mapping
    HOOK_TEMPLATES = {
        "J_HOOK": ".set noreorder\nj {function_name}\nnop\n", # Mips
        "JAL_HOOK": ".set noreorder\njal {function_name}\n",  # Mips
        "B_HOOK": ".set noreorder\nb {function_name}\n",      # PowerPC
        "BL_HOOK": ".set noreorder\nbl {function_name}\n",    # PowerPC
    }
    
    @staticmethod
    def _strip_ansi_codes(text: str) -> str:
        """Remove ANSI color codes and escape sequences from text"""
        import re
        # Match all ANSI escape sequences:
        # - \x1b\[[0-9;]*m  (color codes like [31m, [0m)
        # - \x1b\[K          (clear to end of line)
        # - \x1b\[[0-9;]*[A-Za-z]  (other control sequences)
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[mKA-Za-z]|\x1b\[K')
        return ansi_escape.sub('', text)

    def _strip_project_paths(self, text: str) -> str:
        r"""
        Strip project directory paths from compiler error/warning messages.
        Only strips paths that are within the project directory.
        Leaves system paths (like C:\MinGW\...) unchanged.
        """
        if not text:
            return text

        # Get project directory and normalize it
        project_dir = os.path.abspath(self.project_data.GetProjectFolder())

        # Normalize path separators to match the OS
        # We need to handle both forward and backslashes in compiler output
        project_dir_normalized = os.path.normpath(project_dir)

        # Create variants with different path separators (for cross-platform)
        project_dir_forward = project_dir_normalized.replace('\\', '/')
        project_dir_back = project_dir_normalized.replace('/', '\\')

        result = text

        # Replace backward slash version (Windows style)
        if project_dir_back in result:
            # Find and replace, preserving the path separator style used in the message
            result = result.replace(project_dir_back + '\\', '')
            result = result.replace(project_dir_back + '/', '')
            result = result.replace(project_dir_back, '')

        # Replace forward slash version (Unix style or mixed)
        if project_dir_forward in result:
            result = result.replace(project_dir_forward + '/', '')
            result = result.replace(project_dir_forward + '\\', '')
            result = result.replace(project_dir_forward, '')

        return result

    def _colorize_filename_in_line(self, line: str) -> str:
        """
        Colorize the filename portion of a compiler message line.
        Format: "filename.c:line:col: message"
        or "In file included from filename.c:line:"
        Colors only the filename in purple for easy identification.
        """
        if not line:
            return line

        # Check for "In file included from" pattern
        include_prefix = "In file included from "
        if line.startswith(include_prefix):
            # Extract the part after the prefix
            after_prefix = line[len(include_prefix):]

            # Find the first colon in the filename part
            first_colon = after_prefix.find(':')
            if first_colon == -1:
                return line

            # Extract filename and rest
            filename = after_prefix[:first_colon]
            rest_of_line = after_prefix[first_colon:]

            # Only colorize if it looks like a file
            if '.' in filename or '/' in filename or '\\' in filename:
                from termcolor import colored
                colored_filename = colored(filename, "magenta")
                return include_prefix + colored_filename + rest_of_line

            return line

        # Standard compiler message format: "filename.c:line:col: message"
        # Find the first colon (separates filename from line number)
        first_colon = line.find(':')
        if first_colon == -1:
            return line  # No filename pattern found

        # Check if this looks like a compiler message (has at least two colons)
        second_colon = line.find(':', first_colon + 1)
        if second_colon == -1:
            return line  # Not a compiler message format

        # Extract the filename part
        filename = line[:first_colon]
        rest_of_line = line[first_colon:]

        # Only colorize if it looks like a file (has an extension or path separator)
        if '.' in filename or '/' in filename or '\\' in filename:
            from termcolor import colored
            colored_filename = colored(filename, "magenta")
            return colored_filename + rest_of_line

        return line
    
    def __init__(self, project_data: ProjectData, mod_builder: ModBuilder, verbose: bool = False, no_warnings: bool = False):
        self.project_data = project_data
        self.mod_builder = mod_builder
        # Use tool_dir from mod_builder instead of getcwd()
        self.tool_dir = mod_builder.tool_dir
        self.verbose = verbose
        self.no_warnings = no_warnings

        # Callbacks for progress updates
        self.on_progress: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Auto-detected hooks
        self.auto_hooks: List[AutoHookInfo] = []

        # Warning and note collection
        self.compilation_warnings: List[Tuple[str, str]] = []  # List of (filename, warnings_text)
        self.compilation_notes: List[Tuple[str, str]] = []  # List of (filename, notes_text)

        # Initialize build cache for incremental compilation
        project_folder = self.project_data.GetProjectFolder()
        cache_path = os.path.join(project_folder, '.config', 'output', '.build_cache.json')
        self.build_cache = BuildCache(cache_path)
    
    def compile_project(self) -> CompilationResult:
        """Main compilation pipeline with auto-hook detection"""
        result = CompilationResult(success=False)
        
        # Clear previous warnings and notes
        self.compilation_warnings = []
        self.compilation_notes = []
        
        # NEW: Track which hooks to clean up after compilation
        hooks_to_cleanup = []
        
        # NEW: Clean up previous auto-hooks before starting
        self._cleanup_previous_multipatch_hooks()
        self._cleanup_previous_auto_hooks()
        
        try:
            # Step 0: Scan for auto-hooks in C/C++ files
            if self.verbose:
                self._log_progress("Scanning for auto-hooks...")
            self.auto_hooks = self._scan_for_auto_hooks()
            
            if self.auto_hooks:
                if self.verbose:
                    self._log_progress(f"  Found {len(self.auto_hooks)} auto-hook(s)")
                
                # Create hooks and ASM files
                if self.verbose:
                    self._log_progress("Creating auto-generated hooks...")
                validation_result = self._create_auto_hooks()
                if not validation_result.success:
                    return validation_result
            
            # NEW: Step 0.5: Process multi-patch ASM files
            if self.verbose:
                self._log_progress("Processing multi-patch ASM files...")
            multipatch_result = self._process_multipatches(hooks_to_cleanup)
            if not multipatch_result.success:
                return multipatch_result
            
            # Step 1: Validate environment
            if self.verbose:
                self._log_progress("Validating compilation environment...")
            if not self._validate_environment():
                result.message = "Compilation environment validation failed"
                return result
            
            # Step 2: Update linker script (now includes auto-generated hooks)
            if self.verbose:
                self._log_progress("Generating linker script...")
            if not self._update_linker_script():
                result.message = "Failed to generate linker script"
                return result
            
            # Step 3: Compile source files (with build name define)
            self._log_progress("Compiling...")
            compile_result = self._compile_sources()
            if not compile_result.success:
                result.message = compile_result.message
                result.details = compile_result.details
                return result
            
            result.object_files = compile_result.object_files
            
            # Step 4: Link object files
            self._log_progress("Linking...")
            link_result = self._link_objects(result.object_files)
            if not link_result.success:
                result.message = link_result.message
                result.details = link_result.details
                result.linker_overflow_errors = link_result.linker_overflow_errors  # Copy overflow errors
                return result
            
            # Step 5: Extract sections
            self._log_progress("Extracting...")
            extract_result = self._extract_sections()
            if not extract_result.success:
                result.message = extract_result.message
                result.details = extract_result.details
                return result
            
            # Step 6: Copy binary patches
            if self.verbose:
                self._log_progress("Copying binary patches...")
            patch_result = self._copy_binary_patches()
            if not patch_result.success:
                result.message = patch_result.message
                result.details = patch_result.details
                return result
            
            # Success!
            result.success = True
            #result.message = "Compilation successful!"
            if self.auto_hooks:
                result.message += f" ({len(self.auto_hooks)} auto-hook(s) created)"
            
            # Display all collected warnings AFTER compilation (unless suppressed)
            if self.compilation_warnings and not self.no_warnings:
                self._log_progress("")  # Blank line
                for filename, warnings_text in self.compilation_warnings:
                    self._display_warnings_block(filename, warnings_text)

            self._log_progress("\n " + result.message)
            
        except Exception as e:
            result.message = f"Unexpected error: {str(e)}"
            self._log_error(result.message)
            import traceback
            self._log_error(traceback.format_exc())

        return result

    def _copy_binary_patches(self) -> CompilationResult:
        """Copy binary patch files to bin_files directory"""
        result = CompilationResult(success=True)
        
        project_folder = self.project_data.GetProjectFolder()
        bin_output_dir = os.path.join(project_folder, '.config', 'output', 'bin_files')
        
        binary_patches = self.project_data.GetCurrentBuildVersion().GetEnabledBinaryPatches()
        
        if not binary_patches:
            return result  # No patches to copy
        
        if self.verbose:
            self._log_progress(f"  Found {len(binary_patches)} binary patch(es)")
        
        copied_count = 0
        
        for patch in binary_patches:
            patch_name = patch.GetName()
            
            # Get the binary files for this patch
            binary_files = patch.GetCodeFilesPaths()
            
            if not binary_files:
                if self.verbose:
                    self._log_progress(f"    Warning: No binary files for patch '{patch_name}'")
                continue
            
            # Use the first binary file (patches should only have one file)
            source_file = binary_files[0]
            
            if not os.path.exists(source_file):
                if self.verbose:
                    self._log_progress(f"    Warning: Binary file not found: {source_file}")
                continue
            
            # Copy to bin_files with patch name
            dest_file = os.path.join(bin_output_dir, f"{patch_name}.bin")
            
            try:
                import shutil
                shutil.copyfile(source_file, dest_file)
                if self.verbose:
                    self._log_progress(f"    Copied: {os.path.basename(source_file)} → {patch_name}.bin")
                copied_count += 1
            except Exception as e:
                self._log_error(f"    Failed to copy {patch_name}: {str(e)}")
                result.success = False
                result.message = f"Failed to copy binary patch: {patch_name}"
                return result
        
        if self.verbose:
            self._log_progress(f"  Copied {copied_count} binary patch(es)")
        return result
    
    # ==================== AUTO-HOOK DETECTION ====================
    
    def _scan_for_auto_hooks(self) -> List[AutoHookInfo]:
        """
        Scan all C/C++ source files for auto-hook macros.
        
        Supported formats:
        - J_HOOK(0x80123456)                          // assumes main executable, auto finds file address
        - J_HOOK(0x80123456, "filename.bin")          // specific file, auto finds file address
        - J_HOOK(0x80123456, "filename.bin", 0x4321)  // specific file, explicit file addrress
        - JAL_HOOK(...), B_HOOK(...), BL_HOOK(...)    // same patterns
        """
        auto_hooks = []
        
        # Get all C/C++ files from codecaves
        source_files = []
        for cave in self.project_data.GetCurrentBuildVersion().GetEnabledCodeCaves():
            source_files.extend(cave.GetCodeFilesPaths())
        
        # NEW: Enhanced regex pattern to match all three formats
        # Matches: HOOK_TYPE(address) or HOOK_TYPE(address, "file") or HOOK_TYPE(address, "file", fileaddr)
        hook_pattern = re.compile(
            r'(J_HOOK|JAL_HOOK|B_HOOK|BL_HOOK)\s*\(\s*'
            r'(0x[0-9A-Fa-f]+)'  # Memory address
            r'(?:\s*,\s*"([^"]+)")?'  # Optional file parameter
            r'(?:\s*,\s*(0x[0-9A-Fa-f]+))?\s*\)'  # NEW: Optional explicit file address
        )
        
        for source_file in source_files:
            if not os.path.exists(source_file):
                continue
            
            try:
                with open(source_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    # Skip comments
                    if line.strip().startswith('//') or line.strip().startswith('/*'):
                        continue
                    
                    # Find hook macro
                    match = hook_pattern.search(line)
                    if not match:
                        continue
                    
                    hook_type = match.group(1)
                    memory_address = match.group(2)
                    target_file = match.group(3)  # Optional
                    explicit_file_addr = match.group(4)  # NEW: Optional explicit file address
                    
                    # Find the function name on the next non-empty line
                    function_name = self._find_function_name(lines, line_num)
                    
                    if not function_name:
                        self._log_error(f"  Warning: Could not find function after {hook_type} at {source_file}:{line_num}")
                        continue
                    
                    auto_hook = AutoHookInfo(
                        hook_type=hook_type,
                        memory_address=memory_address,
                        function_name=function_name,
                        source_file=source_file,
                        line_number=line_num,
                        target_file=target_file,
                        explicit_file_addr=explicit_file_addr  # NEW
                    )
                    
                    auto_hooks.append(auto_hook)
                    
                    # Enhanced verbose output
                    if self.verbose:
                        msg = f"    {hook_type} @ {memory_address} → {function_name}()"
                        if target_file:
                            msg += f" [file: {target_file}]"
                        if explicit_file_addr:
                            msg += f" [explicit addr: {explicit_file_addr}]"
                        self._log_progress(msg)
                    
            except Exception as e:
                self._log_error(f"  Error scanning {source_file}: {str(e)}")
                continue
        
        return auto_hooks
    
    def _find_function_name(self, lines: List[str], start_line: int) -> Optional[str]:
        """
        Find the function name after a hook macro.
        Looks for pattern: type function_name(
        """
        # Function pattern: matches "int MyFunc(" or "void MyFunc("
        func_pattern = re.compile(r'\w+\s+(\w+)\s*\(')
        
        # Search next 5 lines for function declaration
        for i in range(start_line, min(start_line + 5, len(lines))):
            line = lines[i].strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('//') or line.startswith('/*'):
                continue
            
            match = func_pattern.search(line)
            if match:
                return match.group(1)
        
        return None
    
    def _create_auto_hooks(self) -> CompilationResult:
        result = CompilationResult(success=True)
        
        project_folder = self.project_data.GetProjectFolder()
        current_build = self.project_data.GetCurrentBuildVersion()
        
        # Create auto-hooks directory
        auto_hooks_dir = os.path.join(project_folder, "asm", ".auto_hooks")
        os.makedirs(auto_hooks_dir, exist_ok=True)
        
        # Get main executable
        main_exe = current_build.GetMainExecutable()
        if not main_exe:
            result.success = False
            result.message = "No main executable set - cannot create auto-hooks"
            return result
        
        # Track which hooks need manual setup
        missing_offsets = []
        
        for i, hook_info in enumerate(self.auto_hooks, 1):
            # Determine target file
            target_file = hook_info.target_file if hook_info.target_file else main_exe
            
            # Create Hook object
            hook_name = f"AutoHook_{hook_info.function_name}_{i}"
            hook = Hook()
            hook.SetName(hook_name)
            hook.SetTemporary(True)
            
            # Set memory address (strip 0x prefix for internal storage)
            mem_addr = hook_info.memory_address.replace("0x", "").replace("0X", "")
            hook.SetMemoryAddress(mem_addr)
            
            # Set injection file
            hook.SetInjectionFile(target_file)
            
            # NEW: Three-tier priority for file address
            # 1. Explicit file address from J_HOOK(addr, file, fileaddr) (highest priority)
            # 2. Section map (automatic)
            # 3. Single offset (fallback)
            
            if hook_info.explicit_file_addr:
                # Priority 1: User provided explicit file address
                file_addr_hex = hook_info.explicit_file_addr.replace("0x", "").replace("0X", "")
                hook.SetInjectionFileAddress(file_addr_hex)
                hook.SetAutoCalculateInjectionFileAddress(False)
                
                if self.verbose:
                    self._log_progress(f"    {hook_name}: file addr = {hook_info.explicit_file_addr} (explicit)")
            else:
                # Priority 2 & 3: Try section map, then fall back to single offset
                try:
                    mem_addr_int = int(mem_addr, 16)
                    
                    # Remove 0x80 prefix if present
                    if mem_addr.startswith("80"):
                        mem_addr_int = int(mem_addr[2:], 16)
                    
                    # Try section map calculation
                    file_offset = current_build.GetFileOffsetForAddress(target_file, mem_addr_int)
                    
                    if file_offset is not None:
                        # Priority 2: Success with section map!
                        hook.SetInjectionFileAddress(f"{file_offset:X}")
                        hook.SetAutoCalculateInjectionFileAddress(True)
                        
                        if self.verbose:
                            self._log_progress(f"    {hook_name}: file offset = 0x{file_offset:X} (section map)")
                    else:
                        # Priority 3: Fallback to old offset method
                        offset_str = current_build.GetInjectionFileOffset(target_file)
                        
                        if offset_str and offset_str != "":
                            offset_int = int(offset_str, 16)
                            file_addr = mem_addr_int - offset_int
                            
                            hook.SetInjectionFileAddress(f"{file_addr:X}")
                            hook.SetAutoCalculateInjectionFileAddress(True)
                            
                            if self.verbose:
                                self._log_progress(f"    {hook_name}: file offset = 0x{file_addr:X} (single offset)")
                        else:
                            # No offset available at all
                            missing_offsets.append((hook_info, target_file))
                            hook.SetAutoCalculateInjectionFileAddress(False)
                            
                            if self.verbose:
                                self._log_progress(f"    {hook_name}: NO OFFSET AVAILABLE")
                
                except ValueError as e:
                    self._log_error(f"    Warning: Invalid address format for {hook_name}: {e}")
                    missing_offsets.append((hook_info, target_file))
                    hook.SetAutoCalculateInjectionFileAddress(False)
            
            # Create ASM file
            asm_file_path = os.path.join(auto_hooks_dir, f"{hook_name}.s")
            
            platform = current_build.GetPlatform()
            asm_template = self._get_asm_template(hook_info.hook_type, hook_info.function_name, platform)
            
            with open(asm_file_path, 'w') as f:
                f.write(f"# Auto-generated hook for {hook_info.function_name}()\n")
                f.write(f"# Source: {os.path.basename(hook_info.source_file)}:{hook_info.line_number}\n")
                f.write(f"# Type: {hook_info.hook_type}\n")
                f.write(f"# Memory: {hook_info.memory_address}\n")
                if hook_info.target_file:
                    f.write(f"# Target file: {hook_info.target_file}\n")
                if hook_info.explicit_file_addr:
                    f.write(f"# Explicit file address: {hook_info.explicit_file_addr}\n")
                f.write("\n")
                f.write(asm_template)
            
            # Add ASM file to hook
            hook.AddCodeFile(asm_file_path)
            
            # Add hook to project
            current_build.AddHook(hook)
            
            if self.verbose:
                self._log_progress(f"   Created: {hook_name} @ {hook_info.memory_address}")
        
        # Warn about missing file offsets (only for hooks without explicit addresses)
        if missing_offsets:
            self._log_error("\n ⚠ WARNING: Some auto-hooks need manual file addresses:")
            for hook_info, target_file in missing_offsets:
                self._log_error(f"  • {hook_info.function_name}() → {target_file}")
                self._log_error(f"    - No section map found")
                self._log_error(f"    - No file offset set")
            self._log_error("\nFix this by:")
            self._log_error("  1. Provide explicit file address: J_HOOK(0x80123456, \"file.bin\", 0x1234), OR")
            self._log_error("  2. Set file offset in 'Game Files To Inject Into' tab, OR")
            self._log_error("  3. Build section map for the file (if supported)")
            self._log_error("Then recompile.")
        
        return result
    
    def _get_asm_template(self, hook_type: str, function_name: str, platform: str) -> str:
        """Get the appropriate ASM template for the hook type and platform"""
        template = self.HOOK_TEMPLATES.get(hook_type, "")

        # Adjust for platform
        if platform in ["Gamecube", "Wii"]:
            # PowerPC doesn't need .set noreorder
            template = template.replace(".set noreorder\n", "")

            # PowerPC uses different jump instructions
            if hook_type == "J_HOOK":
                template = f"b {function_name}\n"
            elif hook_type == "JAL_HOOK":
                template = f"bl {function_name}\n"
        elif platform == "PS2":
            if hook_type == "J_HOOK":
                template = template.replace("\nnop\n", "\n")

        return template.format(function_name=function_name)
    
    # ==================== COMPILATION (Enhanced) ====================
    
    def _compile_sources(self) -> CompilationResult:
        """Compile all C/C++/ASM source files with incremental build support"""
        result = CompilationResult(success=False)

        project_dir = os.path.abspath(self.project_data.GetProjectFolder())
        current_build = self.project_data.GetCurrentBuildVersion()
        platform = current_build.GetPlatform()
        obj_output_dir = os.path.abspath(os.path.join(project_dir, ".config", "output", "object_files"))

        if not os.path.exists(obj_output_dir):
            self._log_error(f"Object output directory doesn't exist: {obj_output_dir}")
            result.message = "Object output directory missing"
            return result

        # Collect all source files (including auto-hooks)
        all_source_files = self._collect_source_files()

        if not all_source_files:
            result.message = "No source files found to compile"
            self._log_error(result.message)
            return result

        # Get build configuration for incremental compilation
        build_name = current_build.GetBuildName()
        build_index = self.project_data.GetBuildVersionIndex()
        user_compiler_flags = current_build.GetCompilerFlags()

        # Construct full compiler flags string for comparison
        # Note: -fno-exceptions and -fno-rtti are added per-file for C++ files only
        compiler_flags_str = f"-g -ffreestanding -fno-builtin {user_compiler_flags}"

        # Check if build configuration changed (forces full rebuild)
        force_rebuild = self.build_cache.build_config_changed(
            compiler_flags_str,
            platform,
            build_name,
            build_index
        )

        if force_rebuild:
            if self.verbose:
                self._log_progress("  Build configuration changed - rebuilding all files")
            # Update build config in cache
            self.build_cache.update_build_config(compiler_flags_str, platform, build_name, build_index)

        # Check if any header file changed (forces full rebuild)
        include_dir = os.path.join(project_dir, "include")
        if self.build_cache.include_dir_changed(include_dir):
            force_rebuild = True
            if self.verbose:
                self._log_progress("  Header files changed - rebuilding all files")

        if self.verbose:
            self._log_progress(f"  Found {len(all_source_files)} source file(s) to compile")

        compiled_obj_files = []
        files_compiled = 0
        files_skipped = 0

        for src_file_path in all_source_files:
            src_file_path = os.path.abspath(src_file_path)
            src_filename = os.path.basename(src_file_path)
            obj_filename = os.path.splitext(src_filename)[0] + '.o'
            obj_file_path = os.path.join(obj_output_dir, obj_filename)

            if not os.path.exists(src_file_path):
                result.message = f"Source file not found: {src_file_path}"
                self._log_error(result.message)
                return result

            # Check if we can skip compilation (incremental build)
            should_compile = force_rebuild
            reason = ""

            if not should_compile:
                # Check if object file exists
                if not os.path.exists(obj_file_path):
                    should_compile = True
                    reason = "object file doesn't exist"
                else:
                    # Check timestamps
                    src_mtime = os.path.getmtime(src_file_path)
                    obj_mtime = os.path.getmtime(obj_file_path)

                    if src_mtime > obj_mtime:
                        should_compile = True
                        reason = "source file newer than object file"

            if should_compile:
                # Compile the file
                compile_reason = f" ({reason})" if reason and self.verbose else ""
                self._log_progress(f"  {src_filename}{compile_reason}")

                compile_result = self._compile_single_file(
                    src_file_path,
                    obj_output_dir,
                    platform
                )

                if not compile_result.success:
                    result.message = f"Failed to compile {src_filename}"
                    result.details = compile_result.details
                    return result

                # Update cache with new file info
                obj_mtime = os.path.getmtime(obj_file_path) if os.path.exists(obj_file_path) else 0.0
                src_mtime = os.path.getmtime(src_file_path)
                self.build_cache.set_file_info(src_file_path, src_mtime, obj_filename, obj_mtime)

                compiled_obj_files.append(compile_result.message)
                files_compiled += 1
            else:
                # Skip compilation, reuse existing .o file
                if self.verbose:
                    self._log_progress(f"  {src_filename} (up-to-date)")
                compiled_obj_files.append(obj_filename)
                files_skipped += 1

        # Save build cache
        self.build_cache.save()

        # Log compilation statistics
        if files_skipped > 0:
            self._log_progress(f"  Compiled: {files_compiled} file(s), Skipped: {files_skipped} file(s) (up-to-date)")

        result.success = True
        result.object_files = compiled_obj_files
        result.message = f"Compiled {len(compiled_obj_files)} file(s)"
        return result
    
    def _compile_single_file(self, src_file_path: str, output_dir: str, platform: str) -> CompilationResult:
        """Compile a single file with build name as preprocessor define"""
        result = CompilationResult(success=False)
        
        src_file_path = os.path.abspath(src_file_path)
        output_dir = os.path.abspath(output_dir)
        
        src_filename = os.path.basename(src_file_path)
        obj_filename = os.path.splitext(src_filename)[0] + ".o"
        output_obj_path = os.path.abspath(os.path.join(output_dir, obj_filename))
        
        compiler_path = self._get_compiler_path(platform)
        project_dir = os.path.abspath(self.project_data.GetProjectFolder())
        include_dir = os.path.abspath(os.path.join(project_dir, "include"))
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Get build name for preprocessor define
        build_name = self.project_data.GetCurrentBuildVersion().GetBuildName()

        # Replace spaces/special chars with underscores
        safe_build_name = re.sub(r'[^A-Za-z0-9_]', '_', build_name).upper()

        safe_platform_name = re.sub(r'[^A-Za-z0-9_]', '_', platform).upper()

        # Get build index
        build_index = self.project_data.GetBuildVersionIndex()

        # Get compiler flags (debug mode or user-defined)
        current_build = self.project_data.GetCurrentBuildVersion()
        if current_build.IsDebugMode():
            # Debug mode: use -O0 for accurate debugging
            user_compiler_flags = "-O0"
        else:
            # Normal mode: use user-defined flags
            user_compiler_flags = current_build.GetCompilerFlags()
        user_compiler_flags_list = user_compiler_flags.split()

        # Check if this is a C++ file (vs C file)
        cpp_extensions = ('.cpp', '.cc', '.cxx', '.c++', '.C', '.CPP', '.CXX', '.CC')
        is_cpp_file = src_file_path.lower().endswith(cpp_extensions) or src_file_path.endswith('.C')

        # Compilation command
        compile_cmd = [
            compiler_path,
            "-c",
            "-G0",
            "-I", include_dir,
            "-g",
            "-ffreestanding",
            "-fno-builtin"
        ]

        # Add C++-specific flags only for C++ files
        if is_cpp_file:
            compile_cmd.extend(["-fno-exceptions", "-fno-rtti"])

        # Used to have to exclude this for ps2, but I updated it to GCC 15
        # So it's ok now!
        compile_cmd.append("-fdiagnostics-color=always")
        

        # Preprocessor defines
        compile_cmd.extend([
            f"-D{safe_build_name}",  # Add build name define (-DNTSC_U)
            f"-DBUILD_NAME={safe_build_name}",  # Also provide as BUILD_NAME 
            f"-DBUILD={build_index}",  # Add numeric build index (-DBUILD=0) (This is mainly here to support projects converted from the psx-modding-toolchain)
            f"-D{safe_platform_name}",  # Add platform define (-DPS2, -DGAMECUBE)
            f"-DPLATFORM={safe_platform_name}",  # Also provide as PLATFORM
        ])
        
        # The src file, and output obj file
        compile_cmd.extend([            
            src_file_path,
            "-o", 
            output_obj_path
            ])
        
        # Add user flags (from the input box in the build tab)
        for flag in user_compiler_flags_list:
            compile_cmd.append(flag)

        if self.verbose:
            self._log_progress(f"    Build Version #define: {safe_build_name}, BUILD={build_index}")
            self._log_progress(f"    Platform #define: {safe_platform_name}, PLATFORM={safe_platform_name}")
        
        # Run GCC with the compiler command
        try:
            compiler_dir = os.path.dirname(compiler_path)
            env = os.environ.copy()
            env["PATH"] = compiler_dir + os.pathsep + env.get("PATH", "")

            process = subprocess.run(
                compile_cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_dir,
                env=env,
            )
            
            # Only log stdout if it exists and is not empty (verbose mode)
            if self.verbose and process.stdout and process.stdout.strip():
                self._log_progress("\n    ╔══════════════════════════════════════════════════════════╗")
                self._log_progress("    ║              COMPILER OUTPUT (stdout)                    ║")
                self._log_progress("    ╚══════════════════════════════════════════════════════════╝")
                for line in process.stdout.strip().split('\n'):
                    if line.strip():
                        self._log_progress(f"    {line}")
            
            # Handle stderr (errors, warnings, and notes)
            if process.stderr and process.stderr.strip():
                stderr_lines = process.stderr.strip().split('\n')
                has_errors = False
                has_warnings = False
                has_notes = False

                # Scan for errors/warnings/notes
                for line in stderr_lines:
                    line_lower = line.lower()
                    # Check for various error formats (old and new GCC)
                    if 'error:' in line_lower or 'error ' in line_lower or ': error' in line_lower:
                        has_errors = True
                    elif 'warning:' in line_lower or 'warning ' in line_lower or ': warning' in line_lower:
                        has_warnings = True
                    elif 'note:' in line_lower or ': note' in line_lower:
                        has_notes = True
                
                # If errors, display immediately
                if has_errors:
                    print("")
                    print_error("╔══════════════════════════════════════════════════════════╗")
                    print_error("║                  COMPILATION ERRORS                      ║")
                    print_error("╚══════════════════════════════════════════════════════════╝")

                    # Display all error lines WITH notes (keep context together)
                    for line in stderr_lines:
                        if line.strip():
                            cleaned_line = self._strip_project_paths(line)
                            colorized_line = self._colorize_filename_in_line(cleaned_line)
                            print(colorized_line)  # Use normal print to preserve GCC colors

                    print_error("════════════════════════════════════════════════════════════")
                    print("")

                    # Also send errors to GUI callback if available
                    if self.on_error:
                        self.on_error("")
                        self.on_error("╔══════════════════════════════════════════════════════════╗")
                        self.on_error("║                  COMPILATION ERRORS                      ║")
                        self.on_error("╚══════════════════════════════════════════════════════════╝")
                        for line in stderr_lines:
                            if line.strip():
                                cleaned_line = self._strip_project_paths(line)
                                clean_message = self._strip_ansi_codes(cleaned_line)
                                self.on_error(clean_message)
                        self.on_error("════════════════════════════════════════════════════════════")
                        self.on_error("")

                # If warnings or notes (and no errors), collect them for later display (unless suppressed)
                if (has_warnings or has_notes) and not has_errors and not self.no_warnings:
                    # Strip project paths from warnings/notes before storing
                    cleaned_stderr = self._strip_project_paths(process.stderr)
                    self.compilation_warnings.append((src_filename, cleaned_stderr))
                    
                # If verbose mode and neither errors nor warnings nor notes, show output
                elif self.verbose:
                    self._log_progress("")
                    self._log_progress("╔══════════════════════════════════════════════════════════╗")
                    self._log_progress("║              COMPILER OUTPUT (stderr)                    ║")
                    self._log_progress("╚══════════════════════════════════════════════════════════╝")
                    for line in stderr_lines:
                        if line.strip():
                            cleaned_line = self._strip_project_paths(line)
                            colorized_line = self._colorize_filename_in_line(cleaned_line)
                            print(colorized_line)  # Use normal print to preserve GCC colors
            
            # Return failure if compilation failed
            if process.returncode != 0:
                # If we have stderr but didn't detect it as errors, log it now (for old compilers)
                if process.stderr and process.stderr.strip() and not has_errors:
                    print("")
                    print_error("╔══════════════════════════════════════════════════════════╗")
                    print_error("║                  COMPILATION FAILED                      ║")
                    print_error("╚══════════════════════════════════════════════════════════╝")
                    for line in process.stderr.strip().split('\n'):
                        if line.strip():
                            cleaned_line = self._strip_project_paths(line)
                            colorized_line = self._colorize_filename_in_line(cleaned_line)
                            print(colorized_line)  # Use normal print to preserve GCC colors
                    print_error("════════════════════════════════════════════════════════════")
                    print("")

                    # Also send to GUI callback if available
                    if self.on_progress:
                        self.on_progress("")
                        self.on_progress("╔══════════════════════════════════════════════════════════╗")
                        self.on_progress("║                  COMPILATION FAILED                      ║")
                        self.on_progress("╚══════════════════════════════════════════════════════════╝")
                        for line in process.stderr.strip().split('\n'):
                            if line.strip():
                                cleaned_line = self._strip_project_paths(line)
                                clean_message = self._strip_ansi_codes(cleaned_line)
                                self.on_progress(clean_message)
                        self.on_progress("════════════════════════════════════════════════════════════")
                        self.on_progress("")

                # Store details - if we already displayed formatted errors, don't duplicate them
                if has_errors:
                    # We already displayed errors in formatted block, just note that
                    result.details = ""
                else:
                    # Store cleaned stderr for display
                    result.details = self._strip_project_paths(process.stderr)
                return result
            
            if not os.path.exists(output_obj_path):
                result.details = f"Object file was not created: {output_obj_path}"
                return result
            
            result.success = True
            result.message = obj_filename
            if self.verbose:
                self._log_progress(f"     Created: {obj_filename}")
            
        except FileNotFoundError:
            result.details = f"Compiler not found: {compiler_path}"
        except Exception as e:
            result.details = f"Compilation error: {str(e)}"
        
        return result
    
    
    def _validate_environment(self) -> bool:
        """Check if all required tools are available. They should be because they're bundled, but I might switch to a 'download tools' option in the gui eventually"""
        platform = self.project_data.GetCurrentBuildVersion().GetPlatform()
        
        compiler_path = self._get_compiler_path(platform)
        if not os.path.exists(compiler_path):
            self._log_error(f"Compiler not found: {compiler_path}")
            return False
        
        objcopy_path = self._get_objcopy_path(platform)
        if not os.path.exists(objcopy_path):
            self._log_error(f"Objcopy not found: {objcopy_path}")
            return False
        
        project_dir = self.project_data.GetProjectFolder()
        if not os.path.exists(project_dir):
            self._log_error(f"Project folder not found: {project_dir}")
            return False
        
        return True
    
    def _get_compiler_path(self, platform: str) -> str:
        relative_path = self.mod_builder.compilers.get(platform, "")
        return os.path.join(self.tool_dir, relative_path)
    
    def _get_objcopy_path(self, platform: str) -> str:
        relative_path = self.mod_builder.objcopy_exes.get(platform, "")
        return os.path.join(self.tool_dir, relative_path)
    
    def _collect_source_files(self) -> List[str]:
        source_files = []
        
        # From code caves
        for cave in self.project_data.GetCurrentBuildVersion().GetEnabledCodeCaves():
            source_files.extend(cave.GetCodeFilesPaths())
        
        # From hooks
        for hook in self.project_data.GetCurrentBuildVersion().GetEnabledHooks():
            source_files.extend(hook.GetCodeFilesPaths())

        return source_files

    def clean_build_cache(self):
        if self.verbose:
            self._log_progress("Clearing build cache...")
        self.build_cache.clear()

    def _update_linker_script(self) -> bool:
        try:
            project_folder = self.project_data.GetProjectFolder()
            build_name = self.project_data.GetCurrentBuildVersion().GetBuildName()
            current_build = self.project_data.GetCurrentBuildVersion()
            
            code_caves = self.project_data.GetCurrentBuildVersion().GetEnabledCodeCaves()
            hooks = self.project_data.GetCurrentBuildVersion().GetEnabledHooks()
            
            linker_script_path = os.path.join(project_folder, ".config", "linker_script.ld")
            obj_dir_rel_path = ".config/output/object_files"
            
            symbols_filename = current_build.GetSymbolsFile()

            with open(linker_script_path, "w") as script_file:
                script_file.write(f"INPUT(symbols/{symbols_filename})\n")
                script_file.write("MEMORY\n{\n")
                script_file.write("    /* RAM locations for injected code */\n")
                
                for cave in code_caves:
                    size = cave.GetSize() if cave.GetSize() else '100000'
                    if not size or size == '0' or size == '0x0' or size.lower() == 'none':
                        size = '100000'  # 1MB default
                
                    script_file.write(
                        f"    {cave.GetName()} : ORIGIN = 0x{cave.GetMemoryAddress()}, "
                        f"LENGTH = 0x{size}\n"
                    )
                
                for hook in hooks:
                    script_file.write(
                        f"    {hook.GetName()} : ORIGIN = 0x{hook.GetMemoryAddress()}, "
                        f"LENGTH = 0x100000\n"
                    )
                
                script_file.write("}\n\n")
                script_file.write("SECTIONS\n{\n")
                
                # Hooks
                for hook in hooks:
                    script_file.write(f"    /* Hook: {hook.GetName()} */\n")
                    script_file.write(f"    .{hook.GetName()} :\n    {{\n")
                    
                    for asm_file in hook.GetCodeFilesNames():
                        o_file_name = os.path.splitext(asm_file)[0] + ".o"
                        o_file_rel_path = f"{obj_dir_rel_path}/{o_file_name}"

                        script_file.write(
                            f"        {o_file_rel_path}(.text)\n"
                            f"        {o_file_rel_path}(.rodata)\n"
                            f"        {o_file_rel_path}(.rodata*)\n"
                            f"        {o_file_rel_path}(.data)\n"
                            f"        {o_file_rel_path}(.bss)\n"
                        )
                    
                    script_file.write(f"    }} > {hook.GetName()}\n\n")
                
                # Code caves
                for i, cave in enumerate(code_caves):
                    script_file.write(f"    /* Codecave: {cave.GetName()} */\n")
                    script_file.write(f"    .{cave.GetName()} :\n    {{\n")
                    
                    for c_file in cave.GetCodeFilesNames():
                        o_file_name = os.path.splitext(c_file)[0] + ".o"
                        o_file_rel_path = f"{obj_dir_rel_path}/{o_file_name}"
                        
                        script_file.write(
                            f"        {o_file_rel_path}(.text)\n"
                            f"        {o_file_rel_path}(.rodata)\n"
                            f"        {o_file_rel_path}(.rodata*)\n"
                            f"        {o_file_rel_path}(.data)\n"
                            f"        {o_file_rel_path}(.bss)\n"
                            f"        {o_file_rel_path}(.sdata)\n"
                            f"        {o_file_rel_path}(.sbss)\n"
                            f"        {o_file_rel_path}(.scommon)\n"
                        )
                    
                    if i == len(code_caves) - 1:
                        script_file.write("        *(.text)\n")
                        script_file.write("        *(.branch_lt)\n")
                    
                    script_file.write(f"    }} > {cave.GetName()}\n\n")
                
                script_file.write(
                    "    /DISCARD/ :\n"
                    "    {\n"
                    "        *(.comment)\n"
                    "        *(.pdr)\n"
                    "        *(.mdebug)\n"
                    "        *(.reginfo)\n"
                    "        *(.MIPS.abiflags)\n"
                    "        *(.eh_frame)\n"
                    "        *(.gnu.attributes)\n"
                    "    }\n"
                    "}\n"
                )
            
            return True
            
        except Exception as e:
            self._log_error(f"Linker script generation failed: {str(e)}")
            return False
    
    def _link_objects(self, obj_files: List[str]) -> CompilationResult:
        """Link .o files into ELF"""
        result = CompilationResult(success=False)
        
        project_dir = os.path.abspath(self.project_data.GetProjectFolder())
        platform = self.project_data.GetCurrentBuildVersion().GetPlatform()
        obj_output_dir = os.path.abspath(os.path.join(project_dir, ".config", "output", "object_files"))
        
        linker_script = os.path.abspath(os.path.join(project_dir, ".config", "linker_script.ld"))
        output_elf = os.path.abspath(os.path.join(obj_output_dir, "MyMod.elf"))
        output_map = os.path.abspath(os.path.join(obj_output_dir, "MyMod.map"))
        
        if not os.path.exists(linker_script):
            result.details = f"Linker script not found: {linker_script}"
            self._log_error(result.details)
            return result
        
        compiler_path = self._get_compiler_path(platform)
        
        def to_posix_path(path):
            return path.replace('\\', '/')
        
        try:
            linker_script_posix = to_posix_path(linker_script)
            output_elf_posix = to_posix_path(output_elf)
            output_map_posix = to_posix_path(output_map)

            link_cmd = [
                compiler_path,
                "-T", linker_script_posix,
                "-o", output_elf_posix,
                f"-Wl,-Map={output_map_posix}",
                "-nostdlib",
                "-nostartfiles",
            ]
            
            process = subprocess.run(
                link_cmd,
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_dir,
                timeout=30
            )
            
            if self.verbose and process.stdout:
                self._log_progress(f"  Linker stdout: {process.stdout}")
            
            if process.returncode != 0:
                result.details = self._parse_linker_errors(process.stderr, result)
                self._log_error(f"Linker failed: {result.details}")

                # Display overflow errors if any were detected
                if result.linker_overflow_errors:
                    for overflow_info in result.linker_overflow_errors:
                        self._log_error(f"  {overflow_info['section']}: overflowed by {overflow_info['overflow_bytes']}")

                return result
            
            if not os.path.exists(output_elf):
                result.details = f"ELF file was not created: {output_elf}"
                self._log_error(result.details)
                return result
            
            if self.verbose:
                self._log_progress(f"  Created: MyMod.elf")
            
            if os.path.exists(output_map):
                self._move_map_file(output_map, project_dir)
            
            result.success = True
            result.message = "Linking successful"
            
            if result.success:
                # Check for size overflows
                from services.size_analyzer_service import SizeAnalyzerService
                analyzer = SizeAnalyzerService(self.project_data)
                results = analyzer.analyze_all()
                
                overflow_count = sum(1 for r in results if r.is_overflow)
                if overflow_count > 0:
                    self._log_error(f"\nWARNING: {overflow_count} section(s) exceed allocated size!")
                    for r in results:
                        if r.is_overflow:
                            overflow = r.used_bytes - r.allocated_bytes
                            self._log_error(f"  • {r.name}: OVERFLOW by 0x{overflow:X} bytes")
            
        except subprocess.TimeoutExpired:
            result.details = "Linker timed out after 30 seconds"
            self._log_error(result.details)
        except FileNotFoundError:
            result.details = f"Compiler/linker not found: {compiler_path}"
            self._log_error(result.details)
        except Exception as e:
            result.details = f"Linking error: {str(e)}"
            self._log_error(result.details)
            import traceback
            self._log_error(traceback.format_exc())
        
        return result
    
    def _parse_linker_errors(self, stderr: str, result: CompilationResult = None) -> str:
        verbose_print(stderr)

        # Strip project paths from stderr to make easier to read
        stderr_cleaned = self._strip_project_paths(stderr)

        if "overlaps section" in stderr:
            return "Sections overlap. Check that codecaves and hooks don't share addresses."

        if "will not fit in region" in stderr:
            lines = stderr.split('\n')
            overflow_lines = []

            for line in lines:
                if "overflowed by" in line:
                    # Strip paths from overflow line
                    cleaned_line = self._strip_project_paths(line.strip())
                    overflow_lines.append(cleaned_line)

                    # Extract section name and overflow amount
                    if result is not None:
                        # Format: "region `.MyCodecave' overflowed by 0x123 bytes"
                        try:
                            # Extract section name
                            if "`" in line:
                                section_start = line.find("`") + 1
                                section_end = line.find("'", section_start)
                                section_name = line[section_start:section_end]
                            else:
                                section_match = line.split("region")[1].split("overflowed")[0].strip()
                                section_name = section_match.strip("'\" ")

                            # Extract overflow bytes
                            overflow_start = line.find("overflowed by") + len("overflowed by")
                            overflow_text = line[overflow_start:].strip()
                            overflow_bytes_str = overflow_text.split()[0]  # Get first token (hex or decimal)

                            # Convert to hex format
                            try:
                                overflow_int = int(overflow_bytes_str, 0)
                                overflow_bytes_hex = f"0x{overflow_int:X}"
                            except ValueError:
                                overflow_bytes_hex = overflow_bytes_str

                            result.linker_overflow_errors.append({
                                'section': section_name,
                                'overflow_bytes': overflow_bytes_hex
                            })
                        except Exception:
                            pass

            if overflow_lines:
                return "\n".join(overflow_lines)
            return "Section overflow. Code is too large for allocated region."

        return stderr_cleaned
    
    def _move_map_file(self, map_path: str, project_dir: str):
        import shutil
        memory_map_dir = os.path.join(project_dir, ".config", "memory_map")
        os.makedirs(memory_map_dir, exist_ok=True)
        
        try:
            dest = os.path.join(memory_map_dir, "MyMod.map")
            shutil.move(map_path, dest)
            if self.verbose:
                self._log_progress(f"  Map file saved to memory_map/")
        except Exception as e:
            self._log_error(f"Failed to move map file: {str(e)}")
    
    def _extract_sections(self) -> CompilationResult:
        """Extract linker sections from ELF to binary files"""
        result = CompilationResult(success=True)
        
        project_dir = os.path.abspath(self.project_data.GetProjectFolder())
        platform = self.project_data.GetCurrentBuildVersion().GetPlatform()
        
        obj_output_dir = os.path.abspath(os.path.join(project_dir, ".config", "output", "object_files"))
        bin_output_dir = os.path.abspath(os.path.join(project_dir, ".config", "output", "bin_files"))
        input_elf = os.path.abspath(os.path.join(obj_output_dir, "MyMod.elf"))
        
        objcopy_path = self._get_objcopy_path(platform)
        
        os.makedirs(bin_output_dir, exist_ok=True)
        
        if not os.path.exists(input_elf):
            result.success = False
            result.details = f"Input ELF file not found: {input_elf}"
            self._log_error(result.details)
            return result
        
        sections_to_extract = []
        for hook in self.project_data.GetCurrentBuildVersion().GetEnabledHooks():
            sections_to_extract.append(hook.GetName())
        for cave in self.project_data.GetCurrentBuildVersion().GetEnabledCodeCaves():
            sections_to_extract.append(cave.GetName())
        
        if not sections_to_extract:
            if self.verbose:
                self._log_progress("  No sections (hooks or codecaves) defined to extract.")
            return result
        
        if self.verbose:
            self._log_progress(f"  Extracting {len(sections_to_extract)} section(s)...")

        try:
            for section_name in sections_to_extract:
                section_flag = f".{section_name}"
                output_bin_name = f"{section_name}.bin"
                output_bin_path = os.path.abspath(os.path.join(bin_output_dir, output_bin_name))
                
                if self.verbose:
                    self._log_progress(f"    Extracting {section_flag} to {output_bin_name}...")
                
                extract_cmd = [
                    objcopy_path,
                    "-O", "binary",
                    "-j", section_flag,
                    input_elf,
                    output_bin_path
                ]
                
                process = subprocess.run(
                    extract_cmd,
                    shell=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=project_dir,
                    timeout=10
                )
                
                if process.returncode != 0:
                    result.success = False
                    result.details = f"Failed to extract {section_flag}: {process.stderr}"
                    self._log_error(result.details)
                    return result
                
                if not os.path.exists(output_bin_path):
                    result.success = False
                    result.details = f"Extracted file was not created: {output_bin_path}"
                    self._log_error(result.details)
                    return result
                
                if self.verbose:
                    self._log_progress(f"    Created: {output_bin_name}")

            result.message = "All sections extracted successfully"
        
        except subprocess.TimeoutExpired:
            result.success = False
            result.details = "objcopy timed out"
            self._log_error(result.details)
        except FileNotFoundError:
            result.success = False
            result.details = f"objcopy not found: {objcopy_path}"
            self._log_error(result.details)
        except Exception as e:
            result.success = False
            result.details = f"Section extraction error: {str(e)}"
            self._log_error(result.details)
            import traceback
            self._log_error(traceback.format_exc())

        return result
    
    def _process_multipatches(self, hooks_to_cleanup: list) -> CompilationResult:
        """
        Process multi-patch ASM files and create temporary hooks.
        I might think of a better system for this in the future. I like the idea, but I think it could be done better.
        """
        result = CompilationResult(success=True)
        
        current_build = self.project_data.GetCurrentBuildVersion()
        multipatches = current_build.GetMultiPatches()
        
        if not multipatches:
            return result  # No multi-patches to process
        
        from services.asm_parser_service import ASMParserService
        parser = ASMParserService(self.project_data)
        
        total_hooks_created = 0
        
        for multipatch in multipatches:
            asm_file_path = multipatch.GetFilePath()
            base_name = multipatch.GetName()
            
            if not os.path.exists(asm_file_path):
                self._log_error(f"  Warning: Multi-patch file not found: {asm_file_path}")
                self._log_error(f"           Skipping '{base_name}'")
                continue
            
            if self.verbose:
                self._log_progress(f"  Processing multi-patch: {base_name}")
            
            try:
                # Parse and create hooks
                hooks = parser.create_hooks_from_multipatch(asm_file_path, base_name)
                
                if not hooks:
                    self._log_error(f"  Warning: No patches found in {base_name}")
                    continue
                
                # Add hooks TEMPORARILY to current build (only for this compilation)
                for hook in hooks:
                    current_build.AddHook(hook)
                    hooks_to_cleanup.append(hook)  # Track for cleanup
                
                total_hooks_created += len(hooks)
                
                if self.verbose:
                    self._log_progress(f"    Created {len(hooks)} temporary hook(s)")
            
            except Exception as e:
                self._log_error(f"  Error processing multi-patch '{base_name}': {str(e)}")
                import traceback
                self._log_error(traceback.format_exc())
                result.success = False
                result.message = f"Failed to process multi-patch: {base_name}"
                return result
        
        if total_hooks_created > 0:
            self._log_progress(f"  Total multi-patch hooks: {total_hooks_created}")
        
        return result
    
    def _cleanup_previous_multipatch_hooks(self):
        """
        Remove multi-patch generated hooks from previous compilations.
        Multi-patch hooks are regenerated fresh each time, to avoid duplication or other problems.
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        hooks = current_build.GetHooks()
        
        # Remove hooks from multi-patches (contain "_patch_" in name)
        multipatch_names = [mp.GetName() for mp in current_build.GetMultiPatches()]
        hooks_to_remove = []
        
        for hook in hooks:
            hook_name = hook.GetName()
            # Check if hook is from a multi-patch
            for mp_name in multipatch_names:
                if hook_name.startswith(f"{mp_name}_patch_"):
                    hooks_to_remove.append(hook)
                    break
        
        for hook in hooks_to_remove:
            hooks.remove(hook)
        
        if hooks_to_remove and self.verbose:
            self._log_progress(f"  Cleaned up {len(hooks_to_remove)} previous multi-patch hook(s)")
        
        # Clean up generated directory for multi-patches
        project_folder = self.project_data.GetProjectFolder()
        generated_dir = os.path.join(project_folder, "asm", ".generated")
        
        if os.path.exists(generated_dir):
            try:
                import shutil
                shutil.rmtree(generated_dir)
                if self.verbose:
                    self._log_progress(f"  Cleaned up multi-patch generated directory")
            except Exception as e:
                if self.verbose:
                    self._log_progress(f"  Warning: Could not clean generated dir: {e}")
            
    def _cleanup_previous_auto_hooks(self):
        current_build = self.project_data.GetCurrentBuildVersion()
        hooks = current_build.GetHooks()

        # Remove only TEMPORARY hooks that start with "AutoHook_"
        hooks_to_remove = [h for h in hooks if h.GetName().startswith("AutoHook_") and h.IsTemporary()] # List comprehension go crazy

        for hook in hooks_to_remove:
            hooks.remove(hook)
        
        if hooks_to_remove and self.verbose:
            self._log_progress(f"  Cleaned up {len(hooks_to_remove)} previous auto-hook(s)")
        
        # Clean up the auto-hooks directory. (I might rename this in the future to generated_hooks)
        project_folder = self.project_data.GetProjectFolder()
        auto_hooks_dir = os.path.join(project_folder, "asm", ".auto_hooks")
        
        if os.path.exists(auto_hooks_dir):
            try:
                import shutil
                shutil.rmtree(auto_hooks_dir)
                if self.verbose:
                    self._log_progress(f"  Cleaned up auto-hooks directory")
            except Exception as e:
                if self.verbose:
                    self._log_progress(f"  Warning: Could not clean auto-hooks dir: {e}")
    
    
    
    
    def _log_progress(self, message: str):
        print(message)
        
        if self.verbose:
            verbose_print(message)
        
        # Send to GUI callback without color
        if self.on_progress:
            clean_message = self._strip_ansi_codes(message)
            self.on_progress(clean_message)
    
    def _log_error(self, message: str):
        """Log error message"""
        # Always print to console (with colors)
        print_error(f"{message}")
        
        # Send to GUI callback if available (strip ANSI codes)
        if self.on_error:
            clean_message = self._strip_ansi_codes(message)
            self.on_error(clean_message)
    
    def _display_warnings_block(self, filename: str, warnings_text: str):
        """Display a formatted warning block for a specific file"""
        # Print to console - header in cyan, warnings with GCC's own coloring
        print("")
        print_cyan("╔══════════════════════════════════════════════════════════╗")
        print_cyan(f"║            COMPILER WARNINGS ({filename})".ljust(59) + "║")
        print_cyan("╚══════════════════════════════════════════════════════════╝")

        # Print each warning line with GCC's own coloring and colorized filenames
        for line in warnings_text.strip().split('\n'):
            if line.strip():
                colorized_line = self._colorize_filename_in_line(line)
                print(colorized_line)  # Use normal print to preserve GCC colors

        print("")  # Blank line after warnings

        # Also send to GUI if callback exists (strip ANSI codes)
        if self.on_progress:
            self.on_progress("")
            self.on_progress("╔══════════════════════════════════════════════════════════╗")
            self.on_progress(f"║            COMPILER WARNINGS ({filename})".ljust(59) + "║")
            self.on_progress("╚══════════════════════════════════════════════════════════╝")

            # Strip ANSI codes from warnings text for GUI
            clean_warnings = self._strip_ansi_codes(warnings_text)
            for line in clean_warnings.strip().split('\n'):
                if line.strip():
                    self.on_progress(line)
            self.on_progress("")

    def _display_notes_block(self, filename: str, notes_text: str):
        """Display a formatted notes block for a specific file"""
        # Print to console - header in dark grey, notes with GCC's own coloring
        print("")
        print_dark_grey("╔══════════════════════════════════════════════════════════╗")
        print_dark_grey(f"║            COMPILER NOTES ({filename})".ljust(61) + "║")
        print_dark_grey("╚══════════════════════════════════════════════════════════╝")

        # Print each note line with GCC's own coloring and colorized filenames
        for line in notes_text.strip().split('\n'):
            if line.strip():
                colorized_line = self._colorize_filename_in_line(line)
                print(colorized_line)  # Use normal print to preserve GCC colors

        print("")  # Blank line after notes

        # Also send to GUI if callback exists (strip ANSI codes)
        if self.on_progress:
            self.on_progress("")
            self.on_progress("╔══════════════════════════════════════════════════════════╗")
            self.on_progress(f"║            COMPILER NOTES ({filename})".ljust(61) + "║")
            self.on_progress("╚══════════════════════════════════════════════════════════╝")

            # Strip ANSI codes from notes text for GUI
            clean_notes = self._strip_ansi_codes(notes_text)
            for line in clean_notes.strip().split('\n'):
                if line.strip():
                    self.on_progress(line)
            self.on_progress("")