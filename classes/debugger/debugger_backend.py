# classes/debugger/debugger_backend.py

"""
Debugger Backend

Core debugging engine that handles:
- Debug codecave injection into first codecave
- Breakpoint injection and management
- Memory polling and state management
- Communication with emulator
"""

import os
import struct
from typing import Optional, Dict, List, Tuple
from enum import Enum

from classes.debugger.breakpoint import Breakpoint, BreakpointManager, BreakpointLocation
from classes.debugger.debug_codecave import DebugCodecave
from services.dwarf_parser_service import DWARFParser, SourceLine
from classes.project_data.build_version import BuildVersion
from classes.project_data.project_data import ProjectData


class DebuggerState(Enum):
    """Current state of the debugger"""
    IDLE = 0           # Not debugging
    RUNNING = 1        # Game running normally
    BREAKPOINT_HIT = 2 # Stopped at breakpoint
    STEPPING = 3       # Executing single step


class DebuggerBackend:
    """
    Core debugging backend.

    Manages the entire debugging system:
    - Injects debug codecave into first codecave
    - Injects/removes breakpoints
    - Polls emulator memory for breakpoint hits
    - Reads variable values from memory
    """

    def __init__(self, project_data: ProjectData):
        """
        Initialize the debugger backend.

        Args:
            project_data: Project data containing build version and codecaves
        """
        self.project_data = project_data
        self.current_build = project_data.GetCurrentBuildVersion()
        self.platform = self.current_build.GetPlatform()

        # Components
        self.breakpoint_manager = BreakpointManager(max_breakpoints=20)
        self.dwarf_parser: Optional[DWARFParser] = None
        self.debug_codecave: Optional[DebugCodecave] = None

        # State
        self.state = DebuggerState.IDLE
        self.is_initialized = False
        self.codecave_injected = False
        self.last_hit_breakpoint: Optional[Breakpoint] = None

        # Debug codecave memory layout (set during initialization)
        self.codecave_base_address: Optional[int] = None
        self.saved_registers_addr: Optional[int] = None
        self.breakpoint_hit_flag_addr: Optional[int] = None
        self.resume_address_addr: Optional[int] = None
        self.step_mode_flag_addr: Optional[int] = None
        self.current_bp_id_addr: Optional[int] = None

        # Memory access (platform-specific)
        self.memory_interface = None  # Will be set based on platform
        self.emulator_manager = None  # Emulator connection manager

        # Cache for ELF/DWARF data
        self.elf_path: Optional[str] = None
        self.source_line_cache: Dict[str, List[SourceLine]] = {}

    def initialize(self) -> Tuple[bool, str]:
        """
        Initialize the debugger backend.

        This must be called before any other operations.
        Sets up:
        - DWARF parser from compiled ELF
        - Debug codecave in first codecave
        - Memory interface for emulator communication

        Returns:
            (success, error_message)
        """
        # Check if platform is supported
        if self.platform not in ["PS1", "PS2"]:
            return False, f"Platform '{self.platform}' not supported for debugging (only PS1/PS2)"

        # Find the ELF file
        self.elf_path = self._find_elf_file()
        if not self.elf_path:
            return False, "Could not find compiled ELF file. Please compile the project first."

        # Parse DWARF debug symbols
        try:
            self.dwarf_parser = DWARFParser(self.elf_path)
            self.source_line_cache = self.dwarf_parser.get_line_program()
        except Exception as e:
            return False, f"Failed to parse DWARF debug symbols: {e}"

        # Get the first codecave
        codecaves = self.current_build.GetCodeCaves()
        if not codecaves or len(codecaves) == 0:
            return False, "No codecaves defined in build version. Debugger requires at least one codecave."

        first_codecave = codecaves[0]
        # Get memory address and size as int (they're stored as strings)
        self.codecave_base_address = first_codecave.GetMemoryAddressAsInt()
        codecave_size = first_codecave.GetSizeAsInt()

        # Create debug codecave generator
        # Data will be placed at END of codecave to avoid overwriting user code
        self.debug_codecave = DebugCodecave(self.platform, self.codecave_base_address, codecave_size)

        # Get memory layout
        layout = self.debug_codecave.get_memory_layout()
        self.saved_registers_addr = layout['saved_registers']
        self.breakpoint_hit_flag_addr = layout['breakpoint_hit_flag']
        self.resume_address_addr = layout['resume_address']
        self.step_mode_flag_addr = layout['step_mode_flag']
        self.current_bp_id_addr = layout['current_bp_id']

        # Initialize memory interface based on platform
        success, error = self._initialize_memory_interface()
        if not success:
            return False, error

        self.is_initialized = True
        return True, ""

    def _find_elf_file(self) -> Optional[str]:
        """
        Find the compiled ELF file in the project.

        Returns:
            Path to ELF file, or None if not found
        """
        project_folder = self.project_data.GetProjectFolder()

        # ELF is always named MyMod.elf in .config/output/object_files/
        elf_path = os.path.join(project_folder, '.config', 'output', 'object_files', 'MyMod.elf')

        if os.path.exists(elf_path):
            return elf_path
        return None

    def _initialize_memory_interface(self) -> Tuple[bool, str]:
        """
        Initialize the memory interface for emulator communication.

        Returns:
            (success, error_message)
        """
        # Import emulator connection manager
        from services.emulator_connection_manager import get_emulator_manager

        # Get the manager
        self.emulator_manager = get_emulator_manager()

        # Check if emulator is already connected
        connection = self.emulator_manager.get_current_connection()
        if connection:
            self.memory_interface = connection
            return True, ""

        # Not connected - that's okay, we'll connect when user sets breakpoints
        return True, ""

    def inject_debug_codecave(self) -> Tuple[bool, str]:
        """
        Add debug codecave to project build (compile-time injection).

        The debug codecave provides the breakpoint handler that runs when breakpoints are hit.
        This is compiled into the game, then at RUNTIME we inject jump instructions to it.

        Returns:
            (success, error_message)
        """
        if not self.is_initialized:
            return False, "Debugger not initialized. Call initialize() first."

        # Generate debug codecave assembly
        try:
            asm_code = self.debug_codecave.generate_mips_codecave()
        except Exception as e:
            return False, f"Failed to generate debug codecave assembly: {e}"

        # Get first codecave
        codecaves = self.current_build.GetCodeCaves()
        first_codecave = codecaves[0]

        # Create debug codecave assembly file in project's asm directory
        project_folder = self.project_data.GetProjectFolder()
        asm_dir = os.path.join(project_folder, 'asm')

        # Create asm directory if it doesn't exist
        if not os.path.exists(asm_dir):
            os.makedirs(asm_dir)

        debug_codecave_file = os.path.join(asm_dir, 'debug_codecave.s')

        # Always regenerate the file (in case we've updated the debug codecave logic)
        # Write debug codecave assembly
        try:
            with open(debug_codecave_file, 'w') as f:
                f.write(asm_code)
        except Exception as e:
            return False, f"Failed to write debug codecave file: {e}"

        # Add to first codecave's code files (if not already there)
        rel_path = os.path.relpath(debug_codecave_file, project_folder)
        existing_files = first_codecave.GetCodeFilesPaths()

        if rel_path not in existing_files:
            first_codecave.AddCodeFile(rel_path)
            message = "Debug codecave added to project. Please rebuild to include it."
        else:
            message = "Debug codecave updated. Please rebuild to update."

        self.codecave_injected = True
        self.debug_codecave_file = debug_codecave_file
        return True, message

    def remove_debug_codecave(self) -> Tuple[bool, str]:
        """
        Remove the debug codecave assembly from the first codecave.

        Returns:
            (success, error_message)
        """
        if not self.is_initialized:
            return False, "Debugger not initialized"

        # Get first codecave
        codecaves = self.current_build.GetCodeCaves()
        first_codecave = codecaves[0]

        project_folder = self.project_data.GetProjectFolder()
        debug_codecave_file = os.path.join(project_folder, 'asm', 'debug_codecave.s')

        # Delete debug codecave file if it exists
        if os.path.exists(debug_codecave_file):
            try:
                os.remove(debug_codecave_file)
            except Exception as e:
                return False, f"Failed to remove debug codecave file: {e}"

        # Remove from first codecave's code files
        rel_path = os.path.relpath(debug_codecave_file, project_folder)
        code_files = first_codecave.GetCodeFilesPaths()
        if rel_path in code_files:
            code_files.remove(rel_path)

        self.codecave_injected = False
        return True, ""

    def add_breakpoint(self, source_file: str, line_number: int) -> Tuple[Optional[Breakpoint], str]:
        """
        Add a breakpoint at the specified source location.

        Args:
            source_file: Absolute path to source file
            line_number: Line number (1-based)

        Returns:
            (Breakpoint or None, error_message)
        """
        if not self.is_initialized:
            return None, "Debugger not initialized"

        # Get assembly addresses for this line
        addresses = self.dwarf_parser.get_address_for_line(source_file, line_number)

        if not addresses:
            return None, f"No assembly code found for {os.path.basename(source_file)}:{line_number}"

        # Use the first address
        # TODO: Handle multiple addresses (inlined functions, optimizations)
        assembly_address = addresses[0]

        # Create breakpoint location
        location = BreakpointLocation(source_file, line_number, assembly_address)

        # Add to manager
        bp = self.breakpoint_manager.add_breakpoint(location)

        if not bp:
            return None, "Maximum breakpoints reached (20)"

        return bp, ""

    def remove_breakpoint(self, bp_id: int) -> Tuple[bool, str]:
        """
        Remove a breakpoint by ID.

        Args:
            bp_id: Breakpoint ID

        Returns:
            (success, error_message)
        """
        # Find breakpoint
        bp = self.breakpoint_manager.find_by_id(bp_id)
        if not bp:
            return False, f"Breakpoint {bp_id} not found"

        # If injected, remove from memory first
        if bp.is_injected:
            success, error = self._remove_breakpoint_from_memory(bp)
            if not success:
                return False, error

        # Remove from manager
        self.breakpoint_manager.remove_breakpoint(bp_id)
        return True, ""

    def enable_breakpoint(self, bp_id: int) -> Tuple[bool, str]:
        """
        Enable a breakpoint and inject it into game memory.

        Args:
            bp_id: Breakpoint ID

        Returns:
            (success, error_message)
        """
        bp = self.breakpoint_manager.find_by_id(bp_id)
        if not bp:
            return False, f"Breakpoint {bp_id} not found"

        # Enable the breakpoint
        bp.enable()

        # Inject into memory
        success, error = self._inject_breakpoint_to_memory(bp)
        if not success:
            bp.disable()
            return False, error

        return True, ""

    def disable_breakpoint(self, bp_id: int) -> Tuple[bool, str]:
        """
        Disable a breakpoint and remove it from game memory.

        Args:
            bp_id: Breakpoint ID

        Returns:
            (success, error_message)
        """
        bp = self.breakpoint_manager.find_by_id(bp_id)
        if not bp:
            return False, f"Breakpoint {bp_id} not found"

        # Remove from memory
        if bp.is_injected:
            success, error = self._remove_breakpoint_from_memory(bp)
            if not success:
                return False, error

        # Disable the breakpoint
        bp.disable()
        return True, ""

    def _inject_breakpoint_to_memory(self, bp: Breakpoint) -> Tuple[bool, str]:
        """
        Inject a breakpoint into game memory at runtime.

        Replaces the instruction at the breakpoint address with a jump
        to the debug codecave.

        Args:
            bp: Breakpoint to inject

        Returns:
            (success, error_message)
        """
        # Get or establish emulator connection
        connection = self.emulator_manager.get_current_connection()
        if not connection:
            # Try to scan and connect
            emulators = self.emulator_manager.scan_emulators()
            if not emulators:
                return False, "No running emulator found. Please start the game first."

            # Try to connect to first available emulator
            handle, main_ram, kernel32 = self.emulator_manager.get_or_establish_connection(emulators[0])
            if not handle:
                return False, f"Failed to connect to emulator: {emulators[0]}"

            connection = self.emulator_manager.get_current_connection()

        # Import memory utilities
        from services.memory_utils import read_process_memory, write_process_memory

        # Calculate actual memory address (main_ram + offset)
        target_address = bp.location.assembly_address
        if target_address >= 0x80000000:
            # PS1/PS2: Strip 0x80 prefix
            target_address = target_address & 0x00FFFFFF

        # Physical address in emulator memory
        physical_address = connection.main_ram + target_address

        # Read original instructions (8 bytes for j + nop)
        original_bytes = read_process_memory(connection.handle, physical_address, 8)
        if not original_bytes:
            return False, f"Failed to read memory at 0x{target_address:08X}"

        print(f"[Debugger] Read original bytes: {original_bytes.hex()}")
        bp.set_original_instructions(original_bytes)

        # Generate jump instructions
        jump_bytes = self.debug_codecave.generate_breakpoint_jump(bp.bp_id)
        injected_instructions = jump_bytes[0] + jump_bytes[1]  # j + nop (8 bytes)

        bp.set_injected_instructions(injected_instructions)

        # Write jump to memory
        success = write_process_memory(connection.handle, physical_address, injected_instructions)
        if not success:
            return False, f"Failed to write breakpoint to memory at 0x{target_address:08X}"

        bp.mark_injected()
        return True, ""

    def _remove_breakpoint_from_memory(self, bp: Breakpoint) -> Tuple[bool, str]:
        """
        Remove a breakpoint from game memory at runtime.

        Restores the original instructions.

        Args:
            bp: Breakpoint to remove

        Returns:
            (success, error_message)
        """
        print(f"[Debugger] Removing breakpoint ID={bp.bp_id}, injected={bp.is_injected}, has_original={bp.original_instructions is not None}")

        if not bp.original_instructions:
            # If not injected, just mark as removed
            if not bp.is_injected:
                bp.mark_removed()
                return True, "Breakpoint was not injected, removed from list"
            return False, "No original instructions saved (breakpoint may not have been properly injected)"

        # Get emulator connection
        connection = self.emulator_manager.get_current_connection()
        if not connection:
            # Can't remove if not connected, but mark as removed anyway
            bp.mark_removed()
            return True, "Emulator not connected, breakpoint removed from list only"

        # Import memory utilities
        from services.memory_utils import write_process_memory

        # Calculate actual memory address
        target_address = bp.location.assembly_address
        if target_address >= 0x80000000:
            target_address = target_address & 0x00FFFFFF

        physical_address = connection.main_ram + target_address

        # Restore original instructions
        success = write_process_memory(connection.handle, physical_address, bp.original_instructions)
        if not success:
            return False, f"Failed to restore original instructions at 0x{target_address:08X}"

        bp.mark_removed()
        return True, ""

    def poll_breakpoint_hit(self) -> Optional[Breakpoint]:
        """
        Poll the emulator memory to check if a breakpoint was hit.

        Returns:
            Breakpoint that was hit, or None if no breakpoint hit
        """
        if not self.is_initialized:
            return None

        # Get emulator connection
        connection = self.emulator_manager.get_current_connection()
        if not connection:
            return None

        # Import memory utilities
        from services.memory_utils import read_process_memory

        # Calculate physical address of breakpoint_hit_flag
        flag_address = self.breakpoint_hit_flag_addr
        if flag_address >= 0x80000000:
            flag_address = flag_address & 0x00FFFFFF

        physical_flag_addr = connection.main_ram + flag_address

        # Read the flag (4 bytes)
        flag_bytes = read_process_memory(connection.handle, physical_flag_addr, 4)
        if not flag_bytes:
            return None

        # Check if flag is set (non-zero)
        flag_value = int.from_bytes(flag_bytes, byteorder='little')
        if flag_value == 0:
            return None  # No breakpoint hit

        print(f"[Debugger] Breakpoint flag detected! Value: {flag_value}")

        # Read the current breakpoint ID
        bp_id_address = self.current_bp_id_addr
        if bp_id_address >= 0x80000000:
            bp_id_address = bp_id_address & 0x00FFFFFF

        physical_bp_id_addr = connection.main_ram + bp_id_address
        bp_id_bytes = read_process_memory(connection.handle, physical_bp_id_addr, 4)
        if not bp_id_bytes:
            return None

        bp_id = int.from_bytes(bp_id_bytes, byteorder='little')

        # Find the breakpoint
        bp = self.breakpoint_manager.find_by_id(bp_id)
        if bp:
            # Update state
            self.state = DebuggerState.BREAKPOINT_HIT
            bp.hit_count += 1
            self.last_hit_breakpoint = bp

        return bp

    def resume_execution(self) -> Tuple[bool, str]:
        """
        Resume execution after hitting a breakpoint.

        Clears the breakpoint_hit_flag so the debug codecave exits its loop.

        Returns:
            (success, error_message)
        """
        if self.state != DebuggerState.BREAKPOINT_HIT:
            return False, "Not currently stopped at a breakpoint"

        # Get emulator connection
        connection = self.emulator_manager.get_current_connection()
        if not connection:
            return False, "Emulator not connected"

        # Import memory utilities
        from services.memory_utils import write_process_memory

        # Calculate physical address of breakpoint_hit_flag
        flag_address = self.breakpoint_hit_flag_addr
        if flag_address >= 0x80000000:
            flag_address = flag_address & 0x00FFFFFF

        physical_flag_addr = connection.main_ram + flag_address

        # Clear the flag (write 0)
        zero_bytes = (0).to_bytes(4, byteorder='little')
        success = write_process_memory(connection.handle, physical_flag_addr, zero_bytes)

        if not success:
            return False, "Failed to clear breakpoint flag"

        self.state = DebuggerState.RUNNING
        self.last_hit_breakpoint = None
        return True, ""

    def step_over(self) -> Tuple[bool, str]:
        """
        Step over the current line (execute until next line in same function).

        Returns:
            (success, error_message)
        """
        if self.state != DebuggerState.BREAKPOINT_HIT:
            return False, "Not currently stopped at a breakpoint"

        # TODO: Implement step-over logic
        # Set step_mode_flag, clear breakpoint_hit_flag

        return False, "Step-over not yet implemented"

    def get_register_values(self) -> Dict[str, int]:
        """
        Get all register values when stopped at a breakpoint.

        Returns:
            Dictionary mapping register names to values
        """
        if self.state != DebuggerState.BREAKPOINT_HIT:
            return {}

        # Get emulator connection
        connection = self.emulator_manager.get_current_connection()
        if not connection:
            return {}

        # Import memory utilities
        from services.memory_utils import read_process_memory

        # Calculate physical address of saved registers
        regs_address = self.saved_registers_addr
        if regs_address >= 0x80000000:
            regs_address = regs_address & 0x00FFFFFF

        physical_regs_addr = connection.main_ram + regs_address

        # Read all 32 registers (128 bytes total)
        regs_bytes = read_process_memory(connection.handle, physical_regs_addr, 128)
        if not regs_bytes:
            return {}

        # Parse register values (32 registers * 4 bytes each)
        register_names = [
            "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
            "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
            "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
            "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"
        ]

        register_values = {}
        for i, name in enumerate(register_names):
            offset = i * 4
            value = int.from_bytes(regs_bytes[offset:offset+4], byteorder='little')
            register_values[name] = value

        return register_values

    def get_variable_values(self) -> Dict[str, Tuple[str, int, str, bool, bool]]:
        """
        Get all visible variables and their values when stopped at a breakpoint.

        Returns:
            Dictionary mapping variable name to (type_name, value, location, is_parameter, is_global)
            Empty dict if not at breakpoint or error
        """
        if self.state != DebuggerState.BREAKPOINT_HIT:
            return {}

        if not self.dwarf_parser:
            return {}

        connection = self.emulator_manager.get_current_connection()
        if not connection:
            return {}

        try:
            # Get the current breakpoint (the last one that was hit)
            if not self.last_hit_breakpoint:
                return {}

            # Get register values (we need $fp for stack variables)
            registers = self.get_register_values()
            if not registers:
                return {}

            # Get the function context at this address
            func_info = self.dwarf_parser.get_function_at_address(self.last_hit_breakpoint.location.assembly_address)

            variable_values = {}

            # Read local variables and parameters
            if func_info:
                all_locals = func_info.parameters + func_info.local_variables

                for var in all_locals:
                    value = self._read_variable_value(var, registers, connection)
                    if value is not None:
                        # (type_name, value, location, is_parameter, is_global)
                        variable_values[var.name] = (var.type_name, value, var.location, var.is_parameter, False)

            # Read global variables
            global_vars = self.dwarf_parser.get_global_variables()
            for var in global_vars:
                value = self._read_variable_value(var, registers, connection)
                if value is not None:
                    # (type_name, value, location, is_parameter, is_global)
                    variable_values[var.name] = (var.type_name, value, var.location, False, True)

            return variable_values

        except Exception as e:
            print(f"[Debugger] Error reading variable values: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _read_variable_value(self, var, registers: Dict[str, int], connection) -> Optional[int]:
        """
        Read the value of a variable from memory or registers.

        Args:
            var: Variable object from DWARF parser
            registers: Dictionary of current register values
            connection: EmulatorConnection object

        Returns:
            Variable value as integer, or None if cannot be read
        """
        from services.memory_utils import read_process_memory

        try:
            # Parse location string
            location = var.location

            # Global variable at absolute address
            if location.startswith("address:"):
                addr_str = location.split(":")[1]
                addr = int(addr_str, 16)

                # Strip 0x80 prefix and read from physical address
                if addr >= 0x80000000:
                    addr = addr & 0x00FFFFFF
                physical_addr = connection.main_ram + addr

                # Read the value (assuming 4 bytes for now)
                value_bytes = read_process_memory(connection.handle, physical_addr, 4)
                if value_bytes:
                    return int.from_bytes(value_bytes, byteorder='little')

            # Variable in register
            elif location.startswith("register:"):
                reg_name = location.split(":")[1].split("+")[0]  # Handle "register:$a0" or "register:$sp+8"

                if reg_name in registers:
                    reg_value = registers[reg_name]

                    # If there's an offset (e.g., "register:$sp+8")
                    if "+" in location:
                        offset = int(location.split("+")[1])
                        addr = reg_value + offset

                        # Read from memory at that address
                        if addr >= 0x80000000:
                            addr = addr & 0x00FFFFFF
                        physical_addr = connection.main_ram + addr

                        value_bytes = read_process_memory(connection.handle, physical_addr, 4)
                        if value_bytes:
                            return int.from_bytes(value_bytes, byteorder='little')
                    else:
                        # Variable is directly in the register
                        return reg_value

            # Stack variable (offset from frame pointer)
            elif location.startswith("stack:"):
                offset_str = location.split(":")[1]
                offset = int(offset_str)

                # Get frame pointer ($fp = register 30)
                fp_value = registers.get("$fp", 0)
                if fp_value == 0:
                    # Try $sp if $fp not set
                    fp_value = registers.get("$sp", 0)

                if fp_value != 0:
                    # Calculate stack address
                    stack_addr = fp_value + offset

                    # Strip 0x80 prefix and read from physical address
                    if stack_addr >= 0x80000000:
                        stack_addr = stack_addr & 0x00FFFFFF
                    physical_addr = connection.main_ram + stack_addr

                    # Read the value (assuming 4 bytes)
                    value_bytes = read_process_memory(connection.handle, physical_addr, 4)
                    if value_bytes:
                        return int.from_bytes(value_bytes, byteorder='little')

            return None

        except Exception as e:
            print(f"[Debugger] Error reading variable {var.name}: {e}")
            return None

    def shutdown(self) -> Tuple[bool, str]:
        """
        Shutdown the debugger.

        Removes all breakpoints and cleans up.

        Returns:
            (success, error_message)
        """
        # Remove all injected breakpoints
        for bp in self.breakpoint_manager.get_all_injected():
            self._remove_breakpoint_from_memory(bp)

        # Clear all breakpoints
        self.breakpoint_manager.clear_all()

        # Remove debug codecave
        if self.codecave_injected:
            self.remove_debug_codecave()

        self.state = DebuggerState.IDLE
        self.is_initialized = False

        return True, ""
