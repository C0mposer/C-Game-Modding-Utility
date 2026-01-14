import dearpygui.dearpygui as dpg
from classes.project_data.project_data import ProjectData
from functions.verbose_print import verbose_print

class HotkeyManager:
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
        self.registered_hotkeys = {}
        self.previous_states = {}
        
    def register_hotkeys(self):
        # CTRL + SHIFT + V - Open in VSCode
        self.registered_hotkeys['ctrl_shift_v'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_Shift, dpg.mvKey_V],
            'callback': self._hotkey_open_vscode,
            'description': 'Open in VSCode'
        }
        
        # CTRL + SHIFT + S - Open in Sublime
        self.registered_hotkeys['ctrl_shift_s'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_Shift, dpg.mvKey_S],
            'callback': self._hotkey_open_sublime,
            'description': 'Open in VSCode'
        }
        
        # CTRL + SHIFT + M - Open Memory Watch
        self.registered_hotkeys['ctrl_shift_m'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_Shift, dpg.mvKey_M],
            'callback': self._hotkey_memory_watch,
            'description': 'Open Memory Watch'
        }
        
        # CTRL + SHIFT + A - Open Assembly Viewer
        self.registered_hotkeys['ctrl_shift_a'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_Shift, dpg.mvKey_A],
            'callback': self._hotkey_assembly_viewer,
            'description': 'Open Assembly Viewer'
        }
        
        # CTRL + SHIFT + H - Open Hex Differ
        self.registered_hotkeys['ctrl_shift_h'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_Shift, dpg.mvKey_H],
            'callback': self._hotkey_hex_differ,
            'description': 'Open Hex Differ'
        }
        
        # CTRL + SHIFT + W - Close Project
        self.registered_hotkeys['ctrl_shift_w'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_Shift, dpg.mvKey_W],
            'callback': self._hotkey_close_project,
            'description': 'Close Project'
        }
        # CTRL + Q - Close Project
        self.registered_hotkeys['ctrl_q'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_Q],
            'callback': self._hotkey_close_project,
            'description': 'Close Project'
        }
        
        # F1 - Compile
        self.registered_hotkeys['F1'] = {
            'keys': [dpg.mvKey_F1],
            'callback': self._hotkey_compile,
            'description': 'Compile'
        }
        
        # F2 - Compile + Inject
        self.registered_hotkeys['F2'] = {
            'keys': [dpg.mvKey_F2],
            'callback': self._hotkey_compile_and_inject,
            'description': 'Compile and inject'
        }
        
        # F5 - Switch to Codecaves tab
        self.registered_hotkeys['F5'] = {
            'keys': [dpg.mvKey_F5],
            'callback': self._hotkey_switch_to_codecaves,
            'description': 'Switch to Codecaves tab'
        }
        # F6 - Switch to Hooks tab
        self.registered_hotkeys['F6'] = {
            'keys': [dpg.mvKey_F6],
            'callback': self._hotkey_switch_to_hooks,
            'description': 'Switch to Hooks tab'
        }
        # F7 - Switch to patches tab
        self.registered_hotkeys['F7'] = {
            'keys': [dpg.mvKey_F7],
            'callback': self._hotkey_switch_to_patches,
            'description': 'Switch to patches tab'
        }

        # CTRL + S - Save Project
        self.registered_hotkeys['ctrl_s'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_S],
            'callback': self._hotkey_save_project,
            'description': 'Save Project'
        }
        
        for hotkey_id in self.registered_hotkeys.keys():
            self.previous_states[hotkey_id] = False
        
        for hotkey_id, info in self.registered_hotkeys.items():
            keys_str = "+".join([self._key_name(k) for k in info['keys']])
    
    def _key_name(self, key):
        key_names = {
            dpg.mvKey_Control: "Ctrl",
            dpg.mvKey_Shift: "Shift",
            dpg.mvKey_Alt: "Alt",
        }
        if key in key_names:
            return key_names[key]
        key_str = str(key)
        if "mvKey_" in key_str:
            return key_str.split("mvKey_")[1]
        return key_str
    
    # Every frame check
    def check_hotkeys(self):
        for hotkey_id, info in self.registered_hotkeys.items():
            keys = info['keys']
            
            all_pressed = all(dpg.is_key_down(key) for key in keys)
            
            if all_pressed and not self.previous_states[hotkey_id]:
                verbose_print(f"Hotkey triggered: {info['description']}")
                info['callback']()
            
            # Update state for next frame
            self.previous_states[hotkey_id] = all_pressed
    
    def _consume_keypress(self, keys):
        pass
    
    # ==================== Hotkey Callbacks ====================
    
    def _hotkey_open_vscode(self):
        print("Executing: Open in VSCode")
        from gui.gui_text_editors import callback_open_vscode
        callback_open_vscode(None, None, self.project_data)
        
    def _hotkey_open_sublime(self):
        print("Executing: Open in Sublime")
        from gui.gui_text_editors import callback_open_sublime
        callback_open_sublime(None, None, self.project_data)
    
    def _hotkey_memory_watch(self):
        print("Executing: Open Memory Watch")
        from gui.gui_memory_watch import show_memory_watch_window
        show_memory_watch_window(self.project_data)
    
    def _hotkey_assembly_viewer(self):
        print("Executing: Open Assembly Viewer")
        from gui.gui_assembly_viewer import show_assembly_viewer_window
        show_assembly_viewer_window(None, None, self.project_data)
    
    def _hotkey_hex_differ(self):
        print("Executing: Open Hex Differ")
        from gui.gui_hex_differ import show_visual_patcher_window
        show_visual_patcher_window(None, None, self.project_data)
    
    def _hotkey_close_project(self):
        print("Executing: Close Project")
        from gui.gui_main_project_callbacks import callback_close_project
        callback_close_project(None, None, self.project_data)
    
    def _hotkey_save_project(self):
        print("Executing: Save Project")
        from gui.gui_main_project_callbacks import callback_save_project
        callback_save_project(None, None, self.project_data)

    def _hotkey_compile(self):
        print("Executing: Compile")
        if dpg.does_item_exist("main_tab_bar"):
            dpg.set_value("main_tab_bar", "Build")
        from gui.gui_build import callback_compile
        callback_compile(None, None, self.project_data)

    def _hotkey_compile_and_inject(self):
        print("Executing: Compile + Inject")
        if dpg.does_item_exist("main_tab_bar"):
            dpg.set_value("main_tab_bar", "Build")

        from gui.gui_build import callback_compile, callback_inject_emulator
        callback_compile(None, None, self.project_data)

        selected_emulator = dpg.get_value("emulator_dropdown")
        if selected_emulator and selected_emulator != "No emulators detected":
            callback_inject_emulator(None, None, self.project_data)
        else:
            print("No emulator selected for injection")
            
            
    # Switch tabs 
    def _hotkey_switch_to_codecaves(self):
        if dpg.does_item_exist("main_tab_bar"):
            dpg.set_value("main_tab_bar", "Modifications")
        if dpg.does_item_exist("modifications_tab_bar"):
            dpg.set_value("modifications_tab_bar", "code_injection_tab") # The label was renamed to code injection, but I didn't change the tag
   
    def _hotkey_switch_to_hooks(self):
        if dpg.does_item_exist("main_tab_bar"):
            dpg.set_value("main_tab_bar", "Modifications")
        if dpg.does_item_exist("modifications_tab_bar"):
            dpg.set_value("modifications_tab_bar", "hook_injection_tab")
    
    def _hotkey_switch_to_patches(self):
        if dpg.does_item_exist("main_tab_bar"):
            dpg.set_value("main_tab_bar", "Modifications")
        if dpg.does_item_exist("modifications_tab_bar"):
            dpg.set_value("modifications_tab_bar", "binary_patch_injection_tab")




def setup_hotkeys_for_project(project_data: ProjectData) -> HotkeyManager:
    hotkey_manager = HotkeyManager(project_data)
    hotkey_manager.register_hotkeys()
    return hotkey_manager


def poll_hotkeys(hotkey_manager: HotkeyManager):
    if hotkey_manager:
        hotkey_manager.check_hotkeys()