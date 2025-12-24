import dearpygui.dearpygui as dpg
from functions.helper_funcs import *
from functions.print_wrapper import *

#These update the fields automatically! (Immediate mode!)

# Init dpg special variables
def InitSpecialVariables():
    with dpg.value_registry():
            #Create Project
            dpg.add_string_value(default_value="", tag="gui_enter_project_name_tag")
            
            #Files to Inject Into
            dpg.add_string_value(default_value="", tag="gui_file_offset_from_ram_tag")
            
            #Modifications
            #C & C++ Injection
            dpg.add_string_value(default_value="", tag="gui_codecave_name_tag")
            dpg.add_string_value(default_value="", tag="gui_codecave_code_file_listbox_tag")
            dpg.add_string_value(default_value="", tag="gui_codecave_address_tag")
            dpg.add_string_value(default_value="", tag="gui_codecave_size_tag")
            dpg.add_string_value(default_value="", tag="gui_codecave_game_file_combo_tag")