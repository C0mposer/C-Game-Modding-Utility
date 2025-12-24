# services/dwarf_parser_service.py

import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

try:
    from elftools.elf.elffile import ELFFile
    from elftools.dwarf.descriptions import describe_form_class
    from elftools.dwarf.die import DIE
    PYELFTOOLS_AVAILABLE = True
except ImportError:
    PYELFTOOLS_AVAILABLE = False
    print("Warning: pyelftools not installed. DWARF parsing unavailable.")
    print("Install with: pip install pyelftools")


@dataclass
class SourceLine:
    """Represents a single C source line with its assembly address mapping"""
    file_path: str
    line_number: int
    asm_address: int        # Memory address where this line starts
    asm_address_end: int    # Memory address where this line ends (exclusive)
    column: int = 0

    def __repr__(self):
        return f"SourceLine({os.path.basename(self.file_path)}:{self.line_number} @ 0x{self.asm_address:08X}-0x{self.asm_address_end:08X})"


@dataclass
class Variable:
    """Represents a variable (local or global) with debug information"""
    name: str
    type_name: str
    location: str           # "stack:-16", "register:$a0", "address:0x80001234", or "unknown"
    size: int
    is_parameter: bool = False
    address: Optional[int] = None  # Memory address for global variables, None for locals

    def is_global(self) -> bool:
        """Check if this is a global variable (has an address)"""
        return self.address is not None

    def is_local(self) -> bool:
        """Check if this is a local/stack variable"""
        return self.address is None and "stack" in self.location.lower()

    def is_register(self) -> bool:
        """Check if this variable is in a register"""
        return "register" in self.location.lower()

    def __repr__(self):
        if self.address is not None:
            return f"Variable({self.name}: {self.type_name} @ 0x{self.address:08X}, size={self.size})"
        return f"Variable({self.name}: {self.type_name} @ {self.location}, size={self.size})"


@dataclass
class FunctionInfo:
    """Represents a function with debug information"""
    name: str
    start_address: int
    end_address: int
    source_file: str
    line_number: int
    parameters: List[Variable]
    local_variables: List[Variable]

    def __repr__(self):
        return f"Function({self.name} @ 0x{self.start_address:08X}-0x{self.end_address:08X})"


