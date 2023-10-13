import os
import subprocess
import shutil
import ast
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from termcolor import colored
import pcsx2_inject

class BaseIGPatch():
    def __init__(self):
        self.in_game_address = "0x00000000"
        self.disk_address = "0x00000000"
        self.disk_offset = "0x0"
        self.files = ""
        
    def __init__(self, name, in_game_address, disk_address, disk_offset, files):
        self.name = name
        self.in_game_address =in_game_address
        self.disk_address = disk_address
        self.disk_offset = disk_offset
        self.files = files
        
    def get_in_game_address_int(self):
        return int(self.in_game_address, base=16)
    
    def get_disk_address_int(self):
        return int(self.disk_address, base=16)

    def get_files_no_ext(self):
        files_no_ext = []
        for file in self.files:
            files_no_ext = file.split(".")[0]   # Splitting off extension
        return files_no_ext
    
    def get_files_obj_ext(self):
        files_obj_ext = []
        for file in self.files:
            files_obj_ext = file.split(".")[0] + ".o"   # Splitting off extension
        return files_obj_ext

class Codecave(BaseIGPatch):
    def __init__(self):
        self.name = "Codecave"
        super.__init__()
        
    def __init__(self, name, in_game_address, disk_address, disk_offset, c_files):
        super.__init__(name, in_game_address, disk_address, disk_offset, c_files)
        
class Hook(BaseIGPatch):
    def __init__(self):
        self.name = "Hook"
        super.__init__()
        
    def __init__(self, name, in_game_address, disk_address, disk_offset, asm_files):
        super.__init__(name, in_game_address, disk_address, disk_offset, asm_files)
        
        
class UserBinaryPatch(BaseIGPatch):
    def __init__(self):
        self.name = "Patch"
        super.__init__()
        
    def __init__(self, name, in_game_address, disk_address, disk_offset, patch_files):
        super.__init__(name, in_game_address, disk_address, disk_offset, patch_files)


PROJECTS_FOLDER_PATH = 'projects/'  # Replace with the path to your folder

# Lists to store project and codecave details
projects = []
code_caves = []
hooks = []
patches = []

code_caves = Codecave()


g_hasSelectedFirstProject = False

g_current_project_folder = ""
g_current_project_name = ""

g_current_project_game_exe_full_dir = ""
g_current_project_game_exe = ""

g_current_project_selected_platform = ""
g_current_project_feature_mode = ""

g_current_project_disk_offset = ""


g_platform_gcc_strings = {"PS1": "mips-gcc ", "PS2": "ee-gcc ", "Gamecube/Wii": "ppc-gcc "}

g_universal_link_string = "-T ../../linker_script.ld -Xlinker -Map=MyMod.map "
g_platform_linker_strings = {"PS1": "mips-gcc -O binary " + g_universal_link_string, "PS2": "ee-gcc " + g_universal_link_string, "Gamecube/Wii": "ppc-gcc " + g_universal_link_string}

g_universal_objcopy_string = "-O binary output/elf_files/MyMod.elf output/final_bins/"
g_platform_objcopy_strings = {"PS1": "mips-objcopy " + g_universal_objcopy_string, "PS2": "ee-objcopy " + g_universal_objcopy_string, "Gamecube/Wii": "ppc-objcopy " + g_universal_objcopy_string}
    
g_src_files = ""
g_asm_files = ""
g_obj_files = ""
g_patch_files = []

#! Compile/Inject Functionality
def Compile():  
    #print("Moving to Folder: ", g_project_folder)
    main_dir = os.getcwd()
    os.chdir(g_current_project_folder)
    
    #! Compile C/asm files
    starting_compilation = colored("Starting Compilation...", "green")
    compile_string = colored("Compilation string: " + g_platform_gcc_strings[g_current_project_selected_platform], "green")
    print(starting_compilation)
    print(compile_string)
    
    did_hook_compile_fail = os.system(g_platform_gcc_strings[g_current_project_selected_platform])
    if did_hook_compile_fail == 1:
        print("\nCompilation of Source/Hook Failed!\n\n")
        os.chdir(main_dir)
        return
    print(colored("Compilation Finished!\n"), "green")
        
    #! Link .o files
    print("Starting Link...") 
    link_string = g_platform_linker_strings[g_current_project_selected_platform]
    for file in g_obj_files.split():
        shutil.move(file, os.getcwd() + "\output\object_files\\" + file) # Move .o files from main dir to output\object_files
    
    project_dir = os.getcwd()
    os.chdir(project_dir + "\output\object_files")
    print("Link String: " + link_string + "\n")
    did_link_fail = os.system(link_string)                               # Run the link string
    if did_link_fail == 1:
        print("\n\nLinking Failed!\n\n")
        os.chdir(main_dir)
        return
    
    os.system("move MyMod.map ../memory_map > nul ")                     #The nul below is just to get rid of the ugly output
    os.chdir(project_dir)
    print("Linking Finished!\n")
    
    #! Extract Sections to Binary
    for cave in code_caves:   
        os.system(g_platform_objcopy_strings[g_current_project_selected_platform] + cave[0] + ".bin " + "--only-section ." + cave[0])
        print(f"Extracting {cave[0]} compiled code sections from elf to binary file...")
    for hook in hooks:   
        os.system(g_platform_objcopy_strings[g_current_project_selected_platform] + hook[0] + ".bin " + "--only-section ." + hook[0])
        print(f"Extracting {hook[0]} compiled asm hook sections from elf to binary file...\n")
        
    print("Build, Link, & Extracting Finished!\n\n")
    os.chdir(main_dir)
    
    #pcsx2_inject.InjectIntoPCSX2(g_project_folder, code_caves, hooks)
    #InjectIntoExe()
    #BuildPS2ISO()
    return True

def PreparePCSX2Inject(event=0):
    pcsx2_inject.InjectIntoPCSX2(g_current_project_folder, code_caves, hooks)

