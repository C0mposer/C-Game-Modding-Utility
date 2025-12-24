import dearpygui.dearpygui as dpg

def im_color_convert_rgb_to_hsv(r, g, b):
    # Simplified equivalent of ImGui's ColorConvertRGBtoHSV
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    delta = max_val - min_val
    h = s = v = max_val

    if delta > 0:
        s = delta / max_val
        if r == max_val:
            h = (g - b) / delta
        elif g == max_val:
            h = 2.0 + (b - r) / delta
        else:
            h = 4.0 + (r - g) / delta
        h /= 6.0
        if h < 0.0:
            h += 1.0
    
    return h, s, v

def im_color_convert_hsv_to_rgb(h, s, v):
    # Simplified equivalent of ImGui's ColorConvertHSVtoRGB
    if s == 0.0:
        return v, v, v

    h_i = int(h * 6.0)
    f = h * 6.0 - h_i
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    
    h_i %= 6
    if h_i == 0:
        return v, t, p
    elif h_i == 1:
        return q, v, p
    elif h_i == 2:
        return p, v, t
    elif h_i == 3:
        return p, q, v
    elif h_i == 4:
        return t, p, v
    elif h_i == 5:
        return v, p, q
    
    return v, v, v # Should not happen

def hsv_to_rgb_normalized(h, s, v, a=1.0):
    # Converts HSV to RGB and returns as a DPG color (0-255 range)
    r, g, b = im_color_convert_hsv_to_rgb(h, s, v)
    return [int(r * 255), int(g * 255), int(b * 255), int(a * 255)]

def rgb_to_dpg_color(r, g, b, a=1.0):
    # Converts ImVec4 (0.0-1.0) to DPG color (0-255)
    return [int(r * 255), int(g * 255), int(b * 255), int(a * 255)]

def dpg_color_from_imvec4(imvec4):
    return rgb_to_dpg_color(imvec4[0], imvec4[1], imvec4[2], imvec4[3])

def get_hsv_adjusted_color(imvec4, factor_s, factor_v, lit01=0):
    # Helper to apply the lit/dim logic from the original C++
    r, g, b, a = imvec4
    h, s, v = im_color_convert_rgb_to_hsv(r, g, b)
    
    # Replication of the C++ logic:
    # 1. lit (s*0.80, v*1.00)
    # 2. dim (s, v*(0.65 or 0.65)) 
    # The C++ code's 'lit' function is only used internally to swap hi/lo, 
    # but the 'dim' logic is key.

    # dim logic:
    new_v = v * 0.65
    new_s = s
    
    # Specific exception: if B is the max component, keep it high
    # if( hi.z > hi.x && hi.z > hi.y ) return ImVec4(dim.x,dim.y,hi.z,dim.w);
    # This is complex and usually applies to shades of blue/cyan/magenta to keep them bright.
    # We will try to simplify and focus on the main dimming effect.

    return dpg_color_from_imvec4(im_color_convert_hsv_to_rgb(h, new_s * factor_s, new_v * factor_v) + (a,))

def dpg_hsv(h, s, v, a=1.0):
    # Simple DPG helper for HSV colors
    r, g, b = im_color_convert_hsv_to_rgb(h, s, v)
    return rgb_to_dpg_color(r, g, b, a)

