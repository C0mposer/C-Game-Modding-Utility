from functions.helper_funcs import *
from functions.print_wrapper import *
from classes.project_data.build_version import *
from copy import deepcopy
from functions.verbose_print import verbose_print

# Stores Current Project Data
class ProjectData:
    def __init__(self):
        self.project_name: str = None
        self.project_folder: str = None
        self.build_versions: list[BuildVersion] = list()
        self.currently_selected_build_index: int = 0
        
    def SetProjectName(self, name: str):
        self.project_name = name
    def GetProjectName(self) -> str:
        return self.project_name
    
    def AddBuildVersion(self):
        new_build_version = BuildVersion()
        self.build_versions.append(new_build_version)
        
    def AddBuildVersionWithName(self, name: str):
        new_build_version = BuildVersion()
        new_build_version.SetBuildName(name)
        self.build_versions.append(new_build_version)
        
    def DuplicateBuildVersion(self, duplicate_data: BuildVersion, name: str):
        new_build_version = deepcopy(duplicate_data)
        new_build_version.SetBuildName(name)
        self.build_versions.append(new_build_version)
        
    def RemoveLatestBuildVersion(self):
        build_version_removed = self.build_versions.pop()
        print_dark_grey(build_version_removed.GetBuildName())

    def GetCurrentBuildVersion(self):
        return self.build_versions[self.currently_selected_build_index]

    def GetCurrentBuildVersionName(self):
        return self.build_versions[self.currently_selected_build_index].GetBuildName()

    def GetBuildVersionIndex(self):
        return self.currently_selected_build_index
    def SetBuildVersionIndex(self, index: int):
        self.currently_selected_build_index = index
        
    # Set the default project settings from "New Project"        
    def SetDefaultNewProjectData(self):
        self.AddBuildVersionWithName("default_build")
        self.build_versions[0].SetPlatform("PS1")

    def SetProjectFolder(self, file_path):
            base_projects_dir = "projects"

            # Check if the 'projects' directory exists
            if not os.path.exists(base_projects_dir):
                print(f"Directory '{base_projects_dir}/' does not exist. Creating it...")
                try:
                    os.makedirs(base_projects_dir, exist_ok=True)
                    print(f"Directory '{base_projects_dir}/' created successfully.")
                except OSError as e:
                    print(f"Error creating directory '{base_projects_dir}/': {e}")
                    return 

            full_project_path = os.path.join(base_projects_dir, file_path)
            

            # Check if the specific project folder exists and create it if not
            if not os.path.exists(full_project_path):
                verbose_print(f"Project folder '{full_project_path}/' does not exist. Creating it...")
                try:
                    os.makedirs(full_project_path, exist_ok=True)
                    verbose_print(f"Project folder '{full_project_path}/' created successfully.")
                except OSError as e:
                    print(f"Error creating project folder '{full_project_path}/': {e}")
                    return # Exit if project folder creation fails
                self.CreateProjectDirectories(full_project_path)
            else:
                verbose_print("Project Folder Already Exixsts!")

            self.project_folder = full_project_path
            verbose_print(f"Project folder set to: {self.project_folder}")
        
    def GetProjectFolder(self):
        return self.project_folder


    # Create the default project directories
    def CreateProjectDirectories(self, full_project_path):
        """Create the default project directories with enhanced headers"""
        import os
        
        # Create default project files and directories
        os.makedirs(f"{full_project_path}/.config")
           
        # Create symbols file for this build version
        os.makedirs(f"{full_project_path}/symbols")
        project_folder = full_project_path
        symbols_dir = os.path.join(project_folder, "symbols")
        build_name = self.GetCurrentBuildVersion().GetBuildName()
        symbols_file_path = os.path.join(symbols_dir, f"{build_name}.txt")
        # Set this as the default symbols file for the build
        self.GetCurrentBuildVersion().SetSymbolsFile(f"{build_name}.txt")
        
        with open(f"{full_project_path}/symbols/{build_name}.txt", "w") as symbols_file:
            symbols_file.write(f"/* Symbols file for build version: {build_name} */\n")
            symbols_file.write(f"/* This is where you put your in-game global variables & functions */\n")
            symbols_file.write(f"/* found from RAM search/reverse engineering for this specific version. */\n\n")
            symbols_file.write(f"/* Example: */\n")
            symbols_file.write(f"game_symbol = 0x80001234;\n")

        os.makedirs(f"{full_project_path}/src")
        with open(f"{full_project_path}/src/main.c", "w") as main_file:
            main_file.write("""#include <types.h>
#include <symbols.h>

void ModMain(void) {
    // Your code here

    return;
}

"""
    )

        os.makedirs(f"{full_project_path}/asm")