def InjectIntoExe():
    #Read file first to copy it
    mod_file_path = g_current_project_folder + "/output/final_bins/"
    bin_files = os.listdir(mod_file_path)
    patched_exe_name = g_current_project_folder + "/patched_" + g_current_project_game_exe_name
    
    game_exe_file_data = b""
    #print("bruh ", g_currently_selected_game_exe_full_dir)
    with open(g_current_project_game_exe_full_dir, "rb+") as game_exe_file:
        game_exe_file_data = game_exe_file.read()
        
    with open(patched_exe_name, "wb+") as game_exe_file:
        game_exe_file.write(game_exe_file_data)
        
    mod_data = {}    
    for cave in code_caves:
        #Read mod binary data into dictonary
        with open(mod_file_path + cave[0] + ".bin", "rb+") as mod_file:
            mod_data[cave[0]] = mod_file.read()
        #Seek to correct position in game exe and write the correct mod data
        with open(patched_exe_name, "rb+") as game_exe_file:
            game_exe_file.seek(int(cave[2], base=16))    
            game_exe_file.write(mod_data[cave[0]])
            
    for hook in hooks:
        #Read mod binary data into dictonary
        with open(mod_file_path + hook[0] + ".bin", "rb+") as mod_file:
            mod_data[hook[0]] = mod_file.read()
        #Seek to correct position in game exe and write the correct mod data
        with open(patched_exe_name, "rb+") as game_exe_file:
            game_exe_file.seek(int(hook[2], base=16))
            game_exe_file.write(mod_data[hook[0]])
            
#Add Button   
def BuildPS2ISO():
    # Create Iso from Folder
    NEW_ISO_NAME = "Patched Game.iso"
    IMGBURN_COMMAND = "ImgBurn.exe /MODE BUILD /SRC " + f"\"{g_current_project_folder}\Ps2IsoExtract\" /DEST " + NEW_ISO_NAME + " /FILESYSTEM \"ISO9660 + UDF\" /ROOTFOLDER YES /VOLUMELABEL \"Spyro\" /UDFREVISION 1.50" 
    os.system(IMGBURN_COMMAND)

#! Events

def validate_no_space(P):
    if " " in P:
        return False
    return True

# Used to not allow to edit other tabs until after creating/choosing a project
def open_file():
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    
    file_path = filedialog.askopenfilename()
    if file_path:
        g_current_project_game_exe_full_dir = file_path              # Full Path
        g_current_project_game_exe_name = file_path.split("/")[-1]   # Spliting based on /, and getting last index with -1 to get only name of file
        print(f"Selected file: {file_path}")
    #else:
        #messagebox.showerror("Error", "Please choose proper game executable")
    if g_current_project_game_exe_name:
        selected_game_label = ttk.Label(codecave_tab, text='Game Executable:\n' + g_current_project_game_exe_name, font=("GENIUNE", 15))
        selected_game_label.place(x=5, y=40)
        selected_game_label_hook_tab = ttk.Label(hooks_tab, text='Game Executable:\n' + g_current_project_game_exe_name, font=("GENIUNE", 15))
        selected_game_label_hook_tab.place(x=5, y=40)
   
    #Save to config     
    g_current_project_game_exe = g_current_project_game_exe_full_dir
    if g_current_project_game_exe:
        with open(f"{g_current_project_folder}/config/config.txt", "w") as config_file:
            config_file.write(g_current_project_game_exe + "\n")
            config_file.write(g_current_project_selected_platform + "\n")
            print("Game Config saved successfully: "  + g_current_project_game_exe)
            
    #Set compile button text
    name_of_exe = g_current_project_game_exe.split("/")[-1]
    inject_exe_button.config(text=f"Inject into {name_of_exe}")
        
        
def update_linker_script():
    global g_hasSelectedFirstProject
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    global g_current_project_selected_platform
    
        
    with open(f"{g_current_project_folder}/linker_script.ld", "w+") as script_file:
        script_file.write("INPUT(../../symbols/symbols.txt)\nINPUT(../../symbols/function_symbols.txt)\n\nMEMORY\n{\n    /* RAM locations where we'll inject the code for our replacement functions */\n")
        for i, cave in enumerate(code_caves):
            script_file.write(f"    {cave[0]} : ORIGIN = {cave[1]}, LENGTH = 0xFFFF\n")
        for i, hook in enumerate(hooks):
            script_file.write(f"    {hook[0]} : ORIGIN = {hook[1]}, LENGTH = 0xFFFF\n")
            
        script_file.write("}\n\nSECTIONS\n{\n    /* Custom section for Compiled code */\n    ")
        #Code Caves
        for i, cave in enumerate(code_caves):
            script_file.write("." + cave[0])
            script_file.write(" : \n    {\n")
            for c_file in cave[3]:
                o_file = c_file.split(".")[0] + ".o"
                script_file.write("        " + o_file + "(.text)\n        " + o_file + "(.rodata)\n        " + o_file + "(.data)\n        " + o_file + "(.bss)\n")
                #script_file.write("main.o(.text)\n        *(.rodata)\n        *(.data)\n        *(.bss)\n    } > ")
            script_file.write("    } > ")
            script_file.write(f"{cave[0]}\n\n    ")
        #Hooks
        for i, hook in enumerate(hooks):
            script_file.write("/* Custom section for our hook code */\n    ")
            script_file.write("." + hook[0])
            script_file.write(" : \n    {\n")
            for asm_file in hook[3]:
                o_file = asm_file.split(".")[0] + ".o"
                script_file.write("        " + o_file + "(.text)\n        " + o_file + "(.rodata)\n        " + o_file + "(.data)\n        " + o_file + "(.bss)\n")
            script_file.write("    } > ")
            script_file.write(f"{hook[0]}\n\n    ")
            
        script_file.write("/DISCARD/ :\n    {\n        *(.comment)\n        *(.pdr)\n        *(.mdebug)\n        *(.reginfo)\n        *(.MIPS.abiflags)\n        *(.eh_frame)\n        *(.gnu.attributes)\n    }\n}")

def update_codecaves_hooks_config_file():
    with open(f"{g_current_project_folder}/config/codecaves.txt", "w") as codecaves_file:
        codecaves_file.write("Codecaves:\n")
        codecaves_file.write(str(code_caves))
            
    with open(f"{g_current_project_folder}/config/hooks.txt", "w") as hook_file:
        hook_file.write("hooks:\n")
        hook_file.write(str(hooks))
            
    #with open(f"{g_current_project_folder}/config/config.txt", "w") as config_file:
        #config_file.write(g_current_project_game_exe + "\n")
        #config_file.write(g_current_project_selected_platform + "\n")
        #config_file.write(g_current_project_disk_offset)
    
