import os
import subprocess
import shutil
from termcolor import colored
from tkinter import messagebox
from classes.mod_builder import *
from classes.project_data.project_data import*
from functions.print_wrapper import *

def Compile(current_project_data: ProjectData, mod_data: ModBuilder):    
    tool_dir = os.getcwd()
    
    UpdateLinkerScript(current_project_data, mod_data)
    
    project_dir = current_project_data.GetProjectFolder()
    project_platform = current_project_data.GetCurrentBuildVersion().GetPlatform()
    code_caves = current_project_data.GetCurrentBuildVersion().GetCodeCaves()
    hooks = current_project_data.GetCurrentBuildVersion().GetHooks()
    binary_patches = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()
    
    # Define output directory for object files
    obj_output_dir = os.path.join(project_dir, ".config", "output", "object_files")
    os.makedirs(obj_output_dir, exist_ok=True)
    
    # --- Step 1: Compile C/ASM files to .o files ---
    print(colored("Starting Compilation:", "green"))
    
    all_source_files: List[str] = []
    for cave in code_caves:
        all_source_files.extend(cave.GetCodeFilesPaths()) 
    for hook in hooks:
        all_source_files.extend(hook.GetCodeFilesNames())

    # IMPORTANT: Ensure all source file paths are absolute.
    source_files_abs_paths = [os.path.abspath(os.path.join(project_dir, file_name)) for file_name in all_source_files]
    
    # Derive the path to the MIPS GCC wrapper script
    # Assume mod_data.compilers[project_platform] gives the path to the original mips-gcc.exe
    original_compiler_path = os.path.join(tool_dir, mod_data.compilers[project_platform])
    compiler_wrapper_path = os.path.join(os.path.dirname(original_compiler_path), "mips-gcc-wrapper.bat")

    if not os.path.exists(compiler_wrapper_path):
        print_error(f"ERROR: MIPS GCC Wrapper script not found at {compiler_wrapper_path}. Please ensure it's in the toolchain's bin directory.", ValueError)
        return False

    compiled_obj_files: List[str] = []

    for src_file_abs_path in source_files_abs_paths:
        src_filename = os.path.basename(src_file_abs_path)
        obj_filename = os.path.splitext(src_filename)[0] + ".o"
        output_obj_abs_path = os.path.abspath(os.path.join(obj_output_dir, obj_filename)) # Ensure absolute output path

        compile_cmd = [
            compiler_wrapper_path, # Call the wrapper script here
            "-c",
            "-G0",
            "-Os",
            "-I", os.path.abspath(os.path.join(project_dir, "include")), # Absolute path to include
            # "-msoft-float",
            # "-fdiagnostics-color=always",
            "-g",
            src_file_abs_path, # Input source file (absolute path)
            "-o", output_obj_abs_path # Output object file (absolute path)
        ]

        print(colored(f"Compiling: {' '.join(compile_cmd)}", "blue"))
        
        # Run from project_dir as cwd, ensuring all paths are absolute within the command
        gcc_output = subprocess.run(compile_cmd, shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=project_dir)
        gcc_stdout_text = gcc_output.stdout
        gcc_stderr_text = gcc_output.stderr
        
        if gcc_stdout_text:
            print(gcc_stdout_text)
        if gcc_output.returncode != 0:
            print(colored(f"Compilation Failed for {src_filename}!", "red"))
            print(gcc_stderr_text)
            return False
        
        compiled_obj_files.append(obj_filename)

    print(colored("Compilation Finished!", "green"))
        
    # --- Step 2: Link .o files ---
    print(colored("Starting Link:", "green"))

    linker_obj_files_abs_paths = [os.path.abspath(os.path.join(obj_output_dir, obj_name)) for obj_name in compiled_obj_files]
    
    # Use the same wrapper for linking if the linker (mips-ld.exe, typically invoked by mips-gcc)
    # also has issues with spaced paths.
    linker_wrapper_path = compiler_wrapper_path 
    linker_script_abs_path = os.path.abspath(os.path.join(project_dir, ".config", "linker_script.ld"))
    output_elf_abs_path = os.path.abspath(os.path.join(obj_output_dir, "MyMod.elf"))
    output_map_abs_path = os.path.abspath(os.path.join(obj_output_dir, "MyMod.map"))

    linker_flags = mod_data.LINKER_STRING.split() if isinstance(mod_data.LINKER_STRING, str) else mod_data.LINKER_STRING

    link_cmd = [
        linker_wrapper_path, # Call the wrapper script for linking
        *linker_obj_files_abs_paths,
        "-T", linker_script_abs_path,
        "-o", output_elf_abs_path,
        "-Map", output_map_abs_path,
        *linker_flags
    ]

    print(colored(f"Link String: {' '.join(link_cmd)}", "blue"))
    
    linker_output = subprocess.run(link_cmd, shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=project_dir)
    linker_stdout_text = linker_output.stdout
    linker_stderr_text = linker_output.stderr
        
    if linker_stdout_text:
        print(linker_stdout_text)
    if linker_output.returncode != 0:
        print(colored("Linking Failed!", "red"))
        print(linker_stderr_text)
        if "overlaps section" in linker_stderr_text:
            messagebox.showerror("Linking Error", "Linker failed with \"overlapping sections\" error. Ensure codecaves or hooks do not share addresses, or occupy very similar regions.")
        if "will not fit in region" in linker_stderr_text:
            section_name_index = linker_stderr_text.index(": region")
            end_index = linker_stderr_text.index("collect2.exe")
            section_name_error_part = linker_stderr_text[section_name_index + 2 : end_index - 1]
            
            section_overflow_index = section_name_error_part.find("overflowed by ")
            if section_overflow_index != -1:
                section_overflow_text = section_name_error_part[section_overflow_index:]
                section_size_hex_str = section_overflow_text.split(" ")[2]
                try:
                    section_size_int = int(section_size_hex_str, 0)
                    section_size_hex_formatted = hex(section_size_int)
                except ValueError:
                    section_size_hex_formatted = "Unknown Size"
                
                section_name_part = section_name_error_part.split('overflowed')[0].strip()
                messagebox.showerror("Linking Error", f"Linker failed: {section_name_part} overflowed by {section_size_hex_formatted} bytes.")
            else:
                messagebox.showerror("Linking Error", f"Linker failed: {linker_stderr_text}")
        
        return False
    
    memory_map_dir = os.path.join(project_dir, ".config", "memory_map")
    os.makedirs(memory_map_dir, exist_ok=True)
    try:
        shutil.move(output_map_abs_path, os.path.join(memory_map_dir, "MyMod.map"))
        print(colored("Moved MyMod.map to .config/memory_map", "green"))
    except Exception as e:
        print_error(f"Failed to move MyMod.map: {e}")

    print(colored("Linking Finished!", "green"))
    
    # --- Step 3: Extract Sections to Binary ---
    print(colored("Extracting Sections to Binary:", "green"))
    
    # Note: If objcopy also has issues with spaced paths, you might need a similar wrapper for it.
    # For now, let's assume the general toolchain path fix might resolve objcopy's issues too.
    objcopy_executable_original_path = mod_data.objcopy_exes[project_platform]
    
    objcopy_flags = mod_data.OBJCOPY_STRING.split() if isinstance(mod_data.OBJCOPY_STRING, str) else mod_data.OBJCOPY_STRING
    
    sections_to_extract = []
    for cave in code_caves:
        sections_to_extract.append((cave.GetName(), cave.GetName()))
    for hook in hooks:
        sections_to_extract.append((hook.GetName(), hook.GetName()))

    for section_name, output_base_name in sections_to_extract:
        output_bin_path_abs = os.path.abspath(os.path.join(obj_output_dir, f"{output_base_name}.bin"))
        
        objcopy_cmd = [
            objcopy_executable_original_path, # Direct objcopy call for now
            *objcopy_flags,
            f"--only-section=.{section_name}",
            output_elf_abs_path,
            output_bin_path_abs
        ]
        
        print(colored(f"Extracting {section_name}...", "green"))
        print(colored(f"{objcopy_cmd}", "green"))
        objcopy_output = subprocess.run(objcopy_cmd, shell=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=project_dir)
        
        if objcopy_output.stdout:
            print(objcopy_output.stdout)
        if objcopy_output.stderr:
            print(colored(objcopy_output.stderr, "yellow"))
        if objcopy_output.returncode != 0:
            print(colored(f"Error extracting section {section_name}!", "red"))
            return False

    print(colored("Compiling, Linking, & Extracting Finished!\n", "yellow"))
    
    return True

