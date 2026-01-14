import dearpygui.dearpygui as dpg
import pyperclip
import subprocess
import sys

_address_widget_data = {}

_COPY_POPUP_TAG = "address_copy_popup"
_POPUP_CLOSER_TAG = "address_copy_popup_closer"

def _copy_to_clipboard(text):
    # Try pyperclip
    try:
        pyperclip.copy(text)
        result = pyperclip.paste()
        if result == text:
            return True
    except Exception:
        pass

    # Try Windows clip.exe (probably can delete now, since I got pyperclip working, and it's platform independent)
    if sys.platform == 'win32':
        try:
            process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
            process.communicate(input=text.encode('utf-8'))
            return True
        except Exception:
            pass

    return False


def register_address_widget(widget_tag, address_text, has_0x_prefix=True):
    _address_widget_data[widget_tag] = {
        "address": _extract_hex_address(address_text),
        "has_prefix": has_0x_prefix
    }

    with dpg.item_handler_registry() as handler:
        dpg.add_item_clicked_handler(
            button=dpg.mvMouseButton_Right,
            callback=_on_address_right_click,
            user_data=widget_tag
        )

    dpg.bind_item_handler_registry(widget_tag, handler)


def _extract_hex_address(text):
    cleaned = text.strip().upper()
    cleaned = cleaned.replace("0X", "").replace(":", "").replace(" ", "")
    return cleaned


def _on_address_right_click(sender, app_data, widget_tag):
    if widget_tag not in _address_widget_data:
        return

    # Show popup at mouse position
    mouse_pos = dpg.get_mouse_pos(local=False)
    _show_copy_popup(mouse_pos, widget_tag)


def _show_copy_popup(position, widget_tag):
    # Delete existing popup if it exists
    _close_popup()

    data = _address_widget_data[widget_tag]
    hex_addr = data["address"]
    has_prefix = data["has_prefix"]

    # Right click menu (really just a window)
    with dpg.window(
        label="Copy Address",
        tag=_COPY_POPUP_TAG,
        modal=False,
        show=True,
        pos=position,
        width=220,
        height=95,
        no_resize=True,
        no_move=True,
        no_collapse=True,
        no_title_bar=True,
        no_scrollbar=True
    ):
        dpg.add_button(
            label="Copy Address",
            callback=lambda: _copy_address_raw(hex_addr, has_prefix),
            width=-1
        )
        dpg.add_button(
            label="Copy Address (0x prefix)",
            callback=lambda: _copy_address_with_prefix(hex_addr),
            width=-1
        )
        dpg.add_button(
            label="Cancel",
            callback=_close_popup,
            width=-1
        )


def _copy_address_raw(hex_addr, already_has_prefix):
    if already_has_prefix:
        text_to_copy = f"0x{hex_addr}"
    else:
        text_to_copy = hex_addr
    _copy_to_clipboard(text_to_copy)
    _close_popup()


def _copy_address_with_prefix(hex_addr):
    text_to_copy = f"0x{hex_addr}"
    _copy_to_clipboard(text_to_copy)
    _close_popup()


def _close_popup():
    if dpg.does_item_exist(_COPY_POPUP_TAG):
        dpg.delete_item(_COPY_POPUP_TAG)
    if dpg.does_item_exist(_POPUP_CLOSER_TAG):
        dpg.delete_item(_POPUP_CLOSER_TAG)


def _close_popup_on_click(sender, app_data):
    _close_popup()