def project_switched():
    global g_hasSelectedFirstProject
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    global g_current_project_selected_platform
    global g_current_project_disk_offset
    
    #Only run once for first project selected
    if g_hasSelectedFirstProject == False:
        tab_control.add(codecave_tab, text='In-Game Codecaves')
        tab_control.add(hooks_tab, text='ASM Hooks')
        tab_control.add(compile_tab, text='Compile')
    g_hasSelectedFirstProject = True
        
    # For every re-selection/creation
    # Add Current Project Text Label
    current_project_label = ttk.Label(main_tab, text='Current Project:\n' + g_current_project_name, font=("GENIUNE", 20))
    current_project_label.place(x=5, y=5)
    # Clear textbox entries
    codecave_name_entry.delete(0, tk.END)
    hook_name_entry.delete(0, tk.END)
    in_game_memory_entry.delete(0, tk.END)
    in_game_memory_entry_hooks.delete(0, tk.END)
    disk_exe_entry.delete(0, tk.END)
    disk_exe_entry_hooks.delete(0, tk.END)
    c_files_entry.delete(0, tk.END)
    asm_files_entry.delete(0, tk.END)
    
    #Check for config.txt for game exe
    try:
        with open(f"{g_current_project_folder}/config/config.txt", "r") as config_file:
            g_current_project_game_exe = config_file.readline()
            g_current_project_game_exe_full_dir = g_current_project_game_exe.split("\n")[0] # Remove newline
            try:
                g_current_project_selected_platform = config_file.readline().split()[0]
                g_current_project_disk_offset = config_file.readline()
            except:
                print("No platform saved in config yet!")
            g_current_project_game_exe_name = g_current_project_game_exe.split("/")[-1].split("\n")[0] # spliting based on /, and getting last index with -1 to get only name of file, and getting rid of \n at end
            print("Game Config Loaded successfully: "  + g_current_project_game_exe + " " + g_current_project_selected_platform)
            selected_game_label = ttk.Label(codecave_tab, text='Game Executable:\n' + g_current_project_game_exe_name, font=("GENIUNE", 15))
            selected_game_label.place(x=5, y=40)
            selected_game_label_hook_tab = ttk.Label(hooks_tab, text='Game Executable:\n' + g_current_project_game_exe_name, font=("GENIUNE", 15))
            selected_game_label_hook_tab.place(x=5, y=40)
            platform_combobox.set(g_current_project_selected_platform)
    except FileNotFoundError:
        print("No config file")
        g_current_project_game_exe = ""
        g_current_project_game_exe_name = ""
        selected_game_label = ttk.Label(codecave_tab, text='Game Executable:\n' + "None Selected", font=("GENIUNE", 15))
        selected_game_label.place(x=5, y=40)
        selected_game_label_hook_tab = ttk.Label(hooks_tab, text='Game Executable:\n' + "None Selected", font=("GENIUNE", 15))
        selected_game_label_hook_tab.place(x=5, y=40)
    
def create_project():
    global g_current_project_name
    global g_current_project_feature_mode
    global g_current_project_folder
    global code_caves
    global hooks
    
    # Check Project Name Entry
    project_name = project_name_entry.get()
    if not project_name:
        messagebox.showerror("Error", "Please enter a project name.")
        return
    
    # Saving Project name and Directory
    g_current_project_name = project_name
    g_current_project_folder = f"projects/{project_name}"
    if os.path.exists(g_current_project_folder):
        messagebox.showerror("Error", "Project already exists.")
        g_current_project_name = ""
        g_current_project_folder = ""
        return
    
    project_switched()
    print("Currently Selected Project is now: "+ g_current_project_name)

    g_current_project_feature_mode = "Normal"
    
    #Create Main Project Folder
    os.makedirs(g_current_project_folder)
    # Create project files and directories
    os.makedirs(f"{g_current_project_folder}/symbols")
    with open(f"{g_current_project_folder}/symbols/symbols.txt", "w") as symbols_file:
        symbols_file.write("/* This is where you would put your in game global variables you've found from a ram search/reverse engineering */\ngame_symbol = 0x80001234;\n")
    with open(f"{g_current_project_folder}/symbols/function_symbols.txt", "w") as symbols_file:
        symbols_file.write("/* This is where you would put your in game functions you've found through reverse engineering */\nGameFunction = 0x80005678;\n")
        
    os.makedirs(f"{g_current_project_folder}/config")
    with open(f"{g_current_project_folder}/config/codecaves.txt", "w") as codecaves_file:
        codecaves_file.write("")
        
    with open(f"{g_current_project_folder}/config/hooks.txt", "w") as codecaves_file:
        codecaves_file.write("")

    os.makedirs(f"{g_current_project_folder}/src")
    with open(f"{g_current_project_folder}/src/main.c", "w") as main_file:
        main_file.write("#include <stdbool.h>\n#include <custom_types.h>\n#include <symbols.h>\n\nvoid MainHook(void) {\n    // Your code here\n    return;\n}\n")

    os.makedirs(f"{g_current_project_folder}/asm")
    with open(f"{g_current_project_folder}/asm/main_hook.s", "w") as main_file:
        main_file.write("# Enter jump/call to hook here. EX:\njal MainHook\nnop\n")

    os.makedirs(f"{g_current_project_folder}/include")
    with open(f"{g_current_project_folder}/include/symbols.h", "w") as symbols_h:
        symbols_h.write("#ifndef SYMBOLS_H\n#define SYMBOLS_H\n\n\n#endif //SYMBOLS_H\n")
    with open(f"{g_current_project_folder}/include/custom_types.h", "w") as symbols_h:
        symbols_h.write("#ifndef CUSTOM_TYPES_H\n#define CUSTOM_TYPES_H\n\ntypedef char                    byte;\ntypedef signed char             s8;\ntypedef unsigned char           u8;\ntypedef signed short int        s16;\ntypedef unsigned short int      u16;\ntypedef signed int              s32;\ntypedef unsigned int            u32;\n\n#endif //CUSTOM_TYPES_H\n")
    
    os.makedirs(f"{g_current_project_folder}/output")
    os.makedirs(f"{g_current_project_folder}/output/object_files")
    os.makedirs(f"{g_current_project_folder}/output/elf_files")
    os.makedirs(f"{g_current_project_folder}/output/final_bins")
    os.makedirs(f"{g_current_project_folder}/output/memory_map")
    
    with open(f"{g_current_project_folder}/linker_script.ld", "w") as script_file:
        script_file.write("INPUT(symbols/symbols.txt)\nINPUT(symbols/function_symbols.txt)\n\nMEMORY\n{\n    /* RAM locations where we'll inject the code for our replacement functions */\n\n}\n\nSECTIONS\n{\n    /* Custom section for all other code */\n    .custom_section : \n    {\n        main.o(.text)\n        *(.rodata)\n        *(.data)\n        *(.bss)\n    } > freeregion1\n\n    /* Custom section for our hook code */\n    .custom_hook :\n    {\n        main_hook.o(.text)\n    } > hook1\n\n    /DISCARD/ :\n    {\n        *(.comment)\n        *(.pdr)\n        *(.mdebug)\n        *(.reginfo)\n        *(.MIPS.abiflags)\n        *(.eh_frame)\n        *(.gnu.attributes)\n    }\n}")
    
    #Clearing GUI & Setting defaults
    codecaves_listbox.delete(0, tk.END)
    code_caves = [('MainCodecave', '0x00000000', '0x0', ['main.c'])]    # Clearing previous code caves and filling the default
    codecaves_listbox.insert(tk.END, code_caves[0][0])
    
    hooks_listbox.delete(0, tk.END)
    hooks = [('MainHook', '0x00000000', '0x0', ['main_hook.s'])]          # Clearing the previous hooks and filling the default
    hooks_listbox.insert(tk.END, hooks[0][0])
    
    #Add project to list, and clear entry
    projects.append(project_name)
    ########project_listbox.insert(tk.END, project_name)
    project_name_entry.delete(0, tk.END)

    
    #Get all names of projects in project folder and fill select box to populate from new project
    project_listbox.delete(0, tk.END) # Clear listbox
    project_folder_names = [folder for folder in os.listdir(PROJECTS_FOLDER_PATH) if os.path.isdir(os.path.join(PROJECTS_FOLDER_PATH, folder))]
    
    for project in project_folder_names:
        project_listbox.insert(tk.END, project)
        print("Project Names: " + project)

    # Show a "Project added" dialog
    messagebox.showinfo("Success", "Project created successfully.")
    update_codecaves_hooks_config_file()

