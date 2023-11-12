import os
import subprocess
import shutil
import time
import ast
import xml.etree.ElementTree as ET
import requests 
import send2trash
import pyperclip
import tkinter as tk
import sv_ttk
from PIL import ImageTk, Image
from termcolor import colored
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog

#other files
import emu_inject
#from ramwatch import *

PROJECTS_FOLDER_PATH = 'projects/'  # Replace with the path to your folder

#! Globals
g_projects = []
g_code_caves = []
g_hooks = []
g_patches = []

g_shouldShowTabs = False
g_shouldShowPlatforms = False

g_current_project_folder = ""
g_current_project_name = ""

g_current_project_game_exe_full_dir = ""
g_current_project_game_exe = ""

g_current_project_game_disk_full_dir = ""
g_current_project_game_disk = ""

g_current_project_ram_watch_full_dir = ""
g_current_project_ram_watch_name = ""

g_current_project_selected_platform = ""
g_current_project_feature_mode = "Normal"

g_current_project_disk_offset = ""

g_universal_link_string = "-T ../../linker_script.ld -Xlinker -Map=MyMod.map "
g_universal_objcopy_string = "-O binary .config/output/elf_files/MyMod.elf .config/output/final_bins/"

g_platform_gcc_strings = {"PS1": "..\\..\\prereq\\PS1mips\\bin\\mips-gcc ", "PS2": "..\\..\\prereq\\PS2ee\\bin\\ee-gcc ", "Gamecube": "..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc ", "Wii": "..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc ", "N64": "..\\..\\prereq\\N64mips/bin\\mips64-elf-gcc "}
g_platform_linker_strings = {"PS1": "..\\..\\..\\..\\..\\prereq\\PS1mips\\bin\\mips-gcc " + g_universal_link_string, "PS2": "..\\..\\..\\..\\..\\prereq\\PS2ee\\bin\\ee-gcc " + g_universal_link_string, "Gamecube": "..\\..\\..\\..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc " + g_universal_link_string, "Wii": "..\\..\\..\\..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc " + g_universal_link_string, "N64": "..\\..\\..\\..\\..\\prereq\\N64mips\\bin\\mips64-elf-gcc " + g_universal_link_string}
g_platform_objcopy_strings = {"PS1": "..\\..\\prereq\\PS1mips\\bin\\mips-objcopy " + g_universal_objcopy_string, "PS2": "..\\..\\prereq\\PS2ee\\bin\\ee-objcopy " + g_universal_objcopy_string, "Gamecube": "..\\..\\prereq\\devkitPPC\\bin\\ppc-objcopy " + g_universal_objcopy_string, "Wii": "..\\..\\prereq\\devkitPPC\\bin\\ppc-objcopy " + g_universal_objcopy_string, "N64": "..\\..\\prereq\\N64mips\\bin\\mips64-elf-objcopy " + g_universal_objcopy_string}
    
g_optimization_level = "O2"
    
g_src_files = ""
g_header_files = ""
g_asm_files = ""
g_obj_files = ""
g_patch_files = []

g_selected_emu = None

#g_current_project_version = ""


def MoveToRecycleBin(path):
    try:
        send2trash.send2trash(path)
        print(f'Successfully moved {path} to the recycle bin.')
    except Exception as e:
        print(f'Error moving {path} to the recycle bin: {e}')

def RequestGameBoxartImage():
    try:
        image_data = None
        if not os.path.isfile(g_current_project_folder + '/.config/game.jpg'):
            print(colored("Attempting to download game cover art...", "cyan"))
            if g_current_project_selected_platform == "PS1":
                game_exe_formatted = g_current_project_game_exe_name.replace("_", "-").replace(".", "")
                url = f'https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/default/{game_exe_formatted}.jpg' 
                #print(url)
                image_data = requests.get(url).content 
            elif g_current_project_selected_platform == "PS2":
                game_exe_formatted = g_current_project_game_exe_name.replace("_", "-").replace(".", "")
                url = f'https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/default/{game_exe_formatted}.jpg' 
                #print(url)
                image_data = requests.get(url).content 
            elif g_current_project_selected_platform == "Gamecube":
                if g_current_project_game_exe_full_dir != "":
                    with open(g_current_project_game_disk_full_dir, "rb") as game_disk:
                       game_id = game_disk.read()[0:6]
                       game_id_str = game_id.decode()
                       game_id_formatted = game_id_str.upper()
                       url = f'https://ia601900.us.archive.org/20/items/coversdb-gc/{game_id_formatted}.png'
                       #print(url) 
                       image_data = requests.get(url).content 
            elif g_current_project_selected_platform == "Wii":
                if g_current_project_game_exe_full_dir != "":
                    with open(g_current_project_game_disk_full_dir, "rb") as game_disk:
                       game_id = game_disk.read()[0:6]
                       game_id_str = game_id.decode()
                       game_id_formatted = game_id_str.upper()
                       url = f'https://ia803209.us.archive.org/15/items/coversdb-wii/{game_id_formatted}.png'
                       #print(url) 
                       image_data = requests.get(url).content 
            
            f = open(g_current_project_folder + '/.config/game.jpg', 'wb') 
            f.write(image_data) 
            f.close() 
            print(colored("Imported game cover art\n", "cyan"))
    except Exception as e:
        print(e)

def ParseBizhawkRamWatch():
    file_path = g_current_project_ram_watch_full_dir
    if ".wch" in file_path.split("/")[-1].lower():
        watch_file_path = file_path                         # Full Path
        watch_file_name = file_path.split("/")[-1]          # Spliting based on /, and getting last index with -1 to get only name of file
        watch_file_ascii = ""
        symbol_data = [{}]
        with open(watch_file_path, "r") as watch_file:
            watch_file_ascii = watch_file.read()
            watch_file_lines = watch_file_ascii.split("\n")
            
            
            for i, symbol in enumerate(watch_file_lines):
                symbol_info_list = symbol.split("\t")
                try:
                    if symbol_info_list[0] != "SystemID GC" and symbol_info_list[0] != "" and symbol_info_list[1] != "S":   # If not a seperator or first line
                        current_symbol_data = {}
                        current_symbol_data['address'] = "0x80" + symbol_info_list[0] #Grab address without 80 or 00 prefix
                        current_symbol_data['size'] = symbol_info_list[1].replace('d', 'int').replace('w', 'short').replace('b', "char") #Replacing character to represent size with C type
                        current_symbol_data['signedness'] = symbol_info_list[2].replace('s', 'signed').replace('u', 'unsigned').replace("h", "unsigned").replace("b", "unsigned").replace("f", "float") #Replace character to represent signedness with C qualifier
                        current_symbol_data['name'] = symbol_info_list[5].replace(" ", "_") #Grabbing symbol name
                        # Handling fact that float is part of 'signedness' rather than size, so getting rid of size if its a float.
                        if current_symbol_data['signedness'] == "float":
                            current_symbol_data['size'] = ""
                        #Handeling Symbol no name
                        if current_symbol_data['name'] != "":
                            symbol_data.append(current_symbol_data)
                        
                except Exception as e:
                    print(f"{e}\n")
            #print(symbol_data)
            
            bizhawk_symbols_h_string = f"#ifndef BIZHAWK_SYMBOLS_H\n#define BIZHAWK_SYMBOLS_H\n#include <custom_types.h>\n\n//Variables from {watch_file_name}\n"
            for symbol in symbol_data:
                if symbol != {}: #not empty
                    bizhawk_symbols_h_string += f"in_game {symbol['signedness']} {symbol['size']} {symbol['name']}; //{symbol['address']}\n"
                
            bizhawk_symbols_h_string += "\n#endif //BIZHAWK_SYMBOLS_H"
            #print(bizhawk_symbols_h_string)
            with open(f"{g_current_project_folder}/include/bizhawk_symbols.h", "w") as bizhawk_symbols_file:
                bizhawk_symbols_file.write(bizhawk_symbols_h_string)

def OpenBizhawkRamWatch():
    
    global g_current_project_ram_watch_full_dir
    
    if bizhawk_ramwatch_checkbox_state.get() == 1:
        file_path = filedialog.askopenfilename(title="Choose Bizhawk Ramwatch .wch file")
        if ".wch" in file_path.split("/")[-1].lower():
            g_current_project_ram_watch_full_dir = file_path
            save_to_config()
            project_switched()
            return file_path
        else:
            messagebox.showerror("Error", "Invalid Ram Watch File")
            print(colored("Invalid Ram Watch File", "red"))
            bizhawk_ramwatch_checkbox_state.set(0)
    elif bizhawk_ramwatch_checkbox_state.get() == 0:
        g_current_project_ram_watch_full_dir = ""
        save_to_config()     
        project_switched()

def ParseCheatEngineFile():
    #Cheat engine files only get recognized 1 folder layer down because of my shitty XML parsing lol
    
    full_xml_data_keys = []
    full_converted_xml_data = ""
    
    file_path = g_current_project_ram_watch_full_dir
    watch_file_path = file_path                         # Full Path
    watch_file_name = file_path.split("/")[-1]          # Spliting based on /, and getting last index with -1 to get only name of file
    if ".ct" in file_path.split("/")[-1].lower():
        
        tree = ET.parse(watch_file_path)
        root = tree.getroot()[0]
        for i, entry in enumerate(root.findall("CheatEntry")):
            current_symbol_data = {}
            #Get Global Symbols
            for info in entry:
                #print(info.tag, info.text)
                #Get name
                if info.tag == "Description" and info.text != "No description" and info.text != None:
                    current_symbol_data["name"] = info.text.replace("\"", "").replace(" ", "_").replace("(", "_").replace(")", "_").replace("[", "_").replace("]", "_").replace("?", "")
                #Get Address
                if info.tag == "Address" and info.text != "None" and info.text != None:
                    current_symbol_data["address"] = hex(eval("0x00" + info.text.removeprefix("2"))).replace("0x", '0x00') #Evaluating the addition in the string
                #Get type
                if info.tag == "VariableType":
                    current_symbol_data["type"] = info.text.replace("4 Bytes", "int").replace("2 Bytes", "short").replace("Byte", "char").replace("Float", "float").replace("String", "char*").replace('Binary', 'char').replace("Double", "float")
                #Get signedness
                if info.tag == "ShowAsSigned":
                    current_symbol_data["signedness"] = info.text.replace('1', 'signed').replace('0', 'unsigned')
                if info.tag == "Offsets":
                    current_symbol_data['ptr'] = "int*" 
                    
                #Get nested symbols
                layered_entries = info.findall("CheatEntry")
                for layered_entry in layered_entries:
                    current_layered_symbol_data = {}
                    for layered_info in layered_entry:
                        #print(layered_info.tag, layered_info.text)
                        #Get name
                        if layered_info.tag == "Description" and layered_info.text != "\"No description\"":
                            current_layered_symbol_data["name"] = layered_info.text.replace("\"", "").replace(" ", "_").replace("(", "_").replace(")", "_").replace("[", "_").replace("]", "_").replace("?", "")
                        #Get Address
                        if layered_info.tag == "Address" and layered_info.text != "None" and layered_info.text != None:
                            current_layered_symbol_data["address"] = hex(eval("0x00" + layered_info.text.removeprefix("2"))).replace("0x", '0x00') #Evaluating the addition in the string
                        #Get type
                        if layered_info.tag == "VariableType":
                            current_layered_symbol_data["type"] = layered_info.text.replace("4 Bytes", "int").replace("2 Bytes", "short").replace("Byte", "char").replace("Float", "float").replace("String", "char*")
                        #Get signedness
                        if layered_info.tag == "ShowAsSigned":
                            current_layered_symbol_data["signedness"] = layered_info.text.replace('1', 'signed').replace('0', 'unsigned')
                        if info.tag == "Offsets":
                            current_layered_symbol_data['ptr'] = "int*" 
                    #print()
                    full_xml_data_keys.append(current_layered_symbol_data) 
                    
            full_xml_data_keys.append(current_symbol_data)

        full_converted_xml_data_header = f"#ifndef CHEAT_ENGINE_SYMBOLS_H\n#define CHEAT_ENGINE_SYMBOLS_H\n#include <custom_types.h>\n\n//Variables from {watch_file_name}\n"
        #full_xml_data_keys.append(current_symbol_data)
        for symbol_data in full_xml_data_keys:
            if 'address' in symbol_data and 'name' in symbol_data:
                for key, value in symbol_data.items():
                    pass
                    #print(key + ": " + value)
                #print()
                
                if 'ptr' in symbol_data:
                    full_converted_xml_data_header += f"in_game {symbol_data['ptr']} {symbol_data['name']}; //{symbol_data['address']}\n"
                elif symbol_data['type'] == "float" or 'signedness' not in symbol_data:
                    full_converted_xml_data_header += f"in_game {symbol_data['type']} {symbol_data['name']}; //{symbol_data['address']}\n"
                else:
                    full_converted_xml_data_header += f"in_game {symbol_data['signedness']} {symbol_data['type']} {symbol_data['name']}; //{symbol_data['address']}\n"

        full_converted_xml_data_header += "\n#endif //CHEAT_ENGINE_SYMBOLS_H\n"
        #print(full_converted_xml_data_header)
        with open(f"{g_current_project_folder}/include/cheat_engine_symbols.h", "w") as cheat_engine_symbols_file:
            cheat_engine_symbols_file.write(full_converted_xml_data_header)
            
def OpenCheatEngineRamWatch():
    global g_current_project_ram_watch_full_dir
    
    if cheat_engine_ramwatch_checkbox_state.get() == 1:
        file_path = filedialog.askopenfilename(title="Choose Cheat Engine .CT file")
        if ".ct" in file_path.split("/")[-1].lower():
            g_current_project_ram_watch_full_dir = file_path
            save_to_config()
            project_switched()
            return file_path
        else:
            messagebox.showerror("Error", "Invalid Cheat Table File")
            print(colored("Invalid Cheat Table File", "red"))
            cheat_engine_ramwatch_checkbox.deselect()
    elif cheat_engine_ramwatch_checkbox_state.get() == 0:
        g_current_project_ram_watch_full_dir = ""
        save_to_config()
        project_switched()
        
def SetupVSCodeProject():
    if g_current_project_folder != "":
        try:
            os.mkdir(g_current_project_folder + "/.vscode/")
        except:
            pass
        
        template_dir = "prereq/etc/tasks-templates"
        template_ascii = ""
        
        # Write tasks file
        if g_current_project_selected_platform == "Gamecube" or g_current_project_selected_platform == "Wii":
            with open(f"{template_dir}/gc.json", "r") as task_file:
                template_ascii = task_file.read()
                
            replaced_ascii = template_ascii.replace("REPLACE", g_current_project_name)
                
            with open(g_current_project_folder + "/.vscode/tasks.json", "w") as task_file:
                task_file.write(replaced_ascii)
                
        if g_current_project_selected_platform == "PS1":
            with open(f"{template_dir}/ps1.json", "r") as task_file:
                template_ascii = task_file.read()
                
            replaced_ascii = template_ascii.replace("REPLACE", g_current_project_name)
                
            with open(g_current_project_folder + "/.vscode/tasks.json", "w") as task_file:
                task_file.write(replaced_ascii)
                
        if g_current_project_selected_platform == "PS2":
            with open(f"{template_dir}/ps2.json", "r") as task_file:
                template_ascii = task_file.read()
                
            replaced_ascii = template_ascii.replace("REPLACE", g_current_project_name)
                
            with open(g_current_project_folder + "/.vscode/tasks.json", "w") as task_file:
                task_file.write(replaced_ascii)
        
        # Write c_cpp_properties & settings file
        with open(f"{template_dir}/c_cpp_properties.json", "r") as properties_file:
            template_properties_ascii = properties_file.read()    
        with open(g_current_project_folder + "/.vscode/c_cpp_properties.json", "w") as task_file:
            task_file.write(template_properties_ascii)
            
        with open(f"{template_dir}/settings.json", "r") as properties_file:
            template_settings_ascii = properties_file.read()       
        with open(g_current_project_folder + "/.vscode/settings.json", "w") as settings_file:
            settings_file.write(template_settings_ascii)
        
        print(colored("Opening VSCode Project...", "cyan"))
        
        old_dir = os.getcwd()
        os.chdir(g_current_project_folder)
        
        subprocess.Popen("cmd /c code .")     # Open project in VSCode. cmd /c since this is a pipe
        
        os.chdir(old_dir)
    else:
        messagebox.showerror("Error", "Please create/select a project first")

