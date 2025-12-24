import json
import os
from typing import Dict, Any, Optional
from classes.project_data.project_data import ProjectData
from classes.project_data.build_version import BuildVersion
from classes.injection_targets.code_cave import Codecave
from classes.injection_targets.hook import Hook
from classes.injection_targets.binary_patch import BinaryPatch
from classes.injection_targets.multipatch_asm import MultiPatchASM
from classes.injection_targets.injection_target import (
    INJECTION_TYPE_EXISTING_FILE,
    INJECTION_TYPE_NEW_FILE,
    INJECTION_TYPE_MEMORY_ONLY,
)
from services.path_utils import PathUtils
from services.project_validator import ProjectValidator
from functions.verbose_print import verbose_print


class ProjectSerializer:
    """Handles saving and loading project data to/from JSON files"""
    
    PROJECT_FILE_VERSION = "1.0"
    PROJECT_FILE_EXTENSION = ".modproj"
    
    @staticmethod
    def save_project(project_data: ProjectData, file_path: Optional[str] = None) -> bool:
        """
        Save project data to a JSON file.
        If file_path is None, saves to default location in project folder.
        Returns True on success, False on failure.
        """
        try:
            # Determine save path
            if file_path is None:
                project_folder = project_data.GetProjectFolder()
                project_name = project_data.GetProjectName()
                file_path = os.path.join(project_folder, f"{project_name}{ProjectSerializer.PROJECT_FILE_EXTENSION}")
            
            # Serialize project data
            project_dict = ProjectSerializer._serialize_project(project_data)
            
            # Write to file with pretty formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(project_dict, f, indent=2, ensure_ascii=False)

            verbose_print(f" Project saved to: {file_path}")
            return True
            
        except Exception as e:
            print(f" Failed to save project: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def load_project(file_path: str, show_loading: bool = True) -> Optional[ProjectData]:
        """
        Load project data from a JSON file.
        Returns ProjectData on success, None on failure.

        Args:
            file_path: Path to the .modproj file
            show_loading: Whether to show loading indicator (default True)
        """
        import dearpygui.dearpygui as dpg
        from gui.gui_loading_indicator import LoadingIndicator

        try:
            if not os.path.exists(file_path):
                print(f" Project file not found: {file_path}")
                return None

            # Show loading indicator if requested
            if show_loading:
                try:
                    LoadingIndicator.show("Loading Project...")
                    # Force DearPyGui to render the loading indicator
                    dpg.split_frame()
                except:
                    # If loading indicator fails (e.g., context issues), continue anyway
                    pass

            # Read and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                project_dict = json.load(f)

            # Validate version
            file_version = project_dict.get('version', '0.0')
            if file_version != ProjectSerializer.PROJECT_FILE_VERSION:
                print(f" Warning: Project file version {file_version} may not be fully compatible")

            # Convert project folder to absolute path BEFORE deserializing
            # This ensures that when paths are resolved, they use the correct absolute base
            project_folder_from_json = project_dict.get('project_folder', '')
            if not os.path.isabs(project_folder_from_json):
                # Project folder is relative - make it absolute relative to .modproj file location
                modproj_dir = os.path.dirname(os.path.abspath(file_path))
                project_dict['project_folder'] = modproj_dir

            # Deserialize project data (now with absolute project_folder)
            project_data = ProjectSerializer._deserialize_project(project_dict)

            verbose_print(f" Project loaded from: {file_path}")

            # Hide loading indicator before validation (validation shows dialogs)
            if show_loading:
                try:
                    LoadingIndicator.hide()
                except:
                    pass

            # Validate project files and prompt user to fix any missing files
            if not ProjectValidator.validate_and_fix_project(project_data):
                print(f" Project validation cancelled by user")
                return None

            # Add to recent projects after successful load and validation
            try:
                from services.recent_projects_service import RecentProjectsService
                project_name = project_data.GetProjectName()
                platform = project_data.GetCurrentBuildVersion().GetPlatform()
                RecentProjectsService.add_recent_project(file_path, project_name, platform)
            except Exception as e:
                # Don't fail project load if recent projects tracking fails
                print(f" Warning: Failed to update recent projects: {e}")

            return project_data

        except Exception as e:
            if show_loading:
                try:
                    LoadingIndicator.hide()
                except:
                    pass
            print(f" Failed to load project: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def _serialize_project(project_data: ProjectData) -> Dict[str, Any]:
        """Convert ProjectData to a dictionary"""
        project_folder = project_data.GetProjectFolder()
        return {
            'version': ProjectSerializer.PROJECT_FILE_VERSION,
            'project_name': project_data.GetProjectName(),
            'project_folder': './',  # Always relative - .modproj is saved in project folder
            'currently_selected_build_index': project_data.GetBuildVersionIndex(),
            'build_versions': [
                ProjectSerializer._serialize_build_version(bv, project_folder)
                for bv in project_data.build_versions
            ]
        }
    
    @staticmethod
    def _serialize_build_version(build_version: BuildVersion, project_folder: str) -> Dict[str, Any]:
        # Serialize section maps
        section_maps_serialized = {}
        for filename, sections in build_version.section_maps.items():
            section_maps_serialized[filename] = [
                {
                    'section_type': s.section_type,
                    'file_offset': s.file_offset,
                    'mem_start': s.mem_start,
                    'mem_end': s.mem_end,
                    'size': s.size
                }
                for s in sections
            ]

        # Filter out temporary hooks (auto-generated)
        permanent_hooks = [h for h in build_version.GetHooks() if not h.IsTemporary()]

        return {
            'build_name': build_version.GetBuildName(),
            'platform': build_version.GetPlatform(),
            'symbols_file': build_version.GetSymbolsFile(),
            'injection_files': build_version.GetInjectionFiles(),
            'injection_file_offsets': build_version.injection_file_offsets,
            'injection_file_types': build_version.injection_file_types,
            'extracted_game_folder': PathUtils.make_relative_if_in_project(build_version.GetGameFolder(), project_folder),
            'main_executable': build_version.GetMainExecutable(),
            'source_path': PathUtils.make_relative_if_in_project(build_version.GetSourcePath(), project_folder),
            'compiler_flags': build_version.GetCompilerFlags(),
            'is_single_file_mode': build_version.IsSingleFileMode(),
            'single_file_path': PathUtils.make_relative_if_in_project(build_version.GetSingleFilePath(), project_folder),
            'section_maps': section_maps_serialized,
            'code_caves': [
                ProjectSerializer._serialize_codecave(cc, project_folder)
                for cc in build_version.GetCodeCaves()
            ],
            'hooks': [  # NEW: Only serialize permanent hooks
                ProjectSerializer._serialize_hook(h, project_folder)
                for h in permanent_hooks
            ],
            'binary_patches': [
                ProjectSerializer._serialize_binary_patch(bp, project_folder)
                for bp in build_version.GetBinaryPatches()
            ],
            'multi_patches': [
                ProjectSerializer._serialize_multipatch(mp, project_folder)
                for mp in build_version.GetMultiPatches()
            ]
        }
    
    @staticmethod
    def _serialize_codecave(codecave: Codecave, project_folder: str) -> Dict[str, Any]:
        """Convert Codecave to a dictionary"""
        return {
            'name': codecave.GetName(),
            'code_files': PathUtils.convert_paths_to_relative(codecave.GetCodeFilesPaths(), project_folder),
            'memory_address': codecave.GetMemoryAddress(),
            'size': codecave.GetSize(),
            'injection_file': codecave.GetInjectionFile(),
            'injection_file_address': codecave.GetInjectionFileAddress(),
            'auto_calculate_injection_file_address': codecave.GetAutoCalculateInjectionFileAddress(),
            'injection_type': codecave.GetInjectionType(),
            'enabled': codecave.IsEnabled()
        }
    
    @staticmethod
    def _serialize_hook(hook: Hook, project_folder: str) -> Dict[str, Any]:
        """Convert Hook to a dictionary"""
        return {
            'name': hook.GetName(),
            'code_files': PathUtils.convert_paths_to_relative(hook.GetCodeFilesPaths(), project_folder),
            'memory_address': hook.GetMemoryAddress(),
            'size': hook.GetSize(),
            'injection_file': hook.GetInjectionFile(),
            'injection_file_address': hook.GetInjectionFileAddress(),
            'auto_calculate_injection_file_address': hook.GetAutoCalculateInjectionFileAddress(),
            'enabled': hook.IsEnabled()
        }
    
    @staticmethod
    def _serialize_binary_patch(patch: BinaryPatch, project_folder: str) -> Dict[str, Any]:
        """Convert BinaryPatch to a dictionary"""
        return {
            'name': patch.GetName(),
            'code_files': PathUtils.convert_paths_to_relative(patch.GetCodeFilesPaths(), project_folder),
            'memory_address': patch.GetMemoryAddress(),
            'size': patch.GetSize(),
            'injection_file': patch.GetInjectionFile(),
            'injection_file_address': patch.GetInjectionFileAddress(),
            'auto_calculate_injection_file_address': patch.GetAutoCalculateInjectionFileAddress(),
            'enabled': patch.IsEnabled()
        }
    
    @staticmethod
    def _serialize_multipatch(multipatch: MultiPatchASM, project_folder: str) -> Dict[str, Any]:
        """Convert MultiPatchASM to a dictionary"""
        return {
            'name': multipatch.GetName(),
            'file_path': PathUtils.make_relative_if_in_project(multipatch.GetFilePath(), project_folder)
        }
    
    @staticmethod
    def _deserialize_project(project_dict: Dict[str, Any]) -> ProjectData:
        """Convert dictionary to ProjectData"""
        project_data = ProjectData()
        project_data.SetProjectName(project_dict['project_name'])
        project_data.project_folder = project_dict['project_folder']
        project_data.SetBuildVersionIndex(project_dict['currently_selected_build_index'])
        
        # Load build versions
        for bv_dict in project_dict['build_versions']:
            build_version = ProjectSerializer._deserialize_build_version(bv_dict, project_data.project_folder)
            project_data.build_versions.append(build_version)
        
        return project_data
    
    @staticmethod
    def _deserialize_build_version(bv_dict: Dict[str, Any], project_folder: str) -> BuildVersion:
        """Convert dictionary to BuildVersion"""
        from services.section_parser_service import SectionInfo
        build_version = BuildVersion()
        build_version.SetBuildName(bv_dict['build_name'])
        build_version.SetPlatform(bv_dict['platform'])
        symbols_file = bv_dict.get('symbols_file', f"{bv_dict['build_name']}.txt")
        build_version.SetSymbolsFile(symbols_file)
        build_version.injection_files = bv_dict['injection_files']
        build_version.injection_file_offsets = bv_dict['injection_file_offsets']
        build_version.injection_file_types = bv_dict.get('injection_file_types', {})
        build_version.extracted_game_folder = PathUtils.make_absolute_if_relative(bv_dict.get('extracted_game_folder'), project_folder)
        build_version.main_executable = bv_dict.get('main_executable')
        build_version.source_path = PathUtils.make_absolute_if_relative(bv_dict.get('source_path'), project_folder)
        build_version.compiler_flags = bv_dict.get('compiler_flags', '-O2')
        build_version.is_single_file_mode = bv_dict.get('is_single_file_mode', False)
        build_version.single_file_path = PathUtils.make_absolute_if_relative(bv_dict.get('single_file_path'), project_folder)
        
        # Check if game folder needs updating to build-specific path
        if build_version.extracted_game_folder:
            # Old format: .config/game_files
            # New format: .config/game_files/{build_name}
            if '.config/game_files' in build_version.extracted_game_folder:
                # Check if it's the old format (doesn't have build name)
                parts = build_version.extracted_game_folder.split(os.sep)
                if 'game_files' in parts:
                    game_files_index = parts.index('game_files')
                    # If nothing after 'game_files', it's old format
                    if game_files_index == len(parts) - 1:
                        # Update to new format
                        old_path = build_version.extracted_game_folder
                        new_path = os.path.join(old_path, build_version.build_name)
                        
                        # If old path exists but new doesn't, migrate
                        if os.path.exists(old_path) and not os.path.exists(new_path):
                            try:
                                import shutil
                                print(f"Migrating game files for build '{build_version.build_name}'")
                                print(f"   From: {old_path}")
                                print(f"   To: {new_path}")
                                shutil.move(old_path, new_path)
                                build_version.extracted_game_folder = new_path
                                print(f"Migration complete")
                            except Exception as e:
                                print(f"Migration failed: {e}")
        
        # Load codecaves
        for cc_dict in bv_dict['code_caves']:
            codecave = ProjectSerializer._deserialize_codecave(cc_dict, project_folder)
            build_version.code_caves.append(codecave)

        # Load hooks
        for h_dict in bv_dict['hooks']:
            hook = ProjectSerializer._deserialize_hook(h_dict, project_folder)
            build_version.hooks.append(hook)

        # Load binary patches
        for bp_dict in bv_dict['binary_patches']:
            patch = ProjectSerializer._deserialize_binary_patch(bp_dict, project_folder)
            build_version.binary_patches.append(patch)

        # Load multi-patches (NEW)
        for mp_dict in bv_dict.get('multi_patches', []):
            multipatch = ProjectSerializer._deserialize_multipatch(mp_dict, project_folder)
            build_version.multi_patches.append(multipatch)
            
        # Deserialize section maps
        section_maps_dict = bv_dict.get('section_maps', {})
        for filename, sections_list in section_maps_dict.items():
            sections = []
            for s_dict in sections_list:
                section = SectionInfo(
                    section_type=s_dict['section_type'],
                    file_offset=s_dict['file_offset'],
                    mem_start=s_dict['mem_start'],
                    mem_end=s_dict['mem_end'],
                    size=s_dict['size']
                )
                sections.append(section)
            build_version.section_maps[filename] = sections
        
        return build_version
        
    @staticmethod
    def _deserialize_codecave(cc_dict: Dict[str, Any], project_folder: str) -> Codecave:
        """Convert dictionary to Codecave"""
        codecave = Codecave()
        codecave.SetName(cc_dict['name'])
        codecave.code_files = PathUtils.convert_paths_to_absolute(cc_dict['code_files'], project_folder)
        codecave.SetMemoryAddress(cc_dict['memory_address'])
        codecave.SetSize(cc_dict.get('size'))
        codecave.SetInjectionFile(cc_dict.get('injection_file'))
        codecave.SetInjectionFileAddress(cc_dict.get('injection_file_address'))
        codecave.SetAutoCalculateInjectionFileAddress(
            cc_dict.get('auto_calculate_injection_file_address', False)
        )
        codecave.SetInjectionType(cc_dict.get('injection_type', 'existing_file'))
        codecave.SetEnabled(cc_dict.get('enabled', True))  # Default to enabled for backward compatibility
        return codecave
    
    @staticmethod
    def _deserialize_hook(h_dict: Dict[str, Any], project_folder: str) -> Hook:
        """Convert dictionary to Hook"""
        hook = Hook()
        hook.SetName(h_dict['name'])
        hook.code_files = PathUtils.convert_paths_to_absolute(h_dict['code_files'], project_folder)
        hook.SetMemoryAddress(h_dict['memory_address'])
        hook.SetSize(h_dict.get('size'))
        hook.SetInjectionFile(h_dict.get('injection_file'))
        hook.SetInjectionFileAddress(h_dict.get('injection_file_address'))
        hook.SetAutoCalculateInjectionFileAddress(
            h_dict.get('auto_calculate_injection_file_address', False)
        )
        hook.SetEnabled(h_dict.get('enabled', True))  # Default to enabled for backward compatibility
        return hook
    
    @staticmethod
    def _deserialize_binary_patch(bp_dict: Dict[str, Any], project_folder: str) -> BinaryPatch:
        """Convert dictionary to BinaryPatch"""
        patch = BinaryPatch()
        patch.SetName(bp_dict['name'])
        patch.code_files = PathUtils.convert_paths_to_absolute(bp_dict['code_files'], project_folder)
        patch.SetMemoryAddress(bp_dict['memory_address'])
        patch.SetSize(bp_dict.get('size'))
        patch.SetInjectionFile(bp_dict.get('injection_file'))
        patch.SetInjectionFileAddress(bp_dict.get('injection_file_address'))
        patch.SetAutoCalculateInjectionFileAddress(
            bp_dict.get('auto_calculate_injection_file_address', False)
        )
        patch.SetEnabled(bp_dict.get('enabled', True))  # Default to enabled for backward compatibility
        return patch
    
    @staticmethod
    def _deserialize_multipatch(mp_dict: Dict[str, Any], project_folder: str) -> MultiPatchASM:
        """Convert dictionary to MultiPatchASM"""
        multipatch = MultiPatchASM()
        multipatch.SetName(mp_dict['name'])
        multipatch.SetFilePath(PathUtils.make_absolute_if_relative(mp_dict['file_path'], project_folder))
        return multipatch