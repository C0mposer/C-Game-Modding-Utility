import sys
import os
import io
import time 
import argparse
from typing import Optional, List
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classes.project_data.project_data import ProjectData
from classes.mod_builder import ModBuilder
from services.project_serializer import ProjectSerializer
from services.compilation_service import CompilationService, CompilationResult
from services.iso_service import ISOService, ISOResult
from services.emulator_service import EmulatorService, InjectionResult, EMULATOR_CONFIGS
from services.pid_cache_service import PIDCacheService
from functions.verbose_print import verbose_print
from path_helper import get_application_directory


class Colors:
    """ANSI color codes"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'
    
    @staticmethod
    def disable():
        """Disable all colors"""
        Colors.RESET = ''
        Colors.BOLD = ''
        Colors.RED = ''
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.BLUE = ''
        Colors.MAGENTA = ''
        Colors.CYAN = ''
        Colors.GRAY = ''


class CLILogger:
    def __init__(self, verbose: bool = False, quiet: bool = False, no_warnings: bool = False):
        self.verbose = verbose
        self.quiet = quiet
        self.no_warnings = no_warnings
    
    def info(self, message: str):
        if not self.quiet:
            print(f"{Colors.CYAN}{Colors.RESET} {message}")
    
    def success(self, message: str):
        if not self.quiet:
            print(f"{Colors.GREEN}{Colors.RESET} {message}")
    
    def error(self, message: str):
        print(f"{Colors.RED}{Colors.RESET} {message}", file=sys.stderr)
    
    def warning(self, message: str):
        if not self.quiet:
            print(f"{Colors.YELLOW}⚠{Colors.RESET} {message}")
    
    def debug(self, message: str):
        if self.verbose:
            print(f"{Colors.GRAY}->{Colors.RESET} {message}")
    
    def header(self, message: str):
        if not self.quiet:
            print(f"\n{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
            print(f"{Colors.GRAY}{'─' * len(message)}{Colors.RESET}")
    
    def progress(self, message: str):
        if self.verbose and not self.quiet:
            print(f"  {message}")


class ModToolCLI:
    def __init__(self, logger: CLILogger):
        self.logger = logger
        self.tool_dir = get_application_directory()
        self.on_progress = None
        self.on_error = None
        self.verbose = False
    
    def _log(self, msg: str):
        print(msg)
        if self.on_progress:
            self.on_progress(msg)

    def _vlog(self, msg: str):
        if not self.verbose:
            return
        verbose_print(msg)
        if self.on_progress:
            self.on_progress(msg)

    def _elog(self, msg: str):
        from functions.print_wrapper import print_error
        print_error(msg)
        if self.on_error:
            self.on_error(msg)
    
    def find_project_in_cwd(self) -> Optional[str]:
        cwd = os.getcwd()
        self.logger.debug(f"Auto-detecting project in: {cwd}")

        # Look for .modproj files in current directory
        for file in os.listdir(cwd):
            if file.endswith('.modproj'):
                project_file = os.path.join(cwd, file)
                self.logger.debug(f"Auto-detected: {project_file}")
                return project_file

        return None

    def find_project_file(self, project_name: str) -> Optional[str]:
        self.logger.debug(f"Searching for project: {project_name}")

        # Try exact path first
        if os.path.exists(project_name) and project_name.endswith('.modproj'):
            self.logger.debug(f"Found at exact path: {project_name}")
            return project_name

        # Try adding .modproj extension
        if os.path.exists(f"{project_name}.modproj"):
            self.logger.debug(f"Found: {project_name}.modproj")
            return f"{project_name}.modproj"

        # Try in projects/ directory
        projects_dir = os.path.join(self.tool_dir, "projects", project_name)
        if os.path.exists(projects_dir):
            # Look for .modproj file in that directory
            for file in os.listdir(projects_dir):
                if file.endswith('.modproj'):
                    project_file = os.path.join(projects_dir, file)
                    self.logger.debug(f"Found in projects dir: {project_file}")
                    return project_file

        # Try recursive search in projects/ directory
        projects_base = os.path.join(self.tool_dir, "projects")
        if os.path.exists(projects_base):
            for root, dirs, files in os.walk(projects_base):
                for file in files:
                    if file.endswith('.modproj') and project_name.lower() in file.lower():
                        project_file = os.path.join(root, file)
                        self.logger.debug(f"Found via search: {project_file}")
                        return project_file

        self.logger.debug("Project file not found")
        return None

    def load_project(self, project_name: Optional[str]) -> Optional[ProjectData]:
        # Auto-detect if no project name provided
        if project_name is None:
            self.logger.debug("No project specified, attempting auto-detection...")
            project_file = self.find_project_in_cwd()

            if not project_file:
                self.logger.error("No project file found in current directory")
                self.logger.info("Either:")
                self.logger.info("  - Run modtool from a project directory")
                self.logger.info("  - Or specify project name: mod_utility.exe <command> <project>")
                return None

            self.logger.info(f"Auto-detected project: {os.path.basename(project_file)}")
        else:
            # Find project by name
            project_file = self.find_project_file(project_name)

            if not project_file:
                self.logger.error(f"Project not found: {project_name}")
                self.logger.info("Searched in:")
                self.logger.info("  - Current directory")
                self.logger.info("  - projects/ directory")
                self.logger.info("  - Subdirectories")
                return None

        self.logger.debug(f"Loading project from: {project_file}")
        project_data = ProjectSerializer.load_project(project_file, show_loading=False)

        if not project_data:
            self.logger.error(f"Failed to load project: {project_file}")
            return None

        self.logger.debug(f"Project loaded: {project_data.GetProjectName()}")
        return project_data
    
    def save_project(self, project_data: ProjectData) -> bool:
        success = ProjectSerializer.save_project(project_data)
        if success:
            self.logger.debug("Project saved")
        else:
            self.logger.error("Failed to save project")
        return success
    
    def _prompt_build_selection(self, project_data: ProjectData) -> bool:
        build_names = [bv.GetBuildName() for bv in project_data.build_versions]
        
        # If only one build, use it automatically
        if len(build_names) == 1:
            return True
        
        # Display build options
        print(f"\n{Colors.BOLD}Select Build Version:{Colors.RESET}")
        for i, name in enumerate(build_names, 1):
            current = " (current)" if i - 1 == project_data.GetBuildVersionIndex() else ""
            print(f"  {Colors.CYAN}[{i}]{Colors.RESET} {name}{Colors.GRAY}{current}{Colors.RESET}")
        
        # Get user input
        try:
            choice = input(f"\n{Colors.BOLD}Enter number (1-{len(build_names)}) or press Enter for current:{Colors.RESET} ").strip()
            
            # Empty input = use current
            if not choice:
                return True
            
            # Parse number
            choice_num = int(choice)
            if 1 <= choice_num <= len(build_names):
                project_data.SetBuildVersionIndex(choice_num - 1)
                self.logger.success(f"Selected: {build_names[choice_num - 1]}")
                return True
            else:
                self.logger.error(f"Invalid selection. Must be 1-{len(build_names)}")
                return False
                
        except ValueError:
            self.logger.error("Invalid input. Please enter a number.")
            return False
        except KeyboardInterrupt:
            print()  # New line after ^C
            self.logger.info("Cancelled")
            return False
    
    def _prompt_command_selection(self) -> Optional[str]:
        commands = [
            ('compile', 'Compile project sources'),
            ('build', 'Full build (compile + ISO)'),
            ('inject', 'Inject into running emulator'),
            ('xdelta', 'Generate xdelta patch'),
            ('clean', 'Clean build artifacts'),
            ('validate', 'Validate project setup'),
            ('list-builds', 'List build versions'),
            ('set-build', 'Switch build version'),
            ('info', 'Show project information'),
            ('exit', 'Exit modtool')
        ]

        # Display command options
        print(f"\n{Colors.BOLD}Select Command:{Colors.RESET}")
        for i, (cmd, desc) in enumerate(commands, 1):
            default_marker = f" {Colors.GREEN}(default){Colors.RESET}" if cmd == 'compile' else ""
            print(f"  {Colors.CYAN}[{i}]{Colors.RESET} {cmd:<15} {Colors.GRAY}- {desc}{Colors.RESET}{default_marker}")

        # Get user input
        try:
            choice = input(f"\n{Colors.BOLD}Enter number (1-{len(commands)}), 'exit', or press Enter for compile:{Colors.RESET} ").strip()

            # Empty input = default to compile
            if not choice:
                return 'compile'

            # Check for 'exit' string
            if choice.lower() == 'exit':
                return 'exit'

            # Parse number
            choice_num = int(choice)
            if 1 <= choice_num <= len(commands):
                selected_cmd = commands[choice_num - 1][0]
                if selected_cmd != 'exit':
                    self.logger.success(f"Selected: {selected_cmd}")
                return selected_cmd
            else:
                self.logger.error(f"Invalid selection. Must be 1-{len(commands)}")
                return None

        except ValueError:
            self.logger.error("Invalid input. Please enter a number or 'exit'.")
            return None
        except KeyboardInterrupt:
            print()  # New line after ^C
            self.logger.info("Cancelled")
            return 'exit'

    def _display_size_analysis(self, analyzer):
        from services.size_analyzer_service import SizeAnalyzerService

        results = analyzer.analyze_all()
        
        if not results:
            return
        
        print("\n" + "=" * 60)
        print("CODE SIZE ANALYSIS")
        print("=" * 60)
        
        for result in results:
            # Format type
            type_str = result.injection_type.replace('_', ' ').title()
            
            # Format sizes
            used_hex = f"0x{result.used_bytes:X}"
            allocated_hex = f"0x{result.allocated_bytes:X}"
            percentage = result.percentage_used
            
            # Create progress bar (full Unicode for console)
            bar_width = 30
            filled = int((percentage / 100.0) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            
            # Build output line
            print(f"\n{type_str}: {result.name}")
            print(f"  Used: {used_hex} of {allocated_hex} ({percentage:.1f}%)")
            print(f"  [{bar}]")
            print(f"  0x{result.remaining_bytes:X} bytes remaining")
            
            if result.is_overflow:
                overflow = result.used_bytes - result.allocated_bytes
                print(f"  OVERFLOW BY 0x{overflow:X} bytes!")
        
        # Summary
        summary = analyzer.get_summary()
        print("\n" + "-" * 60)
        print(f"SUMMARY: {summary['total_count']} target(s)")
        print(f"  Total Used: 0x{summary['total_used']:X} bytes")
        print(f"  Total Allocated: 0x{summary['total_allocated']:X} bytes")
        print(f"  Overall: {summary['percentage_used']:.1f}% used")
        
        if summary['overflow_count'] > 0:
            print(f"   {summary['overflow_count']} OVERFLOW(S)!")
        if summary['critical_count'] > 0:
            print(f"   {summary['critical_count']} codecaves at >90% capacity")
        if summary['warning_count'] > 0:
            print(f"   {summary['warning_count']} codecaves at >75% capacity")
        
        print("=" * 60)
    

    # Actions
    def cmd_compile(self, project_name: str, build_name: Optional[str] = None) -> int:
        """Compile project sources"""
        self.logger.header("COMPILE")
        
        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1
        
        # Switch build version if specified, or prompt if multiple builds exist
        if build_name:
            if not self._switch_build(project_data, build_name):
                return 1
        else:
            # Prompt user to select build
            if not self._prompt_build_selection(project_data):
                return 1
        
        current_build = project_data.GetCurrentBuildVersion()
        self.logger.info(f"Project: {project_data.GetProjectName()}")
        self.logger.info(f"Build: {current_build.GetBuildName()}")
        self.logger.info(f"Platform: {current_build.GetPlatform()}")

        # Create compilation service with verbose mode
        mod_builder = ModBuilder(tool_dir=self.tool_dir)
        compilation_service = CompilationService(project_data, mod_builder, verbose=self.logger.verbose, no_warnings=self.logger.no_warnings)
        
        # CompilationService now prints directly to console, so we don't need callbacks
        compilation_service.on_progress = lambda msg: None
        compilation_service.on_error = lambda msg: None
        
        # Compile
        print("")  # Blank line before compilation output
        start_time = time.perf_counter()
        result = compilation_service.compile_project()
        elapsed_time = time.perf_counter() - start_time
        
        if result.success:
            # Show size analysis
            from services.size_analyzer_service import SizeAnalyzerService
            analyzer = SizeAnalyzerService(project_data)
            self._display_size_analysis(analyzer)
            
            print("")  # Blank line
            self.logger.success(result.message)
            
            # Final banner at the very end of CLI output
            if not self.logger.quiet:
                banner_top = "\n" + "=" * 60
                banner_msg = f"COMPILATION SUCCESSFUL! (Took {elapsed_time:.2f}s)"
                banner_bottom = "=" * 60
                print(banner_top)
                print(banner_msg)
                print(banner_bottom)
            
            if self.logger.verbose:
                self.logger.info("")
                self.logger.info("Output files:")
                
                # Show output locations
                project_folder = project_data.GetProjectFolder()
                obj_dir = os.path.join(project_folder, ".config", "output", "object_files")
                bin_dir = os.path.join(project_folder, ".config", "output", "bin_files")
                
                self.logger.info(f"  - Object files: {obj_dir}")
                self.logger.info(f"  - Binary files: {bin_dir}")
            
            return 0
        else:
            print("")  # Blank line
            self.logger.error(f"Compilation failed: {result.message}")
            if result.details:
                self.logger.error(f"Details: {result.details}")
            return 1

    
    def cmd_build(self, project_name: str, build_name: Optional[str] = None) -> int:
        self.logger.header("BUILD")
        
        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1
        
        # Switch build version if specified, or prompt
        if build_name:
            if not self._switch_build(project_data, build_name):
                return 1
        else:
            if not self._prompt_build_selection(project_data):
                return 1
        
        current_build = project_data.GetCurrentBuildVersion()
        self.logger.info(f"Project: {project_data.GetProjectName()}")
        self.logger.info(f"Build: {current_build.GetBuildName()}")
        self.logger.info(f"Platform: {current_build.GetPlatform()}")
        
        # Compile
        self.logger.info("")
        self.logger.info("[1/3] Compiling...")

        mod_builder = ModBuilder(tool_dir=self.tool_dir)
        compilation_service = CompilationService(project_data, mod_builder, verbose=self.logger.verbose, no_warnings=self.logger.no_warnings)
        compilation_service.on_progress = lambda msg: None
        compilation_service.on_error = lambda msg: None
        
        import time
        start_time = time.perf_counter()
        compile_result = compilation_service.compile_project()
        elapsed_compile = time.perf_counter() - start_time
        
        if not compile_result.success:
            self.logger.error("Compilation failed")
            return 1
        
        # Show size analysis
        from services.size_analyzer_service import SizeAnalyzerService
        analyzer = SizeAnalyzerService(project_data)
        self._display_size_analysis(analyzer)
        
        self.logger.success("\nCompilation complete")
        
        # Final compilation banner in CLI
        if not self.logger.quiet:
            banner_top = "\n" + "=" * 60
            banner_msg = f"COMPILATION SUCCESSFUL! (Took {elapsed_compile:.2f}s)"
            banner_bottom = "=" * 60
            print(banner_top)
            print(banner_msg)
            print(banner_bottom)
        
        # Build ISO
        self.logger.info("")
        self.logger.info("[2/3] Building ISO...")

        iso_service = ISOService(project_data, verbose=self.logger.verbose, tool_dir=self.tool_dir)
        start_iso = time.perf_counter()
        build_result = iso_service.full_build()
        elapsed_iso = time.perf_counter() - start_iso

        if not build_result.success:
            self.logger.error(f"Build failed: {build_result.message}")
            return 1

        if not self.logger.quiet:
            banner_top = "\n" + "=" * 60
            banner_msg = f"ISO BUILD COMPLETE! (Took {elapsed_iso:.2f}s)"
            banner_bottom = "=" * 60
            print(banner_top)
            print(banner_msg)
            print(banner_bottom)

        self.logger.info(f"Output: {build_result.output_path}")

        # Total time summary
        total_time = elapsed_compile + elapsed_iso
        if not self.logger.quiet:
            banner_top = "\n" + "=" * 60
            banner_msg = f"TOTAL BUILD TIME: {total_time:.2f}s (Compile: {elapsed_compile:.2f}s + ISO: {elapsed_iso:.2f}s)"
            banner_bottom = "=" * 60
            print(banner_top)
            print(banner_msg)
            print(banner_bottom)

        return 0


    def cmd_xdelta(self, project_name: str, original_file: Optional[str] = None,
                   build_name: Optional[str] = None) -> int:
        self.logger.header("GENERATE XDELTA PATCH")

        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1

        # Switch build version if specified, or prompt
        if build_name:
            if not self._switch_build(project_data, build_name):
                return 1
        else:
            if not self._prompt_build_selection(project_data):
                return 1

        current_build = project_data.GetCurrentBuildVersion()
        self.logger.info(f"Project: {project_data.GetProjectName()}")
        self.logger.info(f"Build: {current_build.GetBuildName()}")
        self.logger.info(f"Platform: {current_build.GetPlatform()}")

        # Create ISO service
        iso_service = ISOService(project_data, verbose=self.logger.verbose, tool_dir=self.tool_dir)

        # If no original file provided, check if we need to prompt
        if original_file is None:
            # Try to auto-detect from project settings
            is_single_file = current_build.IsSingleFileMode()

            if is_single_file:
                original_file = current_build.GetSingleFilePath()
            else:
                source_path = current_build.GetSourcePath()
                if source_path and os.path.exists(source_path) and not os.path.isdir(source_path):
                    original_file = source_path

            # If still None or is directory, we need user to specify
            if not original_file or (original_file and os.path.isdir(original_file)):
                self.logger.error("Cannot auto-detect original file")
                self.logger.info("Please specify the original file with: --original <path>")
                return 1

        # Validate original file
        if not os.path.exists(original_file):
            self.logger.error(f"Original file not found: {original_file}")
            return 1

        self.logger.info(f"Original: {original_file}")
        self.logger.info("")
        self.logger.info("Generating xdelta patch...")

        # Generate patch
        start_xdelta = time.perf_counter()
        result = iso_service.generate_xdelta_patch(original_file)
        elapsed_xdelta = time.perf_counter() - start_xdelta

        if result.success:
            if not self.logger.quiet:
                banner_top = "\n" + "=" * 60
                banner_msg = f"XDELTA PATCH GENERATED! (Took {elapsed_xdelta:.2f}s)"
                banner_bottom = "=" * 60
                print(banner_top)
                print(banner_msg)
                print(banner_bottom)

            if result.output_path:
                self.logger.info(f"Patch file: {result.output_path}")
            return 0
        else:
            self.logger.error(f"Patch generation failed: {result.message}")
            return 1

    def cmd_inject(self, project_name: str, emulator_name: Optional[str] = None,
               build_name: Optional[str] = None) -> int:
        self.logger.header("INJECT")

        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1

        # Switch build version if specified, or prompt
        if build_name:
            if not self._switch_build(project_data, build_name):
                return 1
        else:
            if not self._prompt_build_selection(project_data):
                return 1

        current_build = project_data.GetCurrentBuildVersion()
        self.logger.info(f"Project: {project_data.GetProjectName()}")
        self.logger.info(f"Build: {current_build.GetBuildName()}")
        self.logger.info(f"Platform: {current_build.GetPlatform()}")

        # Initialize PID cache service
        pid_cache = PIDCacheService(project_data.GetProjectFolder())

        # Initialize emulator connection manager with cached PIDs
        from services.emulator_connection_manager import get_emulator_manager
        manager = get_emulator_manager()
        manager.set_project_data(project_data)

        # Pre-populate the manager's cache with our file-based cache
        for emu_key, emu_info in EMULATOR_CONFIGS.items():
            cached_pid = pid_cache.get_cached_pid(emu_key, emu_info.process_name)
            if cached_pid:
                manager.cached_pids[emu_key] = cached_pid
                self.logger.debug(f"Pre-loaded cached PID {cached_pid} for {emu_key}")

        # Create emulator service
        emu_service = EmulatorService(project_data)

        # If user specified an emulator, try to find it
        target_emulator = None
        if emulator_name:
            # Try to match emulator name case-insensitively
            for emu_key in EMULATOR_CONFIGS.keys():
                if emu_key.lower() == emulator_name.lower():
                    target_emulator = emu_key
                    self.logger.debug(f"Matched emulator: {emu_key}")
                    break

            if not target_emulator:
                self.logger.error(f"Unknown emulator: {emulator_name}")
                return 1

        # If no emulator specified, scan for available emulators
        if not target_emulator:
            self.logger.debug("No valid cached PID, scanning for emulators...")
            available = emu_service.get_available_emulators()

            if not available:
                self.logger.error("No running emulators detected")
                self.logger.info("\nSupported emulators by platform:")
                self.logger.info("  PS1:")
                self.logger.info("    - DuckStation")
                self.logger.info("    - PCSX-Redux")
                self.logger.info("    - BizHawk")
                self.logger.info("    - Mednafen 1.29")
                self.logger.info("    - Mednafen 1.31")
                self.logger.info("  PS2:")
                self.logger.info("    - PCSX2")
                self.logger.info("  GameCube/Wii:")
                self.logger.info("    - Dolphin")
                self.logger.info("  N64:")
                self.logger.info("    - Project64")
                self.logger.info("\nMake sure the emulator is running with a game loaded.")
                return 1

            # Select emulator
            if emulator_name:
                # User specified emulator - do case-insensitive match
                emulator_name_lower = emulator_name.lower()

                # Find matching emulator
                for emu in available:
                    if emu.lower() == emulator_name_lower:
                        target_emulator = emu
                        break

                if not target_emulator:
                    self.logger.error(f"Emulator '{emulator_name}' not running or not detected")
                    self.logger.info(f"\nCurrently running: {', '.join(available)}")
                    self.logger.info(f"Note: Emulator name is case-insensitive")
                    return 1
            else:
                # Auto-select first available
                target_emulator = available[0]
                if len(available) > 1:
                    self.logger.warning(f"Multiple emulators detected, using: {target_emulator}")
                    self.logger.info(f"Available: {', '.join(available)}")

            # Cache the PID
            if target_emulator in EMULATOR_CONFIGS:
                emu_info = EMULATOR_CONFIGS[target_emulator]
                cached_pid = emu_service._get_pid(emu_info.process_name)
                if cached_pid:
                    pid_cache.cache_pid(target_emulator, cached_pid)
                    self.logger.debug(f"Saved PID {cached_pid} for {target_emulator}")

        self.logger.info(f"Target: {target_emulator}")

        # Inject
        self.logger.info("")
        self.logger.info("Injecting...")
        result = emu_service.inject_into_emulator(target_emulator)

        # After injection, save any newly discovered PIDs
        if target_emulator in manager.cached_pids:
            new_pid = manager.cached_pids[target_emulator]
            pid_cache.cache_pid(target_emulator, new_pid)
            self.logger.debug(f"Saved PID {new_pid} for {target_emulator}")

        if result.success:
            self.logger.success(result.message)
            return 0
        else:
            self.logger.error(f"Injection failed: {result.message}")
            return 1
    
    def cmd_clean(self, project_name: str) -> int:
        self.logger.header("CLEAN")
        
        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1
        
        self.logger.info(f"Project: {project_data.GetProjectName()}")
        
        project_folder = project_data.GetProjectFolder()
        
        # Directories to clean
        clean_dirs = [
            os.path.join(project_folder, ".config", "output", "object_files"),
            os.path.join(project_folder, ".config", "output", "bin_files"),
            os.path.join(project_folder, ".config", "output", "memory_map"),
            os.path.join(project_folder, ".config", "output", "iso_build"),  # Persistent build directories
        ]
        
        # Files to clean
        clean_files = [
            os.path.join(project_folder, "ModdedGame.bin"),
            os.path.join(project_folder, "ModdedGame.cue"),
            os.path.join(project_folder, "ModdedGame.iso"),
        ]
        
        # Add patched files
        for file_name in project_data.GetCurrentBuildVersion().GetInjectionFiles():
            clean_files.append(os.path.join(project_folder, f"patched_{file_name}"))
        
        files_removed = 0
        
        # Clean directories
        import shutil
        for dir_path in clean_dirs:
            if os.path.exists(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    os.makedirs(dir_path, exist_ok=True)
                    self.logger.debug(f"Cleaned: {dir_path}")
                    files_removed += 1
                except Exception as e:
                    self.logger.warning(f"Could not clean {dir_path}: {e}")
        
        # Clean files
        for file_path in clean_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.logger.debug(f"Removed: {file_path}")
                    files_removed += 1
                except Exception as e:
                    self.logger.warning(f"Could not remove {file_path}: {e}")

        # Clear build cache
        cache_path = os.path.join(project_folder, '.config', 'output', '.build_cache.json')
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                self.logger.debug("Cleared build cache")
                files_removed += 1
            except Exception as e:
                self.logger.warning(f"Could not clear build cache: {e}")

        if files_removed > 0:
            self.logger.success(f"Cleaned {files_removed} artifact(s)")
        else:
            self.logger.info("Nothing to clean")

        return 0
    
    def cmd_validate(self, project_name: str) -> int:
        self.logger.header("VALIDATE")
        
        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1
        
        current_build = project_data.GetCurrentBuildVersion()
        self.logger.info(f"Project: {project_data.GetProjectName()}")
        self.logger.info(f"Build: {current_build.GetBuildName()}")
        
        checks_passed = 0
        checks_failed = 0
        
        # Check 1: Platform set
        if current_build.GetPlatform() and current_build.GetPlatform() != "Choose a Platform":
            self.logger.success(f"Platform: {current_build.GetPlatform()}")
            checks_passed += 1
        else:
            self.logger.error("Platform not set")
            checks_failed += 1
        
        # Check 2: Main executable
        if current_build.GetMainExecutable():
            self.logger.success(f"Main executable: {current_build.GetMainExecutable()}")
            checks_passed += 1
        else:
            self.logger.error("Main executable not set")
            checks_failed += 1
        
        # Check 3: Game folder
        if current_build.GetGameFolder():
            self.logger.success(f"Game folder: {current_build.GetGameFolder()}")
            checks_passed += 1
        else:
            self.logger.warning("Game folder not set")
            checks_failed += 1
        
        # Check 4: File offset
        main_exe = current_build.GetMainExecutable()
        if main_exe:
            offset = current_build.GetInjectionFileOffset(main_exe)
            if offset and offset != "":
                self.logger.success(f"File offset: 0x{offset}")
                checks_passed += 1
            else:
                self.logger.error("File offset not set")
                checks_failed += 1
        
        # Check 5: Codecaves
        codecaves = current_build.GetCodeCaves()
        if codecaves:
            self.logger.success(f"Codecaves: {len(codecaves)}")
            checks_passed += 1
        else:
            self.logger.warning("No codecaves defined")
        
        # Check 6: Hooks
        hooks = current_build.GetHooks()
        if hooks:
            self.logger.success(f"Hooks: {len(hooks)}")
            checks_passed += 1
        else:
            self.logger.warning("No hooks defined")
        
        # Check 7: Source files
        project_folder = project_data.GetProjectFolder()
        main_c = os.path.join(project_folder, "src", "main.c")
        if os.path.exists(main_c):
            self.logger.success("Source files present")
            checks_passed += 1
        else:
            self.logger.warning("src/main.c not found")
        
        # Summary
        self.logger.info("")
        if checks_failed == 0:
            self.logger.success(f"Validation passed ({checks_passed} checks)")
            return 0
        else:
            self.logger.error(f"Validation failed ({checks_failed} issues)")
            return 1
    
    def cmd_list_builds(self, project_name: str) -> int:
        self.logger.header("BUILD VERSIONS")
        
        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1
        
        self.logger.info(f"Project: {project_data.GetProjectName()}")
        self.logger.info("")
        
        current_index = project_data.GetBuildVersionIndex()
        
        for i, build_version in enumerate(project_data.build_versions):
            is_current = (i == current_index)
            marker = f"{Colors.GREEN}●{Colors.RESET}" if is_current else f"{Colors.GRAY}○{Colors.RESET}"
            
            name = build_version.GetBuildName()
            platform = build_version.GetPlatform() or "Not set"
            
            print(f"{marker} {name}")
            self.logger.debug(f"  Platform: {platform}")
            self.logger.debug(f"  Codecaves: {len(build_version.GetCodeCaves())}")
            self.logger.debug(f"  Hooks: {len(build_version.GetHooks())}")
        
        return 0
    
    def cmd_set_build(self, project_name: str, build_name: str) -> int:
        self.logger.header("SET BUILD VERSION")
        
        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1
        
        if self._switch_build(project_data, build_name):
            self.save_project(project_data)
            self.logger.success(f"Switched to build: {build_name}")
            return 0
        else:
            return 1
    
    def cmd_info(self, project_name: str) -> int:
        self.logger.header("PROJECT INFO")
        
        # Load project
        project_data = self.load_project(project_name)
        if not project_data:
            return 1
        
        current_build = project_data.GetCurrentBuildVersion()
        
        # Basic info
        print(f"{Colors.BOLD}Project:{Colors.RESET} {project_data.GetProjectName()}")
        print(f"{Colors.BOLD}Folder:{Colors.RESET} {project_data.GetProjectFolder()}")
        print(f"{Colors.BOLD}Build Versions:{Colors.RESET} {len(project_data.build_versions)}")
        
        print(f"\n{Colors.BOLD}Current Build:{Colors.RESET} {current_build.GetBuildName()}")
        print(f"{Colors.BOLD}Platform:{Colors.RESET} {current_build.GetPlatform()}")
        print(f"{Colors.BOLD}Main Executable:{Colors.RESET} {current_build.GetMainExecutable() or 'Not set'}")
        
        # Modifications
        print(f"\n{Colors.BOLD}Modifications:{Colors.RESET}")
        print(f"  - Codecaves: {len(current_build.GetCodeCaves())}")
        print(f"  - Hooks: {len(current_build.GetHooks())}")
        print(f"  - Binary Patches: {len(current_build.GetBinaryPatches())}")
        
        # Codecaves details
        if current_build.GetCodeCaves():
            print(f"\n{Colors.BOLD}Codecaves:{Colors.RESET}")
            for cave in current_build.GetCodeCaves():
                print(f"  - {cave.GetName()} @ 0x{cave.GetMemoryAddress()}")
                if self.logger.verbose:
                    print(f"    Size: 0x{cave.GetSize()}")
                    print(f"    Files: {len(cave.GetCodeFilesPaths())}")
        
        # Hooks details
        if current_build.GetHooks():
            print(f"\n{Colors.BOLD}Hooks:{Colors.RESET}")
            for hook in current_build.GetHooks():
                print(f"  - {hook.GetName()} @ 0x{hook.GetMemoryAddress()}")
                if self.logger.verbose:
                    print(f"    Files: {len(hook.GetCodeFilesPaths())}")
        
        return 0
    

    
    def _switch_build(self, project_data: ProjectData, build_name: str) -> bool:
        build_names = [bv.GetBuildName() for bv in project_data.build_versions]
        
        if build_name not in build_names:
            self.logger.error(f"Build version not found: {build_name}")
            self.logger.info(f"Available: {', '.join(build_names)}")
            return False
        
        new_index = build_names.index(build_name)
        project_data.SetBuildVersionIndex(new_index)
        self.logger.debug(f"Switched to build: {build_name}")
        return True
    
    def _get_supported_emulators_for_platform(self, platform: str) -> List[str]:
        emulator_map = {
            "PS1": ["DuckStation", "PCSX-Redux", "BizHawk", "Mednafen 1.29", "Mednafen 1.31"],
            "PS2": ["PCSX2"],
            "Gamecube": ["Dolphin"],
            "Wii": ["Dolphin"],
            #"N64": ["Project64"]
        }
        return emulator_map.get(platform, [])


#! Entry point
def print_custom_help():
    help_text = """Command-line interface for C/C++ Game Modding Utility

