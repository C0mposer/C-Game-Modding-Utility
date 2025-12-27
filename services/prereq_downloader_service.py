"""
Tool Manager - Downloads and manages platform-specific prerequisite tools
"""

import os
import shutil
import zipfile
import urllib.request
import json
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass


@dataclass
class ToolPackage:
    platform: str
    display_name: str
    url: str
    size_mb: float
    folders: List[str] 


class ToolManager:
    TOOL_PACKAGES = {
        'ps1': ToolPackage(
            platform='ps1',
            display_name='PlayStation 1',
            url='https://github.com/C0mposer/C-Game-Modding-Utility-Pre-Requisites/releases/download/V1.0/PS1-Prereqs.zip',
            size_mb=88.2,
            folders=['PS1mips', 'mkpsxiso']
        ),
        'ps2': ToolPackage(
            platform='ps2',
            display_name='PlayStation 2',
            url='https://github.com/C0mposer/C-Game-Modding-Utility-Pre-Requisites/releases/download/V1.0/PS2-Prereqs.zip',
            size_mb=140.0,
            folders=['7z', 'pine', 'PS2ee', 'PS2ISOTools']
        ),
        'gc-wii': ToolPackage(
            platform='gc-wii',
            display_name='GameCube & Wii',
            url='https://github.com/C0mposer/C-Game-Modding-Utility-Pre-Requisites/releases/download/V1.0/GC-Wii-Prereqs.zip',
            size_mb=106.0,
            folders=['devkitPPC', 'DolphinMemoryEngine', 'DolphinTool', 'doltool', 'gc-fst', 'wit']
        ),
    }

    # Map platform names to package keys
    PLATFORM_MAP = {
        'PS1': 'ps1',
        'PS2': 'ps2',
        'Gamecube': 'gc-wii',
        'Wii': 'gc-wii'
    }

    def __init__(self, tool_dir: str):
        self.tool_dir = tool_dir
        self.prereq_dir = os.path.join(tool_dir, 'prereq')
        os.makedirs(self.prereq_dir, exist_ok=True)

    def is_platform_installed(self, platform: str) -> bool:
        """Check if platform tools are installed"""
        if platform not in self.TOOL_PACKAGES:
            return False

        package = self.TOOL_PACKAGES[platform]

        # Check if all expected folders exist
        for folder in package.folders:
            full_path = os.path.join(self.prereq_dir, folder)
            if not os.path.isdir(full_path):
                return False

        return True

    def check_platform_prereqs(self, platform_name: str) -> bool:
        """
        Check if prerequisites for a platform are installed

        Args:
            platform_name: Platform name (PS1, PS2, Gamecube, Wii)

        Returns:
            True if installed, False if missing
        """
        platform_key = self.PLATFORM_MAP.get(platform_name)
        if not platform_key:
            return True  # Unknown platform, assume OK

        return self.is_platform_installed(platform_key)

    def get_missing_platforms(self, required_platforms: List[str]) -> List[str]:
        """Get list of platforms that need to be installed"""
        missing = []
        for platform in required_platforms:
            if not self.is_platform_installed(platform):
                missing.append(platform)
        return missing

    def download_platform_tools(self, platform: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        if platform not in self.TOOL_PACKAGES:
            print(f"Error: Unknown platform '{platform}'")
            return False

        package = self.TOOL_PACKAGES[platform]

        print(f"\nDownloading {package.display_name} tools ({package.size_mb:.1f} MB)...")

        try:
            # Download to temp file
            temp_zip = os.path.join(self.prereq_dir, f'{platform}_temp.zip')

            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if progress_callback:
                    progress_callback(downloaded, total_size)
                else:
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\rProgress: {percent:.1f}%", end='', flush=True)

            urllib.request.urlretrieve(package.url, temp_zip, download_progress)
            print()  # New line after progress

            # Extract to prereq directory
            print(f"Extracting {package.display_name} tools...")
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(self.prereq_dir)

            # Clean up temp file
            os.remove(temp_zip)

            # Verify installation
            if self.is_platform_installed(platform):
                print(f"{package.display_name} tools installed")
                return True
            else:
                print(f"Installation verification failed for {package.display_name}")
                return False

        except Exception as e:
            print(f"Error downloading {package.display_name} tools: {str(e)}")
            # Clean up on error
            if os.path.exists(temp_zip):
                try:
                    os.remove(temp_zip)
                except:
                    pass
            return False

    def download_all_platforms( self, platforms: List[str], progress_callback: Optional[Callable[[str, int, int], None]] = None) -> Dict[str, bool]:

        results = {}

        for platform in platforms:
            if progress_callback:
                callback = lambda downloaded, total: progress_callback(platform, downloaded, total)
            else:
                callback = None

            results[platform] = self.download_platform_tools(platform, callback)

        return results

    def get_platform_info(self, platform: str) -> Optional[ToolPackage]:
        return self.TOOL_PACKAGES.get(platform)

    def get_all_platforms(self) -> List[str]:
        return list(self.TOOL_PACKAGES.keys())

    def get_total_download_size(self, platforms: List[str]) -> float:
        total = 0.0
        for platform in platforms:
            if platform in self.TOOL_PACKAGES:
                total += self.TOOL_PACKAGES[platform].size_mb
        return total

