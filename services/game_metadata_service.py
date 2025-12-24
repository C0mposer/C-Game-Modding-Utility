import os
from typing import Optional
from functions.verbose_print import verbose_print


class GameMetadataService:
    @staticmethod
    def get_game_id(build_version, platform: str) -> Optional[str]:
        if platform == "PS1":
            return GameMetadataService.get_ps1_game_id(build_version)
        elif platform == "PS2":
            return GameMetadataService.get_ps2_game_id(build_version)
        elif platform == "Gamecube":
            return GameMetadataService.get_gamecube_game_id(build_version)
        elif platform == "Wii":
            return GameMetadataService.get_wii_game_id(build_version)
        else:
            return None

    @staticmethod
    def get_ps1_game_id(build_version) -> Optional[str]:
        """
        SCUS_942.82 -> SCUS-94282
        """
        main_exe = build_version.GetMainExecutable()
        if main_exe:
            # Format: Replace underscore with dash, remove dots
            game_id = main_exe.replace("_", "-").replace(".", "")
            return game_id
        return None

    @staticmethod
    def get_ps2_game_id(build_version) -> Optional[str]:
        """
        SLUS_123.45 -> SLUS-12345
        """
        main_exe = build_version.GetMainExecutable()
        if main_exe:
            # Format: Remove underscores and dots
            game_id = main_exe.replace("_", "-").replace(".", "")
            return game_id
        return None

    @staticmethod
    def get_gamecube_game_id(build_version) -> Optional[str]:
        """Get GameCube game ID from ISO file or ISO.hdr"""
        # Try single file first
        if build_version.IsSingleFileMode():
            single_file = build_version.GetSingleFilePath()
            if single_file and os.path.exists(single_file):
                verbose_print(f"  Trying to read GameCube ID from single file: {single_file}")
                return GameMetadataService.read_game_id_from_file(single_file, offset=0, length=6)

        # Try ISO header and other files in extracted folder
        game_folder = build_version.GetGameFolder()
        if game_folder and os.path.exists(game_folder):
            # List of possible file locations to check
            possible_files = [
                os.path.join(game_folder, '&&systemdata', 'ISO.hdr'),  # GameCube ISO header
                os.path.join(game_folder, 'sys', 'boot.bin'),
                os.path.join(game_folder, '&&systemdata', 'Start.dol'),
                os.path.join(game_folder, 'sys', 'main.dol'),
                os.path.join(game_folder, 'Start.dol'),
                os.path.join(game_folder, 'main.dol'),
            ]

            main_exe = build_version.GetMainExecutable()
            if main_exe:
                # Search recursively for the main executable
                for root, _dirs, files in os.walk(game_folder):
                    if main_exe in files:
                        exe_path = os.path.join(root, main_exe)
                        possible_files.insert(0, exe_path) 
                        break

            # Try each possible file
            for file_path in possible_files:
                verbose_print(f"  Looking for GameCube ID source at: {file_path}")
                if os.path.exists(file_path):
                    verbose_print(f"  Found file, reading GameCube ID...")
                    game_id = GameMetadataService.read_game_id_from_file(file_path, offset=0, length=6)
                    if game_id:
                        return game_id

        verbose_print(f"  Could not find any GameCube ID source")
        return None

    @staticmethod
    def get_wii_game_id(build_version) -> Optional[str]:
        """
        Extract Wii game ID from ISO file or boot.bin

        Note: For Wii, sys/boot.bin is the most reliable source after extraction,
        as the game ID location in a disc file varies depending on the file format (offset 0 for ISO, offset 0x200 for WBFS, etc.)
        but, it's always at offset 0 in the extracted sys/boot.bin file (from my testing so far)
        """
        # Try single file first
        if build_version.IsSingleFileMode():
            single_file = build_version.GetSingleFilePath()
            if single_file and os.path.exists(single_file):
                verbose_print(f"  Trying to read Wii ID from single file: {single_file}")
                return GameMetadataService.read_game_id_from_file(single_file, offset=0, length=6)

        # Try source path (original ISO)
        source_path = build_version.GetSourcePath()
        verbose_print(f"  Wii source_path: {source_path}")
        if source_path and os.path.exists(source_path) and os.path.isfile(source_path):
            verbose_print(f"  Trying to read Wii ID from source ISO: {source_path}")
            game_id = GameMetadataService.read_game_id_from_file(source_path, offset=0, length=6)
            if game_id:
                return game_id
            # Try WBFS offset if standard offset failed
            verbose_print(f"  Trying WBFS offset (0x200)...")
            game_id = GameMetadataService.read_game_id_from_file(source_path, offset=0x200, length=6)
            if game_id:
                return game_id

        # Try boot.bin in extracted folder
        game_folder = build_version.GetGameFolder()
        verbose_print(f"  Wii game_folder: {game_folder}")
        if game_folder and os.path.exists(game_folder):
            verbose_print(f"  Game folder exists, searching for Wii ID files...")

            # List of possible file locations to check
            possible_files = [
                os.path.join(game_folder, 'sys', 'boot.bin'),
                os.path.join(game_folder, '&&systemdata', 'ISO.hdr'), 
                os.path.join(game_folder, '&&systemdata', 'Start.dol'),
                os.path.join(game_folder, 'sys', 'main.dol'),
                os.path.join(game_folder, 'Start.dol'),
                os.path.join(game_folder, 'main.dol'),
            ]

            # Also search for the main executable in subfolders
            main_exe = build_version.GetMainExecutable()
            if main_exe:
                verbose_print(f"  Searching for main executable: {main_exe}")
                # Search recursively for the main executable
                for root, _dirs, files in os.walk(game_folder):
                    if main_exe in files:
                        exe_path = os.path.join(root, main_exe)
                        verbose_print(f"  Found main executable at: {exe_path}")
                        possible_files.insert(0, exe_path)  # Prioritize this
                        break

            # Try each possible file
            for file_path in possible_files:
                verbose_print(f"  Looking for Wii ID source at: {file_path}")
                if os.path.exists(file_path):
                    verbose_print(f"  Found file, reading Wii ID...")
                    game_id = GameMetadataService.read_game_id_from_file(file_path, offset=0, length=6)
                    if game_id:
                        return game_id
                else:
                    verbose_print(f"    File does not exist")

        verbose_print(f"  Could not find any Wii ID source")
        return None

    @staticmethod
    def read_game_id_from_file(file_path: str, offset: int, length: int) -> Optional[str]:
        try:
            with open(file_path, 'rb') as f:
                f.seek(offset)
                game_id_bytes = f.read(length)
                # Decode and clean the game ID
                game_id = game_id_bytes.decode('ascii', errors='ignore').strip()

                # Filter out non-printable and non-alphanumeric characters
                # Valid game IDs should only contain letters and numbers
                game_id = ''.join(c for c in game_id if c.isalnum())

                # Validate: Game IDs should be exactly 6 alphanumeric characters
                if len(game_id) == 6 and game_id.isalnum():
                    verbose_print(f"   Found valid game ID: {game_id}")
                    return game_id.upper()
                else:
                    verbose_print(f"  Invalid game ID format: '{game_id}' (length: {len(game_id)})")
                    return None
        except Exception as e:
            verbose_print(f"Could not read game ID from {file_path}: {e}")
            return None