def select_project(event=0):
    global g_current_project_name
    global code_caves
    global hooks
    global g_current_project_folder
    
    try:
        selected_project = project_listbox.get(project_listbox.curselection())
    except:
        messagebox.showerror("Error", "No project selected")
        return
    g_current_project_name = selected_project
    g_current_project_folder = f"projects/" + g_current_project_name
    print("Currently Selected Project is now: "+ g_current_project_name)
    project_switched()
    
    code_caves = []   # Clearing previous code cave
    
    #Check for a codecaves.txt file and fill the python list with the data in it using an ast evaluation
    if os.path.exists(f"projects/" + selected_project + "/config/codecaves.txt"):
        codecaves_listbox.delete(0, tk.END)
        with open(f"projects/" + selected_project + "/config/codecaves.txt", "r") as codecaves_file:
            codecaves_file.readline() # Skip the first line
            file_string = codecaves_file.read()
            if file_string:
                ast_file_string = ast.literal_eval(file_string)
                code_caves = ast_file_string
                print("Code Caves updated to: " + str(code_caves))
                # Show a "Project added" dialog
                i = 0
                for cave in code_caves:
                    print("Codecaves loaded: " + str(cave))
                    codecaves_listbox.insert(tk.END, cave[0])
                    i += i
    
    hooks = []   # Clearing previous hooks
    
    #Check for a hooks.txt file and fill the python list with the data in it using an ast evaluation    
    if os.path.exists(f"projects/" + selected_project + "/config/hooks.txt"):
        hooks_listbox.delete(0, tk.END)
        with open(f"projects/" + selected_project + "/config/hooks.txt", "r") as hook_file:
            hook_file.readline() # Skip the first line
            file_string = hook_file.read()
            ast_file_string = ast.literal_eval(file_string)
            hooks = ast_file_string
            print("Hooks updated to: " + str(hooks))
        # Show a "Project added" dialog
        i = 0
        for hook in hooks:
            print("Hooks loaded: " + str(hook))
            hooks_listbox.insert(tk.END, hook[0])
            i += i
    #Update Platform Settings
    on_platform_select()
    update_linker_script()
            
    
def remove_project_confirm():
    if project_listbox.curselection():
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete " + str(project_listbox.get(project_listbox.curselection())) + " project?") == True:
            remove_project()
    else:
        messagebox.showerror("Error", "Must select project to delete")
        
    
def remove_project():
    global g_current_project_folder
    selected_project_index = project_listbox.curselection()
    selected_project_name = project_listbox.get(selected_project_index)
    
    project_listbox.delete(selected_project_index)

    project_dir_to_delete = "projects/" + selected_project_name

    try:
        shutil.rmtree(project_dir_to_delete)
        messagebox.showinfo("Success", f"Directory '{project_dir_to_delete}' and its contents have been deleted.")
        print(f"Directory '{project_dir_to_delete}' and its contents have been deleted.")
    except FileNotFoundError:
        messagebox.showerror("Error", f"Directory '{project_dir_to_delete}' does not exist.")
        print(f"Directory '{project_dir_to_delete}' does not exist.")
    except PermissionError:
        messagebox.showerror("Error," f"Permission denied. Unable to delete '{project_dir_to_delete}'.")
        print(f"Permission denied. Unable to delete '{project_dir_to_delete}'.")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        print(f"An error occurred: {e}")
    
    
    
        
