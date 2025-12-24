"""
Ghidra Pattern Service
Scans executables for Ghidra OS library function patterns and adds them to symbol files
"""

import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple


class GhidraPattern:
    """Represents a single Ghidra pattern"""

    def __init__(self, label: str, pattern_bytes: bytes):
        self.label = label
        self.pattern_bytes = pattern_bytes

    def __repr__(self):
        return f"GhidraPattern(label={self.label}, bytes={self.pattern_bytes.hex()})"


class GhidraPatternService:
    """Service for scanning executables using Ghidra patterns"""

    # Patterns to skip (nothing-burger patterns as mentioned by user)
    SKIP_PATTERNS = [
        "jump_to_00000000",
        "RFU",  # Reserved for Future Use - catches all RFU000, RFU003, RFU005, etc.
        "possiblefuncstart",  # Too generic
    ]

    def __init__(self):
        self.patterns_dir = os.path.join("prereq", "ghidra-patterns")

    def scan_executable(self, platform: str, executable_path: str) -> List[Tuple[str, int]]:
        """
        Scan an executable for OS library function patterns.

        Args:
            platform: Platform name ("PS1" or "PS2")
            executable_path: Path to the executable to scan

        Returns:
            List of tuples (function_name, address)
        """
        # Load patterns for platform
        patterns = self._load_patterns_for_platform(platform)

        if not patterns:
            print(f"No patterns loaded for platform {platform}")
            return []

        # Read executable file
        try:
            with open(executable_path, 'rb') as f:
                executable_data = f.read()
        except Exception as e:
            print(f"Error reading executable {executable_path}: {e}")
            return []

        # Scan for patterns
        found_symbols = []

        for pattern in patterns:
            # Skip nothing-burger patterns
            if any(skip in pattern.label for skip in self.SKIP_PATTERNS):
                continue

            # Find all occurrences of this pattern
            offset = 0
            while True:
                idx = executable_data.find(pattern.pattern_bytes, offset)
                if idx == -1:
                    break

                # Calculate address (platform-specific base address + offset)
                address = self._calculate_address(platform, idx)
                found_symbols.append((pattern.label, address))

                # Move past this match to find duplicates
                offset = idx + 1

        # Remove duplicates (keep first occurrence of each symbol)
        seen_labels = set()
        unique_symbols = []
        for label, address in found_symbols:
            if label not in seen_labels:
                seen_labels.add(label)
                unique_symbols.append((label, address))

        return unique_symbols

    def add_symbols_to_file(self, symbols_file_path: str, symbols: List[Tuple[str, int]]):
        """
        Add found symbols to a symbols file.

        Args:
            symbols_file_path: Path to the symbols file
            symbols: List of (function_name, address) tuples
        """
        if not symbols:
            return

        # Ensure directory exists
        os.makedirs(os.path.dirname(symbols_file_path), exist_ok=True)

        # Read existing symbols file if it exists
        existing_content = ""
        if os.path.exists(symbols_file_path):
            with open(symbols_file_path, 'r') as f:
                existing_content = f.read()

        # Parse existing symbols to avoid duplicates
        existing_labels = set()
        for line in existing_content.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('/*') and not line.startswith('//'):
                label = line.split('=')[0].strip()
                existing_labels.add(label)

        # Build new symbols to add
        new_symbols_text = []
        for label, address in symbols:
            if label not in existing_labels:
                new_symbols_text.append(f"{label} = 0x{address:08X};")

        if not new_symbols_text:
            print("No new symbols to add (all already exist)")
            return

        # Add header and symbols
        header = "\n/* Auto-detected OS library functions from Ghidra patterns */\n"
        symbols_block = '\n'.join(new_symbols_text) + '\n'

        # Append to file
        with open(symbols_file_path, 'a') as f:
            if existing_content and not existing_content.endswith('\n'):
                f.write('\n')
            f.write(header)
            f.write(symbols_block)

        print(f"Added {len(new_symbols_text)} OS library symbols to {symbols_file_path}")

    def generate_header_file(self, header_file_path: str, symbols: List[Tuple[str, int]], build_name: str):
        """
        Generate or update a C header file with prototypes for the found symbols.
        Uses #ifdef guards to separate build-specific functions.

        Args:
            header_file_path: Path to the header file to create/update
            symbols: List of (function_name, address) tuples
            build_name: Name of the build version (used for #ifdef guard)
        """
        if not symbols:
            return

        # Map of function names to their prototypes
        # Only include functions we're confident about
        known_prototypes = {
            # String functions
            'strlen': 'int strlen(const char* str);',
            'strcpy': 'char* strcpy(char* dest, const char* src);',
            'strncpy': 'char* strncpy(char* dest, const char* src, int n);',
            'strcat': 'char* strcat(char* dest, const char* src);',
            'strncat': 'char* strncat(char* dest, const char* src, int n);',
            'strcmp': 'int strcmp(const char* str1, const char* str2);',
            'strncmp': 'int strncmp(const char* str1, const char* str2, int n);',
            'strchr': 'char* strchr(const char* str, int c);',
            'strrchr': 'char* strrchr(const char* str, int c);',
            'strcspn': 'int strcspn(const char* str1, const char* str2);',
            'strspn': 'int strspn(const char* str1, const char* str2);',
            'strpbrk': 'char* strpbrk(const char* str1, const char* str2);',
            'strstr': 'char* strstr(const char* haystack, const char* needle);',

            # Memory functions
            'memcpy': 'void* memcpy(void* dest, const void* src, int n);',
            'memmove': 'void* memmove(void* dest, const void* src, int n);',
            'memset': 'void* memset(void* ptr, int value, int n);',
            'memcmp': 'int memcmp(const void* ptr1, const void* ptr2, int n);',
            'memchr': 'void* memchr(const void* ptr, int value, int n);',
            'malloc': 'void* malloc(int size);',
            'calloc': 'void* calloc(int num, int size);',
            'realloc': 'void* realloc(void* ptr, int size);',
            'free': 'void free(void* ptr);',

            # String conversion
            'atoi': 'int atoi(const char* str);',
            'atol': 'long atol(const char* str);',
            'atof': 'double atof(const char* str);',
            'atob': 'int atob(const char* str);',
            'todigit': 'int todigit(int c);',
            'strtol': 'long strtol(const char* str, char** endptr, int base);',
            'strtoul': 'unsigned long strtoul(const char* str, char** endptr, int base);',

            # Character functions
            'toupper': 'int toupper(int c);',
            'tolower': 'int tolower(int c);',
            'isalpha': 'int isalpha(int c);',
            'isdigit': 'int isdigit(int c);',
            'isalnum': 'int isalnum(int c);',
            'isspace': 'int isspace(int c);',
            'isupper': 'int isupper(int c);',
            'islower': 'int islower(int c);',
            'isprint': 'int isprint(int c);',
            'iscntrl': 'int iscntrl(int c);',
            'isxdigit': 'int isxdigit(int c);',

            # Math
            'abs': 'int abs(int n);',
            'labs': 'long labs(long n);',

            # Random
            'rand': 'int rand(void);',
            'srand': 'void srand(unsigned int seed);',

            # Program control
            'exit': 'void exit(int status);',

            # Standard I/O
            'printf': 'int printf(const char* format, ...);',
            'sprintf': 'int sprintf(char* str, const char* format, ...);',
            'std_out_putchar': 'int std_out_putchar(int c);',
            'std_in_getchar': 'int std_in_getchar(void);',
            'std_in_gets': 'char* std_in_gets(char* str);',
            'std_out_puts': 'int std_out_puts(const char* str);',

            # File I/O
            'FileOpen': 'int FileOpen(const char* filename, int mode);',
            'FileSeek': 'int FileSeek(int fd, int offset, int whence);',
            'FileRead': 'int FileRead(int fd, void* buffer, int size);',
            'FileWrite': 'int FileWrite(int fd, const void* buffer, int size);',
            'FileClose': 'int FileClose(int fd);',
            'FileIoctl': 'int FileIoctl(int fd, int cmd, void* arg);',
            'FileGetc': 'int FileGetc(int fd);',
            'FilePutc': 'int FilePutc(int c, int fd);',
            'FileRename': 'int FileRename(const char* oldname, const char* newname);',
            'FileDelete': 'int FileDelete(const char* filename);',
            'FileUndelete': 'int FileUndelete(const char* filename);',
            'FileGetDeviceFlag': 'int FileGetDeviceFlag(int fd);',
            'GetLastFileError': 'int GetLastFileError(void);',
        }

        # Categorize found symbols
        categories = {
            'String Functions': [],
            'Memory Functions': [],
            'String Conversion': [],
            'Character Functions': [],
            'Math Functions': [],
            'Random Numbers': [],
            'Program Control': [],
            'Standard I/O': [],
            'File I/O': []
        }

        for label, address in symbols:
            if label not in known_prototypes:
                continue

            # Categorize
            if label in ['strlen', 'strcpy', 'strncpy', 'strcat', 'strncat', 'strcmp', 'strncmp',
                        'strchr', 'strrchr', 'strcspn', 'strspn', 'strpbrk', 'strstr']:
                categories['String Functions'].append(label)
            elif label in ['memcpy', 'memmove', 'memset', 'memcmp', 'memchr',
                          'malloc', 'calloc', 'realloc', 'free']:
                categories['Memory Functions'].append(label)
            elif label in ['atoi', 'atol', 'atof', 'atob', 'todigit', 'strtol', 'strtoul']:
                categories['String Conversion'].append(label)
            elif label in ['toupper', 'tolower', 'isalpha', 'isdigit', 'isalnum', 'isspace',
                          'isupper', 'islower', 'isprint', 'iscntrl', 'isxdigit']:
                categories['Character Functions'].append(label)
            elif label in ['abs', 'labs']:
                categories['Math Functions'].append(label)
            elif label in ['rand', 'srand']:
                categories['Random Numbers'].append(label)
            elif label in ['exit']:
                categories['Program Control'].append(label)
            elif label in ['printf', 'sprintf', 'std_out_putchar', 'std_in_getchar',
                          'std_in_gets', 'std_out_puts']:
                categories['Standard I/O'].append(label)
            elif label.startswith('File') or label == 'GetLastFileError':
                categories['File I/O'].append(label)

        # Check if header file already exists
        existing_content = ""
        if os.path.exists(header_file_path):
            with open(header_file_path, 'r') as f:
                existing_content = f.read()

            # Check if this build already has a section - if so, remove it first
            if f'#ifdef {build_name}' in existing_content:
                print(f"Build {build_name} already exists in header, updating...")
                # Remove the old section
                lines = existing_content.split('\n')
                new_lines = []
                skip = False
                for line in lines:
                    if f'#ifdef {build_name}' in line:
                        skip = True
                    elif skip and f'#endif /* {build_name} */' in line:
                        skip = False
                        continue
                    if not skip:
                        new_lines.append(line)
                existing_content = '\n'.join(new_lines)

        # Ensure directory exists
        os.makedirs(os.path.dirname(header_file_path), exist_ok=True)

        # Generate build-specific section
        build_section = []
        build_section.append(f'#ifdef {build_name}')
        build_section.append('')

        # Add categories with functions
        for category, funcs in categories.items():
            if not funcs:
                continue

            build_section.append('/* ' + '=' * 74 + ' */')
            build_section.append(f'/* {category:<73}*/')
            build_section.append('/* ' + '=' * 74 + ' */')
            build_section.append('')

            for func in sorted(funcs):
                build_section.append(known_prototypes[func])

            build_section.append('')

        build_section.append(f'#endif /* {build_name} */')
        build_section.append('')

        # If file doesn't exist, create with header/footer
        if not existing_content:
            header_content = []
            header_content.append('/*')
            header_content.append(' * library_symbols.h')
            header_content.append(' *')
            header_content.append(' * Auto-generated OS Library Function Prototypes')
            header_content.append(' * Generated from Ghidra pattern scans')
            header_content.append(' *')
            header_content.append(' * Each build version has its own #ifdef section')
            header_content.append(' */')
            header_content.append('')
            header_content.append('#ifndef LIBRARY_SYMBOLS_H')
            header_content.append('#define LIBRARY_SYMBOLS_H')
            header_content.append('')
            header_content.extend(build_section)
            header_content.append('#endif /* LIBRARY_SYMBOLS_H */')
            header_content.append('')

            with open(header_file_path, 'w') as f:
                f.write('\n'.join(header_content))
        else:
            # Append to existing file before the final #endif
            lines = existing_content.split('\n')

            # Find the last #endif /* LIBRARY_SYMBOLS_H */
            insert_index = -1
            for i in range(len(lines) - 1, -1, -1):
                if '#endif /* LIBRARY_SYMBOLS_H */' in lines[i]:
                    insert_index = i
                    break

            if insert_index == -1:
                # Malformed file, recreate it
                with open(header_file_path, 'w') as f:
                    f.write(existing_content)
                    f.write('\n\n')
                    f.write('\n'.join(build_section))
            else:
                # Insert before the final #endif
                new_lines = lines[:insert_index] + build_section + lines[insert_index:]
                with open(header_file_path, 'w') as f:
                    f.write('\n'.join(new_lines))

        print(f"Added {len([l for l, a in symbols if l in known_prototypes])} function prototypes for {build_name} to: {header_file_path}")

    def rename_build_in_header(self, header_file_path: str, old_build_name: str, new_build_name: str):
        """
        Rename a build version's #ifdef section in the header file.

        Args:
            header_file_path: Path to the header file
            old_build_name: Old build version name
            new_build_name: New build version name
        """
        if not os.path.exists(header_file_path):
            return

        try:
            with open(header_file_path, 'r') as f:
                content = f.read()

            # Replace the #ifdef and #endif comments
            old_ifdef = f'#ifdef {old_build_name}'
            new_ifdef = f'#ifdef {new_build_name}'
            old_endif_comment = f'#endif /* {old_build_name} */'
            new_endif_comment = f'#endif /* {new_build_name} */'

            updated_content = content.replace(old_ifdef, new_ifdef)
            updated_content = updated_content.replace(old_endif_comment, new_endif_comment)

            # Write back
            with open(header_file_path, 'w') as f:
                f.write(updated_content)

            print(f"Updated header file: renamed {old_build_name} -> {new_build_name}")

        except Exception as e:
            print(f"Error updating header file during rename: {e}")

    def _load_patterns_for_platform(self, platform: str) -> List[GhidraPattern]:
        """Load Ghidra patterns for a specific platform"""

        # Map platform to pattern file
        pattern_files = {
            "PS1": "r3000_LE_patterns.xml",
            "PS2": "r5900_LE_patterns.xml"
        }

        if platform not in pattern_files:
            return []

        pattern_file_path = os.path.join(self.patterns_dir, pattern_files[platform])

        if not os.path.exists(pattern_file_path):
            print(f"Pattern file not found: {pattern_file_path}")
            return []

        try:
            return self._parse_pattern_file(pattern_file_path)
        except Exception as e:
            print(f"Error parsing pattern file {pattern_file_path}: {e}")
            return []

    def _parse_pattern_file(self, file_path: str) -> List[GhidraPattern]:
        """Parse a Ghidra pattern XML file"""

        patterns = []

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Parse simple <pattern> elements with labels
            for pattern_elem in root.findall('.//pattern'):
                # Look for funcstart with label
                funcstart = pattern_elem.find('.//funcstart[@label]')

                if funcstart is not None:
                    label = funcstart.get('label')

                    # Get pattern data
                    data_elem = pattern_elem.find('data')
                    if data_elem is not None and data_elem.text:
                        pattern_bytes = self._parse_pattern_data(data_elem.text)

                        if pattern_bytes:
                            patterns.append(GhidraPattern(label, pattern_bytes))

        except Exception as e:
            print(f"Error parsing XML file {file_path}: {e}")

        return patterns

    def _parse_pattern_data(self, data_text: str) -> Optional[bytes]:
        """Parse pattern data string into bytes"""

        try:
            # Remove comments
            if '<!--' in data_text:
                data_text = data_text.split('<!--')[0]

            # Split by whitespace and parse hex values
            hex_values = data_text.strip().split()

            byte_list = []
            for hex_val in hex_values:
                hex_val = hex_val.strip()

                # Skip wildcards and complex patterns for now
                if '.' in hex_val or 'x' not in hex_val.lower():
                    continue

                # Parse hex byte (e.g., "0xa0" or "0xA0")
                if hex_val.startswith('0x') or hex_val.startswith('0X'):
                    try:
                        byte_val = int(hex_val, 16)
                        byte_list.append(byte_val)
                    except ValueError:
                        # Skip unparseable values
                        pass

            if byte_list:
                return bytes(byte_list)
            else:
                return None

        except Exception:
            return None

    def _calculate_address(self, platform: str, file_offset: int) -> int:
        """
        Calculate RAM address from file offset.

        For now, we just return the file offset and let the user adjust
        the base address if needed. Proper implementation would parse
        the executable format (ELF for PS2, PS-EXE for PS1) and calculate
        the actual RAM address.
        """

        # Platform-specific base addresses (common defaults)
        # These are typical, but may vary per game
        base_addresses = {
            "PS1": 0x80010000,  # PS1 executables typically load here
            "PS2": 0x00100000,  # PS2 ELF executables typically load here
        }

        base = base_addresses.get(platform, 0)

        # For PS1, we need to parse the PS-EXE header to get the actual load address
        # For PS2, we need to parse the ELF header
        # For now, just use offset + base

        return base + file_offset
