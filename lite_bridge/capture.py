"""Capture the IngeTrazo viewport as a PNG for the workflow.

Uses the viewport's framebuffer (the image as it is drawn). Needs PySide6, which IngeTrazo provides.
"""
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

from . import workflow


def grab_view(viewport):
    """The viewport as a QImage. Falls back to a widget grab when the framebuffer isn't available."""
    image = None
    try:
        image = viewport.grabFramebuffer()
    except Exception:
        image = None
    if image is None or image.isNull():
        image = viewport.grab().toImage()
    return image


def capture_png(viewport, max_side, ratio=None):
    """Capture the viewport, centre-cropped to the ratio when one is given. Returns (png_bytes, width, height)."""
    image = grab_view(viewport)
    if ratio is not None:
        fit_w, fit_h = workflow.fit_to_ratio(image.width(), image.height(), ratio)
        image = image.copy((image.width() - fit_w) // 2, (image.height() - fit_h) // 2, fit_w, fit_h)
    w, h = workflow.generation_size(image.width(), image.height(), max_side)
    image = image.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    data = bytes(buffer.data())
    buffer.close()
    return data, w, h


def image_from_png(data):
    """A QImage from PNG bytes, for the preview"""
    image = QImage()
    image.loadFromData(data, "PNG")
    return image
