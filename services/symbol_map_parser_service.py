# services/symbol_parser_service.py

import os
import re
from typing import List, Dict, Optional, Tuple

class Symbol:
    """Represents a symbol from the memory map"""
    def __init__(self, name: str, address: int, size: int = 0, section: str = "", symbol_type: str = ""):
        self.name = name
        self.address = address
        self.size = size
        self.section = section
        self.symbol_type = symbol_type  # "Game Symbol" or "Mod Symbol"

    def __repr__(self):
        return f"Symbol({self.name} @ 0x{self.address:X}, size={self.size}, type={self.symbol_type})"


class SymbolParserService:
    """Parses .map files to extract symbol information"""
    
    def __init__(self, map_file_path: str):
        self.map_file_path = map_file_path
        self.symbols: List[Symbol] = []
    
    def parse(self) -> List[Symbol]:
        """Parse the map file and return list of symbols"""
        if not os.path.exists(self.map_file_path):
            print(f"Map file not found: {self.map_file_path}")
            return []
        
        try:
            with open(self.map_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to detect map file format
            if self._is_symbol_assignment_format(content):
                print("Detected symbol assignment format (LOAD symbols)")
                self.symbols = self._parse_symbol_assignments(content)
            else:
                print("Detected GNU ld section format")
                self.symbols = self._parse_gnu_map(content)
            
            # Sort by address
            self.symbols.sort(key=lambda s: s.address)
            
            print(f"Parsed {len(self.symbols)} symbols from map file")
            return self.symbols
            
        except Exception as e:
            print(f"Error parsing map file: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _is_symbol_assignment_format(self, content: str) -> bool:
        """Check if map file uses symbol assignment format"""
        # Look for lines like: "0x0000000080001234                game_symbol = 0x80001234"
        pattern = r'^\s*0x[0-9a-fA-F]+\s+\w+\s*=\s*0x[0-9a-fA-F]+'
        return bool(re.search(pattern, content, re.MULTILINE))
    
    def _parse_symbol_assignments(self, content: str) -> List[Symbol]:
        """
        Parse symbol assignment format map files.
        Format 1: 0x0000000080001234                game_symbol = 0x80001234
        Format 2:                0x00000000803f1cbc                has_pressed (within sections)
        """
        symbols = []

        # Pattern 1: Symbol assignments (game symbols from LOAD)
        # Group 1: address, Group 2: symbol name, Group 3: assigned address
        assignment_pattern = r'^\s*0x([0-9a-fA-F]+)\s+(\w+)\s*=\s*0x([0-9a-fA-F]+)'

        # Pattern 2: Section symbols (mod code globals)
        # Heavily indented lines with just address and symbol name
        # Format:                0x00000000803f1cbc                has_pressed
        section_symbol_pattern = r'^\s{16,}0x([0-9a-fA-F]+)\s+(\w+)\s*$'

        lines = content.split('\n')
        current_section = ""

        for line in lines:
            # Track current section for context
            section_match = re.match(r'^\s*(\.\w+)\s+0x[0-9a-fA-F]+', line)
            if section_match:
                current_section = section_match.group(1)

            # Try to match symbol assignment format (game symbols)
            match = re.match(assignment_pattern, line)
            if match:
                # Use the assigned address (Group 3) as the actual address
                address_str = match.group(3)
                symbol_name = match.group(2)

                # Skip internal linker symbols
                if symbol_name.startswith('_'):
                    # Keep it - underscore symbols are often important game variables
                    pass

                # Convert address
                try:
                    address = int(address_str, 16)

                    # Skip zero addresses
                    if address == 0:
                        continue

                    # Create symbol (size is unknown from this format)
                    symbol = Symbol(
                        name=symbol_name,
                        address=address,
                        size=0,  # Unknown in this format
                        section="symbols",
                        symbol_type="Game Symbol"
                    )

                    symbols.append(symbol)

                except ValueError:
                    continue

            # Try to match section symbol format (mod code globals)
            else:
                section_match = re.match(section_symbol_pattern, line)
                if section_match:
                    address_str = section_match.group(1)
                    symbol_name = section_match.group(2)

                    # Skip linker-generated symbols and section names
                    if symbol_name.startswith('_') or symbol_name.startswith('.'):
                        continue

                    # Skip common linker symbols
                    if symbol_name in ['PROVIDE', 'HIDDEN', 'KEEP', 'SORT']:
                        continue

                    # Skip .text section symbols (functions - user only wants data symbols)
                    if current_section == ".text":
                        continue

                    try:
                        address = int(address_str, 16)

                        # Skip zero addresses
                        if address == 0:
                            continue

                        # Create symbol with section info
                        symbol = Symbol(
                            name=symbol_name,
                            address=address,
                            size=0,  # Size usually on the section line, not symbol line
                            section=current_section if current_section else "unknown",
                            symbol_type="Mod Symbol"
                        )

                        symbols.append(symbol)

                    except ValueError:
                        continue

        return symbols
    
    def _parse_gnu_map(self, content: str) -> List[Symbol]:
        """Parse GNU ld format map file (original implementation)"""
        symbols = []
        
        # Pattern: .section     0xADDRESS   0xSIZE symbol_name
        lines = content.split('\n')
        current_section = ""
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Detect section headers
            if line.startswith('.'):
                section_match = re.match(r'^(\.\w+)', line)
                if section_match:
                    current_section = section_match.group(1)
            
            # Parse symbol lines (starts with address)
            addr_match = re.match(r'^\s*0x([0-9a-fA-F]+)\s+0x([0-9a-fA-F]+)\s+(.+)', line)
            if addr_match:
                address = int(addr_match.group(1), 16)
                size = int(addr_match.group(2), 16)
                name_part = addr_match.group(3).strip()
                
                # Extract symbol name (before any file references)
                symbol_name = name_part.split()[0] if name_part else ""
                
                # Skip if it's just a file reference
                if symbol_name.endswith('.o') or '/' in symbol_name or '\\' in symbol_name:
                    continue
                
                # Skip section markers
                if symbol_name.startswith('.') or symbol_name == '*fill*':
                    continue
                
                # Only include symbols in valid address ranges (skip 0x0)
                if address == 0:
                    continue
                
                symbol = Symbol(
                    name=symbol_name,
                    address=address,
                    size=size,
                    section=current_section
                )
                
                symbols.append(symbol)
        
        return symbols
    
    def find_symbol(self, name: str) -> Optional[Symbol]:
        """Find symbol by name (case-insensitive)"""
        name_lower = name.lower()
        for symbol in self.symbols:
            if symbol.name.lower() == name_lower:
                return symbol
        return None
    
    def find_symbols_at_address(self, address: int) -> List[Symbol]:
        """Find all symbols at a specific address"""
        return [s for s in self.symbols if s.address == address]
    
    def find_symbol_containing_address(self, address: int) -> Optional[Symbol]:
        """Find the symbol that contains the given address"""
        for symbol in self.symbols:
            if symbol.size > 0:
                if symbol.address <= address < symbol.address + symbol.size:
                    return symbol
        return None