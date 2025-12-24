# Split into multiple files maybe?

from __future__ import annotations
import os
from typing import Dict, List, Optional

from classes.project_data.project_data import ProjectData
from services.game_metadata_service import GameMetadataService
import shutil

_HEX_CHARS = set("0123456789abcdefABCDEF")
GECKO_MAX_LINES = 256


def _is_hex_word(s: str) -> bool:
    """Return True if s is a non-empty hex word (no 0x prefix)."""
    return len(s) > 0 and all(c in _HEX_CHARS for c in s)


def iter_gecko_code_lines(code_text: str):
    """
    Yield 'real' Gecko code lines from a block of text.

    Rules:
      - Skips blank lines.
      - Skips obvious non-code/comment lines:
            * lines starting with '#', '//', ';', '*'
            * title lines like:  "Project - GameCube Gecko"
            * 'Mod' header
      - Strips inline comments like:  XXXXYYYY ZZZZZZZZ  # comment
      - Only yields lines that look like two hex words.
    """
    for raw in code_text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # Full-line comments or obvious non-code
        if line.startswith(("#", "//", ";", "*")):
            continue
        if line.startswith("\"") and line.endswith("\""):
            # e.g. "My Project - GameCube Gecko"
            continue
        if line.lower() == "mod":
            continue

        # Strip inline comments
        for sep in ("#", "//", ";"):
            if sep in line:
                line = line.split(sep, 1)[0].strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 2:
            # Not a standard "XXXXXXXX YYYYYYYY" style line
            continue

        if not (_is_hex_word(parts[0]) and _is_hex_word(parts[1])):
            continue

        # This is a valid Gecko line
        yield line


def count_gecko_code_lines(code_text: str) -> int:
    """Count how many valid Gecko code lines are in the text block."""
    return sum(1 for _ in iter_gecko_code_lines(code_text))


def check_gecko_length(
    code_text: str,
    max_lines: int = GECKO_MAX_LINES,
) -> tuple[bool, int, int]:
    """
    Check if the Gecko code is within the configured line limit.

    Returns:
        (ok, count, max_lines)
        ok = True  -> count <= max_lines
        ok = False -> count  > max_lines
    """
    count = count_gecko_code_lines(code_text)
    return (count <= max_lines), count, max_lines

