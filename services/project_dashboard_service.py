"""
Project Dashboard Service
Calculates and provides statistics about the current project
"""

import os
from typing import Dict, Any, Optional
from classes.project_data.project_data import ProjectData


class ProjectDashboardService:
    """Service for calculating project statistics"""

    @staticmethod
    def get_project_stats(project_data: ProjectData) -> Dict[str, Any]:
        """
        Calculate comprehensive project statistics

        Returns:
            Dict containing various project metrics
        """
        current_build = project_data.GetCurrentBuildVersion()

        # Count modifications
        codecave_count = len(current_build.GetCodeCaveNames())
        hook_count = len(current_build.GetHookNames())
        patch_count = len(current_build.GetBinaryPatchNames())
        multipatch_count = len(current_build.GetMultiPatchNames())
        total_modifications = codecave_count + hook_count + patch_count + multipatch_count

        # Count code files and lines of code across all codecaves
        total_code_files = 0
        c_files = 0
        asm_files = 0
        total_lines = 0
        c_lines = 0
        asm_lines = 0

        for codecave in current_build.GetEnabledCodeCaves():
            code_files = codecave.GetCodeFilesPaths()
            total_code_files += len(code_files)

            for file in code_files:
                ext = os.path.splitext(file)[1].lower()

                # Count lines in file
                if os.path.exists(file):
                    try:
                        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len([line for line in f if line.strip()])  # Count non-empty lines
                            total_lines += lines

                            if ext in ['.c', '.cpp', '.cc']:
                                c_files += 1
                                c_lines += lines
                            elif ext in ['.s', '.asm']:
                                asm_files += 1
                                asm_lines += lines
                    except:
                        # If we can't read the file, just count it
                        if ext in ['.c', '.cpp', '.cc']:
                            c_files += 1
                        elif ext in ['.s', '.asm']:
                            asm_files += 1
                else:
                    # File doesn't exist, just count it
                    if ext in ['.c', '.cpp', '.cc']:
                        c_files += 1
                    elif ext in ['.s', '.asm']:
                        asm_files += 1

        # Calculate total code size (estimated from codecaves)
        total_code_size = 0
        for codecave in current_build.GetEnabledCodeCaves():
            size_str = codecave.GetSize()
            if size_str:
                try:
                    # Parse hex size
                    size = int(size_str, 16)
                    total_code_size += size
                except ValueError:
                    pass

        # Get game files info
        game_files_count = len(current_build.GetInjectionFiles())
        main_exe = current_build.GetMainExecutable()

        # Check if symbols file exists
        symbols_file = current_build.GetSymbolsFile()
        project_folder = project_data.GetProjectFolder()
        symbols_path = os.path.join(project_folder, "symbols", symbols_file) if symbols_file else None
        symbols_exists = symbols_path and os.path.exists(symbols_path)

        # Count symbols if file exists
        symbols_count = 0
        if symbols_exists:
            try:
                with open(symbols_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Count non-comment, non-empty lines with '='
                        if line and not line.startswith('/*') and not line.startswith('//') and '=' in line:
                            symbols_count += 1
            except:
                pass

        # Platform info
        platform = current_build.GetPlatform()

        # Build version info
        build_count = len(project_data.build_versions)
        current_build_name = current_build.GetBuildName()

        return {
            # Modification counts
            'codecaves': codecave_count,
            'hooks': hook_count,
            'patches': patch_count,
            'multipatches': multipatch_count,
            'total_modifications': total_modifications,

            # Code file counts
            'total_code_files': total_code_files,
            'c_files': c_files,
            'asm_files': asm_files,

            # Lines of code
            'total_lines': total_lines,
            'c_lines': c_lines,
            'asm_lines': asm_lines,

            # Size info
            'total_code_size': total_code_size,
            'total_code_size_kb': total_code_size / 1024.0 if total_code_size > 0 else 0,

            # Game files
            'game_files': game_files_count,
            'main_executable': main_exe if main_exe else "Not set",

            # Symbols
            'symbols_count': symbols_count,
            'symbols_file': symbols_file if symbols_file else "None",

            # Build info
            'platform': platform if platform else "Not set",
            'build_count': build_count,
            'current_build': current_build_name,
        }

    @staticmethod
    def format_stats_summary(stats: Dict[str, Any]) -> str:
        """Format stats into a readable summary string"""
        lines = []

        # Platform and build
        lines.append(f"Platform: {stats['platform']} | Build: {stats['current_build']} ({stats['build_count']} total)")

        # Modifications
        mods = []
        if stats['codecaves'] > 0:
            mods.append(f"{stats['codecaves']} codecave{'s' if stats['codecaves'] != 1 else ''}")
        if stats['hooks'] > 0:
            mods.append(f"{stats['hooks']} hook{'s' if stats['hooks'] != 1 else ''}")
        if stats['patches'] > 0:
            mods.append(f"{stats['patches']} patch{'es' if stats['patches'] != 1 else ''}")
        if stats['multipatches'] > 0:
            mods.append(f"{stats['multipatches']} multipatch{'es' if stats['multipatches'] != 1 else ''}")

        if mods:
            lines.append(f"Modifications: {', '.join(mods)} ({stats['total_modifications']} total)")
        else:
            lines.append("Modifications: None")

        # Code files
        if stats['total_code_files'] > 0:
            lines.append(f"Code Files: {stats['c_files']} C/C++, {stats['asm_files']} ASM ({stats['total_code_files']} total)")

        # Size
        if stats['total_code_size'] > 0:
            if stats['total_code_size_kb'] < 1:
                lines.append(f"Code Size: {stats['total_code_size']} bytes")
            else:
                lines.append(f"Code Size: {stats['total_code_size_kb']:.2f} KB ({stats['total_code_size']} bytes)")

        # Symbols
        if stats['symbols_count'] > 0:
            lines.append(f"Symbols: {stats['symbols_count']} defined")

        return " | ".join(lines)
