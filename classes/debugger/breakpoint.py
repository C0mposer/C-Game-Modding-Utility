# classes/debugger/breakpoint.py

"""
Breakpoint Management

Represents a single software breakpoint with its metadata and state.
"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class BreakpointLocation:
    """Location information for a breakpoint"""
    source_file: str      # Absolute path to C source file
    line_number: int      # Line number in source (1-based)
    assembly_address: int # MIPS assembly address where breakpoint is set

    def __repr__(self):
        return f"BreakpointLocation({self.source_file}:{self.line_number} @ 0x{self.assembly_address:08X})"


class Breakpoint:
    """
    Represents a single software breakpoint.

    A breakpoint consists of:
    - Location: source file, line number, assembly address
    - State: enabled/disabled, hit count
    - Original instructions: saved before injection
    - Injection data: jump to debug codecave
    """

    def __init__(self, bp_id: int, location: BreakpointLocation):
        """
        Initialize a breakpoint.

        Args:
            bp_id: Unique breakpoint ID (1-based)
            location: Source location and assembly address
        """
        self.bp_id = bp_id
        self.location = location

        # State
        self.enabled = False
        self.hit_count = 0
        self.is_injected = False

        # Original instructions (saved before injection)
        self.original_instructions: Optional[bytes] = None

        # Injection data (jump to debug codecave)
        self.injected_instructions: Optional[bytes] = None

    def __repr__(self):
        state = "enabled" if self.enabled else "disabled"
        injected = "injected" if self.is_injected else "not injected"
        return f"Breakpoint({self.bp_id}, {self.location}, {state}, {injected}, hits={self.hit_count})"

    def set_original_instructions(self, instructions: bytes):
        """
        Save the original instructions before injection.

        Args:
            instructions: Original instruction bytes (8 bytes for 2 MIPS instructions)
        """
        if len(instructions) != 8:
            raise ValueError(f"Expected 8 bytes for 2 MIPS instructions, got {len(instructions)}")
        self.original_instructions = instructions

    def set_injected_instructions(self, instructions: bytes):
        """
        Set the injected instructions (jump to debug codecave).

        Args:
            instructions: Injected instruction bytes (8 bytes for j + nop)
        """
        if len(instructions) != 8:
            raise ValueError(f"Expected 8 bytes for 2 MIPS instructions, got {len(instructions)}")
        self.injected_instructions = instructions

    def mark_injected(self):
        """Mark this breakpoint as successfully injected into game memory"""
        self.is_injected = True

    def mark_removed(self):
        """Mark this breakpoint as removed from game memory"""
        self.is_injected = False

    def increment_hit_count(self):
        """Increment the hit count when breakpoint is triggered"""
        self.hit_count += 1

    def enable(self):
        """Enable this breakpoint"""
        self.enabled = True

    def disable(self):
        """Disable this breakpoint"""
        self.enabled = False

    def get_file_offset(self, section_base_vma: int, section_file_offset: int) -> int:
        """
        Calculate file offset from assembly address.

        Args:
            section_base_vma: Base VMA of the .text section (e.g., 0x00000000)
            section_file_offset: File offset of the .text section (e.g., 0x1000)

        Returns:
            File offset where breakpoint should be injected
        """
        # Strip 0x80 prefix if present (PS1/PS2 memory addresses)
        address = self.location.assembly_address
        if address >= 0x80000000:
            address = address & 0x00FFFFFF

        # Calculate offset within section
        offset_in_section = address - section_base_vma

        # Add section's file offset
        file_offset = section_file_offset + offset_in_section

        return file_offset


class BreakpointManager:
    """
    Manages all breakpoints for the debugging session.

    Handles:
    - Adding/removing breakpoints
    - Enabling/disabling breakpoints
    - Finding breakpoints by location or ID
    - Managing breakpoint ID allocation
    """

    def __init__(self, max_breakpoints: int = 20):
        """
        Initialize the breakpoint manager.

        Args:
            max_breakpoints: Maximum number of simultaneous breakpoints
        """
        self.max_breakpoints = max_breakpoints
        self.breakpoints: List[Breakpoint] = []
        self._next_id = 1

    def add_breakpoint(self, location: BreakpointLocation) -> Optional[Breakpoint]:
        """
        Add a new breakpoint at the specified location.

        Args:
            location: Source file, line, and assembly address

        Returns:
            The created Breakpoint, or None if max breakpoints reached
        """
        # Check if we've reached the limit
        if len(self.breakpoints) >= self.max_breakpoints:
            return None

        # Check if breakpoint already exists at this location
        existing = self.find_by_location(location.source_file, location.line_number)
        if existing:
            return existing

        # Create new breakpoint
        bp = Breakpoint(self._next_id, location)
        self._next_id += 1

        self.breakpoints.append(bp)
        return bp

    def remove_breakpoint(self, bp_id: int) -> bool:
        """
        Remove a breakpoint by ID.

        Args:
            bp_id: Breakpoint ID to remove

        Returns:
            True if removed, False if not found
        """
        bp = self.find_by_id(bp_id)
        if bp:
            self.breakpoints.remove(bp)
            return True
        return False

    def find_by_id(self, bp_id: int) -> Optional[Breakpoint]:
        """
        Find a breakpoint by its ID.

        Args:
            bp_id: Breakpoint ID

        Returns:
            Breakpoint if found, None otherwise
        """
        for bp in self.breakpoints:
            if bp.bp_id == bp_id:
                return bp
        return None

    def find_by_location(self, source_file: str, line_number: int) -> Optional[Breakpoint]:
        """
        Find a breakpoint by source location.

        Args:
            source_file: Absolute path to source file
            line_number: Line number (1-based)

        Returns:
            Breakpoint if found, None otherwise
        """
        for bp in self.breakpoints:
            if (bp.location.source_file == source_file and
                bp.location.line_number == line_number):
                return bp
        return None

    def find_by_address(self, address: int) -> Optional[Breakpoint]:
        """
        Find a breakpoint by assembly address.

        Args:
            address: Assembly address

        Returns:
            Breakpoint if found, None otherwise
        """
        for bp in self.breakpoints:
            if bp.location.assembly_address == address:
                return bp
        return None

    def get_all_enabled(self) -> List[Breakpoint]:
        """Get all enabled breakpoints"""
        return [bp for bp in self.breakpoints if bp.enabled]

    def get_all_injected(self) -> List[Breakpoint]:
        """Get all injected breakpoints"""
        return [bp for bp in self.breakpoints if bp.is_injected]

    def clear_all(self):
        """Remove all breakpoints"""
        self.breakpoints.clear()
        self._next_id = 1

    def __len__(self):
        """Return number of breakpoints"""
        return len(self.breakpoints)

    def __iter__(self):
        """Iterate over all breakpoints"""
        return iter(self.breakpoints)
