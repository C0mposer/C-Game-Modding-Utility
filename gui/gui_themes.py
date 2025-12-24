# gui/gui_themes.py

import dearpygui.dearpygui as dpg
from typing import Tuple
import json
import os

class ThemeManager:
    """Manages DearPyGui theme customization"""
    
    def __init__(self):
        self.current_hue = 0.58  # Default blue hue (210 degrees / 360)
        self.current_saturation = 0.6  # Default saturation intensity
        self.theme_tag = "custom_global_theme"
        self.config_file = "theme_config.json"
        
    def hsv_to_rgb(self, h: float, s: float, v: float) -> Tuple[int, int, int]:
        """Convert HSV to RGB (0-255 range)"""
        if s == 0.0:
            val = int(v * 255)
            return (val, val, val)
        
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6
        
        if i == 0:
            r, g, b = v, t, p
        elif i == 1:
            r, g, b = q, v, p
        elif i == 2:
            r, g, b = p, v, t
        elif i == 3:
            r, g, b = p, q, v
        elif i == 4:
            r, g, b = t, p, v
        else:
            r, g, b = v, p, q
        
        # Clamp and convert to 0-255 range
        r = max(0, min(255, int(r * 255)))
        g = max(0, min(255, int(g * 255)))
        b = max(0, min(255, int(b * 255)))
        
        return (r, g, b)
    
    def create_theme(self, hue: float, base_saturation: float):
        """Create or update the global theme with specified hue and saturation"""
        # Delete existing theme if it exists
        if dpg.does_item_exist(self.theme_tag):
            dpg.delete_item(self.theme_tag)
        
        # Calculate colors from hue and saturation
        # Button colors (varying brightness based on base saturation)
        button_base = self.hsv_to_rgb(hue, base_saturation, 0.6)
        button_hovered = self.hsv_to_rgb(hue, min(base_saturation + 0.1, 1.0), 0.7)
        button_active = self.hsv_to_rgb(hue, min(base_saturation + 0.2, 1.0), 0.8)
        
        # Tab colors
        tab_base = self.hsv_to_rgb(hue, base_saturation * 0.83, 0.5)
        tab_hovered = self.hsv_to_rgb(hue, base_saturation, 0.6)
        tab_active = self.hsv_to_rgb(hue, min(base_saturation + 0.1, 1.0), 0.7)
        
        # Header colors (for collapsing headers)
        header_base = self.hsv_to_rgb(hue, base_saturation * 0.83, 0.45)
        header_hovered = self.hsv_to_rgb(hue, base_saturation, 0.55)
        header_active = self.hsv_to_rgb(hue, min(base_saturation + 0.1, 1.0), 0.65)
        
        # Title colors
        title_base = self.hsv_to_rgb(hue, base_saturation, 0.53)
        title_active = self.hsv_to_rgb(hue, min(base_saturation + 0.2, 1.0), 0.7)
        title_collapsed = self.hsv_to_rgb(hue, base_saturation * 0.83, 0.45)
        
        # Checkbox/Radio colors
        check_mark = self.hsv_to_rgb(hue, min(base_saturation + 0.2, 1.0), 0.8)
        frame_bg = self.hsv_to_rgb(hue, base_saturation * 0.5, 0.3)
        frame_hovered = self.hsv_to_rgb(hue, base_saturation * 0.67, 0.4)
        frame_active = self.hsv_to_rgb(hue, base_saturation * 0.83, 0.5)
        
        # Slider colors
        slider_grab = self.hsv_to_rgb(hue, min(base_saturation + 0.1, 1.0), 0.6)
        slider_grab_active = self.hsv_to_rgb(hue, min(base_saturation + 0.2, 1.0), 0.7)
        
        # Text selection
        text_selected_bg = self.hsv_to_rgb(hue, base_saturation * 0.83, 0.4)
        
        # Separator
        separator = self.hsv_to_rgb(hue, base_saturation * 0.67, 0.4)
        
        with dpg.theme(tag=self.theme_tag):
            with dpg.theme_component(dpg.mvAll):
                # Buttons
                dpg.add_theme_color(dpg.mvThemeCol_Button, button_base, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, button_hovered, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, button_active, category=dpg.mvThemeCat_Core)
                
                # Tabs
                dpg.add_theme_color(dpg.mvThemeCol_Tab, tab_base, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, tab_hovered, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, tab_active, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabUnfocused, tab_base, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabUnfocusedActive, tab_active, category=dpg.mvThemeCat_Core)
                
                # Headers
                dpg.add_theme_color(dpg.mvThemeCol_Header, header_base, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, header_hovered, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, header_active, category=dpg.mvThemeCat_Core)
                
                # Title
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, title_base, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, title_active, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgCollapsed, title_collapsed, category=dpg.mvThemeCat_Core)
                
                # Checkboxes and frames
                dpg.add_theme_color(dpg.mvThemeCol_CheckMark, check_mark, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, frame_bg, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, frame_hovered, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, frame_active, category=dpg.mvThemeCat_Core)
                
                # Sliders
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, slider_grab, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, slider_grab_active, category=dpg.mvThemeCat_Core)
                
                # Text selection
                dpg.add_theme_color(dpg.mvThemeCol_TextSelectedBg, text_selected_bg, category=dpg.mvThemeCat_Core)
                
                # Separator
                dpg.add_theme_color(dpg.mvThemeCol_Separator, separator, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_SeparatorHovered, header_hovered, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_SeparatorActive, header_active, category=dpg.mvThemeCat_Core)
    
    def apply_theme(self):
        """Apply the theme to the entire application"""
        self.create_theme(self.current_hue, self.current_saturation)
        dpg.bind_theme(self.theme_tag)
    
    def set_hue(self, hue: float):
        """Update hue and reapply theme"""
        self.current_hue = hue
        self.apply_theme()
        self.save_config()
    
    def set_saturation(self, saturation: float):
        """Update saturation intensity and reapply theme"""
        self.current_saturation = saturation
        self.apply_theme()
        self.save_config()
    
    def set_hue_and_saturation(self, hue: float, saturation: float):
        """Update both hue and saturation and reapply theme"""
        self.current_hue = hue
        self.current_saturation = saturation
        self.apply_theme()
        self.save_config()
    
    def save_config(self):
        """Save theme configuration to file"""
        try:
            config = {
                'hue': self.current_hue,
                'saturation': self.current_saturation
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Could not save theme config: {e}")
    
    def load_config(self):
        """Load theme configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.current_hue = config.get('hue', 0.58)
                    self.current_saturation = config.get('saturation', 0.6)
                    return True
        except Exception as e:
            print(f"Could not load theme config: {e}")
        return False


# Global theme manager instance
_theme_manager = ThemeManager()


def initialize_theme_system():
    """Initialize the theme system (call this once at startup)"""
    _theme_manager.load_config()
    _theme_manager.apply_theme()


def show_theme_customization_window():
    """Show the theme customization window"""
    WINDOW_TAG = "theme_customization_window"
    
    if dpg.does_item_exist(WINDOW_TAG):
        dpg.show_item(WINDOW_TAG)
        return
    
    with dpg.window(
        label="Theme Customization",
        tag=WINDOW_TAG,
        width=450,
        height=550,
        pos=[400, 200],
        on_close=lambda: dpg.hide_item(WINDOW_TAG)
    ):
        dpg.add_text("Adjust UI Color Theme", color=(150, 150, 255))
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Color picker section
        dpg.add_text("Select Color:")
        dpg.add_text("Use the color wheel to choose your theme color", color=(150, 150, 150))
        dpg.add_spacer(height=10)
        
        # Convert current HSV to RGB for color picker
        current_color = _theme_manager.hsv_to_rgb(
            _theme_manager.current_hue,
            _theme_manager.current_saturation,
            1.0  # Full brightness for picker display
        )
        
        # Add DearPyGUI's built-in color picker with wheel
        dpg.add_color_picker(
            tag=f"{WINDOW_TAG}_color_picker",
            default_value=(*current_color, 255),
            width=200,
            callback=_on_color_picked,
            no_alpha=True,
            display_rgb=True,
            display_hsv=True,
            picker_mode=dpg.mvColorPicker_wheel
        )
        
        dpg.add_spacer(height=20)
        dpg.add_separator()
        dpg.add_spacer(height=15)
        
        # Intensity slider section
        dpg.add_text("Color Intensity:")
        dpg.add_text("Adjust the saturation/vibrancy of the colors", color=(150, 150, 150))
        dpg.add_spacer(height=10)
        
        dpg.add_slider_float(
            label="Intensity",
            tag=f"{WINDOW_TAG}_saturation_slider",
            default_value=_theme_manager.current_saturation,
            min_value=0.2,
            max_value=1.0,
            callback=_on_saturation_changed,
            width=-1
        )
        
        dpg.add_spacer(height=10)
        
        # Color preview strip
        with dpg.group(horizontal=True):
            dpg.add_text("Preview:")
            dpg.add_spacer(width=10)
            
            # Create preview squares
            for i in range(5):
                brightness = 0.4 + (i * 0.15)
                with dpg.drawlist(width=40, height=40):
                    color = _theme_manager.hsv_to_rgb(
                        _theme_manager.current_hue, 
                        _theme_manager.current_saturation, 
                        brightness
                    )
                    dpg.draw_rectangle(
                        (0, 0), (40, 40),
                        color=color,
                        fill=color,
                        tag=f"{WINDOW_TAG}_preview_{i}"
                    )
        
        dpg.add_spacer(height=15)
        dpg.add_separator()
        dpg.add_spacer(height=10)
        
        # Preset buttons
        dpg.add_text("Presets:")
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Blue",
                callback=lambda: _apply_preset(0.58, 0.6),
                width=70
            )
            dpg.add_button(
                label="Purple",
                callback=lambda: _apply_preset(0.75, 0.6),
                width=70
            )
            dpg.add_button(
                label="Red",
                callback=lambda: _apply_preset(0.0, 0.6),
                width=70
            )
            dpg.add_button(
                label="Orange",
                callback=lambda: _apply_preset(0.08, 0.6),
                width=70
            )
            dpg.add_button(
                label="Green",
                callback=lambda: _apply_preset(0.33, 0.6),
                width=70
            )


def _rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert RGB (0-255) to HSV (0-1 range)"""
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    diff = max_val - min_val
    
    # Calculate hue
    if diff == 0:
        h = 0
    elif max_val == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif max_val == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    else:
        h = (60 * ((r - g) / diff) + 240) % 360
    
    # Calculate saturation
    s = 0 if max_val == 0 else (diff / max_val)
    
    # Value
    v = max_val
    
    return (h / 360.0, s, v)


def _on_color_picked(sender, color_value):
    """Callback when color is picked from the color picker"""
    # color_value from DearPyGUI is (r, g, b, a) where values are 0-255
    # Ensure we handle both integer and float values properly
    r = color_value[0] if color_value[0] <= 1.0 else color_value[0] / 255.0
    g = color_value[1] if color_value[1] <= 1.0 else color_value[1] / 255.0
    b = color_value[2] if color_value[2] <= 1.0 else color_value[2] / 255.0
    
    # Convert to 0-255 range for RGB to HSV conversion
    r_255 = int(r * 255) if r <= 1.0 else int(r)
    g_255 = int(g * 255) if g <= 1.0 else int(g)
    b_255 = int(b * 255) if b <= 1.0 else int(b)
    
    # Convert RGB to HSV
    h, s, v = _rgb_to_hsv(r_255, g_255, b_255)
    
    # Update only the hue (keep current saturation setting from intensity slider)
    _theme_manager.set_hue(h)
    _update_preview_colors()


def _on_saturation_changed(sender, saturation_value):
    """Callback when saturation slider changes"""
    _theme_manager.set_saturation(saturation_value)
    _update_preview_colors()


def _apply_preset(hue_value: float, saturation_value: float):
    """Apply a preset hue and saturation value"""
    WINDOW_TAG = "theme_customization_window"
    
    # Update saturation slider
    if dpg.does_item_exist(f"{WINDOW_TAG}_saturation_slider"):
        dpg.set_value(f"{WINDOW_TAG}_saturation_slider", saturation_value)
    
    # Update color picker to show the preset color
    if dpg.does_item_exist(f"{WINDOW_TAG}_color_picker"):
        preset_color = _theme_manager.hsv_to_rgb(hue_value, 1.0, 1.0)
        dpg.set_value(f"{WINDOW_TAG}_color_picker", (*preset_color, 255))
    
    # Apply theme
    _theme_manager.set_hue_and_saturation(hue_value, saturation_value)
    
    _update_preview_colors()


def _update_preview_colors():
    """Update the preview color squares"""
    WINDOW_TAG = "theme_customization_window"
    
    for i in range(5):
        preview_tag = f"{WINDOW_TAG}_preview_{i}"
        if dpg.does_item_exist(preview_tag):
            brightness = 0.4 + (i * 0.15)
            color = _theme_manager.hsv_to_rgb(
                _theme_manager.current_hue, 
                _theme_manager.current_saturation, 
                brightness
            )
            dpg.configure_item(preview_tag, color=color, fill=color)


def get_theme_manager():
    """Get the global theme manager instance"""
    return _theme_manager