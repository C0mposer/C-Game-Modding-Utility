# gui/gui_assembly_viewer.py

import dearpygui.dearpygui as dpg
import os
import subprocess
import re
from typing import Dict, List, Optional, Tuple
from classes.project_data.project_data import ProjectData

class AssemblyFunction:
    """Represents a parsed assembly function"""
    def __init__(self, name: str, address: str, section: str, instructions: List[Tuple[str, str, str]]):
        self.name = name
        self.address = address
        self.section = section
        self.instructions = instructions  # [(address, hex_code, instruction), ...]

class AssemblyViewerService:
    """Handles objdump parsing and assembly display"""
    
    # Objdump paths for each platform
    OBJDUMP_PATHS = {
        "PS1": "prereq/PS1mips/bin/mips-objdump.exe",
        "PS2": "prereq/PS2ee/bin/ee-objdump.exe",
        "Gamecube": "prereq/devkitPPC/bin/ppc-objdump.exe",
        "Wii": "prereq/devkitPPC/bin/ppc-objdump.exe",
        "N64": "prereq/N64mips/bin/mips64-elf-objdump.exe"
    }
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
        self.tool_dir = os.getcwd()
        self.functions: Dict[str, AssemblyFunction] = {}
    
    def get_objdump_path(self) -> Optional[str]:
        """Get objdump path for current platform"""
        platform = self.project_data.GetCurrentBuildVersion().GetPlatform()
        relative_path = self.OBJDUMP_PATHS.get(platform)
        
        if not relative_path:
            return None
        
        full_path = os.path.join(self.tool_dir, relative_path)
        if not os.path.exists(full_path):
            print(f"Objdump not found: {full_path}")
            return None
        
        return full_path
    
    def run_objdump(self) -> Optional[str]:
        """Run objdump on the compiled ELF file"""
        objdump_path = self.get_objdump_path()
        if not objdump_path:
            return None
        
        # Get ELF file path
        project_folder = self.project_data.GetProjectFolder()
        elf_path = os.path.join(project_folder, '.config', 'output', 'object_files', 'MyMod.elf')
        
        if not os.path.exists(elf_path):
            print(f"ELF file not found: {elf_path}")
            return None
        
        try:
            print(f"Running objdump on {elf_path}...")
            result = subprocess.run(
                [objdump_path, elf_path, '-d'],
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.tool_dir,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"Objdump failed: {result.stderr}")
                return None
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            print("Objdump timed out")
            return None
        except Exception as e:
            print(f"Objdump error: {e}")
            return None
    
    def parse_objdump_output(self, output: str) -> Dict[str, AssemblyFunction]:
        """Parse objdump output into function objects"""
        functions = {}
        
        lines = output.split('\n')
        current_section = "unknown"
        current_function = None
        current_address = None
        current_function_section = "unknown"  # Track section for current function
        current_instructions = []
        
        # Patterns
        section_pattern = re.compile(r'^Disassembly of section (\.\w+):')
        function_pattern = re.compile(r'^([0-9a-fA-F]+) <(.+)>:')
        # More flexible instruction pattern for both MIPS and PPC
        instruction_pattern = re.compile(r'^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F\s]+?)\s{2,}(.+)$')
        # Pattern to detect likely data (starts with . or looks like disassembled data)
        data_directive_pattern = re.compile(r'^\s*\.')
        
        for line in lines:
            # Check for section header (comes BEFORE functions)
            section_match = section_pattern.match(line)
            if section_match:
                current_section = section_match.group(1)
                continue
            
            # Check for function header
            func_match = function_pattern.match(line)
            if func_match:
                func_name = func_match.group(2)
                
                # Skip compiler-generated labels (not real functions, just markers)
                # Common patterns: $L, $LM, $LC, .L, etc.
                if func_name.startswith('$L') or func_name.startswith('.L'):
                    # Don't treat this as a new function, just continue parsing
                    continue
                
                # This is a real function - save previous function with ITS section
                if current_function and current_instructions:
                    functions[current_function] = AssemblyFunction(
                        name=current_function,
                        address=current_address,
                        section=current_function_section,
                        instructions=current_instructions
                    )
                
                # Start new function - capture current section for THIS function
                current_address = func_match.group(1)
                current_function = func_name
                current_function_section = current_section  # Save section for this function
                current_instructions = []
                continue
            
            # Check for instruction
            inst_match = instruction_pattern.match(line)
            if inst_match and current_function:
                addr = inst_match.group(1)
                hex_code = inst_match.group(2).strip()  # Strip whitespace from hex
                instruction = inst_match.group(3)
                
                # Stop parsing if we hit data directives
                if data_directive_pattern.match(instruction):
                    # We've hit data, save current function and stop
                    if current_instructions:
                        functions[current_function] = AssemblyFunction(
                            name=current_function,
                            address=current_address,
                            section=current_function_section,
                            instructions=current_instructions
                        )
                    current_function = None
                    current_instructions = []
                    continue
                
                current_instructions.append((addr, hex_code, instruction))
        
        # Don't forget last function
        if current_function and current_instructions:
            functions[current_function] = AssemblyFunction(
                name=current_function,
                address=current_address,
                section=current_function_section,
                instructions=current_instructions
            )
        
        print(f"Parsed {len(functions)} function(s)")
        return functions


