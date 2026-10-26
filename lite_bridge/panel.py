"""The Lite Bridge side panel: one prompt, one size, one checkpoint, an optional 2x upscale, and the setup check.

Uses PySide6 widgets, which IngeTrazo provides.
"""
import os
import random
import time

from PySide6.QtCore import QSettings, QSize, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)

from . import capture, models, workflow
from .worker import CheckWorker, DownloadWorker, GenerateWorker


def _default_output_dir():
    return os.path.join(os.path.expanduser("~"), "Pictures", "IngeTrazoLite")


def _pixmap(data, width, height=260):
    pixmap = QPixmap()
    pixmap.loadFromData(data, "PNG")
    return pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


LIGHT = """
QWidget { background: #f4f4f4; color: #222; font-size: 12px; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff; color: #222; border: 1px solid #ccc; padding: 3px; }
QPushButton { background: #e8e8e8; color: #222; border: 1px solid #b5b5b5; padding: 6px; }
QPushButton:hover { background: #dcdcdc; }
QPushButton#primary { background: #b7e4b9; color: #1d4d22; border: 1px solid #8fcc95; font-weight: bold; }
QPushButton#primary:hover { background: #a3dba8; }
QGroupBox { border: 1px solid #ccc; margin-top: 10px; padding-top: 8px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
QLabel#preview { background: #ffffff; border: 1px solid #ccc; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { background: #e4e4e4; color: #9a9a9a; }
"""

DARK = """
QWidget { background: #1e1f22; color: #e6e6e6; font-size: 12px; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #2b2d31; color: #e6e6e6; border: 1px solid #3c3f45; padding: 3px; }
QPushButton { background: #3a3d43; color: #e6e6e6; border: 1px solid #50535a; padding: 6px; }
QPushButton:hover { background: #46494f; }
QPushButton#primary { background: #4e8f57; color: #f0fff1; border: 1px solid #3d7345; font-weight: bold; }
QPushButton#primary:hover { background: #5aa063; }
QGroupBox { border: 1px solid #3c3f45; margin-top: 10px; padding-top: 8px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
QLabel#preview { background: #2b2d31; border: 1px solid #3c3f45; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { background: #25272b; color: #6b6f76; }
"""

class LitePanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.dock = None  # set by setup() to the side-tray dock
        self.settings = QSettings("IngeTrazo", "LiteBridge")
        self.worker = None
        self.check = None
        self.download = None
        self.missing = []
        self._pending_generate = False  # a generation waiting for its files to download
        self._last_result = ""
        self._build()
        self._load_settings()

    # ----- layout ------------------------------------------------------------------

    def _on_theme_changed(self):
        self.settings.setValue("theme", self.theme.currentData())
        self._apply_theme(self.theme.currentData())

    def _apply_theme(self, name):
        self.setStyleSheet(DARK if name == "dark" else LIGHT)

    def _build(self):
        # The content scrolls, as in the Flux Bridge panel, so the groups keep their full height
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        outer.addWidget(scroll)
        layout = QVBoxLayout(body)
        header = QPushButton("  Lite Bridge")
        header.setObjectName("primary")
        header.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons", "lite_48.png")))
        header.setIconSize(QSize(32, 32))
        header.setToolTip("Lite Bridge: capture the viewport and redraw it with Stable Diffusion 1.5")
        header.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(header)
        top = QHBoxLayout()  # the Theme row, as in the Flux Bridge panel
        top.addWidget(QLabel("Theme"))
        self.theme = QComboBox()
        self.theme.addItem("Light", "light")
        self.theme.addItem("Dark", "dark")
        self.theme.setCurrentIndex(max(0, self.theme.findData(self.settings.value("theme", "light"))))
        self.theme.currentIndexChanged.connect(lambda _: self._on_theme_changed())
        top.addWidget(self.theme)
        layout.addLayout(top)
        self._apply_theme(self.theme.currentData())
        layout.addWidget(QLabel("Capture the viewport and redraw it with Stable Diffusion 1.5 (free demo)"))

        # Setup: the ComfyUI server, and the model files in the ComfyUI folder
        setup = QGroupBox("Setup: ComfyUI and models")
        setup_layout = QVBoxLayout(setup)
        setup_layout.addWidget(QLabel("ComfyUI server"))
        self.server = QLineEdit("http://127.0.0.1:8188")
        setup_layout.addWidget(self.server)
        check = QPushButton("Test connection")
        check.clicked.connect(self._test_connection)
        setup_layout.addWidget(check)
        self.check_report = QLabel("")
        self.check_report.setWordWrap(True)
        setup_layout.addWidget(self.check_report)

        setup_layout.addWidget(QLabel("ComfyUI folder (the one with models and custom_nodes)"))
        folder_row = QHBoxLayout()
        self.comfy_folder = QLineEdit("")
        folder_row.addWidget(self.comfy_folder)
        browse_folder = QPushButton("Browse...")
        browse_folder.clicked.connect(self._choose_comfy_folder)
        folder_row.addWidget(browse_folder)
        setup_layout.addLayout(folder_row)
        scan = QPushButton("Scan ComfyUI folder")
        scan.clicked.connect(self._scan_folder)
        setup_layout.addWidget(scan)
        self.scan_report = QLabel("")
        self.scan_report.setWordWrap(True)
        setup_layout.addWidget(self.scan_report)
        self.download_button = QPushButton("Download missing files")
        self.download_button.clicked.connect(self._download_missing)
        self.download_button.setVisible(False)
        setup_layout.addWidget(self.download_button)
        self.auto_download = QCheckBox("Download missing models automatically when I generate")
        self.auto_download.setChecked(True)
        setup_layout.addWidget(self.auto_download)
        self.download_status = QLabel("")
        self.download_status.setWordWrap(True)
        setup_layout.addWidget(self.download_status)
        layout.addWidget(setup)

        # Generation: the prompt and the settings, in one group as in the Flux Bridge panel
        gen = QGroupBox("Prompt")
        gen_layout = QVBoxLayout(gen)
        self.prompt = QPlainTextEdit(workflow.DEFAULT_PROMPT)
        self.prompt.setFixedHeight(80)
        gen_layout.addWidget(self.prompt)

        row = QHBoxLayout()
        row.addWidget(QLabel("Longest side (px)"))
        self.max_side = QSpinBox()
        self.max_side.setRange(512, 1024)
        self.max_side.setSingleStep(8)
        self.max_side.setValue(768)
        row.addWidget(self.max_side)
        gen_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Proportion"))
        self.aspect = QComboBox()
        for value, label in workflow.ASPECT_ITEMS:
            self.aspect.addItem(label, value)
        row.addWidget(self.aspect)
        gen_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("How much to change (0 keeps the view, 1 ignores it)"))
        self.change = QDoubleSpinBox()
        self.change.setRange(0.3, 0.9)
        self.change.setSingleStep(0.05)
        self.change.setValue(workflow.DEFAULT_CHANGE)
        row.addWidget(self.change)
        gen_layout.addLayout(row)

        self.upscale = QCheckBox("Upscale 2x with Real-ESRGAN (needs the upscaler file)")
        gen_layout.addWidget(self.upscale)
        layout.addWidget(gen)


        out = QGroupBox("Output")
        out_layout = QVBoxLayout(out)
        out_layout.addWidget(QLabel("Output folder"))
        out_row = QHBoxLayout()
        self.output = QLineEdit(_default_output_dir())
        out_row.addWidget(self.output)
        browse_output = QPushButton("Browse...")
        browse_output.clicked.connect(self._choose_output_folder)
        out_row.addWidget(browse_output)
        out_layout.addLayout(out_row)
        layout.addWidget(out)

        self.generate_button = QPushButton("Capture and generate")
        self.generate_button.setObjectName("primary")  # the green button, as in the Flux Bridge panel
        self.generate_button.clicked.connect(self._generate)
        layout.addWidget(self.generate_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(False)
        layout.addWidget(self.cancel_button)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        # Both previews: what was sent to the model, and what it made
        previews = QHBoxLayout()
        capture_box = QVBoxLayout()
        capture_box.addWidget(QLabel("Capture (sent to the model)"))
        self.preview_capture = QLabel("No capture yet")
        self.preview_capture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_capture.setMinimumHeight(180)
        capture_box.addWidget(self.preview_capture)
        previews.addLayout(capture_box)
        result_box = QVBoxLayout()
        result_box.addWidget(QLabel("Result"))
        self.preview_result = QLabel("No result yet")
        self.preview_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_result.setMinimumHeight(180)
        result_box.addWidget(self.preview_result)
        previews.addLayout(result_box)
        preview_box = QGroupBox("Previews")
        preview_box.setLayout(previews)
        layout.addWidget(preview_box)

        open_result = QPushButton("Open last result")
        open_result.clicked.connect(self._open_last_result)
        layout.addWidget(open_result)
        open_folder = QPushButton("Open output folder")
        open_folder.clicked.connect(self._open_output_folder)
        layout.addWidget(open_folder)
        layout.addStretch(1)

    # ----- settings ----------------------------------------------------------------

    def _load_settings(self):
        s = self.settings
        self.server.setText(s.value("server", self.server.text()))
        self.comfy_folder.setText(s.value("comfy_folder", ""))
        self.prompt.setPlainText(s.value("prompt", self.prompt.toPlainText()))
        self.max_side.setValue(int(s.value("max_side", self.max_side.value())))
        self.aspect.setCurrentIndex(max(0, self.aspect.findData(s.value("aspect", "VIEW"))))
        self.change.setValue(float(s.value("change", self.change.value())))
        self.upscale.setChecked(str(s.value("upscale", "false")).lower() == "true")
        self.output.setText(s.value("output", self.output.text()))

    def _save_settings(self):
        s = self.settings
        s.setValue("server", self.server.text().strip())
        s.setValue("comfy_folder", self.comfy_folder.text().strip())
        s.setValue("prompt", self.prompt.toPlainText())
        s.setValue("max_side", self.max_side.value())
        s.setValue("aspect", self.aspect.currentData())
        s.setValue("change", self.change.value())
        s.setValue("upscale", self.upscale.isChecked())
        s.setValue("output", self.output.text().strip())

    # ----- setup -------------------------------------------------------------------

    def _choose_comfy_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose the ComfyUI folder", self.comfy_folder.text())
        if folder:
            self.comfy_folder.setText(folder)
            self._save_settings()

    def _choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose the output folder", self.output.text())
        if folder:
            self.output.setText(folder)
            self._save_settings()

    def _scan_folder(self):
        self._save_settings()
        folder = self.comfy_folder.text().strip()
        lines, missing = models.scan_folder(folder)
        self.scan_report.setText("\n".join(lines))
        self.missing = missing or []
        if missing is None:
            self.download_button.setVisible(False)
            return
        self.download_button.setVisible(bool(self.missing))
        if self.missing:
            size = sum(m["size_gb"] for m in self.missing)
            self.download_button.setText(f"Download missing files (about {size:.2f} GB)")

    def _download_missing(self, confirm=True):
        folder = self.comfy_folder.text().strip()
        if not folder or not self.missing:
            self.download_status.setText("Scan the ComfyUI folder first.")
            return
        if confirm:
            names = "\n".join(f"- {m['label']} (about {m['size_gb']} GB)" for m in self.missing)
            answer = QMessageBox.question(
                self, "Download the missing files",
                f"Download these files into the ComfyUI folder?\n\n{names}\n\n"
                "The models are under OpenRAIL-family licences with use restrictions. Read their licences on the "
                "model pages before you use them.")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.download_button.setEnabled(False)
        self.download_status.setText("Starting the download...")
        self.download = DownloadWorker(folder, list(self.missing), self)
        self.download.progress.connect(self._on_download_progress)
        self.download.done.connect(self._on_download_done)
        self.download.failed.connect(self._on_download_failed)
        self.download.start()

    def _on_download_progress(self, label, done, total):
        if total:
            self.download_status.setText(f"{label}: {done / 1e9:.2f} of {total / 1e9:.2f} GB ({100 * done / total:.0f}%)")
        else:
            self.download_status.setText(f"{label}: {done / 1e9:.2f} GB")

    def _on_download_done(self, message):
        self.download_button.setEnabled(True)
        self.download_status.setText(message)
        self._scan_folder()
        if self._pending_generate:  # the generation that asked for these files starts now
            self._pending_generate = False
            self._generate()

    def _on_download_failed(self, message):
        self.download_button.setEnabled(True)
        self.download_status.setText(f"Download failed: {message}")
        self._pending_generate = False

    # ----- connection ----------------------------------------------------------------

    def _test_connection(self):
        self._save_settings()
        self.check_report.setText("Testing...")
        self.check = CheckWorker(self.server.text().strip().rstrip("/"), self)
        self.check.done.connect(self._on_check_done)
        self.check.failed.connect(lambda msg: self.check_report.setText(msg))
        self.check.start()

    def _on_check_done(self, lines, ok):
        self.check_report.setText("\n".join(lines))

    # ----- generation ----------------------------------------------------------------

    def _set_status(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet("color: #c0392b;" if error else "")

    def _generate(self):
        if self.worker is not None and self.worker.isRunning():
            self._set_status("A generation is already running.", True)
            return
        self._save_settings()
        folder = self.comfy_folder.text().strip()
        _, missing = models.scan_folder(folder)
        needed = [m for m in (missing or []) if m["required"] or (self.upscale.isChecked() and m["key"] == "upscale")]
        if needed and self.auto_download.isChecked():
            self.missing = needed
            self._pending_generate = True
            self._download_missing(confirm=False)
            return
        if self.upscale.isChecked() and not models.is_present(folder, "upscale"):
            self._set_status("The 2x upscale needs the Real-ESRGAN file. Scan the ComfyUI folder and download it, "
                             "or untick Upscale.", True)
            return
        try:
            png, width, height = capture.capture_png(self.app.viewport, self.max_side.value(),
                                                     workflow.aspect_ratio(self.aspect.currentData()))
        except Exception as e:
            self._set_status(f"Capture failed: {e}", True)
            return

        out_dir = self.output.text().strip() or _default_output_dir()
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        capture_path = os.path.join(out_dir, f"ingetrazo_lite_capture_{stamp}.png")
        with open(capture_path, "wb") as f:
            f.write(png)
        self.preview_capture.setPixmap(_pixmap(png, self.preview_capture.width()))

        params = {
            "prompt": self.prompt.toPlainText().strip() or workflow.DEFAULT_PROMPT,
            "width": width, "height": height,
            "change": self.change.value(),
            "seed": random.randint(1, 2 ** 31 - 1),
            "upscale": self.upscale.isChecked(),
        }
        job = {"server": self.server.text().strip().rstrip("/"), "capture_path": capture_path,
               "out_dir": out_dir, "params": params}
        self.worker = GenerateWorker(job, self)
        self.worker.status.connect(lambda text: self._set_status(text))
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(lambda msg: self._on_failed(msg))
        self.generate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        size = f"{width * 2} x {height * 2} (upscaled 2x)" if params["upscale"] else f"{width} x {height}"
        self._set_status(f"Starting at {size}...")
        self.worker.start()

    def _cancel(self):
        if self.worker is not None:
            self.worker.cancel()
            self._set_status("Cancelling...")

    def _finish(self):
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def _on_done(self, result):
        self._finish()
        self._last_result = result["result"]
        self.preview_result.setPixmap(_pixmap(result["result_bytes"], self.preview_result.width()))
        self._set_status(f"Done. Saved to {result['result']}")

    def _on_failed(self, message):
        self._finish()
        self._set_status(message, True)

    def _open_output_folder(self):
        folder = self.output.text().strip() or _default_output_dir()
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _open_last_result(self):
        if self._last_result and os.path.isfile(self._last_result):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_result))
        else:
            self._set_status("No result yet.", True)
