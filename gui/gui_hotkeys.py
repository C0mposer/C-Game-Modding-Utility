import dearpygui.dearpygui as dpg
from classes.project_data.project_data import ProjectData

class HotkeyManager:
    """Manages keyboard shortcuts for the application"""
    
    def __init__(self, project_data: ProjectData):
        self.project_data = project_data
        self.registered_hotkeys = {}
        self.previous_states = {}  # Track previous frame states
        
    def register_hotkeys(self):
        """Register all hotkeys with their callbacks"""
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
        
        # Optional: CTRL + S - Save Project
        self.registered_hotkeys['ctrl_s'] = {
            'keys': [dpg.mvKey_Control, dpg.mvKey_S],
            'callback': self._hotkey_save_project,
            'description': 'Save Project'
        }
        
        # Initialize previous states
        for hotkey_id in self.registered_hotkeys.keys():
            self.previous_states[hotkey_id] = False
        
        #print("Hotkeys registered:")
        for hotkey_id, info in self.registered_hotkeys.items():
            keys_str = "+".join([self._key_name(k) for k in info['keys']])
            #print(f"  {keys_str}: {info['description']}")
    
    def _key_name(self, key):
        """Get readable name for a key constant"""
        key_names = {
            dpg.mvKey_Control: "Ctrl",
            dpg.mvKey_Shift: "Shift",
            dpg.mvKey_Alt: "Alt",
        }
        if key in key_names:
            return key_names[key]
        # For letter keys, extract the letter
        key_str = str(key)
        if "mvKey_" in key_str:
            return key_str.split("mvKey_")[1]
        return key_str
    
    def check_hotkeys(self):
        """Check if any hotkeys are pressed (call every frame)"""
        for hotkey_id, info in self.registered_hotkeys.items():
            keys = info['keys']
            
            # Check if all keys in the combination are currently pressed
            all_pressed = all(dpg.is_key_down(key) for key in keys)
            
            # Only trigger on the transition from not-pressed to pressed
            if all_pressed and not self.previous_states[hotkey_id]:
                print(f"Hotkey triggered: {info['description']}")
                info['callback']()
            
            # Update state for next frame
            self.previous_states[hotkey_id] = all_pressed
    
    def _consume_keypress(self, keys):
        """No longer needed with state tracking, but kept for compatibility"""
        pass
    
    # ==================== Hotkey Callbacks ====================
    
    def _hotkey_open_vscode(self):
        """CTRL + SHIFT + V - Open in VSCode"""
        print("Executing: Open in VSCode")
        from gui.gui_text_editors import callback_open_vscode
        callback_open_vscode(None, None, self.project_data)
        
    def _hotkey_open_sublime(self):
        """CTRL + SHIFT + S - Open in Sublime"""
        print("Executing: Open in Sublime")
        from gui.gui_text_editors import callback_open_sublime
        callback_open_sublime(None, None, self.project_data)
    
    def _hotkey_memory_watch(self):
        """CTRL + SHIFT + M - Open Memory Watch"""
        print("Executing: Open Memory Watch")
        from gui.gui_memory_watch import show_memory_watch_window
        show_memory_watch_window(self.project_data)
    
    def _hotkey_assembly_viewer(self):
        """CTRL + SHIFT + A - Open Assembly Viewer"""
        print("Executing: Open Assembly Viewer")
        from gui.gui_assembly_viewer import show_assembly_viewer_window
        show_assembly_viewer_window(None, None, self.project_data)
    
    def _hotkey_hex_differ(self):
        """CTRL + SHIFT + H - Open Hex Differ"""
        print("Executing: Open Hex Differ")
        from gui.gui_hex_differ import show_visual_patcher_window
        show_visual_patcher_window(None, None, self.project_data)
    
    def _hotkey_close_project(self):
        """CTRL + SHIFT + W - Close Project"""
        print("Executing: Close Project")
        from gui.gui_main_project_callbacks import callback_close_project
        callback_close_project(None, None, self.project_data)
    
    def _hotkey_save_project(self):
        """CTRL + S - Save Project"""
        print("Executing: Save Project")
        from gui.gui_main_project_callbacks import callback_save_project
        callback_save_project(None, None, self.project_data)


# ==================== Integration with Main Window ====================

def setup_hotkeys_for_project(project_data: ProjectData) -> HotkeyManager:
    """
    Set up hotkey system for the main project window.
    Call this when creating the project window.
    
    Returns the HotkeyManager instance so it can be polled every frame.
    """
    hotkey_manager = HotkeyManager(project_data)
    hotkey_manager.register_hotkeys()
    return hotkey_manager


def poll_hotkeys(hotkey_manager: HotkeyManager):
    """
    Check for hotkey presses (call every frame).
    
    Args:
        hotkey_manager: The HotkeyManager instance created by setup_hotkeys_for_project
    """
    if hotkey_manager:
        hotkey_manager.check_hotkeys()