def SetupNotepadProject():
    if g_current_project_folder != "":
        try:
            os.mkdir(g_current_project_folder + "/.compile_scripts/")
        except:
            pass
        
        # Get full project dir path
        old_dir = os.getcwd()
        os.chdir(g_current_project_folder)
        full_project_dir = f"\"{os.getcwd()}\""
        os.chdir(old_dir)
        
        template_dir = "prereq/etc/tasks-templates"
        compile_ascii = ""
        build_ascii = ""
        inject_ascii = {}
        
        # Get template global bat files
        with open(f"{template_dir}/compile.bat", "r") as compile_file:
            compile_ascii = compile_file.read()
            
        replaced_compile_ascii = compile_ascii.replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
                
        with open(f"{template_dir}/ISO_build.bat", "r") as build_file:
            build_ascii = build_file.read()
            
        replaced_build_ascii = build_ascii.replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
        
        # Write global bat files
        with open(g_current_project_folder + "/.compile_scripts/compile.bat", "w") as compile_file:
            compile_file.write(replaced_compile_ascii)
            
        with open(g_current_project_folder + "/.compile_scripts/build_iso.bat", "w") as build_file:
            build_file.write(replaced_build_ascii)
            

        #Platform specific emu injects
        if g_current_project_selected_platform == "Gamecube" or g_current_project_selected_platform == "Wii":
            with open(f"{template_dir}/inject_dolphin_50_20240.bat", "r") as inject_file:
                inject_ascii["dolphin"] = inject_file.read()
                
            replaced_ascii = inject_ascii['dolphin'].replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
                
            with open(g_current_project_folder + "/.compile_scripts/inject_dolphin_50_20240.bat", "w") as task_file:
                task_file.write(replaced_ascii)
                
            with open(f"{template_dir}/inject_dolphin_50_19870.bat", "r") as inject_file:
                inject_ascii["dolphin"] = inject_file.read()
                
            replaced_ascii = inject_ascii['dolphin'].replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
                
            with open(g_current_project_folder + "/.compile_scripts/inject_dolphin_50_19870.bat", "w") as task_file:
                task_file.write(replaced_ascii)
                
        if g_current_project_selected_platform == "PS1":
            #Duckstation
            with open(f"{template_dir}/inject_duckstation.bat", "r") as inject_file:
                inject_ascii["duckstation"] = inject_file.read()
                
            replaced_ascii = inject_ascii['duckstation'].replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
            
            with open(g_current_project_folder + "/.compile_scripts/inject_duckstation.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
             
            #Bizhawk   
            with open(f"{template_dir}/inject_bizhawk_2.6.1.bat", "r") as inject_file:
                inject_ascii["bizhawk 2.6.1"] = inject_file.read()
                
            replaced_ascii = inject_ascii['bizhawk 2.6.1'].replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
            
            with open(g_current_project_folder + "/.compile_scripts/inject_bizhawk_2.6.1.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
                
            #Mednafen 1.29  
            with open(f"{template_dir}/inject_mednafen_1.29.bat", "r") as inject_file:
                inject_ascii["mednafen 1.29"] = inject_file.read()
                
            replaced_ascii = inject_ascii['mednafen 1.29'].replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
            
            with open(g_current_project_folder + "/.compile_scripts/inject_mednafen_1.29.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
                
            #Mednafen 1.31  
            with open(f"{template_dir}/inject_mednafen_1.31.bat", "r") as inject_file:
                inject_ascii["mednafen 1.31"] = inject_file.read()
                
            replaced_ascii = inject_ascii['mednafen 1.31'].replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
            
            with open(g_current_project_folder + "/.compile_scripts/inject_mednafen_1.31.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
                
        if g_current_project_selected_platform == "PS2":
            #PCSX2 1.6.0
            with open(f"{template_dir}/inject_pcsx2_1.6.0.bat", "r") as inject_file:
                inject_ascii["pcsx2 1.7.5112"] = inject_file.read()
                
            replaced_ascii = inject_ascii['pcsx2 1.7.5112'].replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
            
            with open(g_current_project_folder + "/.compile_scripts/inject_pcsx2_1.6.0.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
             
            #PCSX2 1.7.5112   
            with open(f"{template_dir}/inject_pcsx2_1.7.5112.bat", "r") as inject_file:
                inject_ascii["bizhawk 2.6.1"] = inject_file.read()
                
            replaced_ascii = inject_ascii['bizhawk 2.6.1'].replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir)
            
            with open(g_current_project_folder + "/.compile_scripts/inject_pcsx2_1.7.5112.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
        
        
        print(colored("Opening Notepad++ Project...", "cyan"))
        
        old_dir = os.getcwd()
        os.chdir(g_current_project_folder)
        full_project_dir = os.getcwd()
        
        #print(f"\"..\\..\\{template_dir}/open_notepad++_project.bat\"" + " " + f"\"{full_project_dir}\"")
        template_dir_baskslash = template_dir.replace('/', '\\')
        try:
            subprocess.Popen(f"cmd /c ..\\..\\{template_dir_baskslash}\open_notepad++_project.bat" + " " + f"\"{full_project_dir}\"")     # Open project in Notepad++. Timeout to regain control after opening? Find a way to fix this later.
        except:
            print(colored("Opened Notepad++ Project", "cyan"))
        
        os.chdir(old_dir)
    else:
        messagebox.showerror("Error", "Please create/select a project first")

def SetupSublimeProject():
    if g_current_project_folder != "":
        try:
            os.mkdir(g_current_project_folder + "/.sublime/")
        except:
            pass
        try:
            os.mkdir(g_current_project_folder + "/.compile_scripts/")
        except:
            pass
        
        SublimeBatTextReplacement = lambda ascii: ascii.replace("REPLACE", g_current_project_name).replace("PATH", full_project_dir).replace("pause", "")
        
        # Get full project dir path
        old_dir = os.getcwd()
        os.chdir(g_current_project_folder)
        full_project_dir = os.getcwd()
        os.chdir(old_dir)
        
        template_dir = "prereq/etc/tasks-templates"
        sublime_ascii = ""
        compile_ascii = ""
        build_ascii = ""
        build_exe_ascii = ""
        inject_ascii = {}
        
        # Get template global bat files
        with open(f"{template_dir}/compile.bat", "r") as compile_file:
            compile_ascii = compile_file.read()
            
        replaced_compile_ascii = SublimeBatTextReplacement(compile_ascii)
                
        with open(f"{template_dir}/ISO_build.bat", "r") as build_file:
            build_ascii = build_file.read()
                
        with open(f"{template_dir}/EXE_build.bat", "r") as build_exe_file:
            build_exe_ascii = build_exe_file.read()
            
        replaced_build_ascii =  SublimeBatTextReplacement(build_ascii)
        
        replaced_build_exe_ascii =  SublimeBatTextReplacement(build_exe_ascii)
        
        # Write global bat files
        with open(g_current_project_folder + "/.compile_scripts/compile.bat", "w") as compile_file:
            compile_file.write(replaced_compile_ascii)
            
        with open(g_current_project_folder + "/.compile_scripts/build_iso.bat", "w") as build_file:
            build_file.write(replaced_build_ascii)
            

        #Platform specific options
        if g_current_project_selected_platform == "Gamecube" or g_current_project_selected_platform == "Wii":
            
            #Build Exe
            with open(g_current_project_folder + "/.compile_scripts/build_exe.bat", "w") as build_file:
                build_file.write(replaced_build_ascii)
                
            # Get template Sublime File
            with open(f"{template_dir}/gamecube.sublime-project", "r") as sublime_file:
                sublime_ascii = sublime_file.read()
                
            replace_sublime_ascii = sublime_ascii.replace("PATH", full_project_dir).replace("\\", "\\\\")
            
            # Write template sublime files
            with open(g_current_project_folder + "/.sublime/project.sublime-project", "w") as sublime_file:
                sublime_file.write(replace_sublime_ascii)
            
            #Dolphin 1
            with open(f"{template_dir}/inject_dolphin_50_19870.bat", "r") as inject_file:
                inject_ascii["dolphin"] = inject_file.read()
                
            replaced_ascii = SublimeBatTextReplacement(inject_ascii['dolphin'])
                
            with open(g_current_project_folder + "/.compile_scripts/inject_dolphin_50_19870.bat", "w") as task_file:
                task_file.write(replaced_ascii)
                
            #Dolphin 2
            with open(f"{template_dir}/inject_dolphin_50_20240.bat", "r") as inject_file:
                inject_ascii["dolphin"] = inject_file.read()
                
            replaced_ascii = SublimeBatTextReplacement(inject_ascii['dolphin'])
                
            with open(g_current_project_folder + "/.compile_scripts/inject_dolphin_50_20240.bat", "w") as task_file:
                task_file.write(replaced_ascii)
                
        if g_current_project_selected_platform == "PS1":
            
            # Get template Sublime File
            with open(f"{template_dir}/ps1.sublime-project", "r") as sublime_file:
                sublime_ascii = sublime_file.read()
                
            replace_sublime_ascii = sublime_ascii.replace("PATH", full_project_dir).replace("\\", "\\\\")
            
            # Write template sublime files
            with open(g_current_project_folder + "/.sublime/project.sublime-project", "w") as sublime_file:
                sublime_file.write(replace_sublime_ascii)
            
            
            #Emulator Injection bats
            #Duckstation
            with open(f"{template_dir}/inject_duckstation.bat", "r") as inject_file:
                inject_ascii["duckstation"] = inject_file.read()
                
            replaced_ascii = SublimeBatTextReplacement(inject_ascii['duckstation'])
            
            with open(g_current_project_folder + "/.compile_scripts/inject_duckstation.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
             
            #Bizhawk   
            with open(f"{template_dir}/inject_bizhawk_2.6.1.bat", "r") as inject_file:
                inject_ascii["bizhawk 2.6.1"] = inject_file.read()
                
            replaced_ascii = SublimeBatTextReplacement(inject_ascii['bizhawk 2.6.1'])
            
            with open(g_current_project_folder + "/.compile_scripts/inject_bizhawk_2.6.1.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
                
            #Mednafen 1.29  
            with open(f"{template_dir}/inject_mednafen_1.29.bat", "r") as inject_file:
                inject_ascii["mednafen 1.29"] = inject_file.read()
                
            replaced_ascii = SublimeBatTextReplacement(inject_ascii['mednafen 1.29'])
            
            with open(g_current_project_folder + "/.compile_scripts/inject_mednafen_1.29.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
                
            #Mednafen 1.31  
            with open(f"{template_dir}/inject_mednafen_1.31.bat", "r") as inject_file:
                inject_ascii["mednafen 1.31"] = inject_file.read()
                
            replaced_ascii = SublimeBatTextReplacement(inject_ascii['mednafen 1.31'])
            
            with open(g_current_project_folder + "/.compile_scripts/inject_mednafen_1.31.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
                
        if g_current_project_selected_platform == "PS2":
            # Get template Sublime File
            with open(f"{template_dir}/ps2.sublime-project", "r") as sublime_file:
                sublime_ascii = sublime_file.read()
                
            replace_sublime_ascii = sublime_ascii.replace("PATH", full_project_dir).replace("\\", "\\\\")
            
            # Write template sublime files
            with open(g_current_project_folder + "/.sublime/project.sublime-project", "w") as sublime_file:
                sublime_file.write(replace_sublime_ascii)
            
            
            #PCSX2 1.6.0
            with open(f"{template_dir}/inject_pcsx2_1.6.0.bat", "r") as inject_file:
                inject_ascii["pcsx2 1.7.5112"] = inject_file.read()
                
            replaced_ascii = SublimeBatTextReplacement(inject_ascii['pcsx2 1.7.5112'])
            
            with open(g_current_project_folder + "/.compile_scripts/inject_pcsx2_1.6.0.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
             
            #PCSX2 1.7.5112   
            with open(f"{template_dir}/inject_pcsx2_1.7.5112.bat", "r") as inject_file:
                inject_ascii["bizhawk 2.6.1"] = inject_file.read()
                
            replaced_ascii = SublimeBatTextReplacement(inject_ascii['bizhawk 2.6.1'])
            
            with open(g_current_project_folder + "/.compile_scripts/inject_pcsx2_1.7.5112.bat", "w") as inject_file:
                inject_file.write(replaced_ascii)
                
        print(colored("Opening Sublime Project...", "cyan"))
        
        old_dir = os.getcwd()
        os.chdir(g_current_project_folder)
        full_project_dir = os.getcwd()
        
        subprocess.Popen("cmd /c .sublime\\project.sublime-project")     # Open project in Sublime
        
        os.chdir(old_dir)
    else:
        messagebox.showerror("Error", "Please create/select a project first")

#! Used to find "in_game" text in the C source/header files
def ParseCSourceForSymbols():
    
    #Writing to auto_symbols file with comment, since linker will complain if no text
    with open(".config/symbols/auto_symbols.txt", "w") as symbols_file:                 
        symbols_file.write("/* Symbols declared in C code with \"in_game\" */\n")
                           
    src_files_list = g_src_files.split()
    header_files_list = g_header_files.split()
    
    files_to_parse = src_files_list + header_files_list
    
    try:
        with open(".config/symbols/auto_symbols.txt", "a") as symbols_file: 
            for src_file in files_to_parse:
                with open (src_file, "r") as current_file:
                    file_ascii = current_file.read()
                    in_game_text_found_list = file_ascii.split("in_game ")[1:] # Get rid of the 0th index, since it will be the code before in_game is found. Nothing after the : means keep rest of the list
                    if in_game_text_found_list != []:   # If at least 1 string 1 found
                        if "//CUSTOM_TYPES_H" not in in_game_text_found_list[0]:   # Ensure this isn't the define for in_game inside of CUSTOM_TYPES
                            for symbol in in_game_text_found_list:
                                if symbol.split(" ")[0] == "signed" or symbol.split(" ")[0] == "unsigned": #For if signedness specifier, skip one more white space
                                    symbol_name = symbol.split()[2].split("(")[0].split(";")[0]
                                else:
                                    symbol_name = symbol.split()[1].split("(")[0].split(";")[0]  #No signedness specifier

                                symbol_address = symbol.split("//")[1].split()[0]    # Getting rid of //before address and whitespace or \n after address
                                
                                if symbol_address.find("0x") == -1:
                                    print(colored(f"Invalid memory address '{symbol_address}' for in_game symbol '{symbol_name}'", "red"))
                                #Writing to auto_symbols file
                                else:
                                    symbols_file.write(symbol_name + " = " + symbol_address + ";" + "\n")
                                    #print(symbol_name + " = " + symbol_address + ";" + "\n")
    except Exception as e:
        print(f"ParseCSource: {e}")

#! Compile Function, which calls out to relavent GCC version
def Compile():  
    
    if bizhawk_ramwatch_checkbox_state.get() == 1:
        print("Parsing Bizhawk Ramwatch")
        ParseBizhawkRamWatch()
    if cheat_engine_ramwatch_checkbox_state.get() == 1:
        print("Parsing Cheat Engine Table")
        ParseCheatEngineFile()
    
    #print("Moving to Folder: ", g_project_folder)
    main_dir = os.getcwd()
    os.chdir(g_current_project_folder)
    
    #Parse Ramdump if it exists
    #Add symbols from source that were declared using in_game
    ParseCSourceForSymbols()
    
    #! Compile C/asm files
    starting_compilation = colored("Starting Compilation:", "green")
    compile_string = colored("Compilation string: " + g_platform_gcc_strings[g_current_project_selected_platform], "green")
    print(starting_compilation)
    print(compile_string)
    
    gcc_output = subprocess.run(g_platform_gcc_strings[g_current_project_selected_platform], shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if gcc_output.stdout:
        print(gcc_output.stdout)
        print(gcc_output.stderr)
    if gcc_output.returncode == 1:
        print(colored("Compilation Failed!", "red"))
        print(gcc_output.stderr)
        
        os.chdir(main_dir)
        return False
    
    print(colored("Compilation Finished!", "green"))
        
    #! Link .o files
    print(colored("Starting Link:", "green"))
    link_string = g_platform_linker_strings[g_current_project_selected_platform]
    for file in g_obj_files.split():
        try:
            shutil.move(file, os.getcwd() + "\.config\output\object_files\\" + file) # Move .o files from main dir to output\object_files
        except Exception as e:
            print(colored(f"{e}", "red"))
            os.chdir(main_dir)
            return
    
    project_dir = os.getcwd()
    os.chdir(project_dir + "\.config\output\object_files")
    print(colored("Link String: " + link_string, "green"))
    linker_output = subprocess.run(link_string, shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) # Run the link string
    if linker_output.stdout:
        print(linker_output.stdout)
    if linker_output.returncode == 1:
        print(colored("Linking Failed!", "red"))
        print(linker_output.stderr)
        if "overlaps section" in linker_output.stderr:
            messagebox.showerror("Linking Error", "Linker failed with \"overlapping sections\" error. Ensure codecaves or hooks do not share addresses, or occupy very similar regions.")
        if "will not fit in region" in linker_output.stderr:
            section_name_index = linker_output.stderr.index(": region")
            end_index = linker_output.stderr.index("collect2.exe")
            section_name = linker_output.stderr[(section_name_index + 2):(end_index-1)]
            section_overflow_index = section_name.find("overflowed by ")
            section_size_hex = section_name[section_overflow_index:].split(" ")[2]
            section_size_hex_int = hex(int(section_size_hex))
            messagebox.showerror("Linking Error", f"Linker failed with {section_name.split('overflowed')[0]} overflowed by {section_size_hex_int} bytes.")
        os.chdir(main_dir)
        return False
    
    os.system("move MyMod.map ../memory_map > nul ")                     #The nul below is just to get rid of the ugly output
    os.chdir(project_dir)
    print(colored("Linking Finished!", "green"))
    
    #! Extract Sections to Binary
    for cave in g_code_caves:   
        os.system(g_platform_objcopy_strings[g_current_project_selected_platform] + cave[0] + ".bin " + "--only-section ." + cave[0])
        print(colored(f"Extracting {cave[0]} compiled code sections from elf to binary file...", "green"))
    for hook in g_hooks:   
        os.system(g_platform_objcopy_strings[g_current_project_selected_platform] + hook[0] + ".bin " + "--only-section ." + hook[0])
        print(colored(f"Extracting {hook[0]} compiled asm hook sections from elf to binary file...", "green"))
    
        
    print(colored("Compiling, Linking, & Extracting Finished!", "yellow"))
    os.chdir(main_dir)
    
    #pcsx2_inject.InjectIntoPCSX2(g_project_folder, code_caves, hooks)
    #InjectIntoExe()
    #BuildPS2ISO()
    PrepareBuildInjectGUIOptions()
    
    check_memory_map_sizes()
    
    return True

# Change button text for emulator when new selection made
def ChangeEmulatorText(event=0):
    
    #Update inject button text
    emu_choice = g_selected_emu.get()
    emu_choice_name = emu_choice.split()[0]
    #Change text, and adjust size for emu choice
    if emu_choice_name == "Duckstation":
        inject_emu_button.config(text="Inject into " + emu_choice.split()[0], font=("NONE", 10))
    elif emu_choice_name == "PCSX2" or emu_choice_name == "Dolphin":
        inject_emu_button.config(text="Inject into " + emu_choice.split()[0], font=("NONE", 12))
    else:
        inject_emu_button.config(text="Inject into " + emu_choice.split()[0], font=("NONE", 11))
    
def PrepareBuildInjectGUIOptions():
    global inject_exe_button
    global inject_emu_button
    global open_exe_button
    global emulators_combobox
    global inject_worse_emu_button
    global g_selected_emu
    global inject_emulator_label
    global choose_exe_label
    global build_iso_button
    global build_exe_button
    global change_exe_button
    global create_ps2_code_button
    global create_cheat_code_label
    global bizhawk_ramwatch_checkbox
    global bizhawk_ramwatch_checkbox_state
    
    #Hide old build/inject options
    if inject_exe_button:
        inject_exe_button.place_forget()
    if inject_emu_button:   
        inject_emu_button.place_forget()
    if emulators_combobox:
        emulators_combobox.place_forget()
    if choose_exe_label:
        choose_exe_label.place_forget()
    if inject_emulator_label:
        choose_exe_label.place_forget()
    if build_iso_button:
        build_iso_button.pack_forget()
    if build_exe_button:
        build_exe_button.pack_forget()
    if change_exe_button:
        change_exe_button.place_forget()
    if create_ps2_code_button:
        create_ps2_code_button.place_forget()
    if create_cheat_code_label:
        create_cheat_code_label.place_forget()
        
        
    medium_font_style = ttk.Style()
    medium_font_style.configure("Medium.TButton", font=("Segoe UI", 14))
    small_font_style = ttk.Style()
    small_font_style.configure("Small.TButton", font=("Segoe UI", 14))
        
    # Build button    
    #PS1/PS2 
    if g_current_project_game_disk != "" and ((g_current_project_selected_platform == "PS1" or g_current_project_selected_platform == "PS2")):
        build_iso_button = ttk.Button(compile_tab, text=f"Build Patched Copy of {g_current_project_game_disk}", command=InjectIntoExeAndRebuildGame, style="Medium.TButton") 
        build_iso_button.pack(pady=5)    
    #N64 & GC/WII Option for iso and just exe
    elif g_current_project_game_disk != "" and ((g_current_project_selected_platform == "Gamecube" or g_current_project_selected_platform == "Wii")):
        build_iso_button = ttk.Button(compile_tab, text=f"Build Patched Copy of {g_current_project_game_disk}", command=InjectIntoExeAndRebuildGame, style="Medium.TButton") 
        build_iso_button.pack(pady=5)
        if g_current_project_feature_mode == "Advanced":
            build_exe_button = ttk.Button(compile_tab, text=f"Build Patched Copy of {g_current_project_game_exe_name}", command=InjectIntoJustExe, style="Medium.TButton") 
            build_exe_button.pack()    
    elif g_current_project_game_exe != "" and (g_current_project_selected_platform == "N64"):
        build_exe_button = ttk.Button(compile_tab, text=f"Build Patched Copy of {g_current_project_game_exe_name}", command=InjectIntoJustExe, style="Medium.TButton") 
        build_exe_button.pack()  
    #No ISO, choose one first
    else:
        build_iso_button = ttk.Button(compile_tab, text=f"Choose ISO/BIN/ROM to Build", command=FirstSelectISOThenBuild, style="Medium.TButton") 
        build_iso_button.pack()
     
    #Update compile tab text/buttons
    if g_current_project_game_exe and g_current_project_game_exe_full_dir:
        exe_name = g_current_project_game_exe.split('/')[-1].split("\n")[0]
        if g_current_project_selected_platform == "PS2":
            
            if g_current_project_game_disk_full_dir == "":
                choose_exe_label = tk.Label(compile_tab, text=f"Choose Base PS2 ISO:", font=("jdfa", 15))
            if g_current_project_game_disk_full_dir != "": 
                choose_exe_label = tk.Label(compile_tab, text=f"Change Base PS2 ISO:", font=("jdfa", 15)) 
            choose_exe_label.place(x=0, y=0)
            
            change_exe_button = tk.Button(compile_tab, text=f"Choose PS2 ISO file", command=open_ISO_file, font=("jdfa", 12))
            change_exe_button.place(x=5, y=30)
            
            inject_emulator_label = tk.Label(compile_tab, text="Inject into emulator:", font=("jdfa", 15))
            inject_emulator_label.place(x=610, y=0)
            
            g_selected_emu = tk.StringVar(value="PCSX2 1.6.0")
            emulators_combobox = ttk.Combobox(compile_tab, textvariable=g_selected_emu, font=("sfa", 11))
            emulators_combobox['values'] = ('PCSX2 1.6.0', 'PCSX2 1.7.5112')
            emulators_combobox.place(x=592, y=30)
            emulators_combobox.bind("<<ComboboxSelected>>", ChangeEmulatorText)
            
            inject_emu_button = tk.Button(compile_tab, text=f"Inject into Emulator", command=PreparePCSX2Inject, font=("jdfa", 11))
            inject_emu_button.place(x=652, y=65)
            
            
            create_cheat_code_label = tk.Label(compile_tab, text="Create PS2RD/CheatDevicePS2 Code:", font=("jdfa", 14))
            create_cheat_code_label.place(x=454, y=290)
            
            create_ps2_code_button = tk.Button(compile_tab, text=f"Create PS2RD Code", command=convert_to_ps2rd_code, font=("jdfa", 11))
            create_ps2_code_button.place(x=646, y=320)
            
        if g_current_project_selected_platform == "Gamecube":
            # Create a button choose the game ISO
            if g_current_project_game_disk_full_dir == "":
                choose_exe_label = tk.Label(compile_tab, text=f"Choose Base Gamecube ISO:", font=("jdfa", 15))
            if g_current_project_game_disk_full_dir != "": 
                choose_exe_label = tk.Label(compile_tab, text=f"Change Base Gamecube ISO:", font=("jdfa", 15)) 
            choose_exe_label.place(x=0, y=0)
            
            change_exe_button = tk.Button(compile_tab, text=f"Choose Gamecube ISO file", command=open_ISO_file, font=("jdfa", 12))
            change_exe_button.place(x=5, y=30)
            
            inject_emulator_label = tk.Label(compile_tab, text="Inject into emulator:", font=("jdfa", 15))
            inject_emulator_label.place(x=610, y=0)
            
            g_selected_emu = tk.StringVar(value="Dolphin 5.0-19870")
            emulators_combobox = ttk.Combobox(compile_tab, textvariable=g_selected_emu, font=("sfa", 11))
            emulators_combobox['values'] = ('Dolphin 5.0-19870', 'Dolphin 5.0-20240')
            emulators_combobox.place(x=592, y=30)
            emulators_combobox.bind("<<ComboboxSelected>>", ChangeEmulatorText)
            
            inject_emu_button = tk.Button(compile_tab, text=f"Inject into Emulator", command=PrepareDolphinInject, font=("jdfa", 11))
            inject_emu_button.place(x=652, y=65)
            
        if g_current_project_selected_platform == "Wii":
            # Create a button choose the game ISO
            if g_current_project_game_disk_full_dir == "":
                choose_exe_label = tk.Label(compile_tab, text=f"Choose Base Wii .dol:", font=("jdfa", 15))
            if g_current_project_game_disk_full_dir != "": 
                choose_exe_label = tk.Label(compile_tab, text=f"Change Base Wii .dol:", font=("jdfa", 15)) 
            choose_exe_label.place(x=0, y=0)
            
            change_exe_button = tk.Button(compile_tab, text=f"Choose Wii DOL file", command=open_exe_file, font=("jdfa", 12))
            change_exe_button.place(x=5, y=30)
            
            inject_emulator_label = tk.Label(compile_tab, text="Inject into emulator:", font=("jdfa", 15))
            inject_emulator_label.place(x=610, y=0)
            
            g_selected_emu = tk.StringVar(value="Dolphin 5.0-19870")
            emulators_combobox = ttk.Combobox(compile_tab, textvariable=g_selected_emu, font=("sfa", 11))
            emulators_combobox['values'] = ('Dolphin 5.0-19870', 'Dolphin 5.0-20240')
            emulators_combobox.place(x=592, y=30)
            emulators_combobox.bind("<<ComboboxSelected>>", ChangeEmulatorText)
            
            inject_emu_button = tk.Button(compile_tab, text=f"Inject into Emulator", command=PrepareDolphinInject, font=("jdfa", 11))
            inject_emu_button.place(x=652, y=65)
            
        elif g_current_project_selected_platform == "PS1":   
            # Create a button choose the game ISO
            if g_current_project_game_disk_full_dir == "":
                choose_exe_label = tk.Label(compile_tab, text=f"Choose Base PS1 BIN:", font=("jdfa", 15))
            if g_current_project_game_disk_full_dir != "": 
                choose_exe_label = tk.Label(compile_tab, text=f"Change Base PS1 BIN:", font=("jdfa", 15)) 
            choose_exe_label.place(x=0, y=0)
            
            change_exe_button = tk.Button(compile_tab, text=f"Choose PS1 BIN file", command=open_ISO_file, font=("jdfa", 12))
            change_exe_button.place(x=5, y=30)
            
            inject_emulator_label = tk.Label(compile_tab, text="Inject into emulator:", font=("jdfa", 15))
            inject_emulator_label.place(x=610, y=0)
            
            g_selected_emu = tk.StringVar(value="Duckstation 0.1-5936")
            emulators_combobox = ttk.Combobox(compile_tab, textvariable=g_selected_emu, font=("fasf", 11))
            emulators_combobox['values'] = ('Duckstation 0.1-5936', 'Mednafen 1.29', 'Mednafen 1.31', 'Bizhawk 2.6.1')
            emulators_combobox.place(x=592, y=30)
            emulators_combobox.bind("<<ComboboxSelected>>", ChangeEmulatorText)
            
            inject_emu_button = tk.Button(compile_tab, text=f"Inject into Emulator", command=PreparePS1EmuInject, font=("jdfa", 11))
            inject_emu_button.place(x=652, y=65)
            
            create_cheat_code_label = tk.Label(compile_tab, text="Create Duckstation Cheat Code:", font=("jdfa", 14))
            create_cheat_code_label.place(x=520, y=290)
            
            create_ps2_code_button = tk.Button(compile_tab, text=f"Create Duckstation Code", command=convert_to_gameshark_code, font=("jdfa", 11))
            create_ps2_code_button.place(x=615, y=320)
            
        elif g_current_project_selected_platform == "N64":

            choose_exe_label = tk.Label(compile_tab, text=f"Choose Base N64 ROM:", font=("jdfa", 15))
            choose_exe_label.place(x=0, y=0)
            
            change_exe_button = tk.Button(compile_tab, text=f"Choose N64 ROM file", command=open_exe_file, font=("jdfa", 12))
            change_exe_button.place(x=5, y=30)
            
            inject_emulator_label = tk.Label(compile_tab, text="Inject into emulator:", font=("jdfa", 15))
            inject_emulator_label.place(x=610, y=0)
            
            g_selected_emu = tk.StringVar(value="Duckstation 0.1-5936")
            emulators_combobox = ttk.Combobox(compile_tab, textvariable=g_selected_emu, font=("fasf", 11))
            emulators_combobox['values'] = ('Duckstation 0.1-5936', 'Mednafen 1.29', 'Mednafen 1.31', 'Bizhawk 2.6.1')
            emulators_combobox.place(x=592, y=30)
            emulators_combobox.bind("<<ComboboxSelected>>", ChangeEmulatorText)
            
            inject_emu_button = tk.Button(compile_tab, text=f"Inject into Emulator", command=PreparePS1EmuInject, font=("fasf", 11))
            inject_emu_button.place(x=652, y=65)           

def PreparePCSX2Inject(event=0):
    
    pcsx2_160_info = {
        'name': 'pcsx2',
        'address': 0x20000000,
        'ptr': False,
        'double_ptr': False,
        'base': False
        }
    pcsx2_175112_info = {
        'name': 'pcsx2',
        'base_exe_dll_name': 'pcsx2.exe',
        'main_ram_offset': 0x30B6BB0,
        'ptr': True,
        'double_ptr': False,
        'base': True
        }
        
    if g_selected_emu.get() == "PCSX2 1.6.0":
        complete_message = emu_inject.InjectIntoEmu(pcsx2_160_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        messagebox.showinfo("Info", complete_message)
    elif g_selected_emu.get() == "PCSX2 1.7.5112":
        complete_message = emu_inject.InjectIntoEmu(pcsx2_175112_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        messagebox.showinfo("Info", complete_message)
    else:
        messagebox.showerror("Error", "Please select an emulator")
    
def PrepareDolphinInject(event=0):
    dolphin_50_19870_info = {
        'name': 'Dolphin.exe',
        'base_exe_dll_name': 'Dolphin.exe',
        'main_ram_offset': 0x1189050,
        'base': True,
        'double_ptr': True,
        'ptr': False
        }
    dolphin_50_20240_info = {
        'name': 'Dolphin.exe',
        'base_exe_dll_name': 'Dolphin.exe',
        'main_ram_offset': 0x11D41B0,
        'base': True,
        'double_ptr': True,
        'ptr': False
        }
    
    if g_selected_emu.get() == "Dolphin 5.0-20240":
        complete_message = emu_inject.InjectIntoEmu(dolphin_50_20240_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        messagebox.showinfo("Info", complete_message)
    elif g_selected_emu.get() == "Dolphin 5.0-19870":
        complete_message = emu_inject.InjectIntoEmu(dolphin_50_19870_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        messagebox.showinfo("Info", complete_message)
    else:
        messagebox.showerror("Error", "Please select an emulator")
    
def PreparePS1EmuInject(event=0):
    global g_selected_emu
    
    duckstation_info = {
        'name': 'duckstation',
        'base_exe_dll_name': 'duckstation-qt-x64-ReleaseLTCG.exe',
        'main_ram_offset': 0x87E6B0,
        'ptr': True,
        'double_ptr': False,
        'base': True,
        }
    bizhawk_info = {
        'name': 'EmuHawk',
        'base_exe_dll_name': 'octoshock.dll',
        'main_ram_offset': 0x310f80,
        'ptr': False,
        'double_ptr': False,
        'base': True
        }
    mednafen_129_info = {
        'name': 'mednafen',
        'address': 0x2003E80,
        'base': False,
        'ptr': False,
        'double_ptr': False
    }
    mednafen_131_info = {
        'name': 'mednafen',
        'address': 0x2034E80,
        'base': False,
        'ptr': False,
        'double_ptr': False
    }
    
    if g_selected_emu.get() == "Duckstation 0.1-5936":
        complete_message = emu_inject.InjectIntoEmu(duckstation_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        messagebox.showinfo("Info", complete_message)
    elif g_selected_emu.get() == "Mednafen 1.29":
        complete_message = emu_inject.InjectIntoEmu(mednafen_129_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        messagebox.showinfo("Info", complete_message)
    elif g_selected_emu.get() == "Mednafen 1.31":
        complete_message = emu_inject.InjectIntoEmu(mednafen_131_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        messagebox.showinfo("Info", complete_message)
    elif g_selected_emu.get() == "Bizhawk 2.6.1":
        complete_message = emu_inject.InjectIntoEmu(bizhawk_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        messagebox.showinfo("Info", complete_message)
    else:
        messagebox.showerror("Error", "Please select Emulator")

def InjectIntoJustExe(event=0):
    InjectIntoExeAndRebuildGame(just_exe=True)

def InjectIntoExeAndRebuildGame(just_exe = False):
    #Read exe file first and copy it with prefixed name
    mod_bin_file_path = g_current_project_folder + "/.config/output/final_bins/"
    patches_dir = g_current_project_folder + "/patches/"
    patched_exe_name = g_current_project_folder + "/patched_" + g_current_project_game_exe_name
    
    game_exe_file_data = b""
    with open(g_current_project_game_exe_full_dir, "rb+") as game_exe_file:
        game_exe_file_data = game_exe_file.read()
        
    try:
        with open(patched_exe_name, "wb+") as game_exe_file:
            game_exe_file.write(game_exe_file_data)
    except PermissionError:
        messagebox.showerror("Error", "ISO/BIN Currently open in another program.")
        
    #Patch copied exe
    mod_data = {}    
    for cave in g_code_caves:
        #Read mod binary data into dictonary
        with open(mod_bin_file_path + cave[0] + ".bin", "rb+") as mod_file:
            mod_data[cave[0]] = mod_file.read()
        #Seek to correct position in game exe and write the correct mod data
        with open(patched_exe_name, "rb+") as game_exe_file:
            game_exe_file.seek(int(cave[2], base=16))    
            game_exe_file.write(mod_data[cave[0]])     
            
    for hook in g_hooks:
        #Read mod binary data into dictonary
        with open(mod_bin_file_path + hook[0] + ".bin", "rb+") as mod_file:
            mod_data[hook[0]] = mod_file.read()
        #Seek to correct position in game exe and write the correct mod data
        with open(patched_exe_name, "rb+") as game_exe_file:
            game_exe_file.seek(int(hook[2], base=16))
            game_exe_file.write(mod_data[hook[0]])
    try: 
        if g_patches != []:       
            for patch in g_patches:
                #Read user binary data into dictonary
                with open(patches_dir + patch[3][0], "rb+") as patch_file:
                    mod_data[patch[0]] = patch_file.read()
                #Seek to correct position in game exe and write the correct mod data
                with open(patched_exe_name, "rb+") as game_exe_file:
                    game_exe_file.seek(int(patch[2], base=16))
                    game_exe_file.write(mod_data[patch[0]])
    except Exception as e:
        #print("No patches found, ignoring {e}")
        print(e)
    
            
    if just_exe == False:
        #!Extract ISO and patch SLUS for PS2       
        if g_current_project_selected_platform == "PS2":
            file_path_and_name = g_current_project_game_disk_full_dir
            if file_path_and_name == None:
                print("Improper ISO")
                return
            old_dir = os.getcwd()
            os.chdir(g_current_project_folder)
            command_line_string = "..\\..\\prereq\\7z\\7z x " + "\"" + file_path_and_name + "\"" + " -o\"GameIsoExtract\""
            print(command_line_string + "\nExtracting...")
            did_iso_extract_fail = os.system(command_line_string) #in this context the exe is the iso. Confusing i know but
            if did_iso_extract_fail == 1:
                os.chdir(old_dir)
                error_msg = "ISO Extraction Failed!"
                print(error_msg)
                messagebox.showerror("Error", error_msg)
                return error_msg
            
            #Remove old exe/slus file in extracted iso folder and copy patched one
            original_exe_name = "GameIsoExtract/" + g_current_project_game_exe_name
            try:
                os.remove(original_exe_name)
            except:
                os.chdir(old_dir)
                error_msg = "ISO Extraction Failed!"
                print(error_msg)
                messagebox.showerror("Error", error_msg)
                return error_msg
            
            shutil.copyfile("patched_" + g_current_project_game_exe_name, original_exe_name)
            os.chdir(old_dir)
            print("ISO Extract/Patch Completed!")
            PatchPS2ISO()
        
        #!Extract BIN and patch SCUS for PS1       
        if g_current_project_selected_platform == "PS1":
            file_path_and_name = g_current_project_game_disk_full_dir
            if file_path_and_name == None:
                print("Improper ISO")
                return
            old_dir = os.getcwd()
            os.chdir(g_current_project_folder)
            command_line_string = f"..\\..\\prereq\\mkpsxiso\\dumpsxiso.exe \"{file_path_and_name}\" -x .config\\output\\ExtractedBIN -s .config\\output\\psxbuild.xml"
            print(command_line_string + "\nExtracting...")
            did_iso_extract_fail = os.system(command_line_string) #in this context the exe is the iso. Confusing i know but
            if did_iso_extract_fail == 1:
                os.chdir(old_dir)
                error_msg = "ISO Extraction Failed!"
                print(error_msg)
                messagebox.showerror("Error", error_msg)
                return error_msg
            
            #Remove old exe/slus file in extracted iso folder and copy patched one
            original_exe_name = ".config/output/ExtractedBIN/" + g_current_project_game_exe_name
            os.remove(original_exe_name)
            shutil.copyfile("patched_" + g_current_project_game_exe_name, original_exe_name)
            os.chdir(old_dir)
            print("ISO Extract/Patch Completed!")
            PatchPS1ISO()

        #!Extract ISO and patch Start.dol for Gamecube       
        if g_current_project_selected_platform == "Gamecube":
            file_path_and_name = g_current_project_game_disk_full_dir
            if file_path_and_name == None:
                print("Improper ISO")
                return
            file_name_ext = file_path_and_name.split("/")[-1]
            old_dir = os.getcwd()
            os.chdir(g_current_project_folder)
            try:
                shutil.copyfile(file_path_and_name, f"Modded_{file_name_ext}")
            except PermissionError:
                os.chdir(old_dir)
                messagebox.showerror("Error", "Game ISO or exe currently in use by another software.")
            command_line_string = f"..\\..\\prereq\\gcr\\gcr.exe \"Modded_{file_name_ext}\" \"root/&&SystemData/{g_current_project_game_exe_name}\" i {patched_exe_name.split('/')[-1]}"
            print(command_line_string + "\nExtracting...")
            did_iso_extract_fail = os.system(command_line_string) #in this context the exe is the iso. Confusing i know but
            if did_iso_extract_fail == 1:
                os.chdir(old_dir)
                error_msg = "ISO Extraction Failed!"
                print(error_msg)
                messagebox.showerror("Error", error_msg)
                return error_msg
            
            os.remove(patched_exe_name.split('/')[-1])
            os.chdir(old_dir)
                
        if g_current_project_selected_platform == "Wii":
            print("Wii Extract Pass")
            pass
                
        if g_current_project_selected_platform == "N64":
            print("N64 Extract Pass")
            pass
              
    #!If genereic executable (n64, wii), skip iso/bin stuff all above          
    open_in_explorer = messagebox.askyesno("Completed Patching", "Successfully created patched game! Would you like to open the directory in file explorer?")
    if open_in_explorer:
        #Open in file expolorer
        patched_directory = os.getcwd() + "\\" + patched_exe_name.replace('/', '\\').removesuffix("patched_" + g_current_project_game_exe_name)
        print("Opening Dir: " + patched_directory + "\nFinished!")
        subprocess.Popen("explorer " + patched_directory, shell=True)
        return "Build Complete!"
  
def FirstSelectISOThenBuild():
    open_ISO_file()
    InjectIntoExeAndRebuildGame()
                        
def PatchPS2ISO():
    # Create Iso from Folder
    global g_current_project_folder
    old_dir = os.getcwd()
    os.chdir(g_current_project_folder)
    
    NEW_ISO_NAME = "Patched Game.iso"
    IMGBURN_COMMAND = "..\..\prereq\ImgBurn\ImgBurn.exe /MODE BUILD /BUILDMODE IMAGEFILE /SRC \"GameIsoExtract\" /DEST " + NEW_ISO_NAME + " /FILESYSTEM \"ISO9660 + UDF\" /ROOTFOLDER YES /VOLUMELABEL \"Modded Game\" /UDFREVISION 1.50 /start /close /noimagedetails" 
    os.system(IMGBURN_COMMAND)
    shutil.rmtree("GameIsoExtract")
    os.remove("patched_" + g_current_project_game_exe_name)
    os.chdir(old_dir)
    
def PatchPS1ISO():
    # Create Iso from Folder
    global g_current_project_folder
    old_dir = os.getcwd()
    os.chdir(g_current_project_folder)

    mkpsx_command = f"..\\..\\prereq\\mkpsxiso\\mkpsxiso.exe .config\\output\\psxbuild.xml"
    os.system(mkpsx_command)
    
    os.remove("patched_" + g_current_project_game_exe_name)
    try:
        os.rename("mkpsxiso.bin", "ModdedGame.bin")
    
    #If File exists
    except FileExistsError:
        try:
            os.remove("ModdedGame.bin")
            os.rename("mkpsxiso.bin", "ModdedGame.bin")
        #If file in use
        except PermissionError:
            messagebox.showerror("Error", "File is currently in use, cannot replace.")
            os.chdir(old_dir)
    try:
        os.rename("mkpsxiso.cue", "ModdedGame.cue")
    except FileExistsError:
        os.remove("ModdedGame.cue")
        os.rename("mkpsxiso.cue", "ModdedGame.cue")
    
    os.chdir(old_dir)

#function to extract ps1 game either through gui, or through auto-find-exe
def ExtractPS1Game(user_choose=True, file_path=None):
    if user_choose == True:
        file_path_and_name = open_ISO_file()
    else:
        file_path_and_name = file_path
        
    if not file_path_and_name:
        return  
    output_path = open_output_folder().replace("/", "\\")  
    if not file_path_and_name or not output_path:
        print("Please choose ISO and output folder!")
        messagebox.showerror("Error", "Please choose output folder!")
        return 
        
    if file_path_and_name == None:
        print("Improper ISO")
        return
    
    old_dir = os.getcwd()
    #If extracting with no project
    if g_current_project_folder != "":
        os.chdir(g_current_project_folder)
        command_line_string = f"..\\..\\prereq\\mkpsxiso\\dumpsxiso.exe \"{file_path_and_name}\" -x \"{output_path}\""
    else:
        command_line_string = f"prereq\\mkpsxiso\\dumpsxiso.exe \"{file_path_and_name}\" -x \"{output_path}\""
    print(command_line_string + "\nExtracting...")
    did_iso_extract_fail = os.system(command_line_string) #in this context the exe is the iso. Confusing i know but
    if did_iso_extract_fail == 1:
        os.chdir(old_dir)
        error_msg = "ISO Extraction Failed!"
        print(error_msg)
        messagebox.showerror("Error", error_msg)
        return error_msg
    
    os.chdir(old_dir)
    
    if user_choose == True:
        print(command_line_string + "\nExtracting Done!")
        open_in_explorer = messagebox.askyesno("Completed Extracting", "Successfully extracted PS1 BIN! Would you like to open the directory in file explorer?")
        if open_in_explorer:
            #Open in file expolorer
            print("Opening Dir: " + output_path + "\nFinished!")
            subprocess.Popen(f"explorer \"{output_path}\"", shell=True)
            return "ISO Extract Complete"
    else:
        print(command_line_string + "\nExtracting Done!")
        return output_path

#function to extract ps2 game either through gui, or through auto-find-exe
def ExtractPS2Game(user_choose=True, file_path=None):
    if user_choose == True:
        file_path_and_name = open_ISO_file()
    else:
        file_path_and_name = file_path
        
    if not file_path_and_name:
        return  
    output_path = open_output_folder().replace("/", "\\")
    
    if not file_path_and_name or not output_path:
        print("Please choose ISO and output folder!")
        messagebox.showerror("Error", "Please choose output folder!")
        return
    
    if file_path_and_name == None:
        print("Improper ISO")
        return

    old_dir = os.getcwd()
    #If extracting with no project
    if g_current_project_folder != "":
        os.chdir(g_current_project_folder)
        command_line_string = "..\\..\\prereq\\7z\\7z x " + "\"" + file_path_and_name + "\"" + f" -o\"{output_path}\""
    else:
        command_line_string = "prereq\\7z\\7z x " + "\"" + file_path_and_name + "\"" + f" -o\"{output_path}\""
    print(command_line_string + "\nExtracting...") 
    did_iso_extract_fail = os.system(command_line_string) #in this context the exe is the iso. Confusing i know but
    if did_iso_extract_fail == 1:
        os.chdir(old_dir)
        error_msg = "ISO Extraction Failed!"
        print(error_msg)
        messagebox.showerror("Error", error_msg)
        return error_msg
    
    os.chdir(old_dir)
    
    if user_choose:
        print(command_line_string + "\nExtracting Done!")
        open_in_explorer = messagebox.askyesno("Completed Extracting", "Successfully extracted PS2 ISO! Would you like to open the directory in file explorer?")
        if open_in_explorer:
            #Open in file expolorer
            print("Opening Dir: " + output_path + "\nFinished!")
            subprocess.Popen(f"explorer \"{output_path}\"", shell=True)
            return "ISO Extract Complete"
    else:
        print(command_line_string + "\nExtracting Done!")
        return output_path

def ExtractGamecubeGame(user_choose=True, file_path=None):
    if user_choose == True:
        file_path_and_name = open_ISO_file()
    else:
        file_path_and_name = file_path
        
    if not file_path_and_name:
        return  
    output_path =  open_output_folder()
    output_path_modified = output_path.replace("/", "\\")
    
    if not file_path_and_name or not output_path:
        print("Please choose ISO and output folder!")
        messagebox.showerror("Error", "Please choose output folder!")
        return
    
    if file_path_and_name == None:
        print("Improper ISO")
        return

    old_dir = os.getcwd()
    #If extracting with no project
    if g_current_project_folder != "":
        os.chdir(g_current_project_folder)
        command_line_string = f"..\\..\\prereq\\gcr\\gcr.exe \"{file_path_and_name}\" root e \"{output_path}\""
    else:
        command_line_string = f"prereq\\gcr\\gcr.exe \"{file_path_and_name}\" root e \"{output_path}\""

    
    print(command_line_string + "\nExtracting...") 
    did_iso_extract_fail = os.system(command_line_string) #in this context the exe is the iso. Confusing i know but
    if did_iso_extract_fail == 1:
        os.chdir(old_dir)
        error_msg = "ISO Extraction Failed!"
        print(error_msg)
        messagebox.showerror("Error", error_msg)
        return error_msg  
          
    os.chdir(old_dir)
    
    if user_choose:
        print(command_line_string + "\nExtracting Done!")
        open_in_explorer = messagebox.askyesno("Completed Extracting", "Successfully extracted Gamecube ISO! Would you like to open the directory in file explorer?")
        if open_in_explorer:
            #Open in file expolorer
            print("Opening Dir: " + output_path_modified + "\nFinished!")
            subprocess.Popen(f"explorer \"{output_path_modified}\"", shell=True)
            return "ISO Extract Complete"
    else:
        print(command_line_string + "\nExtracting Done!")
        return output_path

def find_ps_exe_file(directory):
    for filename in os.listdir(directory):
        if filename.startswith("SCUS"):
            return directory + "/" + filename
        if filename.startswith("SCES"):
            return directory + "/" + filename
        if filename.startswith("SLUS"):
            return directory + "/" + filename
        if filename.startswith("SLES"):
            return directory + "/" + filename
    return None

def find_gamecube_exe_file(directory):
    for filename in os.listdir(directory + "/root\&&systemdata/"):
        if filename.startswith("Start"):
            return directory + "/root/&&systemdata/" + filename
    return None

def auto_find_exe(file_path):
    project_platform = g_current_project_selected_platform
    
    if project_platform == "PS1":
        output_path = ExtractPS1Game(user_choose=False, file_path=file_path)
        print(output_path)
        ps1_exe_file = find_ps_exe_file(output_path)
        if ps1_exe_file:
            open_ISO_file(file_path, False)
            return ps1_exe_file
    elif project_platform == "PS2":
        output_path = ExtractPS2Game(user_choose=False, file_path=file_path)
        print(output_path)
        ps2_exe_file = find_ps_exe_file(output_path)
        if ps2_exe_file:
            open_ISO_file(file_path, False)
            return ps2_exe_file
    elif project_platform == "Gamecube":
        output_path = ExtractGamecubeGame(user_choose=False, file_path=file_path)
        print(output_path)
        gamecube_exe_file = find_gamecube_exe_file(output_path)
        if gamecube_exe_file:
            open_ISO_file(file_path, False)
            return gamecube_exe_file

def open_exe_file():
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    global selected_game_label
    global g_current_project_game_disk_full_dir
    
    file_path = filedialog.askopenfilename(title="Choose game executable (SCUS, SLUS, etc)")
    
    if file_path.split(".")[-1] == "iso" or file_path.split(".")[-1] == "bin" or file_path.split(".")[-1] == "ciso" or file_path.split(".")[-1] == "gcm":
        if g_current_project_feature_mode == "Normal":
            should_auto_find_exe = messagebox.askokcancel("Image chosen", f"You have chosen {file_path.split('/')[-1]}. Please choose a folder to extract this image to, And this utility will try to find the main executable file.")
        if g_current_project_feature_mode == "Advanced":
            should_auto_find_exe = messagebox.askyesno("Image chosen", "You have chosen an ISO/BIN file instead of the main executable. Would you to automatically extract this image to a folder, and try to find main executable?")
        if should_auto_find_exe == True:
            if g_current_project_selected_platform == "Gamecube":
                file_path = auto_find_exe(file_path)
            else:
                file_path = auto_find_exe(file_path)
            if file_path:
                messagebox.showinfo("Success", f"Successfully found {file_path.split('/')[-1]} in ISO/BIN")
            else:
                messagebox.showerror("Error", "Could not automatically find executable in ISO/BIN")
        else:
            messagebox.showinfo("Info", "Please manually extract ISO/BIN, then select proper game exetuable file")
            return
    if file_path:
        g_current_project_game_exe_full_dir = file_path              # Full Path
        g_current_project_game_exe_name = file_path.split("/")[-1]   # Spliting based on /, and getting last index with -1 to get only name of file
        print(f"Selected file: {file_path}")
    else:
        messagebox.showerror("Error", "Please select proper game exetuable file")
        return
    #else:
        #messagebox.showerror("Error", "Please choose proper game executable")
    if g_current_project_game_exe_name:
        if selected_game_label == None:
            selected_game_label = ttk.Label(main_tab, text='Game Executable:\n' + g_current_project_game_exe_name, font=("GENIUNE", 15))
            selected_game_label.place(x=300, y=135)
        else:
            selected_game_label.config(text='Game Executable:\n' + g_current_project_game_exe_name, font=("GENIUNE", 15))
   
    #Save to config     
    g_current_project_game_exe = g_current_project_game_exe_full_dir
    if g_current_project_game_exe:
        with open(f"{g_current_project_folder}/.config/config.txt", "w") as config_file:
            config_file.write(g_current_project_game_exe + "\n")
            config_file.write(g_current_project_selected_platform + "\n")
            if g_current_project_game_disk_full_dir != "":
                config_file.write(g_current_project_game_disk_full_dir + "\n")
            if g_current_project_ram_watch_full_dir:
                config_file.write(g_current_project_ram_watch_full_dir + "\n")
            print("Project Config saved. Executable dir: "  +  g_current_project_game_exe)
            
    #Set compile button text
    name_of_exe = g_current_project_game_exe.split("/")[-1]
    if inject_exe_button:
        inject_exe_button.config(text=f"Create new patched {name_of_exe} copy")
        
    check_has_picked_exe()    
    PrepareBuildInjectGUIOptions()
    project_switched()

def open_ISO_file(arg_file_path, user_choice=True):
    global g_current_project_game_disk
    global g_current_project_game_disk_full_dir
    
    if user_choice:
        file_path = filedialog.askopenfilename(title="Choose ISO/BIN file")
    else:
        file_path = arg_file_path
        
    if ".iso" in file_path.split("/")[-1].lower() or ".bin" in file_path.split("/")[-1].lower() or ".ciso" in file_path.split("/")[-1].lower() or ".gcm" in file_path.split("/")[-1].lower():
        g_current_project_game_disk_full_dir = file_path                # Full Path
        g_current_project_game_disk = file_path.split("/")[-1]          # Spliting based on /, and getting last index with -1 to get only name of file
        
        print(f"Selected file: {file_path}")
        if build_iso_button:
            build_iso_button.config(text=f"Build Patched Copy of {g_current_project_game_disk}", command=InjectIntoExeAndRebuildGame)
        #Save to config     
        save_to_config()
            
        return file_path
    else:
        messagebox.showerror("Error", "Please choose proper game iso/bin")
        return None   
           
def open_output_folder():
    return filedialog.askdirectory(title="Choose output directoy") 
    
def save_to_config():
    try:
        with open(f"{g_current_project_folder}/.config/config.txt", "w+") as config_file:
                config_file.write(g_current_project_game_exe_full_dir + "\n")
                config_file.write(g_current_project_selected_platform + "\n")
                if g_current_project_game_disk_full_dir != "":
                    config_file.write(g_current_project_game_disk_full_dir + "\n")
                if g_current_project_ram_watch_full_dir != "":
                    config_file.write(g_current_project_ram_watch_full_dir + "\n")
                print("Project Config saved.")
    #Probably means extracting with no projects selected           
    except FileNotFoundError:
        print("No current project, not saving!")       
    
def extract_ascii_from_bytes(input_bytes):
    try:
        # Attempt to decode the bytes as ASCII
        ascii_text = input_bytes.decode('ascii')
        return ascii_text
    except UnicodeDecodeError:
        # Handle the case where non-ASCII characters are present
        # Replace non-ascii characters with a question mark
        ascii_text = ''.join(chr(byte) if 32 <= byte <= 126 else '?' for byte in input_bytes)
        return ascii_text
    
def search_for_debug_text():
    game_exe_bytes = ""
    with open(g_current_project_game_exe_full_dir, "rb") as exe_file:
        game_exe_bytes = exe_file.read()
        game_exe_ascii = extract_ascii_from_bytes(game_exe_bytes)
        game_ascii_split = game_exe_ascii.split("?")
        game_ascii_list = [item for item in game_ascii_split if item is not None and item != ''] #Removing empty elements
        print(game_ascii_list)
        
        #Get biggest string
        biggest_string_len = 0
        biggest_string = ""
        for game_string in game_ascii_list:
            current_str_len = len(game_string)
            if current_str_len > biggest_string_len:
                biggest_string_len = current_str_len
                biggest_string = game_string
                with open("testtt.txt", "a") as test:
                    test.write(biggest_string + "\n\n")
        
        print(biggest_string)
        
def find_ps2_offset():
    objdump_output = subprocess.run(f"prereq/PS2ee/bin/ee-objdump \"{g_current_project_game_exe_full_dir}\" -x", shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if "Idx Name" in objdump_output.stdout:
        objdump_section_0 = objdump_output.stdout.split("Idx Name")[1].split("\n")[1]
        objdump_section_0_list = objdump_section_0.split()
        #print("objdump section: ")
        #print(objdump_section_0_list)
        print(colored("PS2 offset found", "cyan"))

        if len(objdump_section_0_list) == 7:
            offset = int(objdump_section_0_list[4], base=16) - int(objdump_section_0_list[5], base=16)
        elif len(objdump_section_0_list) == 6:
            offset = int(objdump_section_0_list[3], base=16) - int(objdump_section_0_list[4], base=16)
        else:
            print(colored("Unknown Elf Offset!", "red"))
            return False
        
        return offset
    else:
        print(objdump_output.stderr)
        print(objdump_output.stdout)
        print(colored("Couldn't find offset", "red"))
        return False
    
def find_gamecube_offset():
    objdump_output = subprocess.run(f"prereq/doltool/doltool -i \"{g_current_project_game_exe_full_dir}\"", shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if "Text Section  1" in objdump_output.stdout:
        doltool_section_1 = objdump_output.stdout.split("Text Section  1:")[1]
        doltool_section_1_list = doltool_section_1.split()
        
        disk_area = int(doltool_section_1_list[0].split('=')[1], base=16)
        memory_area = int(doltool_section_1_list[1].split('=')[1].removeprefix("80"), base=16)
        offset = memory_area - disk_area
        
        print(colored("Gamecube offset found", "cyan"))
        
        return offset

    else:
        print(objdump_output.stderr)
        print(objdump_output.stdout)
        print(colored("Couldn't find offset", "red"))
        return False
    
def auto_find_hook_in_ps1_game(event=0):
    with open(g_current_project_game_exe_full_dir, "rb") as game_exe:
        ps1_draw_otag_opcodes =             b'\x09\xf8\x40\x00\x21\x38\x00\x00\x14\x00\xbf\x8f\x10\x00\xb0\x8f\x18\x00\xbd\x27\x08\x00\xe0\x03\x00\x00\x00\x00\xe0\xff\xbd\x27\x18\x00\xb2\xaf'
        ps1_draw_otag_2_opcodes =           b'\x09\xf8\x40\x00\x21\x38\x00\x00\x14\x00\xbf\x8f\x10\x00\xb0\x8f\x08\x00\xe0\x03\x18\x00\xbd\x27\xe0\xff\xbd\x27\x18\x00\xb2\xaf'
        ps1_draw_otag_3_opcodes =           b'\x00\x00\x00\x00\x09\xf8\x40\x00\x21\x38\x00\x00\x14\x00\xbf\x8f\x10\x00\xb0\x8f\x18\x00\xbd\x27\x08\x00\xe0\x03\x00\x00\x00\x00'
        ps1_draw_otag_4_opcodes =           b'\x00\x00\x00\x00\x09\xf8\x40\x00\x21\x30\x00\x00\x14\x00\xbf\x8f\x10\x00\xb0\x8f\x18\x00\xbd\x27\x08\x00\xe0\x03\x00\x00\x00\x00'
        game_exe_bytes = game_exe.read()
        
        if ps1_draw_otag_opcodes in game_exe_bytes:
            print("Found DrawOTag 1!")
            start_of_otag = game_exe_bytes.index(ps1_draw_otag_opcodes)
            jr_ra_placement = start_of_otag + 0x14
            print("Hook address will be: " + hex(jr_ra_placement))
            
            g_hooks.append(("AutoHook", hex(0x80000000 + jr_ra_placement + 0xF800), hex(jr_ra_placement), ["main_hook.s"], "-0xF800"))
        elif ps1_draw_otag_2_opcodes in game_exe_bytes:
            print("Found DrawOTag 2!")
            start_of_otag = game_exe_bytes.index(ps1_draw_otag_2_opcodes)
            jr_ra_placement = start_of_otag + 0x10
            print("Hook address will be: " + hex(jr_ra_placement))
            
            g_hooks.append(("AutoHook", hex(0x80000000 + jr_ra_placement + 0xF800), hex(jr_ra_placement), ["main_hook.s"], "-0xF800"))
        elif ps1_draw_otag_2_opcodes in game_exe_bytes:
            print("Found DrawOTag 3!")
            start_of_otag = game_exe_bytes.index(ps1_draw_otag_3_opcodes)
            jr_ra_placement = start_of_otag + 0x18
            print("Hook address will be: " + hex(jr_ra_placement))
            
            g_hooks.append(("AutoHook", hex(0x80000000 + jr_ra_placement + 0xF800), hex(jr_ra_placement), ["main_hook.s"], "-0xF800"))
        elif ps1_draw_otag_4_opcodes in game_exe_bytes:
            print("Found DrawOTag 3!")
            start_of_otag = game_exe_bytes.index(ps1_draw_otag_4_opcodes)
            jr_ra_placement = start_of_otag + 0x18
            print("Hook address will be: " + hex(jr_ra_placement))
            
            g_hooks.append(("AutoHook", hex(0x80000000 + jr_ra_placement + 0xF800), hex(jr_ra_placement), ["main_hook.s"], "-0xF800"))
        else:
            messagebox.showwarning("Failed", "Could not automatically find hook")
            return
        
        hooks_listbox.insert(tk.END, g_hooks[-1][0])
        messagebox.showinfo("Found hook", "Successfully found universal PS1 hook!")
        update_codecaves_hooks_patches_config_file()    
        update_asm_file_auto_ps1_hook()
        project_switched()
        run_every_tab_switch()
        on_platform_select()
 
def auto_find_hook_in_ps2_game(just_return=False, event=0):
    with open(g_current_project_game_exe_full_dir, "rb") as game_exe:
        ps2_sceSifSendCmd_opcodes =             b'\x2d\x10\xc0\x00\x2d\x18\xe0\x00\x2d\x58\x00\x01\xf0\xff\xbd\x27\x2d\x50\x20\x01\x2d\x30\xa0\x00\x00\x00\xbf\xff\x2d\x38\x40\x00\x2d\x40\x60\x00\x2d\x48\x60\x01'
        ps2_scePad2Read_opcodes =               b'\x2d\x20\x40\x02\x34\x03\x03\x24\x02\x00\x04\x92\x18\x18\x23\x02'
        ps2_scePadRead_opcodes =                b'\x2d\x38\x80\x00\x70\x00\x03\x24\x1c\x00\x04\x24\x18\x18\xe3\x70\x18\x20\xa4\x00'
                                                
        game_exe_bytes = game_exe.read()
        
        offset = find_ps2_offset()
        if offset == False:
            print("Failed to get offset!")
            return
        offset_hex = hex(offset)
        offset_neg_hex = hex(-offset)
        
        if ps2_sceSifSendCmd_opcodes in game_exe_bytes:
            start_of_sce = game_exe_bytes.index(ps2_sceSifSendCmd_opcodes)
            print(f"Found sceSifSendCmd 1 at {hex(start_of_sce)} in {g_current_project_game_exe_name}!\n")
            jr_ra_placement = start_of_sce + 0x34
            
            #For CheatDevicePS2
            if just_return == True:
                master_code_address = jr_ra_placement - 0xc
                master_code_opcode_little_endian = int(int(game_exe_bytes[master_code_address:master_code_address+4].hex(), base=16).to_bytes(4, 'little').hex(), base=16)
                hex_master_code_address = hex(master_code_address + offset).removeprefix("0x")
                hex_master_code_opcode = hex(master_code_opcode_little_endian).removeprefix("0x").zfill(8)
                return {'address': hex_master_code_address, 'opcode': hex_master_code_opcode}
            
        elif ps2_scePad2Read_opcodes in game_exe_bytes:
            start_of_sce = game_exe_bytes.index(ps2_scePad2Read_opcodes)
            print(f"Found scePad2Read at {hex(start_of_sce)} in {g_current_project_game_exe_name}!\n")
            jr_ra_placement = start_of_sce + 0x48
            
        elif ps2_scePadRead_opcodes in game_exe_bytes:
            start_of_sce = game_exe_bytes.index(ps2_scePadRead_opcodes)
            print(f"Found scePadRead at {hex(start_of_sce)} in {g_current_project_game_exe_name}!\n")
            jr_ra_placement = start_of_sce + 0x74
            
            if just_return == True:
                master_code_address = jr_ra_placement - 0xc
                master_code_opcode_little_endian = int(int(game_exe_bytes[master_code_address:master_code_address+4].hex(), base=16).to_bytes(4, 'little').hex(), base=16)
                hex_master_code_address = hex(master_code_address + offset).removeprefix("0x")
                hex_master_code_opcode = hex(master_code_opcode_little_endian).removeprefix("0x").zfill(8)
                return {'address': hex_master_code_address, 'opcode': hex_master_code_opcode}
            
        else:
            messagebox.showwarning("Failed", "Could not automatically find hook")
            return
        
        g_hooks.append(("AutoHook", hex(jr_ra_placement + offset), hex(jr_ra_placement), ["main_hook.s"], offset_neg_hex))
        hooks_listbox.insert(tk.END, g_hooks[-1][0])
        messagebox.showinfo("Found hook", "Successfully found universal PS2 hook!")
        update_codecaves_hooks_patches_config_file()    
        update_asm_file_auto_ps2_hook()
        project_switched()
        run_every_tab_switch()
        on_platform_select()
        
def auto_find_hook_in_gamecube_game(event=0):
    with open(g_current_project_game_exe_full_dir, "rb") as game_exe:
        gc_VIWaitForRetrace_opcodes =             b'\x93\xe1\x00\x44\x89\x03\x00\x2c\xa0\x03\x00\x0e\x55\x1f\x28\x34\xa1\x03\x00\x16\x7c\x1f\x01\xd6\x81\x63\x00\x20\x81\x43\x00\x30\xa1\x83\x00\x0a\x55\x08\x08\x34\x7c\x08\x02\x14\x7c\x0a\x02\x14\x2c\x0b\x00\x00\x90\x04\x00\x00'
        game_exe_bytes = game_exe.read()
        
        offset = find_gamecube_offset()
        if offset == False:
            print("Failed to get offset!")
            return
        offset_neg_hex = hex(-offset)
        
        if gc_VIWaitForRetrace_opcodes in game_exe_bytes:
            start_of_sce = game_exe_bytes.index(gc_VIWaitForRetrace_opcodes)
            print(f"Found VIWaitForRetrace 1 at {hex(start_of_sce)} in {g_current_project_game_exe_name}!\n")
            blr_placement = start_of_sce - 0x10             
        else:
            messagebox.showwarning("Failed", "Could not automatically find hook")
            return
        
        g_hooks.append(("AutoHook", hex(blr_placement + 0x80000000 + offset), hex(blr_placement), ["main_hook.s"], offset_neg_hex))
        hooks_listbox.insert(tk.END, g_hooks[-1][0])
        messagebox.showinfo("Found hook", "Successfully found universal Gamecube hook!")
        update_codecaves_hooks_patches_config_file()    
        update_asm_file_auto_gamecube_hook()
        project_switched()
        run_every_tab_switch()
        on_platform_select()
        
def auto_find_hook_in_wii_game(event=0):
    with open(g_current_project_game_exe_full_dir, "rb") as game_exe:
        wii_osSleepThread_opcodes =             b'\x90\xa4\x02\xe0\x80\x65\x02\xe4\x90\x85\x02\xe4\x2c\x03\x00\x00\x90\x64\x02\xe4'
        game_exe_bytes = game_exe.read()
        
        offset = find_gamecube_offset()
        if offset == False:
            print("Failed to get offset!")
            return
        offset_neg_hex = hex(-offset)
        
        if wii_osSleepThread_opcodes in game_exe_bytes:
            start_of_sce = game_exe_bytes.index(wii_osSleepThread_opcodes)
            print(f"Found OSSleepThread 1 at {hex(start_of_sce)} in {g_current_project_game_exe_name}!\n")
            blr_placement = start_of_sce + 0x5C             
        else:
            messagebox.showwarning("Failed", "Could not automatically find hook")
            return
        
        g_hooks.append(("AutoHook", hex(blr_placement + 0x80000000 + offset), hex(blr_placement), ["main_hook.s"], offset_neg_hex))
        hooks_listbox.insert(tk.END, g_hooks[-1][0])
        messagebox.showinfo("Found hook", "Successfully found universal Wii hook!")
        update_codecaves_hooks_patches_config_file()    
        update_asm_file_auto_wii_hook()
        project_switched()
        run_every_tab_switch()
        on_platform_select()
  
def update_asm_file_auto_ps1_hook():
    with open(f"{g_current_project_folder}/asm/main_hook.s", "w") as main_file:
        main_file.write(".set noreorder\n#Replacing DrawOTag jr ra.\nj CustomFunction\n") 
        print("Updated ASM File for PS1 Auto-Hook")
  
def update_asm_file_auto_ps2_hook():
    with open(f"{g_current_project_folder}/asm/main_hook.s", "w") as main_file:
        main_file.write(".set noreorder\n#Replacing sceSifSendCmd/scePad2Read jr ra.\nj CustomFunction\n")
        print("Updated ASM File for PS2 Auto-Hook")
        
def update_asm_file_auto_gamecube_hook():
    with open(f"{g_current_project_folder}/asm/main_hook.s", "w") as main_file:
        main_file.write("#Replacing VIWaitForRetrace blr.\nb CustomFunction\n")
        print("Updated ASM File for Gamecube Auto-Hook")
        
def update_asm_file_auto_wii_hook():
    with open(f"{g_current_project_folder}/asm/main_hook.s", "w") as main_file:
        main_file.write("#Replacing OSSleepThread blr.\nb CustomFunction\n")
        print("Updated ASM File for Gamecube Auto-Hook")

def convert_to_ps2rd_code(ignore_codecaves=False):
    mod_bin_file_path = g_current_project_folder + "/.config/output/final_bins/"
    patches_file_path = g_current_project_folder + "/patches/"
    
    #Copy mod data
    mod_data = {}    
    chunks = {}
    chunk_size = 4
    
    for cave in g_code_caves:
        #Read mod binary data into dictonary
        with open(mod_bin_file_path + cave[0] + ".bin", "rb+") as mod_file:
            mod_data[cave[0]] = mod_file.read()
            
        #Create P2SRD Code
        for i in range(0, len(mod_data[cave[0]]), chunk_size):
            #If current cave name does not have a list create one
            if cave[0] not in chunks:
                chunks[cave[0]] = []
            #Create the PS2RD code from the data in the caves list
            current_chunk_little_endian = int(mod_data[cave[0]][i:i+chunk_size].hex(), base=16).to_bytes(4, byteorder='little').hex()
            chunks[cave[0]].append("20" + hex(int(cave[1].removeprefix("0x"), base=16) + i).removeprefix("0x") + " " + current_chunk_little_endian)
            
    for hook in g_hooks:
        #Read mod binary data into dictonary
        with open(mod_bin_file_path + hook[0] + ".bin", "rb+") as mod_file:
            mod_data[hook[0]] = mod_file.read()
            
        #Create PS2RD Code
        for i in range(0, len(mod_data[hook[0]]), chunk_size):
            #If current hook name does not have a list create one
            if hook[0] not in chunks:
                chunks[hook[0]] = []
            #Create the PS2RD code from the data in the hooks list
            current_chunk_little_endian = int(mod_data[hook[0]][i:i+chunk_size].hex(), base=16).to_bytes(4, byteorder='little').hex()
            chunks[hook[0]].append("20" + hex(int(hook[1].removeprefix("0x"), base=16) + i).removeprefix("0x") + " " + current_chunk_little_endian)
            
    try:
        if g_patches != []:
            for patch in g_patches:
                #Read mod binary data into dictonary
                with open(patches_file_path + patch[3][0], "rb+") as patch_file:
                    mod_data[patch[0]] = patch_file.read()
                
                #Create PS2RD Code
                for i in range(0, len(mod_data[patch[0]]), chunk_size):
                    #If current patch name does not have a list create one
                    if patch[0] not in chunks:
                        chunks[patch[0]] = []
                    #Create the PS2RD code from the data in the patches list
                    current_chunk_little_endian = int(mod_data[patch[0]][i:i+chunk_size].hex(), base=16).to_bytes(4, byteorder='little').hex()
                    chunks[patch[0]].append("20" + hex(int(patch[1].removeprefix("0x"), base=16) + i).removeprefix("0x") + " " + current_chunk_little_endian)
    except Exception as e:
        #print("No binary patches found, ignoring. {e}")
        print(e)
            
    #print(chunks)
    
    mastercode = auto_find_hook_in_ps2_game(just_return=True)
    
    full_code = f"\"{g_current_project_name} /ID {g_current_project_game_exe_name}\"\nMastercode\n"
    full_code += f"90{mastercode['address']} {mastercode['opcode']}\n\n"
    full_code += f"Mod\n"
    
    if ignore_codecaves == True:
        #Write codes with free ram area
        for value in chunks.values():
            for code in value:
                full_code += code + "\n"    
    
    #Write codes
    for value in chunks.values():
        for code in value:
            full_code += code + "\n"
    
    print(colored("PS2RD Code: \n" + full_code, "blue"))
    
    pyperclip.copy(full_code)
    messagebox.askquestion
    user_answer = messagebox.askyesno("Done", f"Created PS2RD code and copied to clipboard. Would you like to create a {g_current_project_game_exe_name}.cht file?")
    if user_answer == True:
        with open(f"{g_current_project_folder}/{g_current_project_game_exe_name}.cht", "w") as text_file:
            text_file.write(full_code)
        #Open in file expolorer
        cmd_string = f"explorer \"{os.getcwd() + '/' + g_current_project_folder}\"".replace("/", "\\")
        print("Opening Dir: " + cmd_string + "\nFinished!")
        subprocess.Popen(cmd_string, shell=True)
    
def convert_to_gameshark_code(ignore_codecaves=False):
    mod_bin_file_path = g_current_project_folder + "/.config/output/final_bins/"
    patches_file_path = g_current_project_folder + "/patches/"
    
    #Copy mod data
    mod_data = {}    
    chunks = {}
    chunk_size = 2
    
    for cave in g_code_caves:
        #Read mod binary data into dictonary
        with open(mod_bin_file_path + cave[0] + ".bin", "rb+") as mod_file:
            mod_data[cave[0]] = mod_file.read()
            
        #Create Gameshark Code
        for i in range(0, len(mod_data[cave[0]]), chunk_size):
            #If current cave name does not have a list create one
            if cave[0] not in chunks:
                chunks[cave[0]] = []
            #Create the PS2RD code from the data in the caves list
            current_chunk_little_endian = int(mod_data[cave[0]][i:i+chunk_size].hex(), base=16).to_bytes(chunk_size, byteorder='little').hex()
            chunks[cave[0]].append(hex(int(cave[1].removeprefix("0x"), base=16) + i).removeprefix("0x") + " " + current_chunk_little_endian)
            
    for hook in g_hooks:
        #Read mod binary data into dictonary
        with open(mod_bin_file_path + hook[0] + ".bin", "rb+") as mod_file:
            mod_data[hook[0]] = mod_file.read()
            
        #Create Gameshark Code
        for i in range(0, len(mod_data[hook[0]]), chunk_size):
            #If current hook name does not have a list create one
            if hook[0] not in chunks:
                chunks[hook[0]] = []
            #Create the PS2RD code from the data in the hooks list
            current_chunk_little_endian = int(mod_data[hook[0]][i:i+chunk_size].hex(), base=16).to_bytes(chunk_size, byteorder='little').hex()
            chunks[hook[0]].append(hex(int(hook[1].removeprefix("0x"), base=16) + i).removeprefix("0x") + " " + current_chunk_little_endian)
     
    try:        
        for patch in g_patches:
            if g_patches != []:
                #Read mod binary data into dictonary
                with open(patches_file_path + patch[3][0], "rb+") as patch_file:
                    mod_data[patch[0]] = patch_file.read()
                    
                #Create Gameshark Code
                for i in range(0, len(mod_data[patch[0]]), chunk_size):
                    #If current patch name does not have a list create one
                    if patch[0] not in chunks:
                        chunks[patch[0]] = []
                    #Create the Gameshark code from the data in the patches list
                    current_chunk_little_endian = int(mod_data[patch[0]][i:i+chunk_size].hex(), base=16).to_bytes(chunk_size, byteorder='little').hex()
                    chunks[patch[0]].append(hex(int(patch[1].removeprefix("0x"), base=16) + i).removeprefix("0x") + " " + current_chunk_little_endian)
    except:
        print("Binary patches not found, ignoring")
                
    #print(chunks)
    
    
    full_code = f"Mod Gameshark Code\n"
    
    if ignore_codecaves == True:
        #Write codes with free ram area
        for value in chunks.values():
            for code in value:
                full_code += code + "\n"    
    
    #Write codes
    for value in chunks.values():
        for code in value:
            full_code += code + "\n"
    
    print(colored("Gameshark Code: \n" + full_code, "blue"))
    
    pyperclip.copy(full_code)
    user_answer = messagebox.showinfo("Done", f"Created Gameshark code and copied to clipboard.")
    
def auto_place_ps1_header(event=0):
    global g_code_caves
    if g_code_caves == []:
        g_code_caves.append(("Header", "0x8000B0B8", "0x48", ["main.c"], "0x0", "0x10000"))
        codecaves_listbox.insert(tk.END, g_code_caves[-1][0])
        
        update_codecaves_hooks_patches_config_file()    
        project_switched()
        run_every_tab_switch()
        on_platform_select()
        
        messagebox.showinfo("Done", "Created Header codecave using main.c as default file. Note: region only 0x800 bytes in size!")
         
def run_every_tab_switch(event=0):
    global auto_hook_button
    global auto_hook_ps2_button
    global auto_cave_button
    reset_auto_hook_buttons()
    update_linker_script()
        
    #Fill with first cave and hook upon switching    
    if g_code_caves != []:
        codecave_name_entry.delete(0, tk.END)
        in_game_memory_entry.delete(0, tk.END)
        disk_exe_entry.delete(0, tk.END)
        c_files_entry.delete(0, tk.END)
        global_offset_entry.delete(0, tk.END)
        codecave_size_entry.delete(0, tk.END)
        
        codecave_name_entry.insert(0, g_code_caves[0][0])
        in_game_memory_entry.insert(0, g_code_caves[0][1])
        disk_exe_entry.insert(0, g_code_caves[0][2])
        c_files_entry.insert(0, ", ".join(g_code_caves[0][3]))
        try:
            global_offset_entry.config(state="active")
            global_offset_entry.delete(0, tk.END)
            global_offset_entry.insert(0, g_code_caves[0][4])
            global_offset_entry.config(state="disabled")
        except:
            pass
            #print("No offset to load, skipping")
        try:
            codecave_size_entry.insert(0, g_code_caves[0][5])
        except:
            pass
            #print("No size to load, skipping")
        
    if g_hooks != []:
        hook_name_entry.delete(0, tk.END)
        in_game_memory_entry_hooks.delete(0, tk.END)
        disk_exe_entry_hooks.delete(0, tk.END)
        asm_files_entry.delete(0, tk.END)
        hook_name_entry.insert(0, g_hooks[0][0])
        in_game_memory_entry_hooks.insert(0, g_hooks[0][1])
        disk_exe_entry_hooks.insert(0, g_hooks[0][2])
        asm_files_entry.insert(0, ", ".join(g_hooks[0][3]))
        try:
            global_offset_entry_hooks.config(state="active")
            global_offset_entry_hooks.delete(0, tk.END)
            global_offset_entry_hooks.insert(0, g_hooks[0][4])
            global_offset_entry_hooks.config(state="disabled")
        except:
            pass
            #print("No offset to load, skipping")
        
    if g_patches != []:
        patch_name_entry.delete(0, tk.END)
        in_game_memory_entry_patches.delete(0, tk.END)
        disk_exe_entry_patches.delete(0, tk.END)
        patch_files_entry.delete(0, tk.END)
        patch_name_entry.insert(0, g_patches[0][0])
        in_game_memory_entry_patches.insert(0, g_patches[0][1])
        disk_exe_entry_patches.insert(0, g_patches[0][2])
        patch_files_entry.insert(0, ", ".join(g_patches[0][3]))
        try:
            global_offset_entry_patches.config(state="active")
            global_offset_entry_patches.delete(0, tk.END)
            global_offset_entry_patches.insert(0, g_patches[0][4])
            global_offset_entry_patches.config(state="disabled")
        except:
            pass
            #print("No offset to load, skipping")
               
def check_memory_map_sizes():
    with open(f"projects\{g_current_project_name}\.config\output\memory_map\MyMod.map") as memory_map_file:
        memory_map_data = memory_map_file.read()

        for cave in g_code_caves:
            if "." + cave[0] in memory_map_data:
                cave_section_index = memory_map_data.find("." + cave[0])
                cave_section_text = memory_map_data[cave_section_index:].split("\n")[0]
                cave_section_name = cave_section_text.split()[0].split(".")[1]
                cave_section_current_size = cave_section_text.split()[2]
                cave_section_address = hex(int(cave_section_text.split()[1], base=16))
                
                cave_section_current_size_int = int(cave_section_current_size, base=16)
                if cave[5]:
                    cave_section_full_size_int = int(cave[5], base=16)
                    cave_size_percentage = cave_section_current_size_int / cave_section_full_size_int
                    
                    print(colored(f"Codecave {cave_section_name} starting at address {cave_section_address}, is currently taking up ", "blue") + colored(f"{cave_section_current_size}", "yellow") + colored(" bytes out of ", "blue") + colored(f"{cave[5]}", "yellow") + colored(f" bytes available. ", "blue") + colored(f"{cave_size_percentage:.0%} full.\n", "yellow"))
                else:
                   print(colored(f"Codecave {cave_section_name} starting at address {cave_section_address}, is currently taking up ", "blue") + colored(f"{cave_section_current_size}", "yellow") + colored(" bytes.\n", "blue"))
                   
def update_linker_script():
    global g_shouldShowTabs
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    global g_current_project_selected_platform
    
    
    if g_current_project_name != "":  
        try:    
            with open(f"{g_current_project_folder}/.config/linker_script.ld", "w+") as script_file:
                script_file.write("INPUT(../../../.config/symbols/symbols.txt)\nINPUT(../../../.config/symbols/function_symbols.txt)\nINPUT(../../../.config/symbols/auto_symbols.txt)\n\nMEMORY\n{\n    /* RAM locations where we'll inject the code for our replacement functions */\n")
                for cave in g_code_caves:
                    script_file.write(f"    {cave[0]} : ORIGIN = {cave[1]}, LENGTH = {cave[5] if cave[5] != '' else '0x100000'}\n") # If a size exists in the code cave, then it places it, If not, it defaults to 0x100000
                for hook in g_hooks:
                    script_file.write(f"    {hook[0]} : ORIGIN = {hook[1]}, LENGTH = 0x100000")
                    
                script_file.write("}\n\nSECTIONS\n{\n    /* Custom section for compiled code */\n    ")
                #Hooks
                for hook in g_hooks:
                    script_file.write("/* Custom section for our hook code */\n    ")
                    script_file.write("." + hook[0])
                    script_file.write(" : \n    {\n")
                    for asm_file in hook[3]:
                        o_file = asm_file.split(".")[0] + ".o"
                        script_file.write("        " + o_file + "(.text)\n        " + o_file + "(.rodata)\n        " + o_file + "(.rodata*)\n        " + o_file + "(.data)\n        " + o_file + "(.bss)\n")
                    script_file.write("    } > ")
                    script_file.write(f"{hook[0]}\n\n    ")
                    
                amount_of_caves = 0    
                for cave in g_code_caves:
                    amount_of_caves += 1
                #Code Caves
                for i, cave in enumerate(g_code_caves):
                    script_file.write("." + cave[0])
                    script_file.write(" : \n    {\n")
                    for c_file in cave[3]:
                        o_file = c_file.split(".")[0] + ".o"
                        script_file.write("        " + o_file + "(.text)\n        " + o_file + "(.rodata)\n        " + o_file + "(.rodata*)\n        " + o_file + "(.data)\n        " + o_file + "(.bss)\n        "         + o_file + "(.sdata)\n        " + o_file + "(.sbss)\n")
                        #script_file.write("main.o(.text)\n        *(.rodata)\n        *(.data)\n        *(.bss)\n    } > ")
                        
                    #If last cave, place remaining sections
                    if i == amount_of_caves:
                        script_file.write("        *(.text)\n")
                        script_file.write("        *(.branch_lt)\n")
                        
                    script_file.write("    } > ")
                    script_file.write(f"{cave[0]}\n\n    ")
                    
                script_file.write("/DISCARD/ :\n    {\n        *(.comment)\n        *(.pdr)\n        *(.mdebug)\n        *(.reginfo)\n        *(.MIPS.abiflags)\n        *(.eh_frame)\n        *(.gnu.attributes)\n    }\n}")
        except UnboundLocalError as e:
            print("update_linker_script() could not find codecave size. Ensure you have put a size for your codecave.")
        except Exception as e:
            print("update_linker_script() error", e)
 
def on_optimization_level_select(event=0):
    global g_optimization_level
    
    g_optimization_level = str(optimization_level_combobox.get())
    
    # To Reset Compile Strings
    on_platform_select()
        
def update_codecaves_hooks_patches_config_file():
    with open(f"{g_current_project_folder}/.config/codecaves.txt", "w") as codecaves_file:
        codecaves_file.write("Codecaves:\n")
        codecaves_file.write(str(g_code_caves))
            
    with open(f"{g_current_project_folder}/.config/hooks.txt", "w") as hook_file:
        hook_file.write("hooks:\n")
        hook_file.write(str(g_hooks))
    try:
        if g_patches != []:
            with open(f"{g_current_project_folder}/.config/patches.txt", "w") as patch_file:
                patch_file.write("patches:\n")
                patch_file.write(str(g_patches))
    except Exception as e:
        #print(f"No binary patches, ignoring.\t {e}")
        print(e)
    
def check_has_picked_exe():
    global g_shouldShowTabs
    global g_shouldShowPlatforms
    
    #Only run once for first project selected
    if g_shouldShowTabs == False and g_current_project_game_exe_full_dir != "":
        tab_control.add(codecave_tab, text='In-Game Codecaves')
        tab_control.add(hooks_tab, text='ASM Hooks')
        tab_control.add(compile_tab, text='Compile')
        
        # Create a "Text Editor" menu and text editor options to it
        other_menu = tk.Menu(menubar)
        menubar.add_cascade(label="Text Editor", menu=other_menu)
        other_menu.add_command(label="Open Project in VSCode", command=SetupVSCodeProject)
        file_menu.add_separator()
        other_menu.add_command(label="Open Project in Sublime", command=SetupSublimeProject)    
        file_menu.add_separator()
        other_menu.add_command(label="Open Project in Notepad++", command=SetupNotepadProject)
        
        # # Create a "Themes" menu and theme options to it
        # themes = tk.Menu(menubar)
        # menubar.add_cascade(label="Themes", menu=themes)
        # themes.add_command(label="Forest Dark", command=change_theme_forest_dark)
        # file_menu.add_separator()
        # themes.add_command(label="Azure Dark", command=change_theme_azure_dark)
        # file_menu.add_separator()
        # themes.add_command(label="Forest Light", command=change_theme_forest_light)
        # file_menu.add_separator()
        # themes.add_command(label="Azure Light", command=change_theme_azure_light)
        
        g_shouldShowTabs = True

def check_has_selected_first_project():
    global g_shouldShowPlatforms
     
    if g_shouldShowPlatforms == False:
        select_platform_label = tk.Label(main_tab, text="Select Project Platform", font=("Segoe UI", 10))
        select_platform_label.place(x=300, y=68)
        platform_combobox.place(x=300, y=93)
        g_shouldShowPlatforms = True

def project_switched():
    global g_shouldShowTabs
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    global g_current_project_selected_platform
    global g_current_project_disk_offset
    global inject_exe_button
    global inject_emu_button
    global platform_combobox
    global open_exe_button
    global choose_exe_label
    global build_iso_button
    global build_exe_button
    global g_current_project_game_disk
    global g_current_project_game_disk_full_dir
    global g_current_project_ram_watch_name
    global current_project_label
    global bizhawk_ramwatch_checkbox
    global bizhawk_ramwatch_checkbox_state
    global cheat_engine_ramwatch_checkbox
    global cheat_engine_ramwatch_checkbox_state
    global g_current_project_ram_watch_full_dir
    global game_cover_image
    global game_cover_image_label
    global bizhawk_ramwatch_label
        
    # For every re-selection/creation
    # Clear textbox entries
    codecave_name_entry.delete(0, tk.END)
    hook_name_entry.delete(0, tk.END)
    in_game_memory_entry.delete(0, tk.END)
    in_game_memory_entry_hooks.delete(0, tk.END)
    disk_exe_entry.delete(0, tk.END)
    disk_exe_entry_hooks.delete(0, tk.END)
    c_files_entry.delete(0, tk.END)
    asm_files_entry.delete(0, tk.END)
    patch_files_entry.delete(0, tk.END)
    
    #Hide build/inject options
    if inject_exe_button:
        inject_exe_button.place_forget()
    if inject_emu_button:   
        inject_emu_button.place_forget()
    if emulators_combobox:
        emulators_combobox.place_forget()
    if inject_emulator_label:
        inject_emulator_label.place_forget()
    if open_exe_button:
        open_exe_button.place_forget()
    if choose_exe_label:
        choose_exe_label.place_forget()
    if inject_emulator_label:
        choose_exe_label.place_forget()
    if build_iso_button:
        build_iso_button.pack_forget()
    if build_exe_button:
        build_exe_button.pack_forget()
    if change_exe_button:
        change_exe_button.place_forget()
    if create_ps2_code_button:
        create_ps2_code_button.place_forget()
    if create_cheat_code_label:
        create_cheat_code_label.place_forget()
    if bizhawk_ramwatch_checkbox:
        bizhawk_ramwatch_checkbox.place_forget()
    if cheat_engine_ramwatch_checkbox:
        cheat_engine_ramwatch_checkbox.place_forget()
    if game_cover_image:
        game_cover_image = None
    if game_cover_image_label:
        game_cover_image_label.place_forget()
    if current_project_label:
        current_project_label.place_forget()
    if bizhawk_ramwatch_label:
        bizhawk_ramwatch_label.place_forget()


    bizhawk_ramwatch_checkbox_state.set(0)
    cheat_engine_ramwatch_checkbox_state.set(0)
        
    #Check for config.txt and load
    try:
        with open(f"{g_current_project_folder}/.config/config.txt", "r") as config_file:
            g_current_project_game_exe = config_file.readline()
            g_current_project_game_exe_full_dir = g_current_project_game_exe.split("\n")[0] # Remove newline
            try:
                g_current_project_selected_platform = config_file.readline().split()[0]
                g_current_project_game_disk_full_dir = config_file.readline().split("\n")[0] # Remove newline
                g_current_project_ram_watch_full_dir = config_file.readline().split("\n")[0]
                g_current_project_game_disk = g_current_project_game_disk_full_dir.split("/")[-1]
                g_current_project_ram_watch_name =g_current_project_ram_watch_full_dir.split("/")[-1]
            except:
                print("No platform saved in config yet!")
            g_current_project_game_exe_name = g_current_project_game_exe.split("/")[-1].split("\n")[0] # spliting based on /, and getting last index with -1 to get only name of file, and getting rid of \n at end
            print("Project Config Loaded successfully!")
            selected_game_label = ttk.Label(main_tab, text='Game Executable:\n' + g_current_project_game_exe_name, font=("GENIUNE", 15))
            selected_game_label.place(x=300, y=135)

            
    #No config file, set defaults        
    except FileNotFoundError:
        print("No config file found!")
        g_current_project_game_exe = None
        g_current_project_game_exe_name = ""
        g_current_project_game_exe_full_dir = ""
        g_current_project_game_disk = ""
        g_current_project_game_disk_full_dir = ""
        g_current_project_selected_platform = ""
        g_current_project_ram_watch_full_dir = ""
        g_current_project_ram_watch_name = ""
        bizhawk_ramwatch_checkbox_state.set(0)
        cheat_engine_ramwatch_checkbox_state.set(0)
        
        selected_game_label = ttk.Label(main_tab, text='Game Executable:\n' + "None Selected", font=("GENIUNE", 15))
        selected_game_label.place(x=300, y=135)
        current_project_label = ttk.Label(main_tab, text='Current Project:\n' + "None Selected", font=("GENIUNE", 20))
        current_project_label.place(x=300, y=5)
        
    # Add Current Project Text Label
    current_project_label = ttk.Label(main_tab, text='Current Project:\n' + g_current_project_name + "", font=("GENIUNE", 20))
    current_project_label.place(x=300, y=5)
    
    # Add Ram watch integration button
    if g_current_project_selected_platform == "PS1" or g_current_project_selected_platform == "Gamecube":
        bizhawk_ramwatch_checkbox = ttk.Checkbutton(main_tab, text="Automatically Integrate Bizhawk Ram Watch", variable=bizhawk_ramwatch_checkbox_state, command=OpenBizhawkRamWatch)
        bizhawk_ramwatch_checkbox.place(x=295, y=420)
        bizhawk_ramwatch_label = tk.Label(main_tab, text=g_current_project_ram_watch_name)
        bizhawk_ramwatch_label.place(x=295, y=446)
        
    if g_current_project_selected_platform == "PS2":
        cheat_engine_ramwatch_checkbox = ttk.Checkbutton(main_tab, text="Automatically Integrate Cheat Engine Table", variable=cheat_engine_ramwatch_checkbox_state, command=OpenCheatEngineRamWatch)
        cheat_engine_ramwatch_checkbox.place(x=295, y=420)
        bizhawk_ramwatch_label = tk.Label(main_tab, text=g_current_project_ram_watch_name)
        bizhawk_ramwatch_label.place(x=295, y=446)
        
    if g_current_project_game_exe_full_dir != "":
        RequestGameBoxartImage()
    # Add Game Cover Image
    try:
        if os.path.isfile(g_current_project_folder + '/.config/game.jpg') and not os.path.isfile(g_current_project_folder + '/.config/game.png'):
            # Load image from disk.
            image_jpg = Image.open(g_current_project_folder + '/.config/game.jpg').resize((200, 200))
            image_jpg.save(g_current_project_folder + '/.config/game.png')
        
        if os.path.isfile(g_current_project_folder + '/.config/game.png'): 
            game_cover_image = tk.PhotoImage(file=g_current_project_folder + '/.config/game.png')
            game_cover_image_label = tk.Label(main_tab, text="test", image=game_cover_image)
            game_cover_image_label.place(x=300, y=215)
    except Exception as e:
        print({e})
        
    
    if platform_combobox:
        platform_combobox.set(g_current_project_selected_platform)
    
    if ".wch" in g_current_project_ram_watch_full_dir.lower():
        if bizhawk_ramwatch_checkbox:
            bizhawk_ramwatch_checkbox_state.set(1)
            
    if ".ct" in g_current_project_ram_watch_full_dir.lower():
        if cheat_engine_ramwatch_checkbox:
            cheat_engine_ramwatch_checkbox_state.set(1)
            
    elif g_current_project_ram_watch_full_dir == "":
        if bizhawk_ramwatch_checkbox:
            bizhawk_ramwatch_checkbox_state.set(0)
        if cheat_engine_ramwatch_checkbox:
            cheat_engine_ramwatch_checkbox_state.set(0)
    
    check_has_selected_first_project()    
    check_has_picked_exe()
             
def create_project():
    global g_current_project_name
    global g_current_project_feature_mode
    global g_current_project_folder
    global g_code_caves
    global g_hooks
    global g_patches
    
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
    
    #Create Main Project Folder
    try:
        os.makedirs(g_current_project_folder)
    except Exception as e:
        print(e)
        messagebox.showerror("Error", "Invalid Project Name")
        return
    
    project_switched()
    print("Currently Selected Project is now: "+ g_current_project_name)
    
    # Create default project files and directories
    os.makedirs(f"{g_current_project_folder}/.config")
    with open(f"{g_current_project_folder}/.config/codecaves.txt", "w") as codecaves_file:
        codecaves_file.write("")
        
    os.makedirs(f"{g_current_project_folder}/.config/symbols")
    with open(f"{g_current_project_folder}/.config/symbols/symbols.txt", "w") as symbols_file:
        symbols_file.write("/* This is where you would put your in game global variables you've found from a ram search/reverse engineering */\ngame_symbol = 0x80001234;\n")
    with open(f"{g_current_project_folder}/.config/symbols/function_symbols.txt", "w") as symbols_file:
        symbols_file.write("/* This is where you would put your in game functions you've found through reverse engineering */\nGameFunction = 0x80005678;\n")
    
    with open(f"{g_current_project_folder}/.config/hooks.txt", "w") as codecaves_file:
        codecaves_file.write("")

    os.makedirs(f"{g_current_project_folder}/src")
    with open(f"{g_current_project_folder}/src/main.c", "w") as main_file:
        main_file.write("#include <custom_types.h>\n#include <symbols.h>\n\nvoid CustomFunction(void) {\n    // Your code here\n\n    return;\n}\n")

    os.makedirs(f"{g_current_project_folder}/asm")
    with open(f"{g_current_project_folder}/asm/main_hook.s", "w") as main_file:
        main_file.write("# Enter jump/call to hook here. EX:\nj CustomFunction\n\n#Other Examples:\n#jal CustomFunction\n\n#b CustomFunction\n#bal CustomFunction\n")

    os.makedirs(f"{g_current_project_folder}/include")
    with open(f"{g_current_project_folder}/include/symbols.h", "w") as symbols_h:
        symbols_h.write("#ifndef SYMBOLS_H\n#define SYMBOLS_H\n#include <custom_types.h>\n\n//You can define in game variables & functions like so:\n//You MUST put a comment with the address at the end:\n\n//In Game Variables:\nin_game int player_lives; //0x80001234\n\n//In Game Functions:\nin_game void InGameFunction(int arg1, char* arg2); //0x80005678\n\n#endif //SYMBOLS_H\n")
    with open(f"{g_current_project_folder}/include/custom_types.h", "w") as symbols_h:
        symbols_h.write("#ifndef CUSTOM_TYPES_H\n#define CUSTOM_TYPES_H\n\n#include <stdbool.h>\n#include <stddef.h>\n\ntypedef unsigned char           u8, uint8_t, byte, uchar, undefined1;\ntypedef signed char             s8, int8_t;\ntypedef unsigned short int      u16, uint16_t, ushort, undefiend2;\ntypedef signed short int        s16, int16_t;\ntypedef unsigned int            u32, uint32_t, uint, undefined4;\ntypedef signed int              s32, int32_t;\n\n#define in_game                 extern \n\n#endif //CUSTOM_TYPES_H\n")
    
    os.makedirs(f"{g_current_project_folder}/.config/output")
    os.makedirs(f"{g_current_project_folder}/.config/output/object_files")
    os.makedirs(f"{g_current_project_folder}/.config/output/elf_files")
    os.makedirs(f"{g_current_project_folder}/.config/output/final_bins")
    os.makedirs(f"{g_current_project_folder}/.config/output/memory_map")
    
    with open(f"{g_current_project_folder}/.config/linker_script.ld", "w") as script_file:
        script_file.write("INPUT(.config/symbols/symbols.txt)\nINPUT(.config/symbols/function_symbols.txt)\n\nMEMORY\n{\n    /* RAM locations where we'll inject the code for our replacement functions */\n\n}\n\nSECTIONS\n{\n    /* Custom section for all other code */\n    .custom_section : \n    {\n        main.o(.text)\n        *(.rodata)\n        *(.data)\n        *(.bss)\n    } > freeregion1\n\n    /* Custom section for our hook code */\n    .custom_hook :\n    {\n        main_hook.o(.text)\n    } > hook1\n\n    /DISCARD/ :\n    {\n        *(.comment)\n        *(.pdr)\n        *(.mdebug)\n        *(.reginfo)\n        *(.MIPS.abiflags)\n        *(.eh_frame)\n        *(.gnu.attributes)\n    }\n}")
    
    #Clearing GUI & Setting defaults
    g_code_caves = []
    codecaves_listbox.delete(0, tk.END)
    g_hooks = []
    hooks_listbox.delete(0, tk.END)
    g_patches = []
    patches_listbox.delete(0, tk.END)
    
    #Add project to list, and clear entry
    g_projects.append(project_name)
    #project_listbox.insert(tk.END, project_name)
    project_name_entry.delete(0, tk.END)

    
    #Get all names of projects in project folder and fill select box to populate from new project
    project_listbox.delete(0, tk.END) # Clear listbox
    project_folder_names = [folder for folder in os.listdir(PROJECTS_FOLDER_PATH) if os.path.isdir(os.path.join(PROJECTS_FOLDER_PATH, folder))]
    
    for project in project_folder_names:
        project_listbox.insert(tk.END, project)
        print("Project Names: " + project)


    #Insert Default Version
    #project_versions_listbox.insert(tk.END, "MainVersion")

    update_codecaves_hooks_patches_config_file()
    # Show a "Project added" dialog
    messagebox.showinfo("Success", "Project created successfully.")

def select_project(event=0):
    global g_current_project_name
    global g_code_caves
    global g_hooks
    global g_patches
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
    
    g_code_caves = []   # Clearing previous code cave
    
    #Check for a codecaves.txt file and fill the python list with the data in it using an ast evaluation
    if os.path.exists(f"projects/" + selected_project + "/.config/codecaves.txt"):
        codecaves_listbox.delete(0, tk.END)
        with open(f"projects/" + selected_project + "/.config/codecaves.txt", "r") as codecaves_file:
            codecaves_file.readline() # Skip the first line
            file_string = codecaves_file.read()
            if file_string:
                ast_file_string = ast.literal_eval(file_string)
                g_code_caves = ast_file_string
                #print("Code Caves updated to: " + str(g_code_caves))
                # Show a "Project added" dialog
                i = 0
                for cave in g_code_caves:
                    codecaves_listbox.insert(tk.END, cave[0])
                    i += i
    
    g_hooks = []   # Clearing previous hooks
    
    #Check for a hooks.txt file and fill the python list with the data in it using an ast evaluation    
    if os.path.exists(f"projects/" + selected_project + "/.config/hooks.txt"):
        hooks_listbox.delete(0, tk.END)
        with open(f"projects/" + selected_project + "/.config/hooks.txt", "r") as hook_file:
            hook_file.readline() # Skip the first line
            file_string = hook_file.read()
            ast_file_string = ast.literal_eval(file_string)
            g_hooks = ast_file_string
            #print("Hooks updated to: " + str(g_hooks))
        # Show a "Project added" dialog
        i = 0
        for hook in g_hooks:
            hooks_listbox.insert(tk.END, hook[0])
            i += i
        
        
    g_patches = []   # Clearing previous patches
    patches_listbox.delete(0, tk.END)
    try:    
        
        #Check for a patches.txt file and fill the python list with the data in it using an ast evaluation    
        if os.path.exists(f"projects/" + selected_project + "/.config/patches.txt"):
            with open(f"projects/" + selected_project + "/.config/patches.txt", "r") as patch_file:
                patch_file.readline() # Skip the first line
                file_string = patch_file.read()
                ast_file_string = ast.literal_eval(file_string)
                g_patches = ast_file_string
                #print("Patches updated to: " + str(g_patches))
            i = 0
            for patch in g_patches:
                patches_listbox.insert(tk.END, patch[0])
                i += i
    except Exception as e:
        #print("No binary patches, ignoring")
        print(e)
            
            
            
    #Update Platform Settings
    on_platform_select()
    update_linker_script()
    
def clear_project_settings():
    global g_current_project_game_exe
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_disk
    global g_current_project_game_disk_full_dir
    global g_current_project_selected_platform
    global selected_game_label
    global current_project_label
    global g_current_project_ram_watch_full_dir
    global g_current_project_ram_watch_name
    
    g_current_project_game_exe = None
    g_current_project_game_exe_name = ""
    g_current_project_game_exe_full_dir = ""
    g_current_project_game_disk = ""
    g_current_project_game_disk_full_dir = ""
    g_current_project_selected_platform = ""
    g_current_project_ram_watch_full_dir = ""
    g_current_project_ram_watch_name = ""
    selected_game_label = ttk.Label(main_tab, text='Game Executable:\n' + "None Selected", font=("GENIUNE", 15))
    selected_game_label.place(x=300, y=135)
    current_project_label = ttk.Label(main_tab, text='Current Project:\n' + "None Selected", font=("GENIUNE", 20))
    current_project_label.place(x=300, y=5)
            
def remove_project_confirm():
    if project_listbox.curselection():
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete " + str(project_listbox.get(project_listbox.curselection())) + " project?") == True:
            remove_project()
    else:
        messagebox.showerror("Error", "Must select project to delete")
    
#COME BACK TO THIS TO MAKE PROJECT ALWAYS UNSELECT AFTER DELETING    
def remove_project():
    global g_current_project_folder
    global g_code_caves
    global g_hooks
    global g_patches
    
    selected_project_index = project_listbox.curselection()
    selected_project_name = project_listbox.get(selected_project_index)
    
    project_listbox.delete(selected_project_index)

    project_dir_to_delete = "projects/" + selected_project_name

    try:
        MoveToRecycleBin(project_dir_to_delete)
        messagebox.showinfo("Success", f"Directory '{project_dir_to_delete}' and its contents have been moved to the recycle bin.")
        print(f"Directory '{project_dir_to_delete}' and its contents have been moved to the recycle bin.")
    except FileNotFoundError:
        messagebox.showerror("Error", f"Directory '{project_dir_to_delete}' does not exist.")
        print(f"Directory '{project_dir_to_delete}' does not exist.")
    except PermissionError:
        messagebox.showerror("Error," f"Permission denied. Unable to delete '{project_dir_to_delete}'.")
        print(f"Permission denied. Unable to delete '{project_dir_to_delete}'.")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
        print(f"An error occurred: {e}")
        
    g_code_caves = []
    g_hooks = []
    g_patches = []
        
    if selected_project_name == g_current_project_name:
        clear_project_settings()
        #project_switched()
        tab_control.forget(codecave_tab)
        tab_control.forget(hooks_tab)
        tab_control.forget(compile_tab)
    
   
def add_codecave():
    global g_current_project_folder
    global g_current_project_name
    
    does_already_exist = False
    index_where_exists = 0
    
    cave_name = codecave_name_entry.get()
    in_game_memory = in_game_memory_entry.get()
    disk_memory = disk_exe_entry.get()
    disk_offset = global_offset_entry.get()
    cave_size = codecave_size_entry.get()
    
    #Check if name already exists, to only update the codecave, not create a new one
    for i, cave in enumerate(g_code_caves):
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

    if not cave_name or not in_game_memory or not disk_memory or not c_files or not cave_size:
        messagebox.showerror("Error", "Please fill in all fields.")
        return
    
    
    if does_already_exist == False:
        g_code_caves.append((cave_name, in_game_memory, disk_memory, c_files, disk_offset, cave_size))
        codecaves_listbox.insert(tk.END, cave_name)
    else:
        print("Codecave already exists, replacing this index: ", index_where_exists)
        g_code_caves[index_where_exists] = (cave_name, in_game_memory, disk_memory, c_files, disk_offset, cave_size)
    
    #Update project_folder for safetey, and then create a config folder if not already existing
    g_current_project_folder = f"projects/" + g_current_project_name   
    try:
        os.makedirs(f"{g_current_project_folder}/.config")
    except OSError:
        print("Config directory already exists")
           
    codecave_name_entry.delete(0, tk.END)
    in_game_memory_entry.delete(0, tk.END)
    disk_exe_entry.delete(0, tk.END)
    c_files_entry.delete(0, tk.END)
    codecave_size_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_patches_config_file()

def remove_codecave(event=0):
    global g_current_project_folder
    selected_codecave_index = codecaves_listbox.curselection()
    if selected_codecave_index:
        codecaves_listbox.delete(selected_codecave_index)
        del g_code_caves[selected_codecave_index[0]]
        codecave_name_entry.delete(0, tk.END)
        in_game_memory_entry.delete(0, tk.END)
        disk_exe_entry.delete(0, tk.END)
        c_files_entry.delete(0, tk.END)
        global_offset_entry.delete(0, tk.END)
        codecave_size_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_patches_config_file()
        
def select_codecave(event):
    try:
        selected_codecave_index = codecaves_listbox.curselection()
        if selected_codecave_index:
            selected_codecave = g_code_caves[selected_codecave_index[0]]
            codecave_name_entry.delete(0, tk.END)
            in_game_memory_entry.delete(0, tk.END)
            disk_exe_entry.delete(0, tk.END)
            c_files_entry.delete(0, tk.END)
            codecave_size_entry.delete(0, tk.END)

            codecave_name_entry.insert(0, selected_codecave[0])
            in_game_memory_entry.insert(0, selected_codecave[1])
            disk_exe_entry.insert(0, selected_codecave[2])
            c_files_entry.insert(0, ", ".join(selected_codecave[3]))
            global_offset_entry.config(state="active")
            global_offset_entry.delete(0, tk.END)
            global_offset_entry.insert(0, selected_codecave[4])
            global_offset_entry.config(state="disabled")
            codecave_size_entry.insert(0, selected_codecave[5])
            
            update_linker_script()
    except Exception as e:
        print("select_codecave() error: ", e)

def add_hook():
    global g_current_project_folder
    global g_current_project_name
    
    does_already_exist = False
    index_where_exists = 0
    
    hook_name = hook_name_entry.get()
    in_game_hook_memory = in_game_memory_entry_hooks.get()
    disk_hook_memory = disk_exe_entry_hooks.get()
    disk_offset = global_offset_entry_hooks.get()
    
    #Check if name already exists, to only update the hook, not create a new one
    for i, hook in enumerate(g_hooks):
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
        g_hooks.append((hook_name, in_game_hook_memory, disk_hook_memory, asm_files, disk_offset))
        hooks_listbox.insert(tk.END, hook_name)
    else:
        g_hooks[index_where_exists] = (hook_name, in_game_hook_memory, disk_hook_memory, asm_files, disk_offset)
    
    
    #Update project_folder for safetey, and then create a config folder if not already existing
    g_current_project_folder = f"projects/" + g_current_project_name   
    try:
        os.makedirs(f"{g_current_project_folder}/.config")
    except OSError:
        print("Config directory already exists")
        
           
    hook_name_entry.delete(0, tk.END)
    in_game_memory_entry_hooks.delete(0, tk.END)
    disk_exe_entry_hooks.delete(0, tk.END)
    asm_files_entry.delete(0, tk.END)
    global_offset_entry_hooks.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_patches_config_file()

def remove_hook(event=0):
    global g_current_project_folder
    
    selected_hook_index = hooks_listbox.curselection()
    if selected_hook_index:
        hooks_listbox.delete(selected_hook_index)
        del g_hooks[selected_hook_index[0]]
        hook_name_entry.delete(0, tk.END)
        in_game_memory_entry_hooks.delete(0, tk.END)
        disk_exe_entry_hooks.delete(0, tk.END)
        asm_files_entry.delete(0, tk.END)
        global_offset_entry_hooks.delete(0, tk.END)
        
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_patches_config_file()
        
def select_hook(event):
    selected_hook_index = hooks_listbox.curselection()
    if selected_hook_index:
        selected_hook = g_hooks[selected_hook_index[0]]
        hook_name_entry.delete(0, tk.END)
        in_game_memory_entry_hooks.delete(0, tk.END)
        disk_exe_entry_hooks.delete(0, tk.END)
        asm_files_entry.delete(0, tk.END)

        hook_name_entry.insert(0, selected_hook[0])
        in_game_memory_entry_hooks.insert(0, selected_hook[1])
        disk_exe_entry_hooks.insert(0, selected_hook[2])
        asm_files_entry.insert(0, ", ".join(selected_hook[3]))
        global_offset_entry_hooks.config(state="active")
        global_offset_entry_hooks.delete(0, tk.END)
        global_offset_entry_hooks.insert(0, selected_hook[4])
        global_offset_entry_hooks.config(state="disabled")
        
        update_linker_script()
        update_codecaves_hooks_patches_config_file()

def add_patch():
    global g_current_project_folder
    global g_current_project_name
    
    does_already_exist = False
    index_where_exists = 0
    
    patch_name = patch_name_entry.get()
    in_game_patch_memory = in_game_memory_entry_patches.get()
    disk_patch_memory = disk_exe_entry_patches.get()
    
    #Check if name already exists, to only update the patch, not create a new one
    for i, patch in enumerate(g_patches):
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
        g_patches.append((patch_name, in_game_patch_memory, disk_patch_memory, patch_files))
        patches_listbox.insert(tk.END, patch_name)
    else:
        g_patches[index_where_exists] = (patch_name, in_game_patch_memory, disk_patch_memory, patch_files)
    
    #Update project_folder for safetey, and then create a config folder if not already existing
    g_current_project_folder = f"projects/" + g_current_project_name   
    try:
        os.makedirs(f"{g_current_project_folder}/.config")
    except OSError:
        print("Config directory already exists")
           
    patch_name_entry.delete(0, tk.END)
    in_game_memory_entry_patches.delete(0, tk.END)
    disk_exe_entry_patches.delete(0, tk.END)
    patch_files_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_patches_config_file()

def remove_patch(event=0):
    global g_current_project_folder
    
    selected_patch_index = patches_listbox.curselection()
    if selected_patch_index:
        patches_listbox.delete(selected_patch_index)
        del g_patches[selected_patch_index[0]]
        patch_name_entry.delete(0, tk.END)
        in_game_memory_entry_patches.delete(0, tk.END)
        disk_exe_entry_patches.delete(0, tk.END)
        patch_files_entry.delete(0, tk.END)
    
    on_platform_select() #Reset Compile Stuff
    update_linker_script()
    update_codecaves_hooks_patches_config_file()
    
def select_patch(event):
    selected_patch_index = patches_listbox.curselection()
    if selected_patch_index:
        selected_patch = g_patches[selected_patch_index[0]]
        patch_name_entry.delete(0, tk.END)
        in_game_memory_entry_patches.delete(0, tk.END)
        disk_exe_entry_patches.delete(0, tk.END)
        patch_files_entry.delete(0, tk.END)

        patch_name_entry.insert(0, selected_patch[0])
        in_game_memory_entry_patches.insert(0, selected_patch[1])
        disk_exe_entry_patches.insert(0, selected_patch[2])
        patch_files_entry.insert(0, ", ".join(selected_patch[3]))
        update_linker_script()
        update_codecaves_hooks_patches_config_file()
   
def reset_auto_hook_buttons():
    global auto_hook_button    
    global auto_hook_ps2_button
    global auto_cave_button
    
    auto_cave_button.place_forget()

    #check_if_no_hooks
    if g_hooks == [] and g_current_project_selected_platform == "PS1":
        auto_hook_button.config(text=f'Try to automatically find PS1 hook', command=auto_find_hook_in_ps1_game, font=("asfasf", 12), state="active")
        auto_hook_button.place(x=2, y=2)  
    elif g_hooks == [] and g_current_project_selected_platform == "PS2":
        auto_hook_button.config(text=f'Try to automatically find PS2 hook', command=auto_find_hook_in_ps2_game, font=("asfasf", 12), state="active")
        auto_hook_button.place(x=2, y=2)  
    elif g_hooks == [] and g_current_project_selected_platform == "Gamecube":
        auto_hook_button.config(text=f'Try to automatically find Gamecube hook', command=auto_find_hook_in_gamecube_game, font=("asfasf", 12), state="active")
        auto_hook_button.place(x=2, y=2)  
    elif g_hooks == [] and g_current_project_selected_platform == "Wii":
        auto_hook_button.config(text=f'Try to automatically find Wii hook', command=auto_find_hook_in_wii_game, font=("asfasf", 12), state="active")
        auto_hook_button.place(x=2, y=2)  
    elif len(g_hooks) != 0 or g_hooks != []:
        if auto_hook_button:
            auto_hook_button.config(text="", command=None, state="disabled", font=("asfasf", 1))
        #print("This is running. Makes no sense")
        
    #check_if_no_caves
    if g_code_caves == [] and g_current_project_selected_platform == "PS1":
        auto_cave_button.config(text=f'Automatically Use PS1 Header', command=auto_place_ps1_header, font=("asfasf", 12), state="active")
        auto_cave_button.place(x=2, y=2)  
    elif len(g_code_caves) != 0 or g_code_caves != []:
        if auto_cave_button:
            auto_cave_button.config(text="", command=None, state="disabled", font=("asfasf", 1))
        #print("This is running. Makes no sense")
                           
def on_platform_select(event=0):
    global g_current_project_selected_platform
    global g_src_files
    global g_header_files
    global g_asm_files
    global g_obj_files
    global g_patch_files
    global g_platform_gcc_strings
    global g_platform_linker_strings
    global g_platform_objcopy_strings
    global inject_exe_button
    global inject_emu_button
    global open_exe_button
    global emulators_combobox
    global inject_worse_emu_button
    global g_selected_emu
    global choose_exe_label
    global g_current_project_game_disk
    global g_current_project_game_disk_full_dir
    global auto_hook_button
    global auto_hook_ps2_button
    global create_ps2_code_button
    global g_patches
    global g_current_project_ram_watch_full_dir
    global g_current_project_ram_watch_name
    
    #Hide old build/inject options
    if inject_exe_button:
        inject_exe_button.place_forget()
    if inject_emu_button != None:   
        inject_emu_button.place_forget()
    if emulators_combobox != None:
        emulators_combobox.place_forget()
    if open_exe_button != None:
        open_exe_button.place_forget()
    if inject_emulator_label != None:
        inject_emulator_label.place_forget()
    if choose_exe_label != None:
        choose_exe_label.place_forget()   
    if inject_emulator_label != None:
        choose_exe_label.place_forget()
    if build_iso_button:
        build_iso_button.pack_forget()
    if change_exe_button:
        change_exe_button.place_forget()
        change_exe_button.pack_forget()
    if open_exe_button:
        open_exe_button.place_forget()
    if create_ps2_code_button:
        create_ps2_code_button.place_forget()
    if create_cheat_code_label:
        create_cheat_code_label.place_forget()

    g_src_files = ""
    g_header_files = ""
    g_asm_files = ""
    g_obj_files = ""
        
    #Get the current platform selection from the combo-box
    if platform_combobox:
        g_current_project_selected_platform = platform_combobox.get()
    #Update Main Buttons
    
    if g_current_project_selected_platform == "PS1" and g_current_project_feature_mode == "Advanced":
        open_exe_button = tk.Button(main_tab, text="Choose PS1 Executable (SCUS, etc)", command=open_exe_file)
        open_exe_button.place(x=300, y=185)
    elif g_current_project_selected_platform == "PS1" and g_current_project_feature_mode == "Normal":
        open_exe_button = tk.Button(main_tab, text="Choose PS1 .bin file", command=open_exe_file)
        open_exe_button.place(x=300, y=185)
    elif g_current_project_selected_platform == "PS2" and g_current_project_feature_mode == "Advanced":
        open_exe_button = tk.Button(main_tab, text="Choose PS2 Executable (SLUS, etc)", command=open_exe_file)
        open_exe_button.place(x=300, y=185)
    elif g_current_project_selected_platform == "PS2" and g_current_project_feature_mode == "Normal":
        open_exe_button = tk.Button(main_tab, text="Choose PS2 .iso file", command=open_exe_file)
        open_exe_button.place(x=300, y=185)
    elif g_current_project_selected_platform == "Gamecube" and g_current_project_feature_mode == "Advanced":
        open_exe_button = tk.Button(main_tab, text="Choose Gamecube Executable (Start.dol)", command=open_exe_file)
        open_exe_button.place(x=300, y=185)
    elif g_current_project_selected_platform == "Gamecube" and g_current_project_feature_mode == "Normal":
        open_exe_button = tk.Button(main_tab, text="Choose Gamecube .iso .ciso or .gcm file", command=open_exe_file)
        open_exe_button.place(x=300, y=185)
    elif g_current_project_selected_platform == "Wii":
        open_exe_button = tk.Button(main_tab, text="Choose Wii Executable (main.dol)", command=open_exe_file)
        open_exe_button.place(x=300, y=185)
    else:
        open_exe_button = tk.Button(main_tab, text="Choose executable", command=open_exe_file)
        open_exe_button.place(x=300, y=185)
    
    #Reset
    g_platform_gcc_strings = {"PS1": "..\\..\\prereq\\PS1mips\\bin\\mips-gcc ", "PS2": "..\\..\\prereq\\PS2ee\\bin\\ee-gcc ", "Gamecube": "..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc ", "Wii": "..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc ", "N64": "..\\..\\prereq\\N64mips/bin\\mips64-elf-gcc "}
    g_platform_linker_strings = {"PS1": "..\\..\\..\\..\\..\\prereq\\PS1mips\\bin\\mips-gcc " + g_universal_link_string, "PS2": "..\\..\\..\\..\\..\\prereq\\PS2ee\\bin\\ee-gcc " + g_universal_link_string, "Gamecube": "..\\..\\..\\..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc " + g_universal_link_string, "Wii": "..\\..\\..\\..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc " + g_universal_link_string, "N64": "..\\..\\..\\..\\..\\prereq\\N64mips\\bin\\mips64-elf-gcc " + g_universal_link_string}
    g_platform_objcopy_strings = {"PS1": "..\\..\\prereq\\PS1mips\\bin\\mips-objcopy " + g_universal_objcopy_string, "PS2": "..\\..\\prereq\\PS2ee\\bin\\ee-objcopy " + g_universal_objcopy_string, "Gamecube": "..\\..\\prereq\\devkitPPC\\bin\\ppc-objcopy " + g_universal_objcopy_string, "Wii": "..\\..\\prereq\\devkitPPC\\bin\\ppc-objcopy " + g_universal_objcopy_string, "N64": "..\\..\\prereq\\N64mips\\bin\\mips64-elf-objcopy " + g_universal_objcopy_string} 
    
    #Save to config     
    if g_current_project_selected_platform:
        try:
            with open(f"{g_current_project_folder}/.config/config.txt", "w+") as config_file:
                config_file.write(g_current_project_game_exe_full_dir + "\n")
                config_file.write(g_current_project_selected_platform + "\n")
                if g_current_project_game_disk_full_dir != "":
                    config_file.write(g_current_project_game_disk_full_dir + "\n")
                if g_current_project_ram_watch_full_dir != "":
                   config_file.write(g_current_project_ram_watch_full_dir + "\n")
                   
                print("Project Config saved.\n")
        except:
            print("No config file, new project?")
         
    # Get C files 
    for code_cave in g_code_caves:
        for c_file in code_cave[3]:
            g_src_files += "src/" + c_file + " "
            g_obj_files += c_file.split(".")[0] + ".o"  + " "
            
    # Get H files 
    header_files = os.listdir(f"{g_current_project_folder}/include/")
    for h_file in header_files:
            g_header_files += "include/" + h_file + " "
    
    #Get ASM Files        
    for hook in g_hooks:
        for asm_file in hook[3]:
            g_asm_files += "asm/" + asm_file + " "
            g_obj_files += asm_file.split(".")[0] + ".o"  + " "
               
    #Get Patch Files        
    for patch in g_patches:
        for patch_file in patch[3]:
            g_patch_files.append("patches/" + patch_file)
             
    #Update GCC/Linker Strings   
    for key in g_platform_gcc_strings:
        # Add src files to gcc strings
        g_platform_gcc_strings[key] += g_src_files + g_asm_files
        g_platform_linker_strings[key] += g_obj_files + "-o ../elf_files/MyMod.elf -nostartfiles" # ../ because of weird linker thing with directories? In Build I have to do chdir.
        
        if key == "PS1" or key == "PS2" or key == "N64":
            g_platform_gcc_strings[key] += f"-c -G0 -{g_optimization_level} -I include"
        if key == "Gamecube" or key == "Wii":
            g_platform_gcc_strings[key] += f"-c -{g_optimization_level} -I include"
    
    #Set compile button text
    if g_current_project_game_exe:
        name_of_exe = g_current_project_game_exe.split("/")[-1].split("\n")[0] # Funky way of getting rid of dir, and new line
    if inject_exe_button and g_current_project_game_exe:
        inject_exe_button.config(text=f"Create new patched {name_of_exe} copy")
                   
    reset_auto_hook_buttons()
        
    #Set gcc/linker text
    #gcc_label.config(text=f"GCC String for {g_current_project_selected_platform}:\n{g_platform_gcc_strings[g_current_project_selected_platform]}\n")
    #linker_label.config(text=f"Linker string for {g_current_project_selected_platform}:\n{g_platform_linker_strings[g_current_project_selected_platform]}\n", font=("GENIUNE", 8))

def on_feature_mode_selected(event=0):
    global g_current_project_feature_mode
    
    
    selected = current_project_feature_mode.get()
    g_current_project_feature_mode = selected
    print(f"Selected mode: {selected}")
    
    if g_current_project_feature_mode == "Advanced" and g_current_project_name != "":
        tab_control.add(patches_tab, text='Patches')
    elif g_current_project_feature_mode == "Normal" and g_current_project_name != "":
        if tab_control:
            try:
                tab_control.hide(patches_tab)
            except:
                pass
    
    #If project is loaded when user selected mode, then refresh buttons        
    if g_current_project_name != "":
        on_platform_select()

def replace_codecave_offset_text(event=0):
    global g_current_project_disk_offset
    status = is_global_offset_checkbox_checked.get()
    if status == 1:
        disk_memory_value = in_game_memory_entry.get()
        offset_value = global_offset_entry.get()
        if disk_memory_value and offset_value:
            try:
                disk_memory = int(disk_memory_value.removeprefix("0x").removeprefix("80"), base=16) + int(offset_value.removeprefix("0x"), base=16)
                disk_exe_entry.delete(0, tk.END)
                disk_exe_entry.insert(0, hex(disk_memory))
                g_current_project_disk_offset = offset_value
                
            except ValueError:
                print("Invalid values for in-game memory or offset, can't replace.")
        else:
            pass
            #global_offset_entry.config(state="disabled")
        
        update_codecaves_hooks_patches_config_file()
    
def replace_hook_offset_text(event=0):
    global g_current_project_disk_offset
    status = is_global_offset_checkbox_checked.get()
    if status == 1:
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
    
    update_codecaves_hooks_patches_config_file()
    
def replace_patches_offset_text(event=0):
    global g_current_project_disk_offset
    status = is_global_offset_checkbox_checked.get()
    if status == 1:
        disk_memory_value = in_game_memory_entry_patches.get()
        offset_value = global_offset_entry_patches.get()
        if disk_memory_value and offset_value:
            try:
                disk_memory = int(disk_memory_value.removeprefix("0x80"), base=16) + int(offset_value.removeprefix("0x"), base=16)
                disk_exe_entry_patches.delete(0, tk.END)
                disk_exe_entry_patches.insert(0, hex(disk_memory))
                g_current_project_disk_offset = offset_value
            except ValueError:
                print("Invalid values for in-game memory or offset.")
        else:
            pass
            #global_offset_entry.config(state="disabled")
    
    update_codecaves_hooks_patches_config_file()

def toggle_offset_text_state():
    status = is_global_offset_checkbox_checked.get()
    if status == 1:
        global_offset_entry.config(state="active")
        global_offset_entry_hooks.config(state="active")
        global_offset_entry_patches.config(state="active")
        load_disk_offset_hooks()
        replace_codecave_offset_text()
        replace_hook_offset_text()
        replace_patches_offset_text()
        #global_offset_update.config(state="active")
        #disk_exe_entry.delete(0, tk.END)
        #disk_exe_entry_hooks.delete(0, tk.END)
    else:
        global_offset_entry.config(state="disabled")
        global_offset_entry_hooks.config(state="disabled")
        global_offset_entry_patches.config(state="disabled")
        #global_offset_update.config(state="disabled")

    #Update values when checkbox ticked for quality of life   
    replace_codecave_offset_text()

def validate_no_space(P):
    
    if " " in P:
        return False
    return True          
   
def validate_hex_prefix(P):
    # Function to enforce a specific prefix
    prefix = "0x"  # Replace with your desired prefix
    if P != "" and not P.startswith(prefix):
        return False
    return True   
        
def ensure_hex_entries(event=0):
    try:
        if len(in_game_memory_entry.get()) >= 2:
            if in_game_memory_entry.get()[1].lower() != "x" and in_game_memory_entry.get()[2].lower() != "x":
                in_game_memory_entry.insert(0, "0x")
                
        if len(disk_exe_entry.get()) >= 2:
            if disk_exe_entry.get()[1].lower() != "x" and disk_exe_entry.get()[2].lower() != "x":
                disk_exe_entry.insert(0, "0x")
                
        if len(global_offset_entry.get()) >= 2:
            if global_offset_entry.get()[1].lower() != "x" and global_offset_entry.get()[2].lower() != "x":
                global_offset_entry.insert(0, "0x")

        if len(in_game_memory_entry_hooks.get()) >= 2:
            if in_game_memory_entry_hooks.get()[1].lower() != "x" and in_game_memory_entry_hooks.get()[2].lower() != "x":
                in_game_memory_entry_hooks.insert(0, "0x")
        
        if len(disk_exe_entry_hooks.get()) >= 2:
            if disk_exe_entry_hooks.get()[1].lower() != "x" and disk_exe_entry_hooks.get()[2].lower() != "x":
                disk_exe_entry_hooks.insert(0, "0x")
                
        if len(global_offset_entry_hooks.get()) >= 2:
            if global_offset_entry_hooks.get()[1].lower() != "x" and global_offset_entry_hooks.get()[2].lower() != "x":
                global_offset_entry_hooks.insert(0, "0x")
                
        if len(in_game_memory_entry_patches.get()) >= 2:
            if in_game_memory_entry_patches.get()[1].lower() != "x" and in_game_memory_entry_patches.get()[2].lower() != "x":
                in_game_memory_entry_patches.insert(0, "0x")
        
        if len(disk_exe_entry_patches.get()) >= 2:
            if disk_exe_entry_patches.get()[1].lower() != "x" and disk_exe_entry_patches.get()[2].lower() != "x":
                disk_exe_entry_patches.insert(0, "0x")
                
        if len(global_offset_entry_patches.get()) >= 2:
            if global_offset_entry_patches.get()[1].lower() != "x" and global_offset_entry_patches.get()[2].lower() != "x":
                global_offset_entry_patches.insert(0, "0x")
                
        if len(codecave_size_entry.get()) >= 2:
            if codecave_size_entry.get()[1].lower() != "x" and codecave_size_entry.get()[2].lower() != "x":
                codecave_size_entry.insert(0, "0x")
    except IndexError as e:
        pass
    except Exception as e:
        print(e)

def load_disk_offset_codecaves(event=0):
    selected_cave_index = codecaves_listbox.curselection()
    if selected_cave_index:
        selected_cave = g_code_caves[selected_cave_index[0]]
        global_offset_entry.delete(0, tk.END)
        global_offset_entry.insert(0, selected_cave[4])
        update_codecaves_hooks_patches_config_file()

def load_disk_offset_hooks(event=0):
    selected_hook_index = hooks_listbox.curselection()
    if selected_hook_index:
        selected_hook = g_hooks[selected_hook_index[0]]
        global_offset_entry_hooks.delete(0, tk.END)
        global_offset_entry_hooks.insert(0, selected_hook[4])
        update_codecaves_hooks_patches_config_file()
        
def load_disk_offset_patches(event=0):
    selected_patch_index = patches_listbox.curselection()
    if selected_patch_index:
        selected_hook = g_hooks[selected_patch_index[0]]
        global_offset_entry_patches.delete(0, tk.END)
        global_offset_entry_patches.insert(0, selected_hook[4])
        update_codecaves_hooks_patches_config_file()


#Themes
# def change_theme_forest_dark(event=0):
#     ttk.Style().theme_use('forest-dark')
# def change_theme_azure_dark(event=0):
#     root.tk.call("set_theme", "dark")
# def change_theme_forest_light(event=0):
#     ttk.Style().theme_use('forest-light')
# def change_theme_azure_light(event=0):
#     root.tk.call("set_theme", "light")

#! MAIN GUI
root = tk.Tk()
root.title("C/C++ Game Modding Utility")
root.geometry("800x600")
root.bind("<KeyRelease>", ensure_hex_entries)
root.iconbitmap("prereq/icon.ico")
root.resizable(False, False)
validate_no_space_cmd = root.register(validate_no_space)

#Themes
root.tk.call('source', 'prereq/theme/azure.tcl')
root.tk.call('source', 'prereq/theme/forest-light.tcl')
root.tk.call('source', 'prereq/theme/forest-dark.tcl')
ttk.Style().theme_use('forest-dark')

# Create tabs
tab_control = ttk.Notebook(root)
main_tab = ttk.Frame(tab_control)
codecave_tab = ttk.Frame(tab_control)
hooks_tab = ttk.Frame(tab_control)
patches_tab = ttk.Frame(tab_control)
compile_tab = ttk.Frame(tab_control)
# Bind the <<NotebookTabChanged>> event to the tab_changed function
tab_control.bind("<<NotebookTabChanged>>", run_every_tab_switch)

tab_control.add(main_tab, text='Project Setup')
tab_control.pack(expand=1, fill='both')

codecave_tab.bind("<FocusIn>", ensure_hex_entries)
hooks_tab.bind("<FocusIn>", ensure_hex_entries)

# Create a menu bar
menubar = tk.Menu(root)
root.config(menu=menubar)

# Create a "Extract" menu and add items to it
file_menu = tk.Menu(menubar)
menubar.add_cascade(label="Extract", menu=file_menu)
file_menu.add_command(label="Extract PS1 .bin file to folder", command=ExtractPS1Game)
file_menu.add_command(label="Extract PS2 .iso file to folder", command=ExtractPS2Game)
file_menu.add_command(label="Extract Gamecube .iso or .c.iso file to folder", command=ExtractGamecubeGame)
file_menu.add_command(label="Exit", command=root.quit)

#! Main Tab
current_project_label = None

#Feature Mode Combobox
feature_modes = ["Normal", "Advanced"]
current_project_feature_mode = tk.StringVar()
current_project_feature_mode.set("Normal")
project_feature_combobox = ttk.Combobox(root, textvariable=current_project_feature_mode, values=feature_modes)
project_feature_combobox.place(x=685, y=550)
project_feature_combobox.config(width=11)
project_feature_combobox.bind("<<ComboboxSelected>>", on_feature_mode_selected)

project_name_label = ttk.Label(main_tab, text='New Project Name:', font=("Trebuchet MS", 10))
project_name_label.place(x=10, y=10)
project_name_entry = ttk.Entry(main_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
project_name_entry.place(x=10, y=30)
create_project_button = tk.Button(main_tab, text='Create New Project', command=create_project)
select_project_button = tk.Button(main_tab, text='Select Existing Project', command=select_project)
create_project_button.place(x=10, y=70)
select_project_button.place(x=10, y=118)

platform_values = ["PS1", "PS2", "Gamecube", "Wii", "N64", "Other"]
platform_combobox = ttk.Combobox(main_tab, values=platform_values, font=("Segoe UI", 11))
platform_combobox.bind("<<ComboboxSelected>>", on_platform_select)

# Create a listbox to display existing projects
project_listbox = tk.Listbox(main_tab, selectmode=tk.SINGLE, height=20, width=30)
project_listbox.place(x=10, y=150)
project_listbox.bind("<KeyPress-Return>", select_project)
project_listbox.bind("<KeyPress-space>", select_project)
project_listbox.bind("<Double-Button-1>", select_project)

#Get all names of projects in project folder and fill select box
project_folder_names = [folder for folder in os.listdir(PROJECTS_FOLDER_PATH) if os.path.isdir(os.path.join(PROJECTS_FOLDER_PATH, folder))]
for project in project_folder_names:
    project_listbox.insert(0, project)
    print("Projects Loaded: " + project)
print()
    
# Button to remove selected project
remove_project_button = tk.Button(main_tab, text='Remove Project', command=remove_project_confirm)
remove_project_button.place(x=10, y=502)


# # Create a listbox to display existing project versions
# project_versions_listbox = tk.Listbox(main_tab, selectmode=tk.SINGLE, height=6, width=20)
# project_versions_listbox.place(x=640, y=170)
# project_versions_listbox.bind("<KeyPress-Return>", select_project)
# project_versions_listbox.bind("<KeyPress-space>", select_project)
# project_versions_listbox.bind("<Double-Button-1>", select_project)

# # Button to remove selected project
# project_version_label = ttk.Label(main_tab, text='New Version Name:', font=("Trebuchet MS", 10))
# project_version_label.place(x=655, y=15)
# create_version_button = tk.Button(main_tab, text='Add Version', command=remove_project_confirm)
# create_version_button.place(x=675, y=85)
# project_version_entry = ttk.Entry(main_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
# project_version_entry.place(x=642, y=45)
# select_version_button = tk.Button(main_tab, text='Select Existing Version', command=select_project)
# select_version_button.place(x=635, y=130)
# project_version_label = ttk.Label(main_tab, text='Current Selected Version:', font=("Trebuchet MS", 10))
# project_version_label.place(x=630, y=280)    

#! In-Game Codecaves Tab
auto_cave_button = tk.Button(codecave_tab, text=f'Automatically Use PS1 Header', command=auto_place_ps1_header, font=("asfasf", 12))

codecave_name_label = ttk.Label(codecave_tab, text="Codecave Name:")
codecave_name_label.pack()
codecave_name_entry = ttk.Entry(codecave_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
codecave_name_entry.pack(pady=5)

in_game_memory_label = ttk.Label(codecave_tab, text='In-Game Memory Address:')
in_game_memory_label.pack()
in_game_memory_entry = ttk.Entry(codecave_tab,  validate="key", validatecommand=(validate_no_space_cmd, "%P"))
in_game_memory_entry.pack(pady=5)
in_game_memory_entry.bind("<KeyRelease>", replace_codecave_offset_text)
in_game_memory_entry.bind("<FocusIn>", ensure_hex_entries)
in_game_memory_entry.bind("<FocusOut>", ensure_hex_entries)


is_global_offset_checkbox_checked = tk.IntVar()
global_offset_checkbox = ttk.Checkbutton(codecave_tab, text="Use Offset from In-Game Memory", variable=is_global_offset_checkbox_checked, command=toggle_offset_text_state)
global_offset_checkbox.place(x=520, y=118)
global_offset_entry = ttk.Entry(codecave_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
global_offset_entry.place(x=520, y=146)
global_offset_entry.config(state="disabled")
global_offset_entry.bind("<KeyRelease>", replace_codecave_offset_text)
global_offset_entry.bind("<FocusIn>", ensure_hex_entries)
#global_offset_update = ttk.Button(codecave_tab, text="Update", command=replace_codecave_offset_text)
#global_offset_update.place(x=600, y=75)
#global_offset_update.config(state="disabled")


disk_exe_label = ttk.Label(codecave_tab, text='Address in exe/rom:',)
disk_exe_label.pack()
disk_exe_entry = ttk.Entry(codecave_tab, validatecommand=(validate_no_space_cmd, "%P"))
disk_exe_entry.pack(pady=5)
disk_exe_entry.bind("<FocusIn>", ensure_hex_entries)
disk_exe_entry.bind("<FocusOut>", ensure_hex_entries)

codecave_size_label = ttk.Label(codecave_tab, text='Codecave Size:',)
codecave_size_label.pack()
codecave_size_entry = ttk.Entry(codecave_tab, validatecommand=(validate_no_space_cmd, "%P"))
codecave_size_entry.pack(pady=5)
codecave_size_entry.bind("<FocusIn>", ensure_hex_entries)
codecave_size_entry.bind("<FocusOut>", ensure_hex_entries)

c_files_label = ttk.Label(codecave_tab, text='C Files:')
c_files_label.pack()
c_files_entry = ttk.Entry(codecave_tab)
c_files_entry.pack(pady=5)

add_codecave_button = ttk.Button(codecave_tab, text='Add/Save Codecave', command=add_codecave)
add_codecave_button.pack(pady=10)

# Create a listbox to display added codecaves
codecaves_listbox = tk.Listbox(codecave_tab, selectmode=tk.SINGLE, height=15, width=40)
codecaves_listbox.pack(pady=10, expand=True)
codecaves_listbox.bind('<<ListboxSelect>>', select_codecave)
codecaves_listbox.bind('<KeyPress-Delete>', remove_codecave)

# Button to remove selected codecave
remove_codecave_button = tk.Button(codecave_tab, text='Remove Codecave', command=remove_codecave)
remove_codecave_button.place(x=545, y=494)

#! Hooks Tab
auto_hook_button = tk.Button(hooks_tab, text=f'Try to automatically find PS1 hook', command=auto_find_hook_in_ps1_game, font=("asfasf", 12))

hook_name_label = ttk.Label(hooks_tab, text='Hook Name:')
hook_name_label.pack()
hook_name_entry = ttk.Entry(hooks_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
hook_name_entry.pack(pady=5)

in_game_memory_hook_label = ttk.Label(hooks_tab, text='In-Game Memory Address:')
in_game_memory_hook_label.pack()
in_game_memory_entry_hooks = ttk.Entry(hooks_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
in_game_memory_entry_hooks.pack(pady=5)
in_game_memory_entry_hooks.bind("<KeyRelease>", replace_hook_offset_text)
in_game_memory_entry_hooks.bind("<FocusIn>", ensure_hex_entries)

global_offset_checkbox_hooks = ttk.Checkbutton(hooks_tab, text="Use Offset from In-Game Memory", variable=is_global_offset_checkbox_checked, command=toggle_offset_text_state)
global_offset_checkbox_hooks.place(x=520, y=118)
global_offset_entry_hooks = ttk.Entry(hooks_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
global_offset_entry_hooks.place(x=520, y=146)
global_offset_entry_hooks.config(state="disabled")
global_offset_entry_hooks.bind("<KeyRelease>", replace_hook_offset_text)
global_offset_checkbox_hooks.bind("<FocusIn>", ensure_hex_entries)

disk_exe_hook_label = ttk.Label(hooks_tab, text='Address in exe/rom:')
disk_exe_hook_label.pack()
disk_exe_entry_hooks = ttk.Entry(hooks_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
disk_exe_entry_hooks.pack(pady=5)
disk_exe_entry_hooks.bind("<KeyRelease>", replace_hook_offset_text)
disk_exe_entry_hooks.bind("<FocusIn>", ensure_hex_entries)

asm_files_label = ttk.Label(hooks_tab, text='ASM Files:')
asm_files_label.pack()
asm_files_entry = ttk.Entry(hooks_tab)
asm_files_entry.pack(pady=5)

add_codecave_button = ttk.Button(hooks_tab, text='Add/Save Hook', command=add_hook)
add_codecave_button.pack(pady=10)

# Create a listbox to display added hooks
hooks_listbox = tk.Listbox(hooks_tab, selectmode=tk.SINGLE, height=15, width=40)
hooks_listbox.pack(pady=10, expand=True)
hooks_listbox.bind('<<ListboxSelect>>', select_hook)
hooks_listbox.bind('<KeyPress-Delete>', remove_hook)

# Button to remove selected codecave
remove_hook_button = tk.Button(hooks_tab, text='Remove Hook', command=remove_hook)
remove_hook_button.place(x=545, y=494)

#! Patches Tab
patch_name_label = ttk.Label(patches_tab, text='Patch Name:')
patch_name_label.pack()
patch_name_entry = ttk.Entry(patches_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
patch_name_entry.pack(pady=5)

in_game_memory_patch_label = ttk.Label(patches_tab, text='In-Game Memory Address:')
in_game_memory_patch_label.pack()
in_game_memory_entry_patches = ttk.Entry(patches_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
in_game_memory_entry_patches.pack(pady=5)

global_offset_checkbox_patches = ttk.Checkbutton(patches_tab, text="Use Offset from In-Game Memory", variable=is_global_offset_checkbox_checked, command=toggle_offset_text_state)
global_offset_checkbox_patches.place(x=520, y=118)
global_offset_entry_patches = ttk.Entry(patches_tab, validate="key", validatecommand=(validate_no_space_cmd, "%P"))
global_offset_entry_patches.place(x=520, y=146)
global_offset_entry_patches.config(state="disabled")
global_offset_entry_patches.bind("<KeyRelease>", replace_patches_offset_text)

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
patches_listbox = tk.Listbox(patches_tab, selectmode=tk.SINGLE, height=15, width=40)
patches_listbox.pack(pady=10, expand=True)
patches_listbox.bind('<<ListboxSelect>>', select_patch)
patches_listbox.bind('<KeyPress-Delete>', remove_patch)

# Button to remove selected codecave
remove_patch_button = tk.Button(patches_tab, text='Remove Patch', command=remove_patch)
remove_patch_button.place(x=545, y=494)

#! Compile Tab
# Create a Button to compile the mod
optimization_label = ttk.Label(compile_tab, text="Choose Optimization Level:")
optimization_label.pack()
selected_optimization_level = tk.StringVar(value="O2")
optimization_levels = ["O0", "O1", "O2", "Os"]
optimization_level_combobox = ttk.Combobox(compile_tab, values=optimization_levels, textvariable=selected_optimization_level, font=("Segoe UI", 11))
optimization_level_combobox.bind("<<ComboboxSelected>>", on_optimization_level_select)
optimization_level_combobox.pack()

big_font_style = ttk.Style()
big_font_style.configure("Big.TButton", font=("Segoe UI", 20))
compile_button = ttk.Button(compile_tab, text=f"Compile Mod", command=Compile, style="Big.TButton")
compile_button.pack(pady=(10, 50))



#Temporary Objects to be instantiated later
inject_exe_button = None        
inject_emu_button = None        
inject_worse_emu_button = None  
emulators_combobox = None       
open_exe_button = None          
inject_emulator_label = None    
selected_game_label = None      
choose_exe_label = None         
build_iso_button = None   
build_exe_button = None      
change_exe_button = None
select_platform_label = None
create_ps2_code_button = None
create_cheat_code_label = None
bizhawk_ramwatch_checkbox_state = tk.IntVar()
bizhawk_ramwatch_checkbox = None
bizhawk_ramwatch_label = None
cheat_engine_ramwatch_checkbox_state = tk.IntVar()
cheat_engine_ramwatch_checkbox = None
game_cover_image = None
game_cover_image_label = None


root.mainloop()