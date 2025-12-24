from functions.helper_funcs import *
from functions.print_wrapper import *

from classes.project_data.project_data import *

class ModBuilder():
    def __init__(self, tool_dir: str = None):
        # If tool_dir is not provided, fall back to current directory (for backwards compatibility)
        if tool_dir is None:
            import os
            tool_dir = os.getcwd()

        self.tool_dir = tool_dir
        self.compiler_exe: str = None

        # Store relative paths
        self._compiler_rel_paths = {"PS1": "prereq\\PS1mips\\bin\\mips-gcc.exe ", "PS2": "prereq\\PS2ee\\bin\\ee-gcc.exe ", "Gamecube": "prereq\\devkitPPC\\bin\\ppc-gcc.exe ", "Wii": "prereq\\devkitPPC\\bin\\ppc-gcc.exe ", "N64": "prereq\\N64mips/bin\\mips64-elf-gcc.exe "}
        self._objcopy_rel_paths = {"PS1": "prereq\\PS1mips\\bin\\mips-objcopy.exe ", "PS2": "prereq\\PS2ee\\bin\\ee-objcopy.exe ", "Gamecube": "prereq\\devkitPPC\\bin\\ppc-objcopy.exe ", "Wii": "prereq\\devkitPPC\\bin\\ppc-objcopy.exe ", "N64": "prereq\\N64mips/bin\\mips64-elf-objcopy.exe "}

        # Build absolute paths
        import os
        self.compilers = {platform: os.path.join(tool_dir, path.strip()) for platform, path in self._compiler_rel_paths.items()}
        self.objcopy_exes = {platform: os.path.join(tool_dir, path.strip()) for platform, path in self._objcopy_rel_paths.items()}

        self.compiler_text_output: str = "Ready for Compilation..."
        self.compiler_flags: str = "-O2"
        self.was_compilation_successful = False
        self.emulator_options: list[str] = list()
        self.selected_emulator: str = None
        self.LINKER_STRING: str = "-T ../../linker_script.ld -Xlinker -Map=MyMod.map "
        self.OBJCOPY_STRING: str = "-O binary .config/output/elf_files/MyMod.elf .config/output/final_bins/"
        
    def GetObjFiles(self, current_project_data: ProjectData):
        obj_files = list()
        
        code_caves = current_project_data.GetCurrentBuildVersion().GetCodeCaves()
        hooks = current_project_data.GetCurrentBuildVersion().GetHooks()
        binary_patches = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()
        
        if hooks:
            for hook in hooks:
                for asm_file in hook.GetCodeFilesNames():
                    obj_files.append(asm_file.split(".")[0] + ".o")

        if code_caves:
            for code_cave in code_caves:
                for c_file in code_cave.GetCodeFilesNames():
                    obj_files.append(c_file.split(".")[0] + ".o")
        
        return obj_files