def UpdateLinkerScript(current_project_data: ProjectData, mod_data: ModBuilder):
    project_folder = current_project_data.GetProjectFolder()
    build_name = current_project_data.GetCurrentBuildVersion().GetBuildName()
    
    code_caves = current_project_data.GetCurrentBuildVersion().GetCodeCaves()
    hooks = current_project_data.GetCurrentBuildVersion().GetHooks()
    binary_patches = current_project_data.GetCurrentBuildVersion().GetBinaryPatches()
    
    try:    
        with open(f"{project_folder}/.config/linker_script.ld", "w+") as script_file:
            script_file.write(f"INPUT(symbols/{build_name}" + ")" + "\nINPUT(.config/symbols/auto_symbols.txt)\n\nMEMORY\n{\n    /* RAM locations where we'll inject the code for our replacement functions */\n")
            for cave in code_caves:
                script_file.write(f"    {cave.GetName()} : ORIGIN = 0x{cave.GetMemoryAddress()}, LENGTH = 0x{cave.GetSize() if cave.GetSize() else '0x100000'}\n") # If a size exists in the code cave, then it places it, If not, it defaults to 0x100000
            for hook in hooks:
                script_file.write(f"    {hook.GetName()} : ORIGIN = 0x{hook.GetMemoryAddress}, LENGTH = 0x100000\n")
                
            script_file.write("}\n\nSECTIONS\n{\n    /* Custom section for compiled code */\n    ")

            for hook in hooks:
                script_file.write("/* Custom section for our hook code */\n    ")
                script_file.write("." + hook.GetName())
                script_file.write(" : \n    {\n")
                for asm_file in hook.GetCodeFilesNames():
                    o_file = asm_file.split(".")[0] + ".o"
                    script_file.write("        " + o_file + "(.text)\n        " + o_file + "(.rodata)\n        " + o_file + "(.rodata*)\n        " + o_file + "(.data)\n        " + o_file + "(.bss)\n")
                script_file.write("    } > ")
                script_file.write(f"{hook.GetName()}\n\n    ")
                
            #so that it matches i, which is 0 index'd    
            amount_of_caves = -1
            for cave in code_caves:
                amount_of_caves += 1
            
            #Code Caves
            for i, cave in enumerate(code_caves):
                script_file.write("." + cave.GetName())
                script_file.write(" : \n    {\n")
                for c_file in cave.GetCodeFilesNames():
                    o_file = c_file.split(".")[0] + ".o"
                    script_file.write("        " + o_file + "(.text)\n        " + o_file + "(.rodata)\n        " + o_file + "(.rodata*)\n        " + o_file + "(.data)\n        " + o_file + "(.bss)\n        "         + o_file + "(.sdata)\n        " + o_file + "(.sbss)\n        "  + o_file + "(.scommon)\n        "  + o_file + f"(.{o_file}.*)\n")
                    #script_file.write("main.o(.text)\n        *(.rodata)\n        *(.data)\n        *(.bss)\n    } > ")
                    
                #!If last cave, place any remaining sections
                if i == amount_of_caves:
                    script_file.write("        *(.text) /* Last section, place any potential remaining code sections */\n")
                    script_file.write("        *(.branch_lt)\n")
                    
                script_file.write("    } > ")
                script_file.write(f"{cave.GetName()}\n\n    ")
                
            script_file.write("/DISCARD/ :\n    {\n        *(.comment)\n        *(.pdr)\n        *(.mdebug)\n        *(.reginfo)\n        *(.MIPS.abiflags)\n        *(.eh_frame)\n        *(.gnu.attributes)\n    }\n}")
    except UnboundLocalError as e:
        print("update_linker_script() could not find codecave size. Ensure you have put a size for your codecave.")
    except Exception as e:
        print_error("update_linker_script() error", e)