class DWARFParser:
    """Parse DWARF debug information from ELF files"""

    def __init__(self, elf_path: str):
        """
        Initialize DWARF parser for an ELF file.

        Args:
            elf_path: Path to ELF file with debug symbols (-g)
        """
        if not PYELFTOOLS_AVAILABLE:
            raise ImportError("pyelftools is required for DWARF parsing. Install with: pip install pyelftools")

        if not os.path.exists(elf_path):
            raise FileNotFoundError(f"ELF file not found: {elf_path}")

        self.elf_path = elf_path
        self.elf_file = None
        self.dwarf_info = None
        self._line_program_cache: Dict[str, List[SourceLine]] = {}
        self._function_cache: List[FunctionInfo] = []

        # Open ELF file
        try:
            self.elf_file = ELFFile(open(elf_path, 'rb'))

            # Check if DWARF info exists
            if not self.elf_file.has_dwarf_info():
                raise ValueError(f"ELF file has no DWARF debug information: {elf_path}\nCompile with -g flag to generate debug symbols.")

            self.dwarf_info = self.elf_file.get_dwarf_info()

        except Exception as e:
            raise RuntimeError(f"Failed to parse ELF file: {e}")

    def get_line_program(self) -> Dict[str, List[SourceLine]]:
        """
        Extract line number program from DWARF .debug_line section.

        Returns:
            Dictionary mapping source file paths to list of SourceLine objects
        """
        if self._line_program_cache:
            return self._line_program_cache

        line_programs: Dict[str, List[SourceLine]] = {}

        # Iterate through all compilation units
        for cu in self.dwarf_info.iter_CUs():
            # Get line program for this compilation unit
            line_program = self.dwarf_info.line_program_for_CU(cu)
            if line_program is None:
                continue

            # Process line program entries
            prev_entry = None

            for entry in line_program.get_entries():
                # Skip entries with no state
                if entry.state is None:
                    continue

                state = entry.state

                # Get source file
                file_entry = line_program['file_entry'][state.file - 1]
                file_path = file_entry.name.decode('utf-8', errors='ignore')

                # Make file path absolute if possible
                dir_index = file_entry.dir_index
                if dir_index != 0:
                    dir_entry = line_program['include_directory'][dir_index - 1]
                    dir_path = dir_entry.decode('utf-8', errors='ignore')
                    file_path = os.path.join(dir_path, file_path)

                # Normalize path
                file_path = os.path.normpath(file_path)

                # Create SourceLine entry
                # Note: We need to wait for the next entry to determine the end address
                if prev_entry is not None:
                    prev_state = prev_entry.state
                    prev_file = line_program['file_entry'][prev_state.file - 1].name.decode('utf-8', errors='ignore')

                    # Same file: create entry for previous line
                    if prev_file == file_entry.name.decode('utf-8', errors='ignore'):
                        source_line = SourceLine(
                            file_path=file_path,
                            line_number=prev_state.line,
                            asm_address=prev_state.address,
                            asm_address_end=state.address,  # End is start of next line
                            column=prev_state.column
                        )

                        if file_path not in line_programs:
                            line_programs[file_path] = []
                        line_programs[file_path].append(source_line)

                prev_entry = entry

        self._line_program_cache = line_programs
        return line_programs

    def get_source_lines_for_address(self, address: int) -> List[SourceLine]:
        """
        Find C source lines that map to a specific assembly address.

        Args:
            address: Memory address (e.g., 0x80001234)

        Returns:
            List of SourceLine objects containing this address
        """
        line_programs = self.get_line_program()

        matching_lines = []
        for file_path, lines in line_programs.items():
            for line in lines:
                if line.asm_address <= address < line.asm_address_end:
                    matching_lines.append(line)

        return matching_lines

    def get_address_for_line(self, file: str, line_number: int) -> List[int]:
        """
        Find assembly addresses for a C source line.

        Args:
            file: Source file path (can be relative or absolute)
            line_number: Line number in source file

        Returns:
            List of assembly addresses corresponding to this line
        """
        line_programs = self.get_line_program()

        # Normalize input file path
        file_norm = os.path.normpath(file)

        addresses = []

        # Search in all files (handle different path formats)
        for file_path, lines in line_programs.items():
            # Match by basename or full path
            if os.path.basename(file_path) == os.path.basename(file_norm) or file_path == file_norm:
                for line in lines:
                    if line.line_number == line_number:
                        addresses.append(line.asm_address)

        return addresses

    def get_functions(self) -> List[FunctionInfo]:
        """
        Extract function information from DWARF .debug_info section.

        Returns:
            List of FunctionInfo objects
        """
        if self._function_cache:
            return self._function_cache

        functions = []

        # Iterate through all compilation units
        for cu in self.dwarf_info.iter_CUs():
            top_die = cu.get_top_DIE()

            # Recursively find all function DIEs
            self._extract_functions_from_die(top_die, functions)

        self._function_cache = functions
        return functions

    def _extract_functions_from_die(self, die: DIE, functions: List[FunctionInfo]):
        """Recursively extract function information from DIE tree"""

        # Check if this is a function/subprogram
        if die.tag == 'DW_TAG_subprogram':
            try:
                # Get function name
                name = die.attributes.get('DW_AT_name')
                if name:
                    name = name.value.decode('utf-8', errors='ignore')
                else:
                    name = "<unknown>"

                # Get address range
                low_pc = die.attributes.get('DW_AT_low_pc')
                high_pc = die.attributes.get('DW_AT_high_pc')

                if low_pc and high_pc:
                    start_address = low_pc.value

                    # high_pc can be an offset or absolute address
                    if describe_form_class(high_pc.form) == 'constant':
                        end_address = start_address + high_pc.value
                    else:
                        end_address = high_pc.value

                    # Get source file and line
                    decl_file = die.attributes.get('DW_AT_decl_file')
                    decl_line = die.attributes.get('DW_AT_decl_line')

                    source_file = "<unknown>"
                    line_number = 0

                    if decl_file and decl_line:
                        # Resolve file index to file path
                        cu = die.cu
                        line_program = self.dwarf_info.line_program_for_CU(cu)
                        if line_program:
                            file_entry = line_program['file_entry'][decl_file.value - 1]
                            source_file = file_entry.name.decode('utf-8', errors='ignore')

                        line_number = decl_line.value

                    # Extract parameters and local variables
                    parameters = []
                    local_variables = []

                    for child in die.iter_children():
                        if child.tag == 'DW_TAG_formal_parameter':
                            var = self._extract_variable_from_die(child, is_parameter=True)
                            if var:
                                parameters.append(var)
                        elif child.tag == 'DW_TAG_variable':
                            var = self._extract_variable_from_die(child, is_parameter=False)
                            if var:
                                local_variables.append(var)

                    # Create FunctionInfo
                    func_info = FunctionInfo(
                        name=name,
                        start_address=start_address,
                        end_address=end_address,
                        source_file=source_file,
                        line_number=line_number,
                        parameters=parameters,
                        local_variables=local_variables
                    )

                    functions.append(func_info)

            except Exception as e:
                print(f"Warning: Could not parse function DIE: {e}")

        # Recurse through children
        for child in die.iter_children():
            self._extract_functions_from_die(child, functions)

    def _extract_variable_from_die(self, die: DIE, is_parameter: bool) -> Optional[Variable]:
        """Extract variable information from DIE"""
        try:
            # Get variable name
            name = die.attributes.get('DW_AT_name')
            if name:
                name = name.value.decode('utf-8', errors='ignore')
            else:
                return None

            # Get type information
            type_die_offset = die.attributes.get('DW_AT_type')
            type_name = "<unknown>"
            size = 0

            if type_die_offset:
                # Follow type reference
                cu = die.cu
                type_die = cu.get_DIE_from_refaddr(type_die_offset.value + cu.cu_offset)
                type_name = self._get_type_name(type_die)

                # Get size
                byte_size = type_die.attributes.get('DW_AT_byte_size')
                if byte_size:
                    size = byte_size.value

            # Get location (stack offset, register, or address)
            location_attr = die.attributes.get('DW_AT_location')
            location = "unknown"
            address = None

            if location_attr:
                # Parse location expression
                location, address = self._parse_location_expression(location_attr)

            return Variable(
                name=name,
                type_name=type_name,
                location=location,
                size=size,
                is_parameter=is_parameter,
                address=address
            )

        except Exception as e:
            print(f"Warning: Could not parse variable DIE: {e}")
            return None

    def _parse_location_expression(self, location_attr) -> Tuple[str, Optional[int]]:
        """
        Parse DWARF location expression to get variable location.

        Args:
            location_attr: DW_AT_location attribute from DIE

        Returns:
            Tuple of (location_string, address)
            - location_string: "stack:offset", "register:name", "address:0xXXXX", or "unknown"
            - address: Memory address for globals, None for locals/registers
        """
        try:
            # Location can be:
            # 1. exprloc (DWARF4+): bytes of location expression
            # 2. loclistptr: reference to location list
            # 3. block: inline location expression

            # Check if it's a simple expression
            if hasattr(location_attr, 'value'):
                loc_expr = location_attr.value

                # If it's a list of location entries (loclistptr)
                if isinstance(loc_expr, int):
                    # This is a location list offset - would need to parse .debug_loc section
                    # For now, mark as unknown
                    return "unknown", None

                # If it's bytes, parse the expression
                if isinstance(loc_expr, bytes):
                    return self._parse_location_bytes(loc_expr)

            return "unknown", None

        except Exception as e:
            print(f"Warning: Could not parse location expression: {e}")
            return "unknown", None

    def _parse_location_bytes(self, expr: bytes) -> Tuple[str, Optional[int]]:
        """
        Parse DWARF location expression bytes.

        MIPS register mapping:
        - DW_OP_reg4 = $a0 (register 4)
        - DW_OP_reg29 = $sp (register 29)
        - DW_OP_fbreg = offset from frame base (usually $fp)

        Common operations:
        - 0x03 (DW_OP_addr): followed by 4-byte address
        - 0x50-0x6F (DW_OP_reg0-31): register 0-31
        - 0x70-0x8F (DW_OP_breg0-31): register + offset
        - 0x91 (DW_OP_fbreg): frame base + offset (SLEB128)
        """
        if len(expr) == 0:
            return "unknown", None

        op = expr[0]

        # DW_OP_addr (0x03) - Global variable at absolute address
        if op == 0x03:
            if len(expr) >= 5:
                # Read 4-byte little-endian address
                addr = int.from_bytes(expr[1:5], byteorder='little')
                return f"address:0x{addr:08X}", addr

        # DW_OP_reg0 to DW_OP_reg31 (0x50-0x6F) - Variable in register
        elif 0x50 <= op <= 0x6F:
            reg_num = op - 0x50
            reg_name = self._get_mips_register_name(reg_num)
            return f"register:{reg_name}", None

        # DW_OP_breg0 to DW_OP_breg31 (0x70-0x8F) - Register + offset
        elif 0x70 <= op <= 0x8F:
            reg_num = op - 0x70
            reg_name = self._get_mips_register_name(reg_num)

            # Read SLEB128 offset
            if len(expr) > 1:
                offset = self._read_sleb128(expr[1:])
                return f"register:{reg_name}+{offset}", None
            return f"register:{reg_name}", None

        # DW_OP_fbreg (0x91) - Frame base + offset (most common for stack variables)
        elif op == 0x91:
            if len(expr) > 1:
                # Read SLEB128 offset from frame base
                offset = self._read_sleb128(expr[1:])
                # Frame base is usually $fp (register 30)
                return f"stack:{offset}", None
            return "stack:0", None

        # Unknown operation
        return f"unknown:op=0x{op:02X}", None

    def _get_mips_register_name(self, reg_num: int) -> str:
        """Get MIPS register name from DWARF register number"""
        mips_regs = [
            "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
            "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
            "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
            "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"
        ]

        if 0 <= reg_num < len(mips_regs):
            return mips_regs[reg_num]
        return f"$r{reg_num}"

    def _read_sleb128(self, data: bytes) -> int:
        """
        Read a signed LEB128 (Little Endian Base 128) encoded integer.
        Used for offsets in DWARF expressions.
        """
        result = 0
        shift = 0

        for byte in data:
            result |= (byte & 0x7F) << shift
            shift += 7

            if (byte & 0x80) == 0:
                # Sign extend if needed
                if shift < 64 and (byte & 0x40):
                    result |= -(1 << shift)
                break

        return result

    def _get_type_name(self, type_die: DIE) -> str:
        """Get human-readable type name from type DIE"""
        try:
            # Check for direct name
            name_attr = type_die.attributes.get('DW_AT_name')
            if name_attr:
                return name_attr.value.decode('utf-8', errors='ignore')

            # Handle typedef, pointer, const, etc.
            if type_die.tag == 'DW_TAG_pointer_type':
                # Follow pointed-to type
                pointed_type = type_die.attributes.get('DW_AT_type')
                if pointed_type:
                    cu = type_die.cu
                    pointed_die = cu.get_DIE_from_refaddr(pointed_type.value + cu.cu_offset)
                    return self._get_type_name(pointed_die) + "*"
                return "void*"

            if type_die.tag == 'DW_TAG_const_type':
                qualified_type = type_die.attributes.get('DW_AT_type')
                if qualified_type:
                    cu = type_die.cu
                    qualified_die = cu.get_DIE_from_refaddr(qualified_type.value + cu.cu_offset)
                    return "const " + self._get_type_name(qualified_die)

            # Base types
            if type_die.tag == 'DW_TAG_base_type':
                encoding = type_die.attributes.get('DW_AT_encoding')
                byte_size = type_die.attributes.get('DW_AT_byte_size')

                if encoding and byte_size:
                    size = byte_size.value
                    enc = encoding.value

                    # Map DWARF encoding to C type names
                    if enc == 5:  # DW_ATE_signed
                        return {1: "char", 2: "short", 4: "int", 8: "long long"}.get(size, f"int{size*8}_t")
                    elif enc == 7:  # DW_ATE_unsigned
                        return {1: "unsigned char", 2: "unsigned short", 4: "unsigned int", 8: "unsigned long long"}.get(size, f"uint{size*8}_t")
                    elif enc == 4:  # DW_ATE_float
                        return {4: "float", 8: "double"}.get(size, "float")

            return "<unknown>"

        except:
            return "<unknown>"

    def get_global_variables(self) -> List[Variable]:
        """
        Extract global variables from DWARF .debug_info section.

        Returns:
            List of Variable objects for global variables
        """
        global_vars = []

        for cu in self.dwarf_info.iter_CUs():
            top_die = cu.get_top_DIE()

            # Look for global variables at top level
            for child in top_die.iter_children():
                if child.tag == 'DW_TAG_variable':
                    var = self._extract_variable_from_die(child, is_parameter=False)
                    if var:
                        global_vars.append(var)

        return global_vars

    def get_function_at_address(self, address: int) -> Optional[FunctionInfo]:
        """
        Find the function that contains a specific address.

        Args:
            address: Memory address

        Returns:
            FunctionInfo if found, None otherwise
        """
        functions = self.get_functions()

        for func in functions:
            if func.start_address <= address < func.end_address:
                return func

        return None

    def close(self):
        """Close ELF file handle"""
        if self.elf_file and hasattr(self.elf_file, 'stream'):
            self.elf_file.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Example usage:
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python dwarf_parser_service.py <elf_file>")
        sys.exit(1)

    elf_path = sys.argv[1]

    try:
        with DWARFParser(elf_path) as parser:
            print(f"\n=== Parsing {os.path.basename(elf_path)} ===\n")

            # Test line program
            print("Line Number Program:")
            line_programs = parser.get_line_program()
            for file_path, lines in line_programs.items():
                print(f"\n  {file_path}:")
                for line in lines[:5]:  # Show first 5 lines
                    print(f"    {line}")
                if len(lines) > 5:
                    print(f"    ... and {len(lines) - 5} more lines")

            # Test function extraction
            print("\n\nFunctions:")
            functions = parser.get_functions()
            for func in functions[:10]:  # Show first 10 functions
                print(f"  {func}")
                if func.parameters:
                    print(f"    Parameters: {func.parameters}")
                if func.local_variables:
                    print(f"    Locals: {func.local_variables}")

            if len(functions) > 10:
                print(f"  ... and {len(functions) - 10} more functions")

            # Test address lookup
            if functions:
                test_func = functions[0]
                print(f"\n\nTesting address lookup for {test_func.name}:")
                lines = parser.get_source_lines_for_address(test_func.start_address)
                for line in lines:
                    print(f"  {line}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