def add_codecave():
    global g_current_project_folder
    global g_current_project_name
    
    does_already_exist = False
    index_where_exists = 0
    
    cave_name = codecave_name_entry.get()
    in_game_memory = in_game_memory_entry.get()
    disk_memory = disk_exe_entry.get()
    
    #Check if name already exists, to only update the codecave, not create a new one
    for i, cave in enumerate(code_caves):
        if cave_name == cave[0]:
            does_already_exist = True
            index_where_exists = i
            
    # Split on commas if found, else split on spaces
    if  c_files_entry.get().find(",") != -1:
        print('Comma Found in C File prompt')
        c_files = c_files_entry.get().split(', ')
    else:
        print('No Comma found in C File prompt')
        c_files = c_files_entry.get().split()

    if not cave_name or not in_game_memory or not disk_memory or not c_files:
        messagebox.showerror("Error", "Please fill in all fields.")
        return
    
    
    if does_already_exist == False:
        code_caves.append((cave_name, in_game_memory, disk_memory, c_files))
        codecaves_listbox.insert(tk.END, cave_name)
    else:
        print("Already Exists here: ", index_where_exists)
        code_caves[index_where_exists] = (cave_name, in_game_memory, disk_memory, c_files)
    
    #Update project_folder for safetey, and then create a config folder if not already existing
    g_current_project_folder = f"projects/" + g_current_project_name   
    try:
        os.makedirs(f"{g_current_project_folder}/config")
    except OSError:
        print("Config directory already exists")
           
    codecave_name_entry.delete(0, tk.END)
    in_game_memory_entry.delete(0, tk.END)
    disk_exe_entry.delete(0, tk.END)
    c_files_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_config_file()

def remove_codecave(event=0):
    global g_current_project_folder
    selected_codecave_index = codecaves_listbox.curselection()
    if selected_codecave_index:
        codecaves_listbox.delete(selected_codecave_index)
        del code_caves[selected_codecave_index[0]]
        codecave_name_entry.delete(0, tk.END)
        in_game_memory_entry.delete(0, tk.END)
        disk_exe_entry.delete(0, tk.END)
        c_files_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_config_file()
        

def select_codecave(event):
    selected_codecave_index = codecaves_listbox.curselection()
    if selected_codecave_index:
        selected_codecave = code_caves[selected_codecave_index[0]]
        codecave_name_entry.delete(0, tk.END)
        in_game_memory_entry.delete(0, tk.END)
        disk_exe_entry.delete(0, tk.END)
        c_files_entry.delete(0, tk.END)

        codecave_name_entry.insert(0, selected_codecave[0])
        in_game_memory_entry.insert(0, selected_codecave[1])
        disk_exe_entry.insert(0, selected_codecave[2])
        c_files_entry.insert(0, ", ".join(selected_codecave[3]))
        update_linker_script()
        
        
               
def replace_codecave_offset_text(event=0):
    global g_current_project_disk_offset
    
    disk_memory_value = in_game_memory_entry.get()
    offset_value = global_offset_entry.get()
    if disk_memory_value and offset_value:
        try:
            disk_memory = int(disk_memory_value.removeprefix("0x"), base=16) + int(offset_value.removeprefix("0x"), base=16)
            disk_exe_entry.delete(0, tk.END)
            disk_exe_entry.insert(0, hex(disk_memory))
            g_current_project_disk_offset = offset_value
            
        except ValueError:
            print("Invalid values for in-game memory or offset.")
    else:
        pass
        #global_offset_entry.config(state="disabled")
    
    update_codecaves_hooks_config_file()
    
def replace_hook_offset_text(event=0):
    global g_current_project_disk_offset
    
    disk_memory_value = in_game_memory_entry_hooks.get()
    offset_value = global_offset_entry_hooks.get()
    if disk_memory_value and offset_value:
        try:
            disk_memory = int(disk_memory_value.removeprefix("0x80"), base=16) + int(offset_value.removeprefix("0x"), base=16)
            disk_exe_entry_hooks.delete(0, tk.END)
            disk_exe_entry_hooks.insert(0, hex(disk_memory))
            g_current_project_disk_offset = offset_value
        except ValueError:
            print("Invalid values for in-game memory or offset.")
    else:
        pass
        #global_offset_entry.config(state="disabled")
    
    update_codecaves_hooks_config_file()

def toggle_offset_text_state():
    status = is_global_offset_checkbox_checked.get()
    if status == 1:
        global_offset_entry.config(state="enabled")
        global_offset_entry_hooks.config(state="enabled")
        #global_offset_update.config(state="enabled")
        disk_exe_entry.delete(0, tk.END)
        disk_exe_entry_hooks.delete(0, tk.END)
    else:
        global_offset_entry.config(state="disabled")
        global_offset_entry_hooks.config(state="disabled")
       #global_offset_update.config(state="disabled")

    #Update values when checkbox ticked for quality of life   
    replace_codecave_offset_text()


def add_hook():
    global g_current_project_folder
    global g_current_project_name
    
    does_already_exist = False
    index_where_exists = 0
    
    hook_name = hook_name_entry.get()
    in_game_hook_memory = in_game_memory_entry_hooks.get()
    disk_hook_memory = disk_exe_entry_hooks.get()
    
    #Check if name already exists, to only update the hook, not create a new one
    for i, hook in enumerate(hooks):
        if hook_name == hook[0]:
            does_already_exist = True
            index_where_exists = i
            print("Hooks: " + hook[i])
        i += i
               
    # Split on commas if found, else split on spaces
    if  asm_files_entry.get().find(",") != -1:
        print('Comma Found in asm File prompt')
        asm_files = asm_files_entry.get().split(',')
    else:
        print('No Comma found in asm File prompt')
        asm_files = asm_files_entry.get().split()

    if not hook_name or not in_game_hook_memory or not disk_hook_memory or not asm_files:
        messagebox.showerror("Error", "Please fill in all fields.")
        return
    
    if does_already_exist == False:
        hooks.append((hook_name, in_game_hook_memory, disk_hook_memory, asm_files))
        hooks_listbox.insert(tk.END, hook_name)
    else:
        hooks[index_where_exists] = (hook_name, in_game_hook_memory, disk_hook_memory, asm_files)
    
    
    #Update project_folder for safetey, and then create a config folder if not already existing
    g_current_project_folder = f"projects/" + g_current_project_name   
    try:
        os.makedirs(f"{g_current_project_folder}/config")
    except OSError:
        print("Config directory already exists")
        
           
    hook_name_entry.delete(0, tk.END)
    in_game_memory_entry_hooks.delete(0, tk.END)
    disk_exe_entry_hooks.delete(0, tk.END)
    asm_files_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_config_file()

