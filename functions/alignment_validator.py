# functions/alignment_validator.py

def get_platform_alignment(platform: str, injection_type: str = "codecave") -> int:
    """
    Get required memory alignment for a platform and injection type.

    Args:
        platform: Platform name (PS1, PS2, N64, GC, Wii, etc.)
        injection_type: Type of injection - "codecave", "hook", or "patch"

    Returns:
        Required alignment in bytes (0, 4, or 8)
        0 means no alignment requirement
    """
    platform_upper = platform.upper()
    injection_type_lower = injection_type.lower()

    # PS2 specific alignment requirements
    if platform_upper == "PS2":
        if injection_type_lower == "codecave":
            return 8  # Codecaves need 8-byte alignment
        elif injection_type_lower == "hook":
            return 4  # Hooks need 4-byte alignment
        elif injection_type_lower == "patch":
            return 0  # Patches have no alignment requirement

    # N64: 8-byte alignment for codecaves
    if platform_upper == "N64":
        if injection_type_lower == "codecave":
            return 8
        else:
            return 4  # Default for hooks/patches

    # PS1, GC, Wii: 4-byte alignment for codecaves
    if platform_upper in ["PS1", "GC", "WII"]:
        if injection_type_lower == "codecave":
            return 4
        else:
            return 4  # Same for hooks/patches

    # Default to 4-byte alignment for unknown platforms (codecaves)
    # and no requirement for patches
    if injection_type_lower == "patch":
        return 0
    return 4


def validate_address_alignment(address_str: str, platform: str, injection_type: str = "codecave") -> tuple[bool, str]:
    """
    Validate that a memory address meets platform alignment requirements.

    Args:
        address_str: Hexadecimal address string (with or without 0x prefix)
        platform: Platform name
        injection_type: Type of injection - "codecave", "hook", or "patch"

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if address is properly aligned
        - error_message: Empty string if valid, error description if invalid
    """
    if not address_str:
        return True, ""  # Empty is handled elsewhere

    try:
        # Remove 0x prefix and 80 prefix if present
        clean_addr = address_str.lower().replace("0x", "").strip()
        if clean_addr.startswith("80") and len(clean_addr) > 2:
            clean_addr = clean_addr[2:]

        # Convert to integer
        addr_int = int(clean_addr, 16)

        # Get required alignment
        required_alignment = get_platform_alignment(platform, injection_type)

        # If no alignment requirement (0), always valid
        if required_alignment == 0:
            return True, ""

        # Check if address is aligned
        if addr_int % required_alignment != 0:
            return False, f"Address must be {required_alignment}-byte aligned for {platform.upper()} {injection_type}s"

        return True, ""

    except ValueError:
        return False, "Invalid hexadecimal address"


def suggest_aligned_address(address_str: str, platform: str, injection_type: str = "codecave", direction: str = "down") -> str:
    """
    Suggest the nearest aligned address.

    Args:
        address_str: Hexadecimal address string
        platform: Platform name
        injection_type: Type of injection - "codecave", "hook", or "patch"
        direction: "down" to round down, "up" to round up

    Returns:
        Suggested aligned address as hex string (without 0x prefix)
    """
    try:
        # Remove 0x prefix and 80 prefix if present
        had_80_prefix = False
        clean_addr = address_str.lower().replace("0x", "").strip()
        if clean_addr.startswith("80") and len(clean_addr) > 2:
            had_80_prefix = True
            clean_addr = clean_addr[2:]

        addr_int = int(clean_addr, 16)
        alignment = get_platform_alignment(platform, injection_type)

        # If no alignment requirement, return as-is
        if alignment == 0:
            return address_str

        # Calculate aligned address
        if direction == "up":
            aligned = ((addr_int + alignment - 1) // alignment) * alignment
        else:
            aligned = (addr_int // alignment) * alignment

        # Format back to hex
        result = f"{aligned:X}"
        if had_80_prefix:
            result = "80" + result

        return result

    except ValueError:
        return address_str


def show_alignment_error_dialog(address_str: str, platform: str, injection_type: str = "codecave"):
    """
    Show a dialog with alignment error and suggestions.

    Args:
        address_str: The invalid address
        platform: Platform name
        injection_type: Type of injection - "codecave", "hook", or "patch"
    """
    from gui import gui_messagebox as messagebox

    alignment = get_platform_alignment(platform, injection_type)

    # If no alignment requirement, this shouldn't be called, but handle it
    if alignment == 0:
        return

    suggestion_down = suggest_aligned_address(address_str, platform, injection_type, "down")
    suggestion_up = suggest_aligned_address(address_str, platform, injection_type, "up")

    message = (
        f"{platform.upper()} requires {alignment}-byte aligned addresses for {injection_type}s.\n\n"
        f"Your address: 0x{address_str}\n\n"
        f"Suggested addresses:\n"
        f"  • 0x{suggestion_down} (round down)\n"
        f"  • 0x{suggestion_up} (round up)\n\n"
        f"Tip: Addresses must be divisible by {alignment}"
    )

    messagebox.showerror("Address Alignment Error", message)