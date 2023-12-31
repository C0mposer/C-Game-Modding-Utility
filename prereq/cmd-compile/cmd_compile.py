import os
import sys
import subprocess
import shutil
import ast
import send2trash
import pyperclip
import tkinter as tk
import xml.etree.ElementTree as ET
from termcolor import colored
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import emu_inject


PROJECTS_FOLDER_PATH = 'projects/'  # Replace with the path to your folder

#! Globals
g_projects = []
g_code_caves = []
g_hooks = []
g_patches = []

g_shouldShowTabs = False

g_current_project_folder = ""
g_current_project_name = ""

g_current_project_game_exe_full_dir = ""
g_current_project_game_exe = ""

g_current_project_game_disk_full_dir = ""
g_current_project_game_disk = ""

g_current_project_ram_watch_full_dir = ""
g_current_project_ram_watch_name = ""

g_current_project_selected_platform = ""

g_current_project_disk_offset = ""

g_universal_link_string = "-T ../../linker_script.ld -Xlinker -Map=MyMod.map "
g_universal_objcopy_string = "-O binary .config/output/elf_files/MyMod.elf .config/output/final_bins/"

g_platform_gcc_strings = {"PS1": "..\\..\\prereq\\PS1mips\\bin\\mips-gcc ", "PS2": "..\\..\\prereq\\PS2ee\\bin\\ee-gcc ", "Gamecube": "..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc ", "Wii": "..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc ", "N64": "..\\..\\prereq\\N64mips/bin\\mips64-elf-gcc "}
g_platform_linker_strings = {"PS1": "..\\..\\..\\..\\..\\prereq\\PS1mips\\bin\\mips-gcc " + g_universal_link_string, "PS2": "..\\..\\..\\..\\..\\prereq\\PS2ee\\bin\\ee-gcc " + g_universal_link_string, "Gamecube": "..\\..\\..\\..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc " + g_universal_link_string, "Wii": "..\\..\\..\\..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc " + g_universal_link_string, "N64": "..\\..\\..\\..\\..\\prereq\\N64mips\\bin\\mips64-elf-gcc " + g_universal_link_string}
g_platform_objcopy_strings = {"PS1": "..\\..\\prereq\\PS1mips\\bin\\mips-objcopy " + g_universal_objcopy_string, "PS2": "..\\..\\prereq\\PS2ee\\bin\\ee-objcopy " + g_universal_objcopy_string, "Gamecube": "..\\..\\prereq\\devkitPPC\\bin\\ppc-objcopy " + g_universal_objcopy_string, "Wii": "..\\..\\prereq\\devkitPPC\\bin\\ppc-objcopy " + g_universal_objcopy_string, "N64": "..\\..\\prereq\\N64mips\\bin\\mips64-elf-objcopy " + g_universal_objcopy_string}
g_platform_zig_strings = {"PS1": "zig cc ", "PS2": "zig cc ", "Gamecube": "zig cc ", "Wii": "zig cc ", "N64": "zig cc "}
    
    
g_src_files = ""
g_header_files = ""
g_asm_files = ""
g_obj_files = ""
g_patch_files = []

g_selected_emu = None
is_zig_project = False

def get_src_files():
    global is_zig_project
    global g_src_files
    global g_obj_files
    
    # Reset
    g_src_files = ""
    g_obj_files = ""
    is_zig_project = False
    
    # Get C/C++/Zig files 
    for code_cave in g_code_caves:
        for c_file in code_cave[3]:
            g_src_files += "src/" + c_file + " "
            g_obj_files += c_file.split(".")[0] + ".o"  + " "
            
            if c_file.split(".")[1] == "zig":
                is_zig_project = True