Interactive Mode:
  mod_utility.exe <PROJECT_NAME>          Shows interactive menu for your project

Explicit Command Mode:
  mod_utility.exe <COMMAND> <PROJECT_NAME> <optional_args>

positional arguments:
  compile             Compile project sources
  build               Full build (compile + ISO)
  xdelta              Generate xdelta patch
  inject              Inject into emulator
  clean               Clean build artifacts
  validate            Validate project
  list-builds         List build versions
  set-build           Switch build version
  info                Show project info

Examples:
  mod_utility.exe compile MyProject
  mod_utility.exe build MyProject
  mod_utility.exe inject MyProject
  mod_utility.exe clean MyProject

Examples with Arguments:
  mod_utility.exe compile MyProject --build=NTSC-U
  mod_utility.exe build MyProject --build=NTSC-U
  mod_utility.exe inject MyProject duckstation
  mod_utility.exe inject MyProject dolphin --build=NTSC-U

For more information, visit: https://github.com/C0mposer/C-Game-Modding-Utility
"""
    print(help_text)

def modtool_main():
    if '--help' in sys.argv or '-h' in sys.argv:
        print_custom_help()
        return 0

    parser = argparse.ArgumentParser(
        prog='Mod Utility',
        description='Command-line interface for C/C++ Game Modding Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False  # Disable automatic help to use custom help
    )

    # For Sublime since it has a problem with the default encoding
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Compile command
    compile_parser = subparsers.add_parser('compile', help='Compile project sources')
    compile_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    compile_parser.add_argument('--build', help='Build version to use')
    compile_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    compile_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    compile_parser.add_argument('--no-color', action='store_true', help='Disable colors')
    compile_parser.add_argument('--no-warnings', action='store_true', help='Suppress compiler warnings (errors still shown)')

    # Build command
    build_parser = subparsers.add_parser('build', help='Full build (compile + ISO)')
    build_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    build_parser.add_argument('--build', help='Build version to use')
    build_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    build_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    build_parser.add_argument('--no-color', action='store_true', help='Disable colors')
    build_parser.add_argument('--no-warnings', action='store_true', help='Suppress compiler warnings (errors still shown)')

    # Xdelta command
    xdelta_parser = subparsers.add_parser('xdelta', help='Generate xdelta patch')
    xdelta_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    xdelta_parser.add_argument('--original', help='Path to original file (auto-detected if not specified)')
    xdelta_parser.add_argument('--build', help='Build version to use')
    xdelta_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    xdelta_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    xdelta_parser.add_argument('--no-color', action='store_true', help='Disable colors')

    # Inject command
    inject_parser = subparsers.add_parser('inject', help='Inject into emulator')
    inject_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    inject_parser.add_argument('emulator', nargs='?', help='Emulator name (case-insensitive, e.g., duckstation, dolphin)')
    inject_parser.add_argument('--build', help='Build version to use')
    inject_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    inject_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    inject_parser.add_argument('--no-color', action='store_true', help='Disable colors')

    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean build artifacts')
    clean_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    clean_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    clean_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    clean_parser.add_argument('--no-color', action='store_true', help='Disable colors')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate project')
    validate_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    validate_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    validate_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    validate_parser.add_argument('--no-color', action='store_true', help='Disable colors')

    # List builds command
    list_parser = subparsers.add_parser('list-builds', help='List build versions')
    list_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    list_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    list_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    list_parser.add_argument('--no-color', action='store_true', help='Disable colors')

    # Set build command
    set_parser = subparsers.add_parser('set-build', help='Switch build version')
    set_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    set_parser.add_argument('build_name', help='Build version name')
    set_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    set_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    set_parser.add_argument('--no-color', action='store_true', help='Disable colors')

    # Info command
    info_parser = subparsers.add_parser('info', help='Show project info')
    info_parser.add_argument('project', nargs='?', default=None, help='Project name or path (auto-detected if run from project directory)')
    info_parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    info_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    info_parser.add_argument('--no-color', action='store_true', help='Disable colors')

    # Global options (still supported before subcommand for backwards compatibility)
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    parser.add_argument('--no-color', action='store_true', help='Disable colors')
    parser.add_argument('--version', action='version', version='Mod Utility 1.0.0')

    # Check if first arg is not a known command
    # If so, it's a project name for interactive mode
    top_level_project = None
    commands = ['compile', 'build', 'xdelta', 'inject', 'clean', 'validate', 'list-builds', 'set-build', 'info']

    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if not first_arg.startswith('-') and first_arg not in commands:
            top_level_project = first_arg
            # Remove it from sys.argv so argparse doesn't see it
            sys.argv.pop(1)

    # Parse arguments
    args = parser.parse_args()

    # Disable colors if requested
    if args.no_color:
        Colors.disable()

    # Create logger
    no_warnings = getattr(args, 'no_warnings', False)  # Default to False if not present
    logger = CLILogger(verbose=args.verbose, quiet=args.quiet, no_warnings=no_warnings)

    # Create CLI instance
    cli = ModToolCLI(logger)

    # Handle no command - show interactive menu
    if not args.command:
        # Check if we have a project to work with (either provided or auto-detected)
        has_project = False

        # Check if project was provided as argument
        if top_level_project:
            has_project = True
        else:
            # Check if we're in a project directory
            if cli.find_project_in_cwd():
                has_project = True

        # If no project available, show help instead of interactive menu
        if not has_project:
            print_custom_help()
            return 0

        # Interactive mode, loop until exit
        while True:
            selected_command = cli._prompt_command_selection()

            if not selected_command:
                continue  # Invalid input, show menu again

            # Check for exit
            if selected_command == 'exit':
                logger.info("Exiting...")
                return 0

            # Set the command and initialize missing arguments
            args.command = selected_command

            # Use top_level_project if provided (e.g., "mod_utility.exe MyProject")
            args.project = top_level_project
            args.build = None
            args.emulator = None
            args.original = None
            args.build_name = None

            # For set-build command, we need to prompt for the build name
            if selected_command == 'set-build':
                try:
                    build_name = input(f"\n{Colors.BOLD}Enter build version name:{Colors.RESET} ").strip()
                    if not build_name:
                        logger.error("Build name is required for set-build command")
                        continue  # Go back to menu
                    args.build_name = build_name
                except KeyboardInterrupt:
                    print()
                    logger.info("Cancelled")
                    continue  # Go back to menu

            # Execute command
            try:
                if args.command == 'compile':
                    cli.cmd_compile(args.project, args.build)

                elif args.command == 'build':
                    cli.cmd_build(args.project, args.build)

                elif args.command == 'xdelta':
                    cli.cmd_xdelta(args.project, args.original, args.build)

                elif args.command == 'inject':
                    cli.cmd_inject(args.project, args.emulator, args.build)

                elif args.command == 'clean':
                    cli.cmd_clean(args.project)

                elif args.command == 'validate':
                    cli.cmd_validate(args.project)

                elif args.command == 'list-builds':
                    cli.cmd_list_builds(args.project)

                elif args.command == 'set-build':
                    cli.cmd_set_build(args.project, args.build_name)

                elif args.command == 'info':
                    cli.cmd_info(args.project)

                else:
                    logger.error(f"Unknown command: {args.command}")

            except KeyboardInterrupt:
                logger.info("\nInterrupted by user")
                continue  # Go back to menu
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()
                continue  # Go back to menu

    # Regular, execute command and exit
    else:
        try:
            if args.command == 'compile':
                return cli.cmd_compile(args.project, args.build)

            elif args.command == 'build':
                return cli.cmd_build(args.project, args.build)

            elif args.command == 'xdelta':
                return cli.cmd_xdelta(args.project, args.original, args.build)

            elif args.command == 'inject':
                return cli.cmd_inject(args.project, args.emulator, args.build)

            elif args.command == 'clean':
                return cli.cmd_clean(args.project)

            elif args.command == 'validate':
                return cli.cmd_validate(args.project)

            elif args.command == 'list-builds':
                return cli.cmd_list_builds(args.project)

            elif args.command == 'set-build':
                return cli.cmd_set_build(args.project, args.build_name)

            elif args.command == 'info':
                return cli.cmd_info(args.project)

            else:
                logger.error(f"Unknown command: {args.command}")
                return 1

        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
            return 130
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1

if __name__ == '__main__':
    sys.exit(modtool_main())