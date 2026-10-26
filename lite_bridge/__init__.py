"""Lite Bridge for IngeTrazo: capture the viewport and redraw it with Stable Diffusion 1.5 (realarchvis SD 1.5 V2 with an LCM LoRA) through ComfyUI.

The free version of Flux Bridge: one prompt, one size, one checkpoint. IngeTrazo calls setup(app) once at startup.
"""
__author__ = "Alvaro Celis"
__version__ = "0.1.1"

import logging

log = logging.getLogger("ingetrazo.plugins")


def setup(app):
    try:
        from .panel import LitePanel

        panel = LitePanel(app)
        dock = app.add_panel("Lite Bridge", panel, panel="lite_bridge")
        panel.dock = dock

        def show_panel():
            app.show_panel(dock)

        app.add_menu_action("Lite Bridge", show_panel, None, tip="Open the Lite Bridge panel")
        app.window._lite_bridge_panel = panel  # keeps the panel alive
    except Exception:
        log.error("Lite Bridge could not start", exc_info=True)
