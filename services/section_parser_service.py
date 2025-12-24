# services/section_parser_service.py

import os
import subprocess
from typing import List, Dict, Optional, Tuple
from functions.verbose_print import verbose_print
from collections import deque

class SectionInfo:
    """Represents a single section in an executable"""
    def __init__(self, section_type: str, file_offset: int, mem_start: int, 
                 mem_end: int, size: int):
        self.section_type = section_type  # "text", "data", etc.
        self.file_offset = file_offset
        self.mem_start = mem_start
        self.mem_end = mem_end
        self.size = size
        self.offset_diff = mem_start - file_offset
    
    def contains_address(self, memory_address: int) -> bool:
        """Check if this section contains the given memory address"""
        return self.mem_start <= memory_address < self.mem_end
    
    def calculate_file_offset(self, memory_address: int) -> Optional[int]:
        """Calculate file offset for a memory address in this section"""
        # Handle addresses with 0x80 prefix
        if memory_address >= 0x80000000:
            memory_address = memory_address & 0x00FFFFFF
        
        if not self.contains_address(memory_address):
            return None
        return memory_address - self.offset_diff
        
    def __repr__(self):
        return (f"Section({self.section_type}, "
                f"mem=0x{self.mem_start:X}-0x{self.mem_end:X}, "
                f"file=0x{self.file_offset:X}, "
                f"diff=0x{self.offset_diff:X})")


