import dearpygui.dearpygui as dpg
import webbrowser

def callback_open_wiki():
    webbrowser.open_new_tab("https://github.com/C0mposer/C-Game-Modding-Utility/wiki")
    
def callback_open_about():
    img_w, img_h, _, img_data = dpg.load_image("prereq/icons/cd.png")

    # Waffles's Logo
    if not dpg.does_item_exist("image_id"):
        with dpg.texture_registry():
            dpg.add_static_texture(img_w, img_h, img_data, tag="image_id")
    img_w_adj = int(img_w * 0.5)
    img_h_adj = int(img_h * 0.5)
    
    # Create About Window
    window_width = 420
    window_height = 220
    viewport_width = 1024
    viewport_height = 768
    pos_x = (viewport_width - window_width) // 2 - 10
    pos_y = (viewport_height - window_height) // 2 - 15

    with dpg.window(label="About", pos= [pos_x, pos_y], width=window_width, height=window_height, no_resize=True, no_move=True):
        with dpg.group(horizontal=True):

            with dpg.drawlist(width=img_w_adj, height=img_h_adj):
                dpg.draw_image(
                    "image_id",
                    pmin=(0, 0),
                    pmax=(img_w_adj, img_h_adj),
                    uv_min=(0, 0),
                    uv_max=(1, 1)
                )

            dpg.add_spacer(width=15)

            with dpg.group():
                dpg.add_text("C Game Modding Utility")
                dpg.add_separator()
                dpg.add_text("Version: 1.0.0")
                dpg.add_text("Author: Composer")
                dpg.add_text("A game modding toolkit that aims")
                dpg.add_text("to simplify mod code injection.")

        