class CheatCodeService:
    """
    Service for generating cheat code formats from the current project.
    """

    FLAG_ADDR_GC_WII = 0x80002FF0
    FLAG_ADDR_PS2 = 0x00FFFFFF
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
        self.project_folder = project_data.GetProjectFolder()
        # Matches CompilationService: .config/output/bin_files
        self.bin_output_dir = os.path.join(
            self.project_folder, ".config", "output", "bin_files"
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _ensure_bin_dir(self) -> None:
        """Ensure bin_files output dir exists (user must have compiled first)."""
        if not os.path.isdir(self.bin_output_dir):
            raise FileNotFoundError(
                f"Bin output directory not found:\n  {self.bin_output_dir}\n\n"
                "Compile the project first so sections are extracted "
                "to .config/output/bin_files."
            )

    def _iter_injection_targets(self):
        """
        Yield (kind, name, address_hex_str) for all injection targets:

            kind: 'codecave' | 'hook' | 'patch'
            name: section/patch name (used as .bin filename)
            address_hex_str: string as returned by GetMemoryAddress()
        """
        build = self.project_data.GetCurrentBuildVersion()

        for cave in build.GetEnabledCodeCaves():
            yield "codecave", cave.GetName(), cave.GetMemoryAddress()

        for hook in build.GetEnabledHooks():
            yield "hook", hook.GetName(), hook.GetMemoryAddress()

        for patch in build.GetEnabledBinaryPatches():
            yield "patch", patch.GetName(), patch.GetMemoryAddress()

    def _normalize_address(self, addr_str: str) -> int:
        """Convert an address string ('80123456' or '0x80123456') to int."""
        if addr_str is None:
            raise ValueError("Missing memory address for injection target.")

        s = str(addr_str).strip()
        if s.lower().startswith("0x"):
            s = s[2:]

        try:
            return int(s, 16)
        except ValueError:
            return int(s, 10)

    def _read_bin(self, name: str) -> Optional[bytes]:
        """
        Read the compiled binary for a section/patch (name.bin in bin_files).

        Returns:
            bytes or None if file missing.
        """
        path = os.path.join(self.bin_output_dir, f"{name}.bin")
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def _to_le_hex(self, chunk: bytes, width: int) -> str:
        """
        Convert a chunk of bytes to little-endian hex of fixed width,
        matching the old `int(...).to_bytes(...).hex()` pattern.
        """
        if not chunk:
            return ""
        value = int.from_bytes(chunk, byteorder="big")
        return value.to_bytes(width, byteorder="little").hex()

    #
    #! PS1: GameShark-style codes
    #
    def generate_ps1_gameshark(self, ignore_codecaves: bool = False) -> str:
        """
        Generate PS1 GameShark-style codes from the current project.

        Mirrors old convert_to_gameshark_code() semantics, but uses:
            - ProjectData / BuildVersion
            - .config/output/bin_files/<Name>.bin

        Args:
            ignore_codecaves: if True, codecaves are skipped.

        Returns:
            Cheat code block as a string.
        """
        self._ensure_bin_dir()

        chunk_size = 2  # 16-bit writes
        chunks: Dict[str, List[str]] = {}

        for kind, name, addr_str in self._iter_injection_targets():
            if ignore_codecaves and kind == "codecave":
                continue

            data = self._read_bin(name)
            if not data:
                continue

            base_addr = self._normalize_address(addr_str)

            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                le_hex = self._to_le_hex(chunk, chunk_size)
                if not le_hex:
                    continue

                addr_hex = f"{base_addr + i:08X}"
                code_line = f"{addr_hex} {le_hex}"
                chunks.setdefault(name, []).append(code_line)

        build_name = self.project_data.GetCurrentBuildVersionName()
        lines: List[str] = []
        lines.append(f"{build_name} Gameshark Code")

        for code_list in chunks.values():
            lines.extend(code_list)

        return "\n".join(lines) + "\n"
    #
    #! PS2
    #
    def generate_ps2_ps2rd(self, ignore_codecaves: bool = False, include_mastercode: bool = True, one_shot: bool = False) -> str:
        """
        Generate PS2RD-style 32-bit write codes: 20AAAAAA VVVVVVVV

        Args:
            ignore_codecaves: if True, skip codecaves.
            include_mastercode: if True, attempt to include a mastercode
                                (stubbed for now).
            one_shot: if True, wrap all patch writes in a run-once block
                      using a 32-bit conditional on FLAG_ADDR_PS2 == 0,
                      then set FLAG_ADDR_PS2 = 1.

        Returns:
            PS2RD code block as a string.
        """
        self._ensure_bin_dir()

        chunk_size = 4  # 32-bit writes
        chunks: Dict[str, List[str]] = {}

        # --- Build per-section 32-bit constant writes (20AAAAAA VVVVVVVV) ---
        for kind, name, addr_str in self._iter_injection_targets():
            if ignore_codecaves and kind == "codecave":
                continue

            data = self._read_bin(name)
            if not data:
                continue

            base_addr = self._normalize_address(addr_str)

            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                le_hex = self._to_le_hex(chunk, 4)
                if not le_hex:
                    continue

                # PS2RD: left side is 8 hex digits: 2-digit code type + 6-digit address field
                # Use lower 24 bits of the EE address as offset
                addr_field = (base_addr + i) & 0x00FFFFFF
                code_line = f"20{addr_field:06X} {le_hex}"
                chunks.setdefault(name, []).append(code_line)

        build = self.project_data.GetCurrentBuildVersion()

        get_exe = getattr(build, "GetMainExecutable", None)
        exe_name = get_exe() if callable(get_exe) else None

        get_proj_name = getattr(self.project_data, "GetProjectName", None)
        if callable(get_proj_name):
            proj_name = get_proj_name()
        else:
            proj_name = os.path.basename(self.project_folder)

        header_title = proj_name
        if exe_name:
            header_title = f"{proj_name} /ID {exe_name}"

        # Flatten all code lines in a stable order
        all_codes: List[str] = []
        for name in sorted(chunks.keys()):
            all_codes.extend(chunks[name])

        lines: List[str] = []
        lines.append(f"\"{header_title}\"")

        if include_mastercode:
            master = self._get_ps2_mastercode()
            if master:
                lines.append("Mastercode")
                lines.append(f"90{master['address']} {master['opcode']}")
                lines.append("")

        lines.append("Mod")

        # No actual patch codes → just return header
        if not all_codes:
            return "\n".join(lines) + "\n"

        # ---------------------------------------------------------------------
        # Always-on behavior (old behavior)
        # ---------------------------------------------------------------------
        if not one_shot:
            lines.extend(all_codes)
            return "\n".join(lines) + "\n"

        # ---------------------------------------------------------------------
        # Run-once behavior using a flag in EE RAM
        #
        # We use:
        #   Caaaaaaa vvvvvvvv  → if (*(u32*)a == v) { execute all remaining codes }
        #   2aaaaaaa vvvvvvvv  → 32-bit constant write
        #
        # Pattern:
        #   C<flag>   00000000    // if flag == 0, run all remaining codes
        #   (all patch writes)
        #   2<flag>   00000001    // set flag = 1, so condition fails next frame
        # ---------------------------------------------------------------------
        flag_addr = self.FLAG_ADDR_PS2
        flag_field = flag_addr & 0x00FFFFFF  # match how we form 20AAAAAA

        # 1) Conditional on flag == 0
        cond_line = f"C0{flag_field:06X} 00000000"

        # 2) All patch writes
        # 3) Set flag = 1 (32-bit constant write)
        flag_set_line = f"20{flag_field:06X} 00000001"

        lines.append(cond_line)
        lines.extend(all_codes)
        lines.append(flag_set_line)

        return "\n".join(lines) + "\n"

    def _get_ps2_mastercode(self) -> Optional[Dict[str, str]]:
        """
        Placeholder for PS2 mastercode detection.

        Old tool used auto_find_hook_in_ps2_game(just_return=True).
        Here we just return None for now.
        """
        return None

    def generate_ps2_pnach(self, ignore_codecaves: bool = False, one_shot: bool = True) -> str:
        """
        Generate a PCSX2 .pnach file for the current build.
        
        one_shot=True  -> place=0 (apply once at boot/startup)
        one_shot=False -> place=1 (apply every frame / vsync)
        """
        self._ensure_bin_dir()

        # place: 0 = boot-only, 1 = continuous (per vsync)
        place = 0 if one_shot else 1

        patches: Dict[str, List[str]] = {}
        kinds: Dict[str, str] = {}


        # Build patches
        for kind, name, addr_str in self._iter_injection_targets():
            if ignore_codecaves and kind == "codecave":
                continue

            data = self._read_bin(name)
            if not data:
                continue

            kinds[name] = kind
            base_addr = self._normalize_address(addr_str)

            i = 0
            n = len(data)
            while i < n:
                remaining = n - i
                addr = base_addr + i

                # Prefer aligned 32-bit writes, then 16-bit, then 8-bit
                if remaining >= 4 and (addr & 3) == 0:
                    # 32-bit (use same endian correction as PS2RD)
                    chunk = data[i:i + 4]
                    hex_word = self._to_le_hex(chunk, 4).upper()
                    dtype = "word"
                    value_str = hex_word
                    size = 4

                elif remaining >= 2 and (addr & 1) == 0:
                    # 16-bit
                    chunk = data[i:i + 2]
                    hex_half = self._to_le_hex(chunk, 2).upper()
                    dtype = "short"
                    value_str = f"0000{hex_half}"
                    size = 2

                else:
                    # 8-bit
                    chunk = data[i:i + 1]
                    hex_byte = self._to_le_hex(chunk, 1).upper()
                    dtype = "byte"
                    value_str = f"000000{hex_byte}"
                    size = 1

                addr_hex = f"{addr:08X}"
                line = f"patch={place},EE,{addr_hex},{dtype},{value_str}"
                patches.setdefault(name, []).append(line)

                i += size

        # Header
        build = self.project_data.GetCurrentBuildVersion()

        get_proj_name = getattr(self.project_data, "GetProjectName", None)
        proj_name = get_proj_name() if callable(get_proj_name) else os.path.basename(self.project_folder)

        get_serial = getattr(build, "GetGameSerial", None)
        serial = get_serial() if callable(get_serial) else ""

        get_crc = getattr(build, "GetGameCRC", None)
        crc = get_crc() if callable(get_crc) else ""

        build_name = getattr(build, "GetBuildName", lambda: "default")()

        lines: List[str] = []
        group_name = f"{serial} - {proj_name}" if serial else proj_name
        lines.append(f"[{group_name}]")
        lines.append(f"author={proj_name}")

        if crc:
            lines.append(f"description=Auto-generated from C Modding Tool by Composer (CRC {crc})")
        else:
            lines.append(f"description=Auto-generated from C Modding Tool by Composer")
        lines.append("")

        # ---------------------------------------------------------------------
        # Patches
        # ---------------------------------------------------------------------
        if not patches:
            return "\n".join(lines) + "\n"

        for name in sorted(patches.keys()):
            kind = kinds.get(name, "section")
            lines.append(f"// {kind.capitalize()}: {name}")
            lines.extend(patches[name])
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


    #
    #! GameCube/Wii
    #
    def _choose_ar_write_prefix(self, addr: int, size_bytes: int) -> str:
        """
        Choose the first byte of an AR RAM write code based on:
            - address (0x80 vs 0x81)
            - write size (1/2/4 bytes)

            AR convention:
            8-bit writes:
                0x80xxxxxx -> 00rrrrrr
                0x81xxxxxx -> 01rrrrrr

            16-bit writes:
                0x80xxxxxx -> 02rrrrrr
                0x81xxxxxx -> 03rrrrrr

            32-bit writes:
                0x80xxxxxx -> 04rrrrrr
                0x81xxxxxx -> 05rrrrrr
        """
        hi = (addr >> 24) & 0xFF

        # Base for 0x80 region
        if size_bytes == 1:
            base = 0x00
        elif size_bytes == 2:
            base = 0x02
        else:
            base = 0x04

        # 0x81 region uses the "+1" variant (01/03/05)
        if hi == 0x81:
            base += 1

        return f"{base:02X}"

    def _generate_action_replay_ram_writes(self, platform_label: str, ignore_codecaves: bool = False, one_shot: bool = True) -> str:
        """
        Generate Action Replay codes for GC/Wii using only RAM write types:
        If one_shot=True (default), all patch writes are wrapped in:
            - A 32-bit "If Equal, All until.." conditional
            - (all patch writes)
            - A write that sets the flag to 1
            - The "00000000 40000000" terminator
        So the full patch body only runs once per boot.
        """
        self._ensure_bin_dir()

        codes_by_name: Dict[str, List[str]] = {}

        # Build per-section AR write codes
        for kind, name, addr_str in self._iter_injection_targets():
            if ignore_codecaves and kind == "codecave":
                continue

            data = self._read_bin(name)
            if not data:
                continue

            base_addr = self._normalize_address(addr_str)
            i = 0
            n = len(data)

            while i < n:
                remaining = n - i
                addr = base_addr + i
                rrrrrr = addr & 0x00FFFFFF

                if remaining >= 4:
                    # 32-bit write
                    word = int.from_bytes(data[i:i + 4], byteorder="big")
                    prefix = self._choose_ar_write_prefix(addr, 4)
                    code_line = f"{prefix}{rrrrrr:06X} {word:08X}"
                    i += 4

                elif remaining >= 2:
                    # 16-bit write
                    half = int.from_bytes(data[i:i + 2], byteorder="big")
                    prefix = self._choose_ar_write_prefix(addr, 2)
                    code_line = f"{prefix}{rrrrrr:06X} 0000{half:04X}"
                    i += 2

                else:
                    # 8-bit write
                    b = data[i]
                    prefix = self._choose_ar_write_prefix(addr, 1)
                    code_line = f"{prefix}{rrrrrr:06X} 000000{b:02X}"
                    i += 1

                codes_by_name.setdefault(name, []).append(code_line)

        # Build header
        build = self.project_data.GetCurrentBuildVersion()

        get_exe = getattr(build, "GetMainExecutable", None)
        exe_name = get_exe() if callable(get_exe) else None

        get_proj_name = getattr(self.project_data, "GetProjectName", None)
        if callable(get_proj_name):
            proj_name = get_proj_name()
        else:
            proj_name = os.path.basename(self.project_folder)

        title = f"{proj_name} - {platform_label} Action Replay"

        # Flatten all code lines
        all_codes: List[str] = []
        for name in sorted(codes_by_name.keys()):
            all_codes.extend(codes_by_name[name])

        lines: List[str] = []
        lines.append(f"\"{title}\"")
        lines.append("Mod")

        # If no codes at all, we're done
        if not all_codes:
            return "\n".join(lines) + "\n"

        if not one_shot:
            # Original behavior: just dump all codes directly
            lines.extend(all_codes)
            return "\n".join(lines) + "\n"

        # --- One-shot wrapper using a flag in 0x80001800–0x80003000 ---

        flag_addr = self.FLAG_ADDR_GC_WII  # 0x80002FF0
        flag_rrrrrr = flag_addr & 0x00FFFFFF  # 0x002FF0

        # 1) Conditional: If Equal (32-bit), All until.., flag == 0
        #
        # From docs:
        #   Conditional: If Equal, All until.. 32-Bit
        #   8Crrrrrr yyyyyyyy
        # Here: [0x80rrrrrr] == 0
        cond_line = f"8C{flag_rrrrrr:06X} 00000000"

        # 2) All patch writes (what we already generated)
        #
        # 3) Set flag = 1 via a 32-bit RAM write
        prefix_flag = self._choose_ar_write_prefix(flag_addr, 4)  # should be 04 for 0x80xxxxxx
        flag_write_line = f"{prefix_flag}{flag_rrrrrr:06X} 00000001"

        # 4) Terminator for "All until.." block
        terminator_line = "00000000 40000000"

        lines.append(cond_line)
        lines.extend(all_codes)
        lines.append(flag_write_line)
        lines.append(terminator_line)

        return "\n".join(lines) + "\n"

    def generate_gc_action_replay(self, ignore_codecaves: bool = False, one_shot: bool = True) -> str:
        """Generate GameCube Action Replay codes."""
        return self._generate_action_replay_ram_writes(
            platform_label="GameCube",
            ignore_codecaves=ignore_codecaves,
            one_shot=one_shot,
        )

    def generate_wii_action_replay(
        self, ignore_codecaves: bool = False, one_shot: bool = True) -> str:
        """Generate Wii Action Replay codes"""
        return self._generate_action_replay_ram_writes(
            platform_label="Wii",
            ignore_codecaves=ignore_codecaves,
            one_shot=one_shot,
        )
        
    def _gecko_encode_offset(self, addr: int, base_codetype: int) -> tuple[int, int]:
        """Convert a full RAM address into 24-bit offset for Gecko."""
        BA = 0x80000000
        if addr < BA or addr > BA + 0x1FFFFFF:
            raise ValueError(
                f"Gecko: address 0x{addr:08X} out of supported range "
                f"(0x{BA:08X} - 0x{BA + 0x1FFFFFF:08X})"
            )

        off = addr - BA  # 25-bit offset

        if off >= 0x01000000:
            codetype = base_codetype + 1
            offset24 = off - 0x01000000
        else:
            codetype = base_codetype
            offset24 = off

        if offset24 < 0 or offset24 > 0xFFFFFF:
            raise ValueError(
                f"Gecko: encoded offset out of range: 0x{offset24:06X}"
            )

        return codetype, offset24
    
    def _generate_gecko_ram_writes(self, platform_label: str, ignore_codecaves: bool = False, one_shot: bool = True) -> str:
        """
        Generate Gecko codes for GC/Wii using direct RAM write codetypes:
            32-bit write:
                04______ XXXXXXXX   (ba + ______)
                
        We default ba to 0x80000000.

        If one_shot=True:
            Wrap the entire patch in:
                IfEqual 32-bit on FLAG_ADDR_GC_WII == 0
                (all patch writes)
                Write FLAG_ADDR_GC_WII = 1
                Endif
            so the patch body runs only once per boot.
        """

        self._ensure_bin_dir()

        codes_by_name: Dict[str, List[str]] = {}

        # --- Build per-section Gecko write codes ---
        for kind, name, addr_str in self._iter_injection_targets():
            if ignore_codecaves and kind == "codecave":
                continue

            data = self._read_bin(name)
            if not data:
                continue

            base_addr = self._normalize_address(addr_str)
            i = 0
            n = len(data)

            while i < n:
                remaining = n - i
                addr = base_addr + i

                # Prefer aligned, larger writes when possible
                if remaining >= 4 and (addr & 3) == 0:
                    # 32-bit write
                    word = int.from_bytes(data[i:i + 4], byteorder="big")
                    ct, off24 = self._gecko_encode_offset(addr, 0x04)
                    code_line = f"{ct:02X}{off24:06X} {word:08X}"
                    i += 4

                elif remaining >= 2 and (addr & 1) == 0:
                    # 16-bit write, count=0 (one halfword)
                    half = int.from_bytes(data[i:i + 2], byteorder="big")
                    ct, off24 = self._gecko_encode_offset(addr, 0x02)
                    # YYYY = 0000 → write once
                    code_line = f"{ct:02X}{off24:06X} 0000{half:04X}"
                    i += 2

                else:
                    # 8-bit write, count=0 (one byte)
                    b = data[i]
                    ct, off24 = self._gecko_encode_offset(addr, 0x00)
                    # YYYY = 0000, middle byte is 00, last byte is value
                    code_line = f"{ct:02X}{off24:06X} 000000{b:02X}"
                    i += 1

                codes_by_name.setdefault(name, []).append(code_line)

        # --- Build header (same style as AR) ---
        build = self.project_data.GetCurrentBuildVersion()

        get_exe = getattr(build, "GetMainExecutable", None)
        exe_name = get_exe() if callable(get_exe) else None

        get_proj_name = getattr(self.project_data, "GetProjectName", None)
        if callable(get_proj_name):
            proj_name = get_proj_name()
        else:
            proj_name = os.path.basename(self.project_folder)

        title = f"{proj_name} - {platform_label} Gecko"

        # Flatten all code lines
        all_codes: List[str] = []
        for name in sorted(codes_by_name.keys()):
            all_codes.extend(codes_by_name[name])

        lines: List[str] = []
        lines.append(f"\"{title}\"")
        lines.append("Mod")

        if not all_codes:
            return "\n".join(lines) + "\n"

        if not one_shot:
            # Simple always-on variant (original behavior style)
            lines.extend(all_codes)
            return "\n".join(lines) + "\n"

        # ---------------------------------------------------------------------
        # One-shot wrapper using a 32-bit IfEqual on FLAG_ADDR_GC_WII == 0
        # ---------------------------------------------------------------------

        flag_addr = self.FLAG_ADDR_GC_WII  # 0x80002FF0

        # 1) If 32 bits at [ba+offset] == 0 → then codes execute
        #    Codetype: 20______ XXXXXXXX (IfEqual 32-bit)
        ct_if, off_if = self._gecko_encode_offset(flag_addr, 0x20)
        cond_line = f"{ct_if:02X}{off_if:06X} 00000000"

        # 2) All patch writes (gated by the If)
        # 3) Write flag = 1 using 32-bit write
        ct_flag, off_flag = self._gecko_encode_offset(flag_addr, 0x04)
        flag_write = f"{ct_flag:02X}{off_flag:06X} 00000001"

        # 4) Endif (one level) – E2T000VV XXXXYYYY, T=0, VV=1
        endif_line = "E2000001 00000000"

        lines.append(cond_line)
        lines.extend(all_codes)
        lines.append(flag_write)
        lines.append(endif_line)

        return "\n".join(lines) + "\n"
    
    def generate_gc_gecko(self, ignore_codecaves: bool = False, one_shot: bool = True) -> str:
        """
        Generate GameCube Gecko codes for current build."""
        return self._generate_gecko_ram_writes(
            platform_label="GameCube",
            ignore_codecaves=ignore_codecaves,
            one_shot=one_shot,
        )

    def generate_wii_gecko(self,ignore_codecaves: bool = False,one_shot: bool = True) -> str:
        """
        Generate Wii Gecko codes for current build."""
        return self._generate_gecko_ram_writes(
            platform_label="Wii",
            ignore_codecaves=ignore_codecaves,
            one_shot=one_shot,
        )
        

    def generate_wii_riivolution_file_patches(self, ignore_codecaves: bool = False,) -> str:
        """Generate a Riivolution XML that uses File Patch entries for all injection files of the current Wii build."""

        build = self.project_data.GetCurrentBuildVersion()
        platform = (build.GetPlatform() or "").upper()

        if platform not in ("GAMECUBE", "WII"):
            return (
                "Riivolution XML generation is only meaningful for GameCube/Wii builds. \n"
            )

        project_folder = self.project_data.GetProjectFolder()
        if not project_folder:
            raise FileNotFoundError("Project folder not set on ProjectData.")

        get_proj_name = getattr(self.project_data, "GetProjectName", None)
        proj_name = get_proj_name() if callable(get_proj_name) else os.path.basename(project_folder)
        build_name = getattr(build, "GetBuildName", lambda: "default")()

        if platform == "WII":
            game_id = GameMetadataService.get_wii_game_id(build)
        else:
            game_id = GameMetadataService.get_gamecube_game_id(build)

        if not game_id or len(game_id) < 4:
            game_code = ""
            dev_code = ""
            region_char = ""
        else:
            game_code = game_id[:3]
            region_char = game_id[3:4]
            dev_code = game_id[4:6] if len(game_id) >= 6 else ""

        # Prepare Riivolution output folder
        riivo_root = os.path.join(project_folder, "riivolution")
        os.makedirs(riivo_root, exist_ok=True)

        # We keep wiidisc root="/riivolution"
        patch_root_rel = ""  # no extra subdirectory

        # Collect <file> patches based on injection files
        injection_files = build.GetInjectionFiles() or []
        file_entries = []

        for filename in injection_files:
            file_type = build.GetInjectionFileType(filename)  # "disk" or "external"

            disc_name = filename        # name on disc
            external_name = filename    # default external name (may change)

            src_path = None

            if file_type == "disk":
                # Prefer patched_<filename> from build folder
                build_dir = os.path.join(project_folder, "build")
                patched_name = f"patched_{filename}"
                patched_path = os.path.join(build_dir, patched_name)

                if os.path.exists(patched_path):
                    src_path = patched_path
                    external_name = patched_name   # external="patched_main.dol"
                else:
                    # Fallback to original file from game folder
                    src_path = build.FindFileInGameFolder(filename)
                    external_name = filename       # external="main.dol"

            elif file_type == "external":
                # For external files, use stored full path if available
                if hasattr(build, "external_file_full_paths") and filename in build.external_file_full_paths:
                    candidate = build.external_file_full_paths[filename]
                    if os.path.exists(candidate):
                        src_path = candidate

                if not src_path:
                    # Fallback – try to locate on disk like a normal file
                    src_path = build.FindFileInGameFolder(filename)

            # If we still don't have a source file, skip this entry
            if not src_path or not os.path.exists(src_path):
                print(f"[Riivolution] Warning: Could not find source for '{filename}', skipping.")
                continue

            # Destination in project /riivolution folder ROOT
            dest_path = os.path.join(riivo_root, external_name)

            # Copy/overwrite
            try:
                shutil.copy2(src_path, dest_path)
                print(f"[Riivolution] Copied '{src_path}' -> '{dest_path}'")
            except Exception as e:
                print(f"[Riivolution] Failed to copy '{src_path}' -> '{dest_path}': {e}")

            # Build XML attributes
            attrs = [
                f'disc="{disc_name}"',
                f'external="{external_name}"',
            ]

            if file_type == "external":
                attrs.append('create="true"')

            file_entries.append("      <file " + " ".join(attrs) + " />")

        if not file_entries:
            return (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<wiidisc version="1" root="/riivolution">\n'
                '  <!-- No injection files found; nothing to patch. -->\n'
                '</wiidisc>\n'
            )

        # Build XML string
        lines = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<wiidisc version="1" root="/riivolution">')

        if game_code:
            id_attrs = [f'game="{game_code}"']
            if dev_code:
                id_attrs.append(f'developer="{dev_code}"')
            lines.append(f'  <id {" ".join(id_attrs)}>')
            if region_char:
                lines.append(f'    <region type="{region_char}" />')
            lines.append("  </id>")

        lines.append("  <options>")
        lines.append(f'    <section name="{proj_name}">')
        lines.append('      <option id="mod" name="Mod Enable" default="2">')
        lines.append('        <choice name="Disabled" />')
        lines.append('        <choice name="Enabled">')
        lines.append('          <patch id="main" />')
        lines.append("        </choice>")
        lines.append("      </option>")
        lines.append("    </section>")
        lines.append("  </options>")

        lines.append("  <patches>")
        # If patch_root_rel is empty, omit root attribute entirely
        if patch_root_rel:
            lines.append(f'    <patch id="main" root="{patch_root_rel}">')
        else:
            lines.append('    <patch id="main">')
        lines.extend(file_entries)
        lines.append("    </patch>")
        lines.append("  </patches>")

        lines.append("</wiidisc>")

        return "\n".join(lines) + "\n"