def check_memory_map_sizes():
    with open(f"projects\{g_current_project_name}\.config\output\memory_map\MyMod.map") as memory_map_file:
        memory_map_data = memory_map_file.read()

        for cave in g_code_caves:
            if "." + cave[0] in memory_map_data:
                cave_section_index = memory_map_data.find("." + cave[0])
                cave_section_text = memory_map_data[cave_section_index:].split("\n")[0]
                cave_section_name = cave_section_text.split()[0].split(".")[1]
                cave_section_current_size = ""
                
                #!Handle if size and address is on line below section name, or same line
                #Checking to see if all data on 1 line
                if len(cave_section_text.split()) >= 2:
                    cave_section_current_size = cave_section_text.split()[2]
                    cave_section_address = hex(int(cave_section_text.split()[1], base=16))
                #If section name is long, it will put the data on the next line, so account for that
                else:   
                    cave_section_text_long = memory_map_data[cave_section_index:].split("\n")[1]
                    cave_section_current_size = cave_section_text_long.split()[1]  
                    cave_section_address = hex(int(cave_section_text_long.split()[0], base=16))
                    
                
                cave_section_current_size_int = int(cave_section_current_size, base=16)
                if cave[5]:
                    cave_section_full_size_int = int(cave[5], base=16)
                    cave_size_percentage = cave_section_current_size_int / cave_section_full_size_int
                    
                    print(colored(f"Codecave {cave_section_name} starting at address {cave_section_address}, is currently taking up ", "cyan") + colored(f"{cave_section_current_size}", "yellow") + colored(" bytes out of ", "cyan") + colored(f"{cave[5]}", "yellow") + colored(f" bytes available. ", "cyan") + colored(f"{cave_size_percentage:.0%} full.\n", "yellow"))
                else:
                   print(colored(f"Codecave {cave_section_name} starting at address {cave_section_address}, is currently taking up ", "cyan") + colored(f"{cave_section_current_size}", "yellow") + colored(" bytes.\n", "cyan"))

def ParseBizhawkRamdump():
    file_path = g_current_project_ram_watch_full_dir
    if ".wch" in file_path.split("/")[-1].lower():
        watch_file_path = file_path                # Full Path
        watch_file_name = file_path.split("/")[-1]          # Spliting based on /, and getting last index with -1 to get only name of file
        watch_file_ascii = ""
        symbol_data = [{}]
        with open(watch_file_path, "r") as watch_file:
            watch_file_ascii = watch_file.read()
            watch_file_lines = watch_file_ascii.split("\n")
            
            
            for i, symbol in enumerate(watch_file_lines):
                symbol_info_list = symbol.split("\t")
                try:
                    if symbol_info_list[0] != "SystemID GC" and symbol_info_list[0] != "" and symbol_info_list[1] != "S":   # If not a seperator
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
                 