class SectionParserService:
    """Parse executable section information for accurate offset calculation"""
    
    @staticmethod
    def parse_executable_sections(exe_path: str, platform: str) -> List[SectionInfo]:
        """
        Parse all sections from an executable file.
        Returns list of SectionInfo objects.
        """
        if platform in ["Gamecube", "Wii"]:
            return SectionParserService.parse_dol_sections(exe_path)
        elif platform == "PS2":
            return SectionParserService.parse_ps2_sections(exe_path)
        elif platform == "PS1":
            return SectionParserService.parse_ps1_sections(exe_path)
        else:
            return []
    
    @staticmethod
    def parse_dol_sections(dol_path: str) -> List[SectionInfo]:
        """
        Parse all sections from DOL file using doltool.
        Returns list of SectionInfo objects.
        """
        tool_dir = os.getcwd()
        doltool_path = os.path.join(tool_dir, "prereq", "doltool", "doltool.exe")
        
        if not os.path.exists(doltool_path):
            print(f"Warning: doltool not found at {doltool_path}")
            return []
        
        try:
            result = subprocess.run(
                [doltool_path, "-i", dol_path],
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tool_dir,
                timeout=10
            )
            
            if result.returncode != 0:
                print(f"doltool failed: {result.stderr}")
                return []
            
            sections = []
            
            # Parse each section line
            # Format: "Text Section  1:  Offset=000004A0  Address=800034A0  Size=003B0B00"
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                if 'Section' not in line or ':' not in line:
                    continue
                
                try:
                    # Split and parse
                    parts = line.split()
                    
                    section_type = parts[0].lower()  # "Text" or "Data"
                    
                    # Extract hex values
                    offset_hex = None
                    address_hex = None
                    size_hex = None
                    
                    for part in parts:
                        if part.startswith('Offset='):
                            offset_hex = part.split('=')[1]
                        elif part.startswith('Address='):
                            address_hex = part.split('=')[1]
                        elif part.startswith('Size='):
                            size_hex = part.split('=')[1]
                    
                    if not all([offset_hex, address_hex, size_hex]):
                        continue
                    
                    file_offset = int(offset_hex, 16)
                    mem_address = int(address_hex, 16)
                    size = int(size_hex, 16)
                    
                    # Remove 0x80 prefix from memory address
                    if address_hex.upper().startswith('80'):
                        mem_address = int('0x' + address_hex[2:], 16)
                    
                    section = SectionInfo(
                        section_type=section_type,
                        file_offset=file_offset,
                        mem_start=mem_address,
                        mem_end=mem_address + size,
                        size=size
                    )
                    
                    sections.append(section)
                    
                except (ValueError, IndexError) as e:
                    print(f"Could not parse DOL section line: {line}")
                    continue
            
            verbose_print(f"Parsed {len(sections)} DOL sections from {os.path.basename(dol_path)}")
            return sections
            
        except subprocess.TimeoutExpired:
            print("doltool timed out")
            return []
        except Exception as e:
            print(f"Error parsing DOL sections: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def parse_ps2_sections(elf_path: str) -> List[SectionInfo]:
        """Parse all sections from PS2 ELF using ee-objdump"""
        tool_dir = os.getcwd()
        objdump_path = os.path.join(tool_dir, "prereq", "PS2ee", "bin", "ee-objdump.exe")
        
        if not os.path.exists(objdump_path):
            print(f"Warning: ee-objdump not found at {objdump_path}")
            return []
        
        try:
            result = subprocess.run(
                [objdump_path, elf_path, "-x"],
                shell=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tool_dir,
                timeout=10
            )
            
            if "Idx Name" not in result.stdout:
                print("Could not parse objdump output")
                return []
            
            sections = []
            
            # Parse section table
            lines = result.stdout.split("Idx Name")[1].split('\n')
            
            for line in lines[1:]:  # Skip header
                line = line.strip()
                if not line or line.startswith('Idx'):
                    continue
                
                parts = line.split()
                
                #print("Before:")
                print(parts)
                # Deal with the situation where Name doesn't exist.
                if len(parts) > 1 and parts[1][0].isnumeric(): # Check if the first character in the string is a number
                    parts = ["No Section Name"] + parts # Shift entire list over
                #print("After:")
                print(parts)
                # Format: Idx Name Size VMA LMA FileOff Algn
                # or: Idx Name Size VMA FileOff Algn
                if len(parts) >= 6:
                    try:
                        section_name = parts[1]
                        print("NAME " + section_name)
                        size = int(parts[2], 16)
                        print("SIZE " + str(size))
                        vma = int(parts[3], 16)

                        # Determine file offset based on format
                        if len(parts) >= 7:
                            # Format with LMA: Idx Name Size VMA LMA FileOff Algn
                            file_off = int(parts[5], 16)
                        else:
                            # Format without LMA: Idx Name Size VMA FileOff Algn
                            file_off = int(parts[4], 16)
                        
                        # Skip zero-size sections
                        if size == 0:
                            continue
                        
                        # Determine section type from name
                        section_type = "unknown"
                        if ".text" in section_name:
                            section_type = "text"
                        elif ".data" in section_name or ".rodata" in section_name:
                            section_type = "data"
                        elif ".bss" in section_name:
                            section_type = "bss"
                        
                        section = SectionInfo(
                            section_type=section_type,
                            file_offset=file_off,
                            mem_start=vma,
                            mem_end=vma + size,
                            size=size
                        )
                        
                        sections.append(section)
                        
                    except (ValueError, IndexError) as e:
                        continue
            
            verbose_print(f"Parsed {len(sections)} PS2 sections from {os.path.basename(elf_path)}")
            return sections
            
        except subprocess.TimeoutExpired:
            print("ee-objdump timed out")
            return []
        except Exception as e:
            print(f"Error parsing PS2 sections: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def parse_ps1_sections(exe_path: str) -> List[SectionInfo]:
        """
        PS1 executables have a simple structure - one section starting at 0x800.
        The file offset is always 0x800 bytes from the memory address.
        """
        try:
            # PS1 executables are simple: everything after 0x800 header
            file_size = os.path.getsize(exe_path)
            
            # PS1 loads at 0x80000000, file starts at 0x800
            section = SectionInfo(
                section_type="text",
                file_offset=0x800,
                mem_start=0x800,
                mem_end=0x800 + (file_size - 0x800),
                size=file_size - 0x800
            )
            
            return [section]
            
        except Exception as e:
            print(f"Error parsing PS1 sections: {e}")
            return []
    
    @staticmethod
    def find_section_for_address(sections: List[SectionInfo], memory_address: int) -> Optional[SectionInfo]:
        """Find the section containing the given memory address"""
        for section in sections:
            if section.contains_address(memory_address):
                return section
        return None
    
    @staticmethod
    def calculate_file_offset(sections: List[SectionInfo], memory_address: int) -> Optional[int]:
        """Calculate file offset for a memory address using section map"""
        # IMPORTANT: Handle PS1/PS2 addresses that start with 0x80
        # If address > 0x80000000, strip the 0x80 prefix to match section format
        if memory_address >= 0x80000000:
            memory_address = memory_address & 0x00FFFFFF  # Remove 0x80 prefix
        
        section = SectionParserService.find_section_for_address(sections, memory_address)
        if section:
            return section.calculate_file_offset(memory_address)
        return None