def show_assembly_viewer_window(sender, app_data, project_data: ProjectData):
    """Show the assembly viewer window"""
    WINDOW_TAG = "assembly_viewer_window"
    
    if dpg.does_item_exist(WINDOW_TAG):
        dpg.show_item(WINDOW_TAG)
        return
    
    # Calculate centered position for 1024x768 viewport
    window_width = 900
    window_height = 650
    viewport_width = 1024
    viewport_height = 768
    pos_x = (viewport_width - window_width) // 2 - 8
    pos_y = (viewport_height - window_height) // 2 - 30

    with dpg.window(
        label="Assembly Viewer",
        tag=WINDOW_TAG,
        width=window_width,
        height=window_height,
        pos=(pos_x, pos_y),
        on_close=lambda: dpg.delete_item(WINDOW_TAG)
    ):
        # Top toolbar
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Refresh",
                callback=lambda: _refresh_assembly_view(project_data)
            )
            dpg.add_spacer(width=10)
            dpg.add_text("Sort by:")
            dpg.add_combo(
                tag=f"{WINDOW_TAG}_sort_order",
                items=["Section", "Alphabetical", "Instruction Count"],
                default_value="Section",
                width=150,
                callback=lambda: _update_function_list_order()
            )
            dpg.add_spacer(width=10)
            dpg.add_text("Filter:")
            dpg.add_input_text(
                tag=f"{WINDOW_TAG}_filter",
                hint="Search functions...",
                width=200,
                callback=lambda s, d: _filter_functions(d)
            )
            dpg.add_spacer(width=10)
            dpg.add_text("", tag=f"{WINDOW_TAG}_status", color=(150, 150, 150))
        
        dpg.add_separator()
        dpg.add_spacer(height=5)
        
        # Main content - side by side
        with dpg.group(horizontal=True):
            # Left side - function list
            with dpg.child_window(width=250, height=550):
                dpg.add_text("Functions", color=(100, 150, 255))
                dpg.add_separator()
                dpg.add_listbox(
                    tag=f"{WINDOW_TAG}_function_list",
                    items=[],
                    callback=lambda s, d: _on_function_selected(d, project_data),
                    width=-1,
                    num_items=35
                )

            dpg.add_spacer(width=10)

            # Right side - assembly display
            with dpg.child_window(width=-1, height=550):
                dpg.add_text("Assembly Code", color=(100, 150, 255), tag=f"{WINDOW_TAG}_asm_title")
                dpg.add_separator()
                
                # Assembly display area
                with dpg.child_window(tag=f"{WINDOW_TAG}_asm_display", border=False):
                    dpg.add_text("Select a function to view assembly...", 
                               tag=f"{WINDOW_TAG}_asm_placeholder",
                               color=(150, 150, 150))
    
    # Initial load
    _refresh_assembly_view(project_data)


def _refresh_assembly_view(project_data: ProjectData):
    """Refresh assembly view by running objdump"""
    WINDOW_TAG = "assembly_viewer_window"
    
    dpg.set_value(f"{WINDOW_TAG}_status", "Running objdump...")
    
    # Create service and run objdump
    service = AssemblyViewerService(project_data)
    output = service.run_objdump()
    
    if not output:
        dpg.set_value(f"{WINDOW_TAG}_status", "❌ Failed to run objdump")
        dpg.configure_item(f"{WINDOW_TAG}_function_list", items=["(objdump failed)"])
        return
    
    # Parse output
    functions = service.parse_objdump_output(output)
    
    if not functions:
        dpg.set_value(f"{WINDOW_TAG}_status", "No functions found")
        dpg.configure_item(f"{WINDOW_TAG}_function_list", items=["(no functions)"])
        return
    
    # Store functions globally for callbacks
    global _asm_viewer_functions
    _asm_viewer_functions = functions
    
    # Update function list with current sort order
    _update_function_list_order()
    
    dpg.set_value(f"{WINDOW_TAG}_status", f"Loaded {len(functions)} function(s)")


