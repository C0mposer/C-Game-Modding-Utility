import os
import subprocess
from typing import Optional, Tuple


class BinmergeService:
    """Service for handling multi-bin PS1 games using binmerge tool"""

    BINMERGE_PATH = os.path.join("prereq", "binmerge", "binmerge.exe")

    @staticmethod
    def parse_cue_file(cue_path: str) -> int:
        """
        Parse a CUE file and count how many FILE entries it has.
        Returns the number of BIN files referenced in the CUE.
        """
        try:
            with open(cue_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Count FILE entries (case-insensitive)
            file_count = content.upper().count('FILE ')
            print(f"  Found {file_count} FILE entries in CUE file")
            return file_count
        except Exception as e:
            print(f"Error parsing CUE file: {e}")
            return 0

    @staticmethod
    def get_bin_from_single_file_cue(cue_path: str) -> Optional[str]:
        """
        If CUE file references only one BIN, extract and return the BIN path.
        Returns None if CUE has multiple bins or can't parse.
        """
        try:
            with open(cue_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Find the FILE line
            for line in lines:
                line_upper = line.strip().upper()
                if line_upper.startswith('FILE '):
                    # Extract filename between quotes
                    # Format: FILE "filename.bin" BINARY
                    parts = line.split('"')
                    if len(parts) >= 2:
                        bin_filename = parts[1]
                        # Get directory of CUE file
                        cue_dir = os.path.dirname(cue_path)
                        bin_path = os.path.join(cue_dir, bin_filename)

                        if os.path.exists(bin_path):
                            print(f"   Found single BIN file: {bin_filename}")
                            return bin_path
                        else:
                            print(f"  BIN file not found: {bin_path}")
                            return None

            print(f"  Could not parse BIN filename from CUE")
            return None
        except Exception as e:
            print(f"Error extracting BIN path from CUE: {e}")
            return None

    @staticmethod
    def merge_bins(cue_path: str, output_name: str) -> Tuple[bool, Optional[str]]:
        """
        Run binmerge on a multi-bin CUE file to create a single merged BIN.

        Args:
            cue_path: Path to the .cue file
            output_name: Name for the merged output (without extension)

        Returns:
            Tuple of (success: bool, merged_bin_path: Optional[str])
        """
        try:
            # Get directory where CUE file is located
            cue_dir = os.path.dirname(cue_path)

            # Build command
            # binmerge expects: binmerge "path/to/file.cue" "OutputName"
            cmd = [
                BinmergeService.BINMERGE_PATH,
                cue_path,
                output_name
            ]

            print(f"Running binmerge...")
            print(f"  Command: {' '.join(cmd)}")
            print(f"  Working directory: {cue_dir}")

            # Run binmerge in the directory where the CUE file is
            result = subprocess.run(
                cmd,
                cwd=cue_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            # Check if successful
            if result.returncode == 0:
                # Merged BIN should be in the same directory as the CUE
                merged_bin_path = os.path.join(cue_dir, f"{output_name}.bin")

                if os.path.exists(merged_bin_path):
                    print(f"   Successfully merged bins: {merged_bin_path}")
                    return True, merged_bin_path
                else:
                    print(f"  binmerge completed but merged file not found: {merged_bin_path}")
                    return False, None
            else:
                print(f"  binmerge failed with return code {result.returncode}")
                if result.stderr:
                    print(f"  Error output: {result.stderr}")
                return False, None

        except subprocess.TimeoutExpired:
            print(f"  binmerge timed out after 5 minutes")
            return False, None
        except Exception as e:
            print(f"  Error running binmerge: {e}")
            import traceback
            traceback.print_exc()
            return False, None

    @staticmethod
    def get_first_data_track_from_cue(cue_path: str) -> Optional[str]:
        """
        Extract the first data track (Track 01) from a multi-bin CUE file.
        For PS1 games, Track 01 is always the data track, and subsequent tracks are audio.
        We only need Track 01 for modding purposes.

        Returns the path to Track 01 BIN file, or None if not found.
        """
        try:
            with open(cue_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Find the first FILE entry (Track 01 - the data track)
            for line in lines:
                line_stripped = line.strip()
                line_upper = line_stripped.upper()

                if line_upper.startswith('FILE '):
                    # Extract filename between quotes
                    # Format: FILE "filename.bin" BINARY
                    parts = line.split('"')
                    if len(parts) >= 2:
                        bin_filename = parts[1]
                        # Get directory of CUE file
                        cue_dir = os.path.dirname(cue_path)
                        bin_path = os.path.join(cue_dir, bin_filename)

                        if os.path.exists(bin_path):
                            print(f"   Found Track 01 (data track): {bin_filename}")
                            return bin_path
                        else:
                            print(f"  Track 01 BIN file not found: {bin_path}")
                            return None

            print(f"  Could not find any FILE entries in CUE")
            return None
        except Exception as e:
            print(f"Error extracting Track 01 from CUE: {e}")
            return None

    @staticmethod
    def create_multibin_cue(modded_bin_path: str, original_cue_path: str, output_cue_path: str) -> bool:
        """
        Create a multi-bin CUE file that combines a modded data track with original audio tracks.

        Args:
            modded_bin_path: Path to the newly built data track BIN
            original_cue_path: Path to the original multi-bin CUE file
            output_cue_path: Path where the new CUE file should be written

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(original_cue_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_lines = f.readlines()

            # Get the modded BIN filename (just the filename, not full path)
            modded_bin_filename = os.path.basename(modded_bin_path)

            # Get directory of original CUE (where audio track BINs are located)
            original_cue_dir = os.path.dirname(original_cue_path)

            # Build new CUE content
            new_cue_lines = []
            first_file_processed = False

            for line in original_lines:
                line_stripped = line.strip()
                line_upper = line_stripped.upper()

                # Replace the first FILE entry (Track 01) with our modded BIN
                if line_upper.startswith('FILE ') and not first_file_processed:
                    # Extract the original file type (usually BINARY)
                    parts = line.split('"')
                    if len(parts) >= 3:
                        file_type = parts[2].strip()  # e.g., "BINARY"
                        new_cue_lines.append(f'FILE "{modded_bin_filename}" {file_type}\n')
                        first_file_processed = True
                    else:
                        # Fallback if parsing fails
                        new_cue_lines.append(f'FILE "{modded_bin_filename}" BINARY\n')
                        first_file_processed = True
                else:
                    # Keep all other lines as-is (audio tracks, TRACK entries, INDEX entries, etc.)
                    new_cue_lines.append(line)

            # Write the new CUE file
            with open(output_cue_path, 'w', encoding='utf-8') as f:
                f.writelines(new_cue_lines)

            print(f"   Created multi-bin CUE file: {os.path.basename(output_cue_path)}")
            print(f"    - Track 01 (data): {modded_bin_filename} (modded)")
            print(f"    - Tracks 02+: Original audio tracks from {os.path.basename(original_cue_path)}")

            return True

        except Exception as e:
            print(f"  Failed to create multi-bin CUE: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def process_ps1_file(file_path: str) -> Tuple[bool, Optional[str], str]:
        """
        Process a PS1 file (BIN or CUE) and determine the correct BIN to use.

        Args:
            file_path: Path to the .bin or .cue file selected by user

        Returns:
            Tuple of (success: bool, bin_path: Optional[str], message: str)
            - If success=True, bin_path contains the file to extract
            - message contains info/error message
        """
        file_ext = os.path.splitext(file_path)[1].lower()

        # If user selected a BIN directly, just use it
        if file_ext == '.bin':
            print("User selected BIN file directly")
            return True, file_path, "Using selected BIN file"

        # If user selected a CUE file
        if file_ext == '.cue':
            print(f"Processing CUE file: {os.path.basename(file_path)}")

            # Count how many bins
            bin_count = BinmergeService.parse_cue_file(file_path)

            if bin_count == 0:
                return False, None, "Could not parse CUE file"

            elif bin_count == 1:
                # Single bin - just extract the bin path from CUE
                print("CUE file references single BIN")
                bin_path = BinmergeService.get_bin_from_single_file_cue(file_path)

                if bin_path:
                    return True, bin_path, f"Using single BIN file from CUE"
                else:
                    return False, None, "Could not locate BIN file referenced in CUE"

            else:
                # Multi-bin - for PS1, we only need Track 01 (the data track)
                # Audio tracks (Track 02+) are not needed for modding
                print(f"CUE file references {bin_count} BIN files (Track 01 + {bin_count-1} audio tracks)")
                print(f"  Only Track 01 (data track) is needed for modding")

                # Get Track 01 (the first bin)
                track01_bin = BinmergeService.get_first_data_track_from_cue(file_path)

                if track01_bin:
                    return True, track01_bin, f"Using Track 01 (data track) from multi-bin CUE"
                else:
                    return False, None, "Could not locate Track 01 (data track) from CUE file"

        # Unknown file type
        return False, None, f"Unsupported file type: {file_ext}"
