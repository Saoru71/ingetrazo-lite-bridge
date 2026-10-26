"""Background threads for generation and the connection test, so the IngeTrazo window stays responsive.

Results come back to the panel through Qt signals, which is the threading pattern the IngeTrazo docs describe.
"""
import json
import os
import time

from PySide6.QtCore import QThread, Signal

from . import comfy, models, workflow


class GenerateWorker(QThread):
    status = Signal(str)
    done = Signal(dict)  # {"result": path, "result_bytes": bytes, "seed": int}
    failed = Signal(str)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        job = self.job
        base = job["server"]
        try:
            self.status.emit("Uploading the capture to ComfyUI...")
            input_name = comfy.upload_image(base, job["capture_path"])
            wf = workflow.build(job["params"], input_name)
            prompt_id = comfy.queue_prompt(base, wf)
            started = time.time()

            outputs = None
            while outputs is None:
                if self._cancel:
                    comfy.interrupt(base)
                    raise RuntimeError("Cancelled")
                if time.time() - started > 3600:
                    raise TimeoutError("Timed out waiting for ComfyUI (60 minutes).")
                entry = comfy.history_entry(base, prompt_id)
                if entry:
                    if entry.get("status", {}).get("status_str") == "error":
                        raise RuntimeError("ComfyUI reported an error. Check the ComfyUI console for details.")
                    outputs = entry.get("outputs")
                if outputs is None:
                    self.status.emit(f"Generating... {int(time.time() - started)} s")
                    self.msleep(1000)

            self.status.emit("Downloading the result...")
            image = (outputs.get(workflow.GEN_NODE_ID, {}).get("images") or [None])[0]
            if image is None:
                raise RuntimeError("ComfyUI returned no image.")
            data = comfy.fetch_image(base, image)
            os.makedirs(job["out_dir"], exist_ok=True)
            path = os.path.join(job["out_dir"], f"ingetrazo_lite_{time.strftime('%Y%m%d_%H%M%S')}.png")
            with open(path, "wb") as f:
                f.write(data)
            with open(path[:-4] + "_workflow.json", "w", encoding="utf-8") as f:
                json.dump(wf, f, indent=2)
            self.done.emit({"result": path, "result_bytes": data, "seed": job["params"]["seed"]})
        except Exception as e:  # reported in the panel; the thread must not raise
            self.failed.emit(str(e))


class CheckWorker(QThread):
    done = Signal(list, bool)  # report lines, all good
    failed = Signal(str)

    def __init__(self, base, parent=None):
        super().__init__(parent)
        self.base = base

    def run(self):
        try:
            lines, ok = models.connection_report(self.base)
            self.done.emit(lines, ok)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadWorker(QThread):
    progress = Signal(str, int, int)  # label of the file, bytes done, bytes total (0 when unknown)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, folder, items, parent=None):
        super().__init__(parent)
        self.folder = folder
        self.items = items  # model file entries from models.MODEL_FILES

    def run(self):
        try:
            for item in self.items:
                dest = models.model_path(self.folder, item)
                label = item["label"]
                models.download_file(item["url"], dest,
                                     lambda done, total, label=label: self.progress.emit(label, done, total))
            self.done.emit(f"Downloaded {len(self.items)} file(s).")
        except Exception as e:
            self.failed.emit(str(e))