def _update_function_list_order():
    """Update function list based on selected sort order"""
    WINDOW_TAG = "assembly_viewer_window"
    
    if '_asm_viewer_functions' not in globals():
        return
    
    sort_order = dpg.get_value(f"{WINDOW_TAG}_sort_order")
    functions = _asm_viewer_functions
    
    if sort_order == "Alphabetical":
        function_names = sorted(functions.keys())
    elif sort_order == "Instruction Count":
        # Sort by instruction count, most first
        function_names = sorted(functions.keys(), key=lambda k: len(functions[k].instructions), reverse=True)
    else:  # Section (default)
        # Sort by section, then by address within section
        function_names = sorted(functions.keys(), key=lambda k: (functions[k].section, int(functions[k].address, 16)))
    
    dpg.configure_item(f"{WINDOW_TAG}_function_list", items=function_names)
    
    # Auto-select first function
    if function_names:
        dpg.set_value(f"{WINDOW_TAG}_function_list", function_names[0])
        _on_function_selected(function_names[0], None)


def _filter_functions(search_text: str):
    """Filter function list based on search text"""
    WINDOW_TAG = "assembly_viewer_window"
    
    if '_asm_viewer_functions' not in globals():
        return
    
    search_lower = search_text.lower()
    functions = _asm_viewer_functions
    
    # Get sort order
    sort_order = dpg.get_value(f"{WINDOW_TAG}_sort_order")
    
    if not search_text:
        # Show all with current sort order
        if sort_order == "Alphabetical":
            function_names = sorted(functions.keys())
        elif sort_order == "Instruction Count":
            function_names = sorted(functions.keys(), key=lambda k: len(functions[k].instructions), reverse=True)
        else:  # Section
            function_names = sorted(functions.keys(), key=lambda k: (functions[k].section, int(functions[k].address, 16)))
    else:
        # Filter first
        filtered = [name for name in functions.keys() if search_lower in name.lower()]
        
        # Then sort
        if sort_order == "Alphabetical":
            function_names = sorted(filtered)
        elif sort_order == "Instruction Count":
            function_names = sorted(filtered, key=lambda k: len(functions[k].instructions), reverse=True)
        else:  # Section
            function_names = sorted(filtered, key=lambda k: (functions[k].section, int(functions[k].address, 16)))
    
    dpg.configure_item(f"{WINDOW_TAG}_function_list", items=function_names)
    
    # Update status
    total = len(functions)
    shown = len(function_names)
    dpg.set_value(f"{WINDOW_TAG}_status", f"Showing {shown} of {total} function(s)")


def _on_function_selected(function_name: str, project_data: ProjectData):
    """Display selected function's assembly"""
    WINDOW_TAG = "assembly_viewer_window"
    
    if '_asm_viewer_functions' not in globals():
        return
    
    func = _asm_viewer_functions.get(function_name)
    if not func:
        return
    
    # Update title
    dpg.set_value(f"{WINDOW_TAG}_asm_title", 
                  f"Disassembly - {func.name} (0x{func.address})")
    
    # Clear display
    _clear_asm_display()
    
    # Render assembly
    _render_assembly(func)


def _clear_asm_display():
    """Clear assembly display area"""
    WINDOW_TAG = "assembly_viewer_window"
    
    if dpg.does_item_exist(f"{WINDOW_TAG}_asm_display"):
        children = dpg.get_item_children(f"{WINDOW_TAG}_asm_display", slot=1)
        if children:
            for child in children:
                if dpg.does_item_exist(child):
                    dpg.delete_item(child)