def remove_hook(event=0):
    global g_current_project_folder
    
    selected_hook_index = hooks_listbox.curselection()
    if selected_hook_index:
        hooks_listbox.delete(selected_hook_index)
        del hooks[selected_hook_index[0]]
        hook_name_entry.delete(0, tk.END)
        in_game_memory_entry_hooks.delete(0, tk.END)
        disk_exe_entry_hooks.delete(0, tk.END)
        asm_files_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_config_file()
        

def select_hook(event):
    selected_hook_index = hooks_listbox.curselection()
    if selected_hook_index:
        selected_hook = hooks[selected_hook_index[0]]
        hook_name_entry.delete(0, tk.END)
        in_game_memory_entry_hooks.delete(0, tk.END)
        disk_exe_entry_hooks.delete(0, tk.END)
        asm_files_entry.delete(0, tk.END)

        hook_name_entry.insert(0, selected_hook[0])
        in_game_memory_entry_hooks.insert(0, selected_hook[1])
        disk_exe_entry_hooks.insert(0, selected_hook[2])
        asm_files_entry.insert(0, ", ".join(selected_hook[3]))
        update_linker_script()
        update_codecaves_hooks_config_file()
        
        
          
def add_patch():
    global g_current_project_folder
    global g_current_project_name
    
    does_already_exist = False
    index_where_exists = 0
    
    patch_name = patch_name_entry.get()
    in_game_patch_memory = in_game_memory_entry_patches.get()
    disk_patch_memory = disk_exe_entry_patches.get()
    
    #Check if name already exists, to only update the patch, not create a new one
    for i, patch in enumerate(patches):
        if patch_name == patch[0]:
            does_already_exist = True
            index_where_exists = i
            print("patches: " + patch[i])
        i += i
               
    # Split on commas if found, else split on spaces
    if  patch_files_entry.get().find(",") != -1:
        print('Comma Found in patch File prompt')
        patch_files = patch_files_entry.get().split(',')
    else:
        print('No Comma found in patch File prompt')
        patch_files = patch_files_entry.get().split()

    if not patch_name or not in_game_patch_memory or not disk_patch_memory or not patch_files:
        messagebox.showerror("Error", "Please fill in all fields.")
        return
    
    if does_already_exist == False:
        patches.append((patch_name, in_game_patch_memory, disk_patch_memory, patch_files))
        patches_listbox.insert(tk.END, patch_name)
    else:
        patches[index_where_exists] = (patch_name, in_game_patch_memory, disk_patch_memory, patch_files)
    
    #Update project_folder for safetey, and then create a config folder if not already existing
    g_current_project_folder = f"projects/" + g_current_project_name   
    try:
        os.makedirs(f"{g_current_project_folder}/config")
    except OSError:
        print("Config directory already exists")
           
    patch_name_entry.delete(0, tk.END)
    in_game_memory_entry_patches.delete(0, tk.END)
    disk_exe_entry_patches.delete(0, tk.END)
    patch_files_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_config_file()

def remove_patch(event=0):
    global g_current_project_folder
    
    selected_patch_index = patches_listbox.curselection()
    if selected_patch_index:
        patches_listbox.delete(selected_patch_index)
        del patches[selected_patch_index[0]]
        patch_name_entry.delete(0, tk.END)
        in_game_memory_entry_patches.delete(0, tk.END)
        disk_exe_entry_patches.delete(0, tk.END)
        patch_files_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_config_file()
        

def select_patch(event):
    selected_patch_index = patches_listbox.curselection()
    if selected_patch_index:
        selected_patch = patches[selected_patch_index[0]]
        patch_name_entry.delete(0, tk.END)
        in_game_memory_entry_patches.delete(0, tk.END)
        disk_exe_entry_patches.delete(0, tk.END)
        asm_files_entry.delete(0, tk.END)

        patch_name_entry.insert(0, selected_patch[0])
        in_game_memory_entry_patches.insert(0, selected_patch[1])
        disk_exe_entry_patches.insert(0, selected_patch[2])
        patch_files_entry.insert(0, ", ".join(selected_patch[3]))
        update_linker_script()
        update_codecaves_hooks_config_file()
        
        
def ensure_hex_entries(event=0):
    if len(in_game_memory_entry.get()) < 2:
        in_game_memory_entry.insert(0, "0x")
            
    if len(disk_exe_entry.get()) < 2:
        disk_exe_entry.insert(0, "0x")
            
    if len(global_offset_entry.get()) < 2:
        global_offset_entry.insert(0, "0x")

    if len(in_game_memory_entry_hooks.get()) < 2:
        in_game_memory_entry_hooks.insert(0, "0x")
            
    if len(disk_exe_entry_hooks.get()) < 2:
        disk_exe_entry_hooks.insert(0, "0x")
            
    if len(global_offset_entry_hooks.get()) < 2:
        global_offset_entry_hooks.insert(0, "0x")
     
                       
