import sys
import dearpygui.dearpygui as dpg
import dearpygui.demo as demo
from tk.tk_file_picker import *
from tkinter import filedialog

from gui.gui_startup_window import *
from dpg.special_variables import *
from dpg.widget_themes import *
from theme_editor.EditThemePlugin import EditThemePlugin
from gui.gui_hotkeys import setup_hotkeys_for_project
from functions.verbose_print import *
from gui.gui_main_project import get_hotkey_manager
from gui.gui_hotkeys import poll_hotkeys
from CLI import modtool_main

def is_cli_mode():
    # Check if any command line arguments were passed (beyond the script name)
    if len(sys.argv) > 2:
        return True
    if "--help" in sys.argv or "-help" in sys.argv:
        return True
    
    # # On Windows, check if attached to a console
    # if sys.platform == 'win32':
    #     try:
    #         # If we can get console info, we're likely in CLI mode
    #         import ctypes
    #         kernel32 = ctypes.windll.kernel32
    #         if kernel32.GetConsoleWindow():
    #             # Check if stdin is connected (indicates CLI launch)
    #             return sys.stdin is not None and not sys.stdin.closed
    #     except:
    #         pass
    
    return False

if __name__ == "__main__":

    # Verbose Output
    if sys.argv.count("-verbose") >= 1:
        if sys.argv[1] == "-verbose":
            is_verbose = True
    
    # Treat as CLI, not GUI
    if is_cli_mode():
        modtool_main()
    #GUI
    else:
        dpg.create_context()
        InitSpecialVariables()
        InitWidgetThemes()

        InitMainWindow() # Init the main window for the first time
        
        width = 1024 
        height = 768
        dpg.create_viewport(title='C & C++ Game Modding Utility', width=width, height=768, min_width = width, min_height = height)
        # with dpg.viewport_menu_bar():
        #     EditThemePlugin()
        
        # from themes.theme1 import ig_theme_v3_dpg
        # current_theme = ig_theme_v3_dpg(0, 0, 3, 0, 0, 1, 1) # (Cyan/Cyan/Orange, Dark, Standard, Bordered, Rounded Frames)
        # dpg.bind_theme(current_theme)
        
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("startup_window", True)

        #
        # demo.show_demo()
        #dpg.show_style_editor()
        #

        ##! EVERY FRAME LOOP
        
        while dpg.is_dearpygui_running():
            
            # Poll hotkeys if project is open
            hotkey_mgr = get_hotkey_manager()
            if hotkey_mgr:
                poll_hotkeys(hotkey_mgr)
            
            dpg.render_dearpygui_frame()

        dpg.destroy_context()