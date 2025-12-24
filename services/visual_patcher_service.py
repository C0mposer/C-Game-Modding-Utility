import os
from typing import List, Dict, Optional, Tuple, NamedTuple
from classes.project_data.project_data import ProjectData

class PatchRegion(NamedTuple):
    """Stores info about a single applied patch"""
    name: str
    type: str  # "Codecave", "Hook", "Binary Patch"
    offset: int
    size: int  # Size of the patch data written
    original_bytes: bytes
    patched_bytes: bytes
    allocated_size: int  # The cave's allocated size from GetSize()

class VisualPatcherService:
    """
    Generates an in-memory diff between an original game file
    and a version patched with all user modifications.
    """
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
        self.bin_output_dir = os.path.join(
            self.project_data.GetProjectFolder(), '.config', 'output', 'bin_files'
        )

    def generate_diff(self, file_name: str) -> Tuple[Optional[bytearray], Optional[bytearray], List[PatchRegion]]:
        """
        Generates the diff for the specified game file.
        
        Returns:
            (original_data, patched_data, patch_regions)
        """
        current_build = self.project_data.GetCurrentBuildVersion()
        
        # 1. Find and read the original file
        original_file_path = current_build.FindFileInGameFolder(file_name)
        if not original_file_path or not os.path.exists(original_file_path):
            print(f"VisualPatcher: Could not find original file {file_name}")
            return None, None, []

        try:
            with open(original_file_path, 'rb') as f:
                original_data = bytearray(f.read())
            patched_data = bytearray(original_data)
            print(f"VisualPatcher: Loaded {file_name} ({len(original_data)} bytes)")
        except Exception as e:
            print(f"VisualPatcher: Error reading {file_name}: {e}")
            return None, None, []
            
        patch_regions = []

        # 2. Apply all patches, similar to ISOService.patch_executable
        all_targets = [
            (current_build.GetEnabledCodeCaves(), "Codecave"),
            (current_build.GetEnabledHooks(), "Hook"),
            (current_build.GetEnabledBinaryPatches(), "Binary Patch")
        ]

        for targets, target_type in all_targets:
            for target in targets:
                # Check if this patch targets this file
                if target.GetInjectionFile() != file_name:
                    continue
                
                # Check for new file type (not supported in this view)
                if target.IsNewFile():
                    continue

                # Get binary patch data
                bin_file = os.path.join(self.bin_output_dir, f"{target.GetName()}.bin")
                if not os.path.exists(bin_file):
                    print(f"VisualPatcher: Skipping {target.GetName()} (no .bin file)")
                    continue
                
                with open(bin_file, 'rb') as f:
                    patch_data = f.read()
                
                # Get file offset
                file_address_str = target.GetInjectionFileAddress()
                if not file_address_str:
                    print(f"VisualPatcher: Skipping {target.GetName()} (no file address)")
                    continue

                try:
                    file_address = int(file_address_str, 16)
                except ValueError:
                    print(f"VisualPatcher: Skipping {target.GetName()} (invalid address)")
                    continue
                
                # Validate bounds
                patch_size = len(patch_data)
                if file_address < 0 or (file_address + patch_size) > len(patched_data):
                    print(f"VisualPatcher: Skipping {target.GetName()} (out of bounds)")
                    continue

                # Store patch info *before* applying
                original_chunk = original_data[file_address : file_address + patch_size]
                
                # Get the allocated cave size from the target
                try:
                    allocated_size = target.GetSizeAsInt() if target.GetSize() else patch_size
                except (ValueError, AttributeError):
                    allocated_size = patch_size
                
                region = PatchRegion(
                    name=target.GetName(),
                    type=target_type,
                    offset=file_address,
                    size=patch_size,
                    original_bytes=original_chunk,
                    patched_bytes=patch_data,
                    allocated_size=allocated_size
                )
                patch_regions.append(region)

                # Apply patch to the in-memory copy
                patched_data[file_address : file_address + patch_size] = patch_data
        
        print(f"VisualPatcher: Applied {len(patch_regions)} patch(es) to in-memory copy.")
        return original_data, patched_data, patch_regions