#Cheat engine files only get recognized 1 layer down because of XML parsing
def ParseCheatEngineFile():
    full_xml_data_keys = []
    full_converted_xml_data = ""
    
    file_path = g_current_project_ram_watch_full_dir
    watch_file_path = file_path                # Full Path
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
                                    symbol_name = symbol.split()[1].split("(")[0].split("[")[0].split(";")[0]  #No signedness specifier

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
    
    if g_current_project_ram_watch_full_dir != "" and (g_current_project_selected_platform == "PS1") or g_current_project_selected_platform == "Gamecube":
        print("Parsing Bizhawk Ramwatch")
        ParseBizhawkRamdump()
    if g_current_project_ram_watch_full_dir != "" and g_current_project_selected_platform == "PS2":
        print("Parsing Cheat Engine Table")
        ParseCheatEngineFile()()
    
    #print("Moving to Folder: ", g_project_folder)
    main_dir = os.getcwd()
    os.chdir(g_current_project_folder)
    
    #Parse Ramdump if it exists
    #Add symbols from source that were declared using in_game
    ParseCSourceForSymbols()
    
    if is_zig_project == False:
        platform_compile_strings = g_platform_gcc_strings
    if is_zig_project == True:
        platform_compile_strings = g_platform_zig_strings
    
    #! Compile C/ASM files
    starting_compilation = colored("Starting Compilation:", "green")
    compile_string = colored("Compilation string: " + g_platform_gcc_strings[g_current_project_selected_platform], "green")
    print(starting_compilation)
    print(compile_string)
    
    gcc_output = subprocess.run(g_platform_gcc_strings[g_current_project_selected_platform], shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if gcc_output.stdout:
        print(gcc_output.stdout)
        print(gcc_output.stderr)
    if gcc_output.returncode == 1:
        print(colored("Compilation of ASM Failed!", "red"))
        print(gcc_output.stderr)
        
        return False
    
    #! Compile Zig files
    if is_zig_project:
        compile_string = colored("Zig compilation string: " + platform_compile_strings[g_current_project_selected_platform], "green")
        print(compile_string)
        
        gcc_output = subprocess.run(platform_compile_strings[g_current_project_selected_platform], shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    
        
    print(colored("Compiling, Linking, & Extracting Finished!\n", "yellow"))
    os.chdir(main_dir)
    
    #pcsx2_inject.InjectIntoPCSX2(g_project_folder, code_caves, hooks)
    #InjectIntoExe()
    #BuildPS2ISO()
    
    check_memory_map_sizes()
    
    return True

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
        
    if g_selected_emu == "PCSX2_1.6.0":
        complete_message = emu_inject.InjectIntoEmu(pcsx2_160_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        #messagebox.showinfo("Info", complete_message)
    elif g_selected_emu == "PCSX2_1.7.5112":
        complete_message = emu_inject.InjectIntoEmu(pcsx2_175112_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        #messagebox.showinfo("Info", complete_message)
    else:
        pass
    
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
    dolphin_50_20347_info = {
        'name': 'Dolphin.exe',
        'base_exe_dll_name': 'Dolphin.exe',
        'main_ram_offset': 0x11DD220,
        'base': True,
        'double_ptr': True,
        'ptr': False
        }
    
    if g_selected_emu == "Dolphin_5.0-20347":
        complete_message = emu_inject.InjectIntoEmu(dolphin_50_20347_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
    elif g_selected_emu == "Dolphin_5.0-20240":
        complete_message = emu_inject.InjectIntoEmu(dolphin_50_20240_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        #messagebox.showinfo("Info", complete_message)
    elif g_selected_emu == "Dolphin_5.0-19870":
        complete_message = emu_inject.InjectIntoEmu(dolphin_50_19870_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        #messagebox.showinfo("Info", complete_message)
    else:
        print("Error", "Please select an emulator")
    
def PreparePS1EmuInject(event=0):
    global g_selected_emu
    
    duckstation_info = {
        'name': 'duckstation',
        'base_exe_dll_name': 'duckstation-qt-x64-ReleaseLTCG.exe',
        'main_ram_offset': 0x87E6B0,
        'ptr': True,
        'double_ptr': False,
        'base': True
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
        'ptr': False,
        'double_ptr': False,
        'base': False
    }
    mednafen_131_info = {
        'name': 'mednafen',
        'address': 0x2034E80,
        'ptr': False,
        'double_ptr': False,
        'base': False
    }
    
    if g_selected_emu == "Duckstation_0.1-5936":
        complete_message = emu_inject.InjectIntoEmu(duckstation_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        #messagebox.showinfo("Info", complete_message)
    elif g_selected_emu == "Mednafen_1.29":
        complete_message = emu_inject.InjectIntoEmu(mednafen_129_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        #messagebox.showinfo("Info", complete_message)
    elif g_selected_emu == "Mednafen_1.31":
        complete_message = emu_inject.InjectIntoEmu(mednafen_131_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        #messagebox.showinfo("Info", complete_message)
    elif g_selected_emu == "Bizhawk_2.6.1":
        complete_message = emu_inject.InjectIntoEmu(bizhawk_info, g_current_project_folder, g_code_caves, g_hooks, g_patches)
        #messagebox.showinfo("Info", complete_message)
    else:
        pass

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
            command_line_string = f"..\\..\\prereq\\gcr\\gcr.exe \"Modded_{file_name_ext}\" \"root/&&SystemData/Start.dol\" i {patched_exe_name.split('/')[-1]}"
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
            
    #Patch N64 Checksum
    if g_current_project_selected_platform == "N64":
        replace_n64_crc(patched_exe_name)
            
    #!If genereic executable (n64, wii), skip iso/bin stuff all above          
    open_in_explorer = messagebox.askyesno("Completed Patching", "Successfully created patched game! Would you like to open the directory in file explorer?")
    if open_in_explorer:
        #Open in file expolorer
        patched_directory = os.getcwd() + "\\" + patched_exe_name.replace('/', '\\').removesuffix("patched_" + g_current_project_game_exe_name)
        print("Opening Dir: " + patched_directory + "\nFinished!")
        subprocess.Popen("explorer " + patched_directory, shell=True)
        return "Build Complete!"
                        
def BuildPS2ISO():
    # Create Iso from Folder
    global g_current_project_folder
    old_dir = os.getcwd()
    os.chdir(g_current_project_folder)
    
    NEW_ISO_NAME = "Patched Game.iso"
    IMGBURN_COMMAND = "ImgBurn.exe /MODE BUILD /BUILDMODE IMAGEFILE /SRC \"GameIsoExtract\" /DEST " + NEW_ISO_NAME + " /FILESYSTEM \"ISO9660 + UDF\" /ROOTFOLDER YES /VOLUMELABEL \"Modded Game\" /UDFREVISION 1.50 /start /close /noimagedetails" 
    os.system(IMGBURN_COMMAND)
    shutil.rmtree("GameIsoExtract")
    os.remove("patched_" + g_current_project_game_exe_name)
    os.chdir(old_dir)
    
def BuildPS1ISO():
    # Create Iso from Folder
    global g_current_project_folder
    old_dir = os.getcwd()
    os.chdir(g_current_project_folder)

    mkpsx_command = f"..\\..\\prereq\\mkpsxiso\\mkpsxiso.exe .config\\output\\psxbuild.xml"
    os.system(mkpsx_command)
    
    os.remove("patched_" + g_current_project_game_exe_name)
    try:
        os.rename("mkpsxiso.bin", "ModdedGame.bin")
    except FileExistsError:
        os.remove("ModdedGame.bin")
        os.rename("mkpsxiso.bin", "ModdedGame.bin")
    try:
        os.rename("mkpsxiso.cue", "ModdedGame.cue")
    except FileExistsError:
        os.remove("ModdedGame.cue")
        os.rename("mkpsxiso.cue", "ModdedGame.cue")
    
    os.chdir(old_dir)

def ExtractPS1Game():
    file_path_and_name = open_ISO_file()
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
    file_name = file_path_and_name.split("/")[-1].split(".")[0]
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
    
    print(command_line_string + "\nExtracting Done!")
    open_in_explorer = messagebox.askyesno("Completed Extracting", "Successfully extracted PS1 BIN! Would you like to open the directory in file explorer?")
    if open_in_explorer:
        #Open in file expolorer
        print("Opening Dir: " + output_path + "\nFinished!")
        subprocess.Popen(f"explorer \"{output_path}\"", shell=True)
        return "ISO Extract Complete"

def ExtractPS2Game():
    file_path_and_name = open_ISO_file()
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
    file_name = file_path_and_name.split("/")[-1].split(".")[0]
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
    
    print(command_line_string + "\nExtracting Done!")
    open_in_explorer = messagebox.askyesno("Completed Extracting", "Successfully extracted PS2 ISO! Would you like to open the directory in file explorer?")
    if open_in_explorer:
        #Open in file expolorer
        print("Opening Dir: " + output_path + "\nFinished!")
        subprocess.Popen(f"explorer \"{output_path}\"", shell=True)
        return "ISO Extract Complete"

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

def ExtractGamecubeGame():
    file_path_and_name = open_ISO_file()
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
    file_name_ext = file_path_and_name.split("/")[-1]
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
    
    print(command_line_string + "\nExtracting Done!")
    open_in_explorer = messagebox.askyesno("Completed Extracting", "Successfully extracted Gamecube ISO! Would you like to open the directory in file explorer?")
    if open_in_explorer:
        #Open in file expolorer
        print("Opening Dir: " + output_path_modified + "\nFinished!")
        subprocess.Popen(f"explorer \"{output_path_modified}\"", shell=True)
        return "ISO Extract Complete"

def replace_n64_crc(modified_exe):
    crc_string = f"prereq/rn64crc/rn64crc.exe \"{modified_exe}\" -Update"
    subprocess.run(crc_string)
    print("Replaced N64 CRC!")

def open_exe_file():
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    global g_current_project_game_disk
    global g_current_project_game_disk_full_dir
    
    file_path = filedialog.askopenfilename(title="Choose game executable (SCUS, SLUS, etc)")
    if file_path:
        g_current_project_game_exe_full_dir = file_path              # Full Path
        g_current_project_game_exe_name = file_path.split("/")[-1]   # Spliting based on /, and getting last index with -1 to get only name of file
        print(f"Selected file: {file_path}")
    else:
        return

   
    #Save to config     
    g_current_project_game_exe = g_current_project_game_exe_full_dir
    if g_current_project_game_exe:
        with open(f"{g_current_project_folder}/.config/config.txt", "w") as config_file:
            config_file.write(g_current_project_game_exe + "\n")
            config_file.write(g_current_project_selected_platform + "\n")
            if g_current_project_game_disk_full_dir != "":
                config_file.write(g_current_project_game_disk_full_dir + "\n")
            print("Project Config saved. Executable dir: "  +  g_current_project_game_exe)
            

def open_ISO_file():
    global g_current_project_game_disk
    global g_current_project_game_disk_full_dir
    
    file_path = filedialog.askopenfilename(title="Choose ISO/BIN file")
    if ".iso" in file_path.split("/")[-1].lower() or ".bin" in file_path.split("/")[-1].lower() or ".ciso" in file_path.split("/")[-1].lower():
        g_current_project_game_disk_full_dir = file_path                # Full Path
        g_current_project_game_disk = file_path.split("/")[-1]          # Spliting based on /, and getting last index with -1 to get only name of file
        
        print(f"Selected file: {file_path}")
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
                print("Project Config saved. Platform is: "  +  g_current_project_selected_platform)
    #Probably means extracting with no projects selected           
    except FileNotFoundError:
        print("No current project, not saving!")   
           
def update_linker_script():
    global g_shouldShowTabs
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    global g_current_project_selected_platform
    
    try:    
        with open(f"{g_current_project_folder}/.config/linker_script.ld", "w+") as script_file:
            script_file.write("INPUT(../../../.config/symbols/symbols.txt)\nINPUT(../../../.config/symbols/function_symbols.txt)\nINPUT(../../../.config/symbols/auto_symbols.txt)\n\nMEMORY\n{\n    /* RAM locations where we'll inject the code for our replacement functions */\n")
            for cave in g_code_caves:
                script_file.write(f"    {cave[0]} : ORIGIN = {cave[1]}, LENGTH = {cave[5]}\n")
            for hook in g_hooks:
                script_file.write(f"    {hook[0]} : ORIGIN = {hook[1]}, LENGTH = {cave[5]}\n")
                
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
            #Code Caves
            for cave in g_code_caves:
                script_file.write("." + cave[0])
                script_file.write(" : \n    {\n")
                for c_file in cave[3]:
                    o_file = c_file.split(".")[0] + ".o"
                    script_file.write("        " + o_file + "(.text)\n        " + o_file + "(.rodata)\n        " + o_file + "(.rodata*)\n        " + o_file + "(.data)\n        " + o_file + "(.bss)\n        "         + o_file + "(.sdata)\n        " + o_file + "(.sbss)\n")
                    #script_file.write("main.o(.text)\n        *(.rodata)\n        *(.data)\n        *(.bss)\n    } > ")
                script_file.write("        *(.text)\n")
                script_file.write("        *(.branch_lt)\n")
                script_file.write("    } > ")
                script_file.write(f"{cave[0]}\n\n    ")
                
            script_file.write("/DISCARD/ :\n    {\n        *(.comment)\n        *(.pdr)\n        *(.mdebug)\n        *(.reginfo)\n        *(.MIPS.abiflags)\n        *(.eh_frame)\n        *(.gnu.attributes)\n    }\n}")
    except Exception as e:
        print("No project currently loaded")
        print(e)
        
def update_codecaves_hooks_config_file():
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
    
def project_switched():
    global g_shouldShowTabs
    global g_current_project_game_exe_name
    global g_current_project_game_exe_full_dir
    global g_current_project_game_exe
    global g_current_project_selected_platform
    global g_current_project_disk_offset
    global platform_combobox
    global g_current_project_game_disk
    global g_current_project_game_disk_full_dir
    global g_current_project_ram_watch_name
    global g_current_project_ram_watch_full_dir
    

        
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
        

            
    #No config file, set defaults        
    except FileNotFoundError:
        print("No config file found!")
        g_current_project_game_exe = None
        g_current_project_game_exe_name = ""
        g_current_project_game_exe_full_dir = ""
        g_current_project_game_disk = ""
        g_current_project_game_disk_full_dir = ""
        g_current_project_selected_platform = ""

def select_project(event=0):
    global g_current_project_name
    global g_code_caves
    global g_hooks
    global g_patches
    global g_current_project_folder
    
    try:
        selected_project = sys.argv[1]
    except:
        #messagebox.showerror("Error", "No project selected")
        return
    g_current_project_name = selected_project
    g_current_project_folder = f"projects/" + g_current_project_name
    print("Currently Selected Project is now: "+ g_current_project_name)
    project_switched()
    
    g_code_caves = []   # Clearing previous code cave
    
    #Check for a codecaves.txt file and fill the python list with the data in it using an ast evaluation
    if os.path.exists(f"projects/" + selected_project + "/.config/codecaves.txt"):
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
                    i += i
    
    g_hooks = []   # Clearing previous hooks
    
    #Check for a hooks.txt file and fill the python list with the data in it using an ast evaluation    
    if os.path.exists(f"projects/" + selected_project + "/.config/hooks.txt"):
        with open(f"projects/" + selected_project + "/.config/hooks.txt", "r") as hook_file:
            hook_file.readline() # Skip the first line
            file_string = hook_file.read()
            ast_file_string = ast.literal_eval(file_string)
            g_hooks = ast_file_string
            #print("Hooks updated to: " + str(g_hooks))
        # Show a "Project added" dialog
        i = 0
        for hook in g_hooks:
            i += i
        
        
    try:    
        g_patches = []   # Clearing previous patches
        
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
                i += i
    except Exception as e:
        #print("No binary patches, ignoring")
        print(e)
            
            
            
    #Update Platform Settings
    on_platform_select()
    update_linker_script()
    

    
    pass
                           
def on_platform_select(event=0):
    global g_platform_gcc_strings
    global g_platform_linker_strings
    global g_platform_objcopy_strings
    global g_platform_zig_strings
    global g_src_files
    global g_header_files
    global g_asm_files
    global g_obj_files
    global g_patch_files
    
    # Get C files 
    get_src_files()
            
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
    
    g_platform_gcc_strings = {"PS1": "..\\..\\prereq\\PS1mips\\bin\\mips-gcc ", "PS2": "..\\..\\prereq\\PS2ee\\bin\\ee-gcc ", "Gamecube": "..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc ", "Wii": "..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc ", "N64": "..\\..\\prereq\\N64mips/bin\\mips64-elf-gcc "}
    g_platform_linker_strings = {"PS1": "..\\..\\..\\..\\..\\prereq\\PS1mips\\bin\\mips-gcc " + g_universal_link_string, "PS2": "..\\..\\..\\..\\..\\prereq\\PS2ee\\bin\\ee-gcc " + g_universal_link_string, "Gamecube": "..\\..\\..\\..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc " + g_universal_link_string, "Wii": "..\\..\\..\\..\\..\\prereq\\devkitPPC\\bin\\ppc-gcc " + g_universal_link_string, "N64": "..\\..\\..\\..\\..\\prereq\\N64mips\\bin\\mips64-elf-gcc " + g_universal_link_string}
    g_platform_objcopy_strings = {"PS1": "..\\..\\prereq\\PS1mips\\bin\\mips-objcopy " + g_universal_objcopy_string, "PS2": "..\\..\\prereq\\PS2ee\\bin\\ee-objcopy " + g_universal_objcopy_string, "Gamecube": "..\\..\\prereq\\devkitPPC\\bin\\ppc-objcopy " + g_universal_objcopy_string, "Wii": "..\\..\\prereq\\devkitPPC\\bin\\ppc-objcopy " + g_universal_objcopy_string, "N64": "..\\..\\prereq\\N64mips\\bin\\mips64-elf-objcopy " + g_universal_objcopy_string}
    g_platform_zig_strings = {"PS1": "zig cc ", "PS2": "zig cc ", "Gamecube": "zig cc ", "Wii": "zig cc ", "N64": "zig cc "}
    
    #Update GCC/Linker Strings   
    for key in g_platform_gcc_strings:
        # Only add asm files if zig project. That way GCC only handles the asm files
        if is_zig_project == True:
            g_platform_gcc_strings[key] += g_asm_files
        # If not a zig project, add both src and asm files to the GCC strings
        else:
            g_platform_gcc_strings[key] += g_asm_files + g_src_files
            
        g_platform_zig_strings[key] += g_asm_files + g_src_files
        g_platform_linker_strings[key] += g_obj_files + "-o ../elf_files/MyMod.elf -nostartfiles" # ../ because of weird linker thing with directories? In Build I have to do chdir.
        
        if key == "PS2":
            g_platform_gcc_strings[key] += f"-c -G0 -O2 -I include fno-builtin -fdiagnostics-color=always"
        if key == "PS1":
            g_platform_gcc_strings[key] += f"-c -G0 -O2 -I include -msoft-float -fno-builtin -fdiagnostics-color=always"
            g_platform_zig_strings[key] += f"-c -G0 -O2 -I include -target mipsel-linux -march=mips1 -mabi=32 -nostartfiles -ffreestanding -nostdlib -fno-builtin -fdiagnostics-color=always"
        if key == "N64":
            g_platform_gcc_strings[key] += f"-c -G0 -O2 -I include -fno-builtin -fdiagnostics-color=always"
            g_platform_zig_strings[key] += f"-c -G0 -O2 -I include -target mipsel-linux -march=mips1 -mabi=32 -nostartfiles -ffreestanding -nostdlib -fno-builtin -fdiagnostics-color=always"
        if key == "Gamecube" or key == "Wii":
            g_platform_gcc_strings[key] += f"-c -O2 -I include -fdiagnostics-color=always -fno-builtin"
            g_platform_zig_strings[key] += f"-c -O2 -I include -target powerpc-linux -march=750 -mabi=32 -nostartfiles -ffreestanding -nostdlib -fno-builtin -fdiagnostics-color=always"



#! COMMAND LINE
# Go to main dir
old_dir = os.getcwd()
os.chdir("..\\..\\")

command = sys.argv[2]
try:
    emu = sys.argv[3]
    platform = sys.argv[4]
except:
    pass # emu/platform not relavent

select_project()

if sys.argv:
    did_compile = Compile()
if not did_compile:
    print("Can't inject, failed to compile")
    sys.exit()
if command == "Build_ISO":
    print(colored("Starting Build...", "magenta"))
    InjectIntoExeAndRebuildGame()
if command == "Build_EXE":
    print(colored("Starting Build...", "magenta"))
    InjectIntoJustExe()
try:
    if command == "Inject_Emulator":
        g_selected_emu = emu
        if platform == "PS1":
            PreparePS1EmuInject()
        if platform == "PS2":
            PreparePCSX2Inject()
        if platform == "Gamecube":
            PrepareDolphinInject()
except:
    pass # Not injecting
  