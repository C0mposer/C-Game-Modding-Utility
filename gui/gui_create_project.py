import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from gui.gui_main_project import *
    
# Init the create project window options
def InitCreateProjectWindow():
    with dpg.window(label="Create Project", tag="Create Project", height=400, width=350, pos=[600/2, 300/2], no_move=True, no_resize=True, no_collapse=True, menubar=False):
        dpg.add_text("Create New Project")
        dpg.add_separator()
        
        dpg.add_input_text(label="Project Name", tag="Project Name", hint="Enter Project Name", source="gui_enter_project_name_tag")
        
        dpg.add_separator()
        dpg.add_button(label="Create", callback=create_button_finalize_callback)
     
     
# Callbacks
def create_button_finalize_callback():
    if dpg.get_value("gui_enter_project_name_tag") == "":
        #print(dpg.last_item)
        return
    InitMainProjectWindow()
    dpg.delete_item("Create Project") # Delete the Create Project Window
    
    