def _render_assembly(func: AssemblyFunction):
    """Render assembly code with syntax highlighting"""
    WINDOW_TAG = "assembly_viewer_window"
    
    # Colors
    COLOR_ADDRESS = (150, 150, 200, 255)
    COLOR_HEX = (180, 180, 100, 255)
    COLOR_INSTRUCTION = (200, 200, 200, 255)
    COLOR_REGISTER = (150, 200, 150, 255)
    COLOR_IMMEDIATE = (200, 150, 150, 255)
    COLOR_LABEL = (150, 180, 255, 255)
    
    with dpg.group(parent=f"{WINDOW_TAG}_asm_display"):
        # Function header
        instruction_count = len(func.instructions)
        # Each instruction is 4 bytes on MIPS and PowerPC architectures
        byte_count = instruction_count * 4

        with dpg.group(horizontal=True):
            dpg.add_text(f"Section: ", color=(150, 150, 150))
            dpg.add_text(func.section, color=COLOR_LABEL)
            dpg.add_text(f" | Instructions: ", color=(150, 150, 150))
            dpg.add_text(str(instruction_count), color=COLOR_LABEL)
            dpg.add_text(f" | Bytes: ", color=(150, 150, 150))
            dpg.add_text(f"{byte_count} (0x{byte_count:X})", color=COLOR_LABEL)

        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Assembly instructions
        for addr, hex_code, instruction in func.instructions:
            with dpg.group(horizontal=True):
                # Address (fixed width)
                dpg.add_text(f"{addr}:", color=COLOR_ADDRESS)
                
                # Hex code (fixed width)
                dpg.add_text(f"  {hex_code:8s}", color=COLOR_HEX)
                
                # Parse and highlight instruction
                _render_instruction(instruction)
        
        dpg.add_spacer(height=20)


def _clean_symbol_offsets(instruction: str) -> str:
    """
    Clean up symbol references with offsets from objdump output.

    Example:
        "jal 411a80<gCreateLightGem+0x16ed00>" -> "jal 411a80 <unknown_symbol>"
        "jal 0x52024 <exact_func>" -> "jal 0x52024 <exact_func>" (keeps exact matches)

    Args:
        instruction: The instruction string from objdump

    Returns:
        Cleaned instruction with offset-based symbols replaced with <unknown_symbol>
    """
    # Pattern to match: address (with or without 0x) followed by <symbol + offset>
    # We want to replace the <...> part with <unknown_symbol> if it contains a '+'
    import re

    # Match pattern like: "411a80<func_name+0x678>" or "0x12345 <func_name + 0x678>"
    # Handles addresses with or without 0x prefix, with or without space before <
    pattern = r'((?:0x)?[0-9a-fA-F]+)\s*<([^>]+)>'

    def replace_func(match):
        address = match.group(1)
        symbol_part = match.group(2)

        # If the symbol contains '+', it's an offset from an unrelated function
        # Replace with <unknown_symbol> for consistency and to keep blue coloring
        if '+' in symbol_part:
            return f"{address} <unknown_symbol>"
        else:
            # It's an exact symbol match, keep it
            return match.group(0)  # Return the whole match unchanged

    return re.sub(pattern, replace_func, instruction)


def _render_instruction(instruction: str):
    """Render a single instruction with basic syntax highlighting"""
    COLOR_INSTRUCTION = (200, 200, 200, 255)
    COLOR_REGISTER = (150, 200, 150, 255)
    COLOR_IMMEDIATE = (200, 150, 150, 255)
    COLOR_LABEL = (150, 180, 255, 255)

    # Clean up symbol references with offsets (e.g., "0x52024 <func + 0x20504>" -> "0x52024")
    # Keep exact symbol matches (e.g., "0x52024 <exact_func>" stays as is)
    instruction = _clean_symbol_offsets(instruction)

    # Split instruction into parts
    parts = instruction.split()
    
    if not parts:
        dpg.add_text("  (empty)", color=(150, 150, 150))
        return
    
    # First part is the instruction mnemonic
    mnemonic = parts[0]
    dpg.add_text(f"  {mnemonic:8s}", color=COLOR_INSTRUCTION)
    
    # Rest are operands
    if len(parts) > 1:
        operands = ' '.join(parts[1:])
        
        # Simple highlighting
        tokens = re.split(r'([,$()]+)', operands)
        
        for token in tokens:
            if not token:
                continue
            
            if token in [',', '(', ')']:
                # Punctuation
                dpg.add_text(token, color=(150, 150, 150))
            elif token.startswith('$') or token.startswith('r') or token in ['ra', 'sp', 'zero', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3', 't0', 't1', 't2', 't3']:
                # Register
                dpg.add_text(token, color=COLOR_REGISTER)
            elif token.startswith('0x') or token.isdigit() or (token.startswith('-') and token[1:].isdigit()):
                # Immediate value
                dpg.add_text(token, color=COLOR_IMMEDIATE)
            elif '<' in token and '>' in token:
                # Label/function reference
                dpg.add_text(token, color=COLOR_LABEL)
            else:
                # Default
                dpg.add_text(token, color=COLOR_INSTRUCTION)


# Global storage for parsed functions
_asm_viewer_functions = {}