#! Make main_hook.s. Probably not needed anymore
#         with open(f"{full_project_path}/asm/main_hook.s", "w") as main_file:
#             main_file.write("""# Manual hook example

# # Enter jump/call to hook here. EX:
# j ModMain

# # Other Examples:
# # jal ModMain
# # b ModMain
# # bal ModMain

#     """)

        os.makedirs(f"{full_project_path}/include")
        
        # Create enhanced types.h
        with open(f"{full_project_path}/include/types.h", "w") as types_h:
            types_h.write("""// types.h - Auto-generated

#ifndef TYPES_H
#define TYPES_H

#include <stddef.h>
// Only include bool macro if below C23, where its a keyword
#if __STDC_VERSION__ < 202311L
#include <stdbool.h>
#endif

// ==================== Type Definitions ====================

typedef unsigned char           u8, uint8_t, byte, uchar, undefined1;
typedef signed char             s8, int8_t;
typedef unsigned short int      u16, uint16_t, ushort, undefined2;
typedef signed short int        s16, int16_t;
typedef unsigned int            u32, uint32_t, uint, undefined4;
typedef signed int              s32, int32_t;


// ==================== Helper Macros ====================

#define ARRAY_SIZE(arr) (sizeof(arr) / sizeof((arr)[0]))

#define ALIGNED(x) __attribute__((aligned(x)))
#define PACKED __attribute__((packed))

#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define MAX(a, b) ((a) > (b) ? (a) : (b))

#define BIT(n) (1U << (n))

// ==================== Modding Macros ====================

// Run code once per function call
#define ONCE \
    static bool _has_run = false; \
    if (!_has_run && (_has_run = true))
    
// Run code every X frames (function calls)
#define COOLDOWN(x)     static int _cooldown = 0;     if (_cooldown++ % x == 0)

// Easier pointer arithmetic
#define OFFSET_VAL(type, ptr, offset) (*(type*)((u8*)(ptr) + (offset))) // Get a value from a pointer at an offset
#define OFFSET_PTR(type, ptr, offset) ((type*)((u8*)(ptr) + (offset)))  // Get an address of a pointer from an offset

// Call a function without making a symbol. Good for quick tests
#define CALL_FUNC(ret, addr, ...) ((ret(*)())addr)(__VA_ARGS__)

// ==================== Hook Macros ====================

#define J_HOOK(address, ...)

#define JAL_HOOK(address, ...)

#define B_HOOK(address, ...)

#define BL_HOOK(address, ...)

#endif // TYPES_H

""")
        
        # Get platform to determine if we need osreport.h
        platform = self.GetCurrentBuildVersion().GetPlatform()

        # Build symbols.h content
        symbols_h_content = """#ifndef SYMBOLS_H
#define SYMBOLS_H
#include <types.h>
"""

        # Add osreport.h include for GameCube/Wii
        if platform in ["Gamecube", "Wii"]:
            symbols_h_content += "\n#include <osreport.h>\n"

        symbols_h_content += """
// You can define in game variables & functions like so:

// extern int player_lives;
// extern void InGameFunction(int arg1, char* arg2);

#endif //SYMBOLS_H

    """

        with open(f"{full_project_path}/include/symbols.h", "w") as symbols_h:
            symbols_h.write(symbols_h_content)

        os.makedirs(f"{full_project_path}/.config/output")
        os.makedirs(f"{full_project_path}/.config/output/object_files")
        # os.makedirs(f"{full_project_path}/.config/output/elf_files") # Probably not needed?
        #os.makedirs(f"{full_project_path}/.config/output/final_bins") # Probably not needed?
        os.makedirs(f"{full_project_path}/.config/output/memory_map")
        
        with open(f"{full_project_path}/.config/linker_script.ld", "w") as script_file:
            script_file.write("""INPUT(symbols/symbols.txt)

    MEMORY
    {
        /* RAM locations where we'll inject the code for our replacement functions */

    }

    SECTIONS
    {
        /* Custom section for all other code */
        .custom_section : 
        {
            main.o(.text)
            *(.rodata)
            *(.data)
            *(.bss)
        } > freeregion1

        /* Custom section for our hook code */
        .custom_hook :
        {
            main_hook.o(.text)
        } > hook1

        /DISCARD/ :
        {
            *(.comment)
            *(.pdr)
            *(.mdebug)
            *(.reginfo)
            *(.MIPS.abiflags)
            *(.eh_frame)
            *(.gnu.attributes)
        }
    }""")
        
        verbose_print(" Created default project structure")