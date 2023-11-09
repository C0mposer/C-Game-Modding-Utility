import ctypes
from ctypes.wintypes import *
import os
import psutil
from termcolor import colored

# Define constants
PROCESS_ALL_ACCESS = 0x1F0FFF
PAGE_EXECUTE_READWRITE = 0x40
PROCESS_VM_OPERATION = 0x8
PROCESS_VM_READ = 0x10
PROCESS_VM_WRITE = 0x20

# Define some data types
DWORD = ctypes.c_uint
LPSTR = ctypes.c_char_p
MAX_PATH = 260  # Maximum path length

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)


# Function to get process ID by a string. It doesn't have to be full, it can just be the start
def get_pid(process_name):
    process_name_lower = process_name.lower()
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        #print(proc.info['name'])
        if proc.info['name'].lower().startswith(process_name_lower):
            return proc.info['pid']
    print(colored("Could not find PID for proccess starting with " + process_name, "red"))
    return None

def GetBaseAddressFromEXE(process_handle, process_name):
    base_address = None
    
    # Define an array to hold module handles
    module_handles = (HMODULE * 1024)()
    cb_needed = DWORD()

    if psapi.EnumProcessModules(process_handle, module_handles, ctypes.sizeof(module_handles), ctypes.byref(cb_needed)):
        for i in range(cb_needed.value // ctypes.sizeof(HMODULE)):
            module_name = (ctypes.c_char * MAX_PATH)()
            if psapi.GetModuleBaseNameA(process_handle, ctypes.c_ulonglong(module_handles[i]), module_name, MAX_PATH) > 0:
                module_name_str = module_name.value.decode('utf-8')
                if module_name_str.lower() == process_name.lower():
                    base_address = module_handles[i]
                    print(colored(f"Base address of {process_name}: {base_address:X}", "blue"))
                    break
    
    return base_address

def read_process_memory(handle, address, size):
    buffer = (ctypes.c_char * size)()
    bytes_read = ctypes.c_size_t()
    
    result = ctypes.windll.kernel32.ReadProcessMemory(handle, address, buffer, size, ctypes.byref(bytes_read))
    
    if result == 0:
        error_code = ctypes.windll.kernel32.GetLastError()
        print(colored(f"ReadProcessMemory failed with error code: {error_code}", "red"))
        return None
    
    return buffer.raw[:bytes_read.value]

# Function to write data to process memory
def write_to_process_memory(handle, address, data, size):
    buffer = (ctypes.c_char * size).from_buffer_copy(data)
    bytes_written = ctypes.c_size_t()
    result = ctypes.windll.kernel32.WriteProcessMemory(handle, address, buffer, size, ctypes.byref(bytes_written))
    return result != 0

# Function to change memory protection
def change_memory_protection(handle, address, size, protection):
    old_protection = ctypes.c_ulong()
    ctypes.windll.kernel32.VirtualProtectEx(handle, address, size, protection, ctypes.byref(old_protection))
    return old_protection

def InjectIntoEmu(emu_info, project_path, codecaves, hooks, patches):

    # Open a handle to the process
    mod_file_path = project_path + "/.config/output/final_bins/"
    patch_file_path = project_path + "/patches/"
    # List all files in the directory
    bin_files = os.listdir(mod_file_path)
    
    # Get the PID of the target process
    emu_pid = get_pid(emu_info['name'])
    if emu_pid is None:
        exit_message = colored(f"Could not find {emu_info['name']} Process!", "red")
        print(exit_message)
        return "Could not find {emu_info['name']} Process!"
        
    emu_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, emu_pid)
    
    if emu_info['base']:
        base_address = GetBaseAddressFromEXE(emu_handle, f"{emu_info['base_exe_dll_name']}")

    #Save the mod data from the /final_bins dir
    mod_data = {}
    bin_files = os.listdir(mod_file_path)
    for mod_file in bin_files:
        # Open and read the mod file
        mod_file_path_included = mod_file_path + mod_file
        try:
            with open(mod_file_path_included, 'rb') as mod_file:
                current_mod_file_name =  str(mod_file.name).split("/")[-1].split(".")[0]    #Getting just the filename, because I NEED ITTT lol
                mod_data[current_mod_file_name] = mod_file.read()
                #print("Reading file", current_mod_file_name)
                #print("current mod_data", mod_data)
        except IOError:
            exit_message = colored(f"Failed to open or read {mod_file}", "red")
            print(exit_message)
            return exit_message
        
    try:    
        if patches != []:
            #Save the patch from the /patches dir
            patch_data = {}
            patch_files = os.listdir(patch_file_path)
            for patch_files in patch_files:
                # Open and read the mod file
                patch_file_path_included = patch_file_path + patch_files
                try:
                    with open(patch_file_path_included, 'rb') as patch_files:
                        current_patch_file_name =  str(patch_files.name).split("/")[-1].split(".")[0]    #Getting just the filename, because I NEED ITTT lol
                        patch_data[current_patch_file_name] = patch_files.read()
                        #print("Reading file", current_mod_file_name)
                        #print("current mod_data", mod_data)
                except IOError:
                    exit_message = colored(f"Failed to open or read {patch_files}", "red")
                    print(exit_message)
                    return exit_message
    except Exception as e:
        #print("No binary patch data, ignoring")
        print("{e}")
        
        
    #Get pointer + base address like duckstation and pcsx2 1.7 and dolphin
    if emu_info['ptr']:
        try:
            ptr_address = read_process_memory(emu_handle, ctypes.c_ulonglong(base_address + emu_info['main_ram_offset']), 8)
            pointer_value = int.from_bytes(ptr_address, byteorder='little', signed=False)  
        except:
            exit_message = colored(f"Failed to read pointer to main ram", "red")
            print(exit_message)
            return "Failed to read pointer to main ram"
        
        main_ram = pointer_value    
        print(colored(f"Address of main ram in emu: {hex(main_ram)}", "blue"))
        
    #Get base address + pointer, to a pointer like dolphin
    if emu_info['double_ptr']:
        try:
            pointer_pointer_address = read_process_memory(emu_handle, ctypes.c_ulonglong(base_address + emu_info['main_ram_offset']), 8)
            pointer_pointer_value = int.from_bytes(pointer_pointer_address, byteorder='little', signed=False)  
            ptr_address = read_process_memory(emu_handle, ctypes.c_ulonglong(pointer_pointer_value), 8)
            pointer_value = int.from_bytes(ptr_address, byteorder='little', signed=False)  
        except:
            exit_message = colored(f"Failed to read pointer to main ram", "red")
            print(exit_message)
            return "Failed to read pointer to main ram"
        
        main_ram = pointer_value    
        print(colored(f"Address of main ram in emu: {hex(main_ram)}", "blue"))
        
    #else just add the offset to the base address, like for bizhawk
    elif not emu_info['ptr'] and emu_info['base']:
        main_ram = base_address + emu_info['main_ram_offset']
    #situation for if just a pointer, haven't encountered yet
    elif not emu_info['base'] and emu_info['ptr']:
        pass
    #else just a global address, like mednafen/pcsx2 1.6.0
    elif not emu_info['base']:
        main_ram = emu_info['address']
        
    #Injecting
    for cave in codecaves:
        # Write the mod data to the process
        address_to_write_to = ctypes.c_ulonglong(main_ram + int(cave[1].removeprefix("0x80"), base=16))
        #print(hex(MAIN_RAM + int(cave[1], base=16)))
        old_protection = change_memory_protection(emu_handle, address_to_write_to, len(mod_data[cave[0]]), PAGE_EXECUTE_READWRITE)
        if write_to_process_memory(emu_handle, address_to_write_to, mod_data[cave[0]], len(mod_data[cave[0]])):
            print(colored(f"Successfully placed custom function code at: {hex(int(cave[1], base=16))}", "yellow"))
            #change_memory_protection(emu_handle, address_to_write_to, len(mod_data[cave[0]]), old_protection)
        else:
            #change_memory_protection(emu_handle, address_to_write_to, len(mod_data[cave[0]]), old_protection)
            error_code = ctypes.windll.kernel32.GetLastError()
            exit_message = colored(f"Failed to write to memory. Code: {error_code}", "red")
            print(exit_message)
            return exit_message
        
    for hook in hooks:
        address_to_write_to = ctypes.c_ulonglong(main_ram + int(hook[1].removeprefix("0x80"), base=16))
        old_protection = change_memory_protection(emu_handle, address_to_write_to, len(mod_data[hook[0]]) * 2, PAGE_EXECUTE_READWRITE)
        if write_to_process_memory(emu_handle, address_to_write_to, mod_data[hook[0]], len(mod_data[hook[0]])):
            print(colored(f"Successfully placed custom hook code at: {hex(int(hook[1], base=16))}", "yellow"))
            #change_memory_protection(emu_handle, address_to_write_to, len(mod_data[hook[0]]) * 2, old_protection)
        else:
            #change_memory_protection(emu_handle, address_to_write_to, len(mod_data[hook[0]]) * 2, old_protection)
            error_code = ctypes.windll.kernel32.GetLastError()
            exit_message = colored(f"Failed to write to memory. Code: {error_code}", "red")
            print(exit_message)
            return exit_message
    
    try:    
        if patches != []:    
            for patch in patches:
                patch_name_no_ext = patch[3][0].split(".")[0]
                address_to_write_to = ctypes.c_ulonglong(main_ram + int(patch[1].removeprefix("0x80"), base=16))
                old_protection = change_memory_protection(emu_handle, address_to_write_to, len(patch_data[patch_name_no_ext]) * 2, PAGE_EXECUTE_READWRITE)
                if write_to_process_memory(emu_handle, address_to_write_to, patch_data[patch_name_no_ext], len(patch_data[patch_name_no_ext])):
                    print(colored(f"Successfully placed custom binary patch data at: {hex(int(patch[1], base=16))}", "yellow"))
                    #change_memory_protection(emu_handle, address_to_write_to, len(patch_data[patch[0]]) * 2, old_protection)
                else:
                    #change_memory_protection(emu_handle, address_to_write_to, len(patch_data[patch[0]]) * 2, old_protection)
                    error_code = ctypes.windll.kernel32.GetLastError()
                    exit_message = colored(f"Failed to write to memory. Code: {error_code}", "red")
                    print(exit_message)
                    return exit_message
    except Exception as e:
        #print("No binary patch data, ignoring")
        print("{e}")
        


    # function_address = kernel32.GetProcAddress(emu_handle, b"eeMem")
    # error_code = ctypes.windll.kernel32.GetLastError()
    # if not function_address:
    #     exit_message = colored(f"Failed. Code: {error_code}", "red")
    #     print(exit_message)
    #     raise Exception("Failed to get the function address")
    
    # print("TEST", function_address)

    # Close the process handle
    ctypes.windll.kernel32.CloseHandle(emu_handle)
    return f"Successfully injected mod into {emu_info['name']}!"

    
if __name__ == "__main__":
    project_path = "projects/SpyroAHT"
    code_caves = [('DebugText', '0x0048ADC0', '0x0', ['main.c'])]
    hooks = [('MainHook', '0x002b30ec', '0', ['main_hook.s'])]
    InjectIntoEmu(project_path, code_caves, hooks)