def on_platform_select(event=0):
    global g_current_project_selected_platform
    global g_src_files
    global g_asm_files
    global g_obj_files
    global g_patch_files
    global g_platform_gcc_strings
    global g_platform_linker_strings
    
    #Reset
    g_platform_gcc_strings = {"PS1": "mips-gcc ", "PS2": "ee-gcc ", "Gamecube/Wii": "ppc-gcc "}
    g_platform_linker_strings = {"PS1": "mips-gcc " + g_universal_link_string, "PS2": "ee-gcc " + g_universal_link_string, "Gamecube/Wii": "ppc-gcc " + g_universal_link_string}
    g_src_files = ""
    g_asm_files = ""
    g_obj_files = ""
    
    #Get the current platform selection from the combo-box
    g_current_project_selected_platform = platform_combobox.get()
    #Save to config     
    if g_current_project_selected_platform:
        with open(f"{g_current_project_folder}/config/config.txt", "w+") as config_file:
            config_file.write(g_current_project_game_exe_full_dir + "\n")
            config_file.write(g_current_project_selected_platform)
            print("Game Config saved successfully with platform: "  +  g_current_project_selected_platform)
            
    # Get C files 
    for code_cave in code_caves:
        for c_file in code_cave[3]:
            g_src_files += "src/" + c_file + " "
            g_obj_files += c_file.split(".")[0] + ".o"  + " "
    
    #Get ASM Files        
    for hook in hooks:
        for asm_file in hook[3]:
            g_asm_files += "asm/" + asm_file + " "
            g_obj_files += asm_file.split(".")[0] + ".o"  + " "
               
    
    #Get Patch Files        
    for patch in patches:
        for patch_file in patch[3]:
            g_patch_files.append("patches/" + patch_file)
            
            
    for key in g_platform_gcc_strings:
        # Add src files to gcc strings
        g_platform_gcc_strings[key] += g_src_files + g_asm_files
        g_platform_linker_strings[key] += g_obj_files + "-o ../elf_files/MyMod.elf -nostartfiles" # ../ because of weird linker thing with directories? In Build I have to do chdir.
        
        if key == "PS1" or key == "PS2":
            g_platform_gcc_strings[key] += "-c -G0 -Os -I include"
        if key == "Gamecube/Wii":
            g_platform_gcc_strings[key] += "-c -Os -I include"
    
    #Set compile button text
    name_of_exe = g_current_project_game_exe.split("/")[-1]
    inject_exe_button.config(text=f"Inject into {name_of_exe}")
            
    #Set gcc/linker text
    #gcc_label.config(text=f"GCC String for {g_current_project_selected_platform}:\n{g_platform_gcc_strings[g_current_project_selected_platform]}\n")
    #linker_label.config(text=f"Linker string for {g_current_project_selected_platform}:\n{g_platform_linker_strings[g_current_project_selected_platform]}\n", font=("GENIUNE", 8))

# Function to handle the selection change
def on_feature_mode_selected(event=0):
    selected = current_project_feature_mode.get()
    g_current_project_feature_mode = selected
    print(f"Selected mode: {selected}")
    
    if g_current_project_feature_mode == "Advanced":
        tab_control.add(patches_tab, text='Patches')
    else:
        tab_control.hide(patches_tab)

#! MAIN


root = tk.Tk()
root.title("Game Code Injection Tool")
root.geometry("800x600")
root.bind("<KeyRelease>", ensure_hex_entries)
root.iconbitmap("icon.ico")
root.resizable(False, False)
validate_no_space_cmd = root.register(validate_no_space)

# Create tabs
tab_control = ttk.Notebook(root)
main_tab = ttk.Frame(tab_control)
codecave_tab = ttk.Frame(tab_control)
hooks_tab = ttk.Frame(tab_control)
patches_tab = ttk.Frame(tab_control)
compile_tab = ttk.Frame(tab_control)

tab_control.add(main_tab, text='Main')
tab_control.pack(expand=1, fill='both')

#! Main Tab

#Feature Mode Combobox
feature_modes = ["Normal", "Advanced"]
current_project_feature_mode = tk.StringVar()
project_feature_combobox = ttk.Combobox(root, textvariable=current_project_feature_mode, values=feature_modes)
project_feature_combobox.pack(side="right", anchor="nw")
project_feature_combobox.bind("<<ComboboxSelected>>", on_feature_mode_selected)

project_name_label = ttk.Label(main_tab, text='New Project Name:', font=("Trebuchet MS", 10))
project_name_label.pack()
project_name_entry = ttk.Entry(main_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
project_name_entry.pack(pady=2)
create_project_button = tk.Button(main_tab, text='Create New Project', command=create_project)
select_project_button = tk.Button(main_tab, text='Select Existing Project', command=select_project)
create_project_button.pack(pady=2)
select_project_button.pack(pady=(20, 0))


# Create a listbox to display existing projects
project_listbox = tk.Listbox(main_tab, selectmode=tk.SINGLE)
project_listbox.pack(pady=2, fill=tk.BOTH, expand=True)
project_listbox.bind("<KeyPress-Return>", select_project)
project_listbox.bind("<KeyPress-space>", select_project)
project_listbox.bind("<Double-Button-1>", select_project)

#Get all names of projects in project folder and fill select box
project_folder_names = [folder for folder in os.listdir(PROJECTS_FOLDER_PATH) if os.path.isdir(os.path.join(PROJECTS_FOLDER_PATH, folder))]
for project in project_folder_names:
    project_listbox.insert(0, project)
    print("Projects Loaded: " + project)
    
# Button to remove selected project
remove_project_button = ttk.Button(main_tab, text='Remove Project', command=remove_project_confirm)
remove_project_button.pack()

#! In-Game Codecaves Tab

codecave_name_label = ttk.Label(codecave_tab, text="Codecave Name:")
codecave_name_label.pack()
codecave_name_entry = ttk.Entry(codecave_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
codecave_name_entry.pack(pady=5)

in_game_memory_label = ttk.Label(codecave_tab, text='Memory address in game:')
in_game_memory_label.pack()
in_game_memory_entry = ttk.Entry(codecave_tab,  validate="key", validatecommand=(validate_no_space_cmd, "%P"))
in_game_memory_entry.pack(pady=5)
in_game_memory_entry.bind("<KeyRelease>", replace_codecave_offset_text)


is_global_offset_checkbox_checked = tk.IntVar()
global_offset_checkbox = ttk.Checkbutton(hooks_tab, text="Use Offset for Disk", variable=is_global_offset_checkbox_checked, command=toggle_offset_text_state)
global_offset_checkbox.place(x=470, y=98)
global_offset_entry = ttk.Entry(codecave_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
global_offset_entry.place(x=470, y=123)
global_offset_entry.config(state="disabled")
global_offset_entry.bind("<KeyRelease>", replace_codecave_offset_text)
#global_offset_update = ttk.Button(codecave_tab, text="Update", command=replace_codecave_offset_text)
#global_offset_update.place(x=600, y=75)
#global_offset_update.config(state="disabled")


disk_exe_label = ttk.Label(codecave_tab, text='Address in game executable:',)
disk_exe_label.pack()
disk_exe_entry = ttk.Entry(codecave_tab, validatecommand=(validate_no_space_cmd, "%P"))
disk_exe_entry.pack(pady=5)

c_files_label = ttk.Label(codecave_tab, text='C Files:')
c_files_label.pack()
c_files_entry = ttk.Entry(codecave_tab)
c_files_entry.pack(pady=5)

add_codecave_button = ttk.Button(codecave_tab, text='Add/Edit Codecave', command=add_codecave)
add_codecave_button.pack(pady=10)

# Create a listbox to display added codecaves
codecaves_listbox = tk.Listbox(codecave_tab, selectmode=tk.SINGLE)
codecaves_listbox.pack(pady=10, fill=tk.BOTH, expand=True)
codecaves_listbox.bind('<<ListboxSelect>>', select_codecave)
codecaves_listbox.bind('<KeyPress-Delete>', remove_codecave)

# Button to remove selected codecave
remove_codecave_button = ttk.Button(codecave_tab, text='Remove Codecave', command=remove_codecave)
remove_codecave_button.pack()

#! Hooks Tab

hook_name_label = ttk.Label(hooks_tab, text='Hook Name:')
hook_name_label.pack()
hook_name_entry = ttk.Entry(hooks_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
hook_name_entry.pack(pady=5)

in_game_memory_hook_label = ttk.Label(hooks_tab, text='In-Game Memory Address:')
in_game_memory_hook_label.pack()
in_game_memory_entry_hooks = ttk.Entry(hooks_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
in_game_memory_entry_hooks.pack(pady=5)

global_offset_checkbox_hooks = ttk.Checkbutton(codecave_tab, text="Use Offset for Disk", variable=is_global_offset_checkbox_checked, command=toggle_offset_text_state)
global_offset_checkbox_hooks.place(x=470, y=98)
global_offset_entry_hooks = ttk.Entry(hooks_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
global_offset_entry_hooks.place(x=470, y=123)
global_offset_entry_hooks.config(state="disabled")
global_offset_entry_hooks.bind("<KeyRelease>", replace_hook_offset_text)

disk_exe_hook_label = ttk.Label(hooks_tab, text='Disk Executable Address:')
disk_exe_hook_label.pack()
disk_exe_entry_hooks = ttk.Entry(hooks_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
disk_exe_entry_hooks.pack(pady=5)

asm_files_label = ttk.Label(hooks_tab, text='ASM Files:')
asm_files_label.pack()
asm_files_entry = ttk.Entry(hooks_tab)
asm_files_entry.pack(pady=5)

add_codecave_button = ttk.Button(hooks_tab, text='Add/Edit Hook', command=add_hook)
add_codecave_button.pack(pady=10)

# Create a listbox to display added hooks
hooks_listbox = tk.Listbox(hooks_tab, selectmode=tk.SINGLE)
hooks_listbox.pack(pady=10, fill=tk.BOTH, expand=True)
hooks_listbox.bind('<<ListboxSelect>>', select_hook)
hooks_listbox.bind('<KeyPress-Delete>', remove_hook)

# Button to remove selected codecave
remove_hook_button = ttk.Button(hooks_tab, text='Remove Hook', command=remove_hook)
remove_hook_button.pack()

#! Patches Tab
patch_name_label = ttk.Label(patches_tab, text='Patch Name:')
patch_name_label.pack()
patch_name_entry = ttk.Entry(patches_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
patch_name_entry.pack(pady=5)

in_game_memory_patch_label = ttk.Label(patches_tab, text='In-Game Memory Address:')
in_game_memory_patch_label.pack()
in_game_memory_entry_patches = ttk.Entry(patches_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
in_game_memory_entry_patches.pack(pady=5)

global_offset_checkbox_patches = ttk.Checkbutton(patches_tab, text="Use Offset for Disk", variable=is_global_offset_checkbox_checked, command=toggle_offset_text_state)
global_offset_checkbox_patches.place(x=470, y=98)
global_offset_entry_patches = ttk.Entry(patches_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
global_offset_entry_patches.place(x=470, y=123)
global_offset_entry_patches.config(state="disabled")
global_offset_entry_patches.bind("<KeyRelease>", replace_codecave_offset_text)

disk_exe_patches_label = ttk.Label(patches_tab, text='Disk Executable Address:')
disk_exe_patches_label.pack()
disk_exe_entry_patches = ttk.Entry(patches_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
disk_exe_entry_patches.pack(pady=5)

patch_files_label = ttk.Label(patches_tab, text='Binary Files:')
patch_files_label.pack()
patch_files_entry = ttk.Entry(patches_tab)
patch_files_entry.pack(pady=5)

add_patches_button = ttk.Button(patches_tab, text='Add/Edit Patch', command=add_patch)
add_patches_button.pack(pady=10)

# Create a listbox to display added patches
patches_listbox = tk.Listbox(patches_tab, selectmode=tk.SINGLE)
patches_listbox.pack(pady=10, fill=tk.BOTH, expand=True)
patches_listbox.bind('<<ListboxSelect>>', select_patch)
patches_listbox.bind('<KeyPress-Delete>', remove_patch)

# Button to remove selected codecave
remove_patch_button = ttk.Button(patches_tab, text='Remove Patch', command=remove_patch)
remove_patch_button.pack()

#! Compile Tab
select_platform_label = tk.Label(compile_tab, text="Select Platform to Compile & Build for:", font=("Segoe UI", 10))
select_platform_label.pack()
platform_values = ["PS1", "PS2", "Gamecube/Wii", "Other"]
platform_combobox = ttk.Combobox(compile_tab, values=platform_values, font=("Segoe UI", 15))
platform_combobox.pack()
platform_combobox.bind("<<ComboboxSelected>>", on_platform_select)

# Create a Label to display the gcc text
#gcc_label = tk.Label(compile_tab, text="")
#gcc_label.pack()

# Create a Label to display the linker value
#linker_label = tk.Label(compile_tab, text="")
#linker_label.pack()


# Create a Button to compile the mod
compile_button = tk.Button(compile_tab, text=f"Compile", command=Compile, font=("Segoe UI", 15))
compile_button.pack()

# Create a Button to inject the mod into the exe
open_exe_button = tk.Button(compile_tab, text="Choose Game Executable (ELF, SCUS, SLUS, etc)", command=open_file)
open_exe_button.pack()

# Create a Button to compile the mod
inject_exe_button = tk.Button(compile_tab, text=f"Inject into", command=Compile)
inject_exe_button.pack()

inject_emu_button = tk.Button(compile_tab, text=f"Inject into PCSX2", command=PreparePCSX2Inject)
inject_emu_button.pack()

    
root.mainloop()