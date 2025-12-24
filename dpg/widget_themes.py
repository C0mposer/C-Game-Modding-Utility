import dearpygui.dearpygui as dpg
from functions.helper_funcs import *
from functions.print_wrapper import *

def hsv_to_rgb(h, s, v):
    if s == 0.0: return (v, v, v)
    i = int(h*6.) # XXX assume int() truncates!
    f = (h*6.)-i; p,q,t = v*(1.-s), v*(1.-s*f), v*(1.-s*(1.-f)); i%=6
    if i == 0: return (255*v, 255*t, 255*p)
    if i == 1: return (255*q, 255*v, 255*p)
    if i == 2: return (255*p, 255*v, 255*t)
    if i == 3: return (255*p, 255*q, 255*v)
    if i == 4: return (255*t, 255*p, 255*v)
    if i == 5: return (255*v, 255*p, 255*q)

# Custom class for storage of widget theme names
class MyWidgetThemes():
    
    def __init__(self):
        self.themes: list[str] = list()
        
    def AddTheme(self, theme_tag: str):
        self.themes.append(theme_tag)
    
    def GetMyThemes(self):
        return self.themes
    
my_widget_themes = MyWidgetThemes() # Singleton

def InitWidgetThemes():
    #Add to Custom Class For Indexing
    my_widget_themes.AddTheme("big_button_theme")
    #dpg logic for Big Button Theme
    with dpg.theme(tag="big_button_theme"):                    
                with dpg.theme_component(dpg.mvAll):
                    dpg.add_theme_color(dpg.mvThemeCol_Button, hsv_to_rgb(7.0, 0.6, 0.6))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, hsv_to_rgb(7.0, 0.8, 0.8))
                    dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hsv_to_rgb(7.0, 0.7, 0.7))
                    dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 3, 3)
    
    with dpg.theme(tag="add_as_cave_theme"):
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (70, 10, 100))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 20, 150))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (60, 10, 70))
    
def SetLastItemsTheme(theme: str):
    dpg.bind_item_theme(dpg.last_item(), str)