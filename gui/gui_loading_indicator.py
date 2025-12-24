import dearpygui.dearpygui as dpg

class LoadingIndicator:
    """Manages loading overlays for background operations"""

    _cancel_requested = False
    _cancel_callback = None

    @staticmethod
    def show(message: str = "Processing...", allow_cancel: bool = False, cancel_callback=None):
        """Show a loading overlay

        Args:
            message: The message to display
            allow_cancel: If True, shows a cancel button
            cancel_callback: Optional callback to call when cancel is clicked
        """
        if dpg.does_item_exist("loading_overlay"):
            dpg.delete_item("loading_overlay")

        LoadingIndicator._cancel_requested = False
        LoadingIndicator._cancel_callback = cancel_callback

        # Get viewport dimensions
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()

        # Adjust height if cancel button is shown
        window_height = 150 if allow_cancel else 100

        # Create semi-transparent overlay
        with dpg.window(
            label="",
            tag="loading_overlay",
            modal=True,
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_close=True,
            width=300,
            height=window_height,
            pos=[(viewport_width - 300) // 2, (viewport_height - window_height) // 2]
        ):
            dpg.add_spacer(height=10)
            dpg.add_text(message, tag="loading_message_text", indent=50)
            dpg.add_spacer(height=10)
            dpg.add_loading_indicator(style=1, radius=3, indent=130)

            if allow_cancel:
                dpg.add_spacer(height=10)
                dpg.add_button(
                    label="Cancel",
                    callback=LoadingIndicator._on_cancel_clicked,
                    width=100,
                    indent=100
                )
    
    @staticmethod
    def hide():
        """Hide the loading overlay"""
        if dpg.does_item_exist("loading_overlay"):
            dpg.delete_item("loading_overlay")
        LoadingIndicator._cancel_requested = False
        LoadingIndicator._cancel_callback = None

    @staticmethod
    def update_message(message: str):
        """Update the loading message"""
        if dpg.does_item_exist("loading_message_text"):
            dpg.set_value("loading_message_text", message)

    @staticmethod
    def is_cancelled() -> bool:
        """Check if cancel was requested"""
        return LoadingIndicator._cancel_requested

    @staticmethod
    def _on_cancel_clicked():
        """Internal callback when cancel button is clicked"""
        LoadingIndicator._cancel_requested = True
        if LoadingIndicator._cancel_callback:
            LoadingIndicator._cancel_callback()