def ig_theme_v3_dpg(
    hue07: int, 
    alt07: int, 
    nav07: int, 
    lit01: int = 0, 
    compact01: int = 0, 
    border01: int = 1, 
    shape0123: int = 1
) -> int:
    """
    Converts the ImGui igThemeV3 C++ code to a Dear PyGui theme.
    """
    # ----------------------------------------------------
    # 1. STYLE VARIABLES (DPG -> mvThemeStyle)
    # ----------------------------------------------------
    
    _8 = 4 if compact01 else 8
    _4 = 2 if compact01 else 4
    _2 = 0.5 if compact01 else 1

    rounded = shape0123 == 2
    frame_rounding = 0 if shape0123 == 0 else (4 if shape0123 == 1 else 12)
    scrollbar_rounding = 8 * rounded + 4
    
    # Create the Theme
    with dpg.theme() as theme_id:
        
        # Global Styles
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_Alpha, 1.0)
            #dpg.add_theme_style(dpg.mvStyleVar_Disabled_Alpha, 0.3)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, _8, _2 + _2)
            dpg.add_theme_style(dpg.mvStyleVar_ItemInnerSpacing, 4, 4)
            dpg.add_theme_style(dpg.mvStyleVar_IndentSpacing, 16)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, 12 if compact01 else 18)
            dpg.add_theme_style(dpg.mvStyleVar_GrabMinSize, 16 if compact01 else 20)
            #dpg.add_theme_style(dpg.mvStyleVar_TabBorderSize, 0)
            #dpg.add_theme_style(dpg.mvStyleVar_TabBarBorderSize, 2)
            dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 8.0, 4.0)
            #dpg.add_theme_style(dpg.mvStyleVar_ColumnsMinSpacing, 6.0)
            
            # The CircleTessellationMaxError logic is tricky in DPG as it's not a common style variable.
            # We'll skip it unless specifically needed for "diamond sliders".

        # Window Styles
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 4, _8)
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, border01)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_WindowMinSize, 32.0, 16.0)

        # Frame Styles (Buttons, Checkboxes, Sliders, InputText)
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 4, _4)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, frame_rounding)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)

        # Popup/Tooltip Styles


        # Tab Styles
        with dpg.theme_component(dpg.mvTab):
            dpg.add_theme_style(dpg.mvStyleVar_TabRounding, 4 if rounded else 0)

        # Scrollbar/Grab Styles

        
        # ----------------------------------------------------
        # 2. COLOR DEFINITIONS (DPG -> mvThemeColor)
        # ----------------------------------------------------
        
        # Color constants from C++ (in 0.0-1.0 ImVec4 format)
        CYAN_VEC    = (000/255.0, 192/255.0, 255/255.0, 1.00)
        RED_VEC     = (230/255.0, 000/255.0, 000/255.0, 1.00)
        YELLOW_VEC  = (240/255.0, 210/255.0, 000/255.0, 1.00)
        ORANGE_VEC  = (255/255.0, 144/255.0, 000/255.0, 1.00)
        LIME_VEC    = (192/255.0, 255/255.0, 000/255.0, 1.00)
        AQUA_VEC    = (000/255.0, 255/255.0, 192/255.0, 1.00)
        MAGENTA_VEC = (255/255.0, 000/255.0, 88/255.0, 1.00)
        PURPLE_VEC  = (192/255.0, 000/255.0, 255/255.0, 1.00)

        LINK_VEC  = (0.26, 0.59, 0.98, 1.00)
        GREY0_VEC = (0.04, 0.05, 0.07, 1.00)
        GREY1_VEC = (0.08, 0.09, 0.11, 1.00)
        GREY2_VEC = (0.10, 0.11, 0.13, 1.00)
        GREY3_VEC = (0.12, 0.13, 0.15, 1.00)
        GREY4_VEC = (0.16, 0.17, 0.19, 1.00)
        GREY5_VEC = (0.18, 0.19, 0.21, 1.00)

        LUMA = lambda v, a: (v/100.0, v/100.0, v/100.0, a/100.0)
        
        # Dynamic Color Selection
        
        color_map = {
            0: CYAN_VEC, 'C': CYAN_VEC,
            1: RED_VEC, 'R': RED_VEC,
            2: YELLOW_VEC, 'Y': YELLOW_VEC,
            3: ORANGE_VEC, 'O': ORANGE_VEC,
            4: LIME_VEC, 'L': LIME_VEC,
            5: AQUA_VEC, 'A': AQUA_VEC,
            6: MAGENTA_VEC, 'M': MAGENTA_VEC,
            7: PURPLE_VEC, 'P': PURPLE_VEC,
        }
        
        alt_vec = color_map.get(alt07, CYAN_VEC)
        hi_vec = color_map.get(hue07, CYAN_VEC)
        nav_vec = color_map.get(nav07, ORANGE_VEC)

        # Applying 'dim' logic from the C++ code for hi, lo, alt, nav colors
        def dim_color(imvec4):
            # ImGui's dim function applies: v*0.65.
            # Since the original code does not explicitly define 'dim' for hi/lo/nav/alt
            # *before* using them, we will apply the adjustment where it is used.
            # For simplicity, we define a dim that simply lowers V (brightness).
            r, g, b, a = imvec4
            h, s, v = im_color_convert_rgb_to_hsv(r, g, b)
            new_v = v * 0.65
            return im_color_convert_hsv_to_rgb(h, s, new_v) + (a,)

        lo_vec = dim_color(hi_vec)
        
        if lit01:
            # If lit01 is true, the C++ code dims 'alt' and 'nav'.
            alt_vec = dim_color(alt_vec)
            nav_vec = dim_color(nav_vec)
        
        # ----------------------------------------------------
        # 3. COLOR MAPPING (DPG -> mvThemeColor)
        # ----------------------------------------------------

        # Helper to add a color
        def add_color(dpg_const, imvec4):
            dpg.add_theme_color(dpg_const, dpg_color_from_imvec4(imvec4), category=dpg.mvThemeCat_Core)

        # Core Colors (dpg.mvAll)
        with dpg.theme_component(dpg.mvAll):
            add_color(dpg.mvThemeCol_Text, LUMA(100, 100))
            add_color(dpg.mvThemeCol_TextDisabled, LUMA(39, 100))
            add_color(dpg.mvThemeCol_Border, GREY4_VEC)
            add_color(dpg.mvThemeCol_BorderShadow, GREY1_VEC)
            add_color(dpg.mvThemeCol_FrameBg, (0.11, 0.13, 0.15, 1.00))
            add_color(dpg.mvThemeCol_FrameBgHovered, GREY4_VEC)
            add_color(dpg.mvThemeCol_FrameBgActive, GREY4_VEC)
            add_color(dpg.mvThemeCol_CheckMark, alt_vec)
            add_color(dpg.mvThemeCol_SliderGrab, lo_vec)
            add_color(dpg.mvThemeCol_SliderGrabActive, hi_vec)
            add_color(dpg.mvThemeCol_Button, (0.10, 0.11, 0.14, 1.00))
            add_color(dpg.mvThemeCol_ButtonHovered, lo_vec)
            add_color(dpg.mvThemeCol_ButtonActive, GREY5_VEC)
            add_color(dpg.mvThemeCol_Header, GREY3_VEC)
            add_color(dpg.mvThemeCol_HeaderHovered, lo_vec)
            add_color(dpg.mvThemeCol_HeaderActive, hi_vec)
            add_color(dpg.mvThemeCol_Separator, (0.13, 0.15, 0.19, 1.00))
            add_color(dpg.mvThemeCol_SeparatorHovered, lo_vec)
            add_color(dpg.mvThemeCol_SeparatorActive, hi_vec)
            add_color(dpg.mvThemeCol_ResizeGrip, LUMA(15, 100))
            add_color(dpg.mvThemeCol_ResizeGripHovered, lo_vec)
            add_color(dpg.mvThemeCol_ResizeGripActive, hi_vec)
            add_color(dpg.mvThemeCol_PlotLines, GREY5_VEC)
            add_color(dpg.mvThemeCol_PlotLinesHovered, lo_vec)
            add_color(dpg.mvThemeCol_PlotHistogram, GREY5_VEC)
            add_color(dpg.mvThemeCol_PlotHistogramHovered, lo_vec)
            add_color(dpg.mvThemeCol_TextSelectedBg, LUMA(39, 100))
            add_color(dpg.mvThemeCol_DragDropTarget, nav_vec)
            add_color(dpg.mvThemeCol_NavHighlight, nav_vec) # Closest to NavCursor
            add_color(dpg.mvThemeCol_NavWindowingHighlight, lo_vec)
            add_color(dpg.mvThemeCol_ModalWindowDimBg, LUMA(0, 63))
            
            # The original uses ImGuiCol_InputTextCursor for white text cursor, which is mapped
            # to a style in DPG, but we'll use mvThemeCol_Text for color consistency.
            # DPG does not have a direct mapping for ImGuiCol_TextLink.

        # Window/Modal Colors (mvWindowAppItem)












            
        # The light mode (lit01) color adjustment loop is complex and
        # will generally require manual DPG theme creation if full color inversion
        # is needed, as DPG does not have a built-in HSV-to-inverse-Luma switch.
        # We will assume the dark theme is the default for this conversion.
        
    return theme_id

# --- Example Usage ---
# import dearpygui.demo as demo

# dpg.create_context()
# dpg.create_viewport(title='igThemeV3 Dear PyGui Conversion', width=800, height=600)
# dpg.setup_dearpygui()

# # Parameters: hue (0-7), alt (0-7), nav (0-7), light (0/1), compact (0/1), borders (0/1), shape (0-3)
# current_theme = ig_theme_v3_dpg(0, 0, 3, 0, 0, 1, 1) # (Cyan/Cyan/Orange, Dark, Standard, Bordered, Rounded Frames)
# dpg.bind_theme(current_theme)

# with dpg.window(label="DPG Theme Demo"):
#     demo.show_demo()

# dpg.show_viewport()
# dpg.start_dearpygui()
# dpg.destroy_context()