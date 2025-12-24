# classes/debugger/debug_codecave.py

"""
Debug Codecave Generator

Generates platform-specific assembly for the debug codecave,
which acts as a "holding pattern" when a breakpoint is hit.
"""

import os
from typing import Dict, List


class DebugCodecave:
    """Generates and manages the debug codecave assembly"""

    # Debug data size (relative offsets from data section start)
    # Data section will be placed at END of codecave to avoid overwriting code
    DATA_SIZE_REGISTERS = 128  # 32 MIPS registers * 4 bytes each
    DATA_SIZE_TOTAL = 256  # 128 bytes for registers + flags, rounded up for safety

    def __init__(self, platform: str, codecave_address: int, codecave_size: int):
        """
        Initialize debug codecave generator.

        Args:
            platform: Platform name ("PS1" or "PS2")
            codecave_address: Memory address where codecave starts
            codecave_size: Total size of codecave in bytes
        """
        self.platform = platform
        self.codecave_address = codecave_address
        self.codecave_size = codecave_size

        # Place data section at the END of the codecave to avoid overwriting user code
        # Reserve last 256 bytes for debug data
        data_section_start = codecave_address + codecave_size - self.DATA_SIZE_TOTAL

        # Calculate absolute addresses for data regions
        self.saved_registers_addr = data_section_start
        self.breakpoint_hit_flag_addr = data_section_start + 128  # After registers
        self.resume_address_addr = data_section_start + 132  # After hit flag
        self.step_mode_flag_addr = data_section_start + 136  # After resume addr
        self.current_bp_id_addr = data_section_start + 140  # After step mode

    def generate_mips_codecave(self) -> str:
        """
        Generate MIPS assembly for debug codecave (PS1/PS2).

        Returns:
            Assembly code as string
        """
        # Strip 0x80 prefix for memory addresses (PS1 uses 0x80xxxxxx)
        def strip_prefix(addr):
            if addr >= 0x80000000:
                return addr & 0x00FFFFFF
            return addr

        # Calculate data section start address
        data_section_start = self.codecave_address + self.codecave_size - self.DATA_SIZE_TOTAL

        saved_regs = strip_prefix(self.saved_registers_addr)
        bp_flag = strip_prefix(self.breakpoint_hit_flag_addr)
        resume_addr = strip_prefix(self.resume_address_addr)
        step_mode = strip_prefix(self.step_mode_flag_addr)
        bp_id = strip_prefix(self.current_bp_id_addr)

        asm = f"""# Debug Codecave for {self.platform}
# Generated debug codecave for software breakpoints
# Base address: 0x{self.codecave_address:08X}

.text
.set noreorder

.global debug_codecave_entry
.global debug_resume
.global debug_step_resume

# Entry point when breakpoint is hit
debug_codecave_entry:
    # IMPORTANT: $k0 contains the breakpoint ID (loaded by the jump instruction)
    # We need to save it FIRST before using $k0 for anything else

    # Store breakpoint ID from $k0 to memory
    # We'll use $k1 as scratch to get the address
    lui $k1, 0x{(bp_id >> 16) & 0xFFFF:04X}
    ori $k1, $k1, 0x{bp_id & 0xFFFF:04X}
    sw $k0, 0($k1)  # Save BP ID from $k0 to current_bp_id address

    # Now we can use $k0 for saving registers
    # Load base address for saved registers into $k0
    lui $k0, 0x{(saved_regs >> 16) & 0xFFFF:04X}
    ori $k0, $k0, 0x{saved_regs & 0xFFFF:04X}

    # Save all registers (0-31)
    sw $zero, 0($k0)   # $0 (always 0, but save anyway)
    sw $at, 4($k0)     # $1 (assembler temporary)
    sw $v0, 8($k0)     # $2 (return value)
    sw $v1, 12($k0)    # $3
    sw $a0, 16($k0)    # $4 (argument 0)
    sw $a1, 20($k0)    # $5
    sw $a2, 24($k0)    # $6
    sw $a3, 28($k0)    # $7
    sw $t0, 32($k0)    # $8 (temporary)
    sw $t1, 36($k0)    # $9
    sw $t2, 40($k0)    # $10
    sw $t3, 44($k0)    # $11
    sw $t4, 48($k0)    # $12
    sw $t5, 52($k0)    # $13
    sw $t6, 56($k0)    # $14
    sw $t7, 60($k0)    # $15
    sw $s0, 64($k0)    # $16 (saved)
    sw $s1, 68($k0)    # $17
    sw $s2, 72($k0)    # $18
    sw $s3, 76($k0)    # $19
    sw $s4, 80($k0)    # $20
    sw $s5, 84($k0)    # $21
    sw $s6, 88($k0)    # $22
    sw $s7, 92($k0)    # $23
    sw $t8, 96($k0)    # $24
    sw $t9, 100($k0)   # $25
    # $k0 and $k1 ($26, $27) - kernel reserved, don't save
    sw $gp, 104($k0)   # $28 (global pointer)
    sw $sp, 108($k0)   # $29 (stack pointer)
    sw $fp, 112($k0)   # $30 (frame pointer)
    sw $ra, 116($k0)   # $31 (return address)

    # Set breakpoint hit flag to 1
    lui $k1, 0x{(bp_flag >> 16) & 0xFFFF:04X}
    ori $k1, $k1, 0x{bp_flag & 0xFFFF:04X}
    li $k0, 1
    sw $k0, 0($k1)

debug_loop:
    # Infinite NOP loop - wait for debugger to clear flag
    nop
    nop
    nop
    nop

    # Check if breakpoint flag is still set
    lui $k1, 0x{(bp_flag >> 16) & 0xFFFF:04X}
    ori $k1, $k1, 0x{bp_flag & 0xFFFF:04X}
    lw $k0, 0($k1)

    # If flag != 0, keep looping
    bnez $k0, debug_loop
    nop  # Branch delay slot

    # Flag cleared - check if in step mode
    lui $k1, 0x{(step_mode >> 16) & 0xFFFF:04X}
    ori $k1, $k1, 0x{step_mode & 0xFFFF:04X}
    lw $k0, 0($k1)

    # If step mode, jump to step_resume
    bnez $k0, debug_step_resume
    nop  # Branch delay slot

    # Otherwise, normal resume
    j debug_resume
    nop

debug_resume:
    # Restore all registers
    lui $k0, 0x{(saved_regs >> 16) & 0xFFFF:04X}
    ori $k0, $k0, 0x{saved_regs & 0xFFFF:04X}

    # Restore in reverse order (except $k0, $k1 which we'll do last)
    lw $ra, 116($k0)   # $31
    lw $fp, 112($k0)   # $30
    lw $sp, 108($k0)   # $29
    lw $gp, 104($k0)   # $28
    lw $t9, 100($k0)   # $25
    lw $t8, 96($k0)    # $24
    lw $s7, 92($k0)    # $23
    lw $s6, 88($k0)    # $22
    lw $s5, 84($k0)    # $21
    lw $s4, 80($k0)    # $20
    lw $s3, 76($k0)    # $19
    lw $s2, 72($k0)    # $18
    lw $s1, 68($k0)    # $17
    lw $s0, 64($k0)    # $16
    lw $t7, 60($k0)    # $15
    lw $t6, 56($k0)    # $14
    lw $t5, 52($k0)    # $13
    lw $t4, 48($k0)    # $12
    lw $t3, 44($k0)    # $11
    lw $t2, 40($k0)    # $10
    lw $t1, 36($k0)    # $9
    lw $t0, 32($k0)    # $8
    lw $a3, 28($k0)    # $7
    lw $a2, 24($k0)    # $6
    lw $a1, 20($k0)    # $5
    lw $a0, 16($k0)    # $4
    lw $v1, 12($k0)    # $3
    lw $v0, 8($k0)     # $2
    lw $at, 4($k0)     # $1
    # Don't restore $zero (always 0)

    # Load resume address into $k1
    lui $k1, 0x{(resume_addr >> 16) & 0xFFFF:04X}
    ori $k1, $k1, 0x{resume_addr & 0xFFFF:04X}
    lw $k1, 0($k1)

    # Jump to resume address
    jr $k1
    nop  # Branch delay slot

debug_step_resume:
    # Step mode: execute original instruction(s), then re-breakpoint
    # This is more complex - for now, just resume normally
    # TODO: Implement step-over/step-into logic

    # Clear step mode flag
    lui $k1, 0x{(step_mode >> 16) & 0xFFFF:04X}
    ori $k1, $k1, 0x{step_mode & 0xFFFF:04X}
    sw $zero, 0($k1)

    # For now, just resume (same as debug_resume)
    j debug_resume
    nop

# Data section (reserved space at END of codecave)
# Placed at address: 0x{data_section_start:08X}
.data
.align 4

saved_registers:
    .space {self.DATA_SIZE_REGISTERS}  # 128 bytes for 32 registers (4 bytes each)

breakpoint_hit_flag:
    .word 0

resume_address:
    .word 0

step_mode_flag:
    .word 0

current_breakpoint_id:
    .word 0
"""
        return asm

    def get_memory_layout(self) -> Dict[str, int]:
        """
        Get memory layout information for the debug codecave.

        Returns:
            Dictionary mapping region names to absolute addresses
        """
        return {
            'codecave_base': self.codecave_address,
            'saved_registers': self.saved_registers_addr,
            'breakpoint_hit_flag': self.breakpoint_hit_flag_addr,
            'resume_address': self.resume_address_addr,
            'step_mode_flag': self.step_mode_flag_addr,
            'current_bp_id': self.current_bp_id_addr,
        }

    def get_register_address(self, register_num: int) -> int:
        """
        Get memory address where a specific register is saved.

        Args:
            register_num: MIPS register number (0-31)

        Returns:
            Memory address where register value is stored
        """
        if not (0 <= register_num <= 31):
            raise ValueError(f"Invalid MIPS register number: {register_num}")

        return self.saved_registers_addr + (register_num * 4)

    def generate_breakpoint_jump(self, breakpoint_id: int) -> List[bytes]:
        """
        Generate MIPS instructions to jump to debug codecave.

        This is what gets injected at the breakpoint location.
        We pass the breakpoint ID by loading it into $k0 before jumping.

        Args:
            breakpoint_id: Unique ID for this breakpoint

        Returns:
            List of instruction bytes (8 bytes = 2 instructions)
        """
        # 2-instruction sequence:
        # 1. lui $k0, breakpoint_id    -> Load BP ID into $k0 (upper 16 bits)
        # 2. j debug_codecave_entry    -> Jump to codecave

        # lui $k0, immediate  -> 0x3C1A0000 | (immediate & 0xFFFF)
        # $k0 is register 26 (0x1A)
        lui_instruction = 0x3C1A0000 | (breakpoint_id & 0xFFFF)

        # j target -> 0x08000000 | (target >> 2)
        target_addr = self.codecave_address & 0x0FFFFFFF  # 28-bit address
        j_instruction = 0x08000000 | (target_addr >> 2)

        # Convert to little-endian bytes (MIPS PS1/PS2 is little-endian)
        lui_bytes = lui_instruction.to_bytes(4, byteorder='little')
        j_bytes = j_instruction.to_bytes(4, byteorder='little')

        return [lui_bytes, j_bytes]


# Example usage and testing
if __name__ == "__main__":
    # Test codecave generation
    print("=== Testing Debug Codecave Generator ===\n")

    # PS1 example
    print("PS1 Debug Codecave:")
    print("-" * 60)
    ps1_codecave = DebugCodecave("PS1", 0x80100000)
    asm = ps1_codecave.generate_mips_codecave()
    print(asm)

    print("\n\nMemory Layout:")
    layout = ps1_codecave.get_memory_layout()
    for name, addr in layout.items():
        print(f"  {name:25s} @ 0x{addr:08X}")

    print("\n\nRegister Save Locations:")
    register_names = [
        "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
        "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
        "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
        "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"
    ]

    for i in range(32):
        addr = ps1_codecave.get_register_address(i)
        print(f"  {register_names[i]:6s} (${i:2d}) @ 0x{addr:08X}")

    print("\n\nBreakpoint Jump Instructions:")
    jump_bytes = ps1_codecave.generate_breakpoint_jump(breakpoint_id=1)
    for i, instr_bytes in enumerate(jump_bytes):
        hex_str = ' '.join(f'{b:02X}' for b in instr_bytes)
        instr_val = int.from_bytes(instr_bytes, byteorder='little')
        print(f"  Instruction {i}: {hex_str} (0x{instr_val:08X})")

    # Write to file for testing
    output_path = "debug_codecave_test.s"
    with open(output_path, 'w') as f:
        f.write(asm)
    print(f"\n\nAssembly written to: {output_path}")
    print("You can assemble this with MIPS assembler to verify correctness!")
