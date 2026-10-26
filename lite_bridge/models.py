"""Checks for the free version: the ComfyUI server, the model files on disk, and their downloads.

Plain Python with no Qt dependency.
"""
import os
import urllib.request

from . import comfy, workflow

# The model files the free version uses. "required" files are needed for every run; the upscaler only for 2x.
MODEL_FILES = [
    {"key": "checkpoint", "label": "realarchvis SD 1.5 V2 checkpoint", "sub": "checkpoints",
     "file": workflow.CHECKPOINT, "url": workflow.CHECKPOINT_URL, "size_gb": 2.1, "required": True},
    {"key": "lora", "label": "LCM LoRA for SD 1.5 (fast sampling)", "sub": "loras",
     "file": workflow.LORA, "url": workflow.LORA_URL, "size_gb": 0.13, "required": True},
    {"key": "upscale", "label": "Real-ESRGAN x4plus upscaler (for 2x upscale)", "sub": "upscale_models",
     "file": workflow.UPSCALE_FILE, "url": workflow.UPSCALE_URL, "size_gb": 0.07, "required": False},
]


def checkpoint_names(base):
    """The checkpoint files ComfyUI can see, from its node definition"""
    info = comfy.object_info(base, "CheckpointLoaderSimple")
    return info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]


def lora_names(base):
    """The LoRA files ComfyUI can see, from its node definition"""
    info = comfy.object_info(base, "LoraLoader")
    return info.get("LoraLoader", {}).get("input", {}).get("required", {}).get("lora_name", [[]])[0]


def connection_report(base):
    """Lines for the panel and whether ComfyUI is reachable and has the checkpoint"""
    lines = []
    try:
        stats = comfy.system_stats(base)
        version = stats.get("system", {}).get("comfyui_version", "unknown")
        lines.append(f"Connected to ComfyUI {version}.")
    except comfy.ComfyError as e:
        return [str(e), "Start ComfyUI, then test again."], False

    ok = True
    if workflow.CHECKPOINT in checkpoint_names(base):
        lines.append(f"OK: {workflow.CHECKPOINT} is in the checkpoints folder.")
    else:
        lines.append(f"Missing: {workflow.CHECKPOINT}. Scan the ComfyUI folder to download it.")
        ok = False
    if workflow.LORA in lora_names(base):
        lines.append(f"OK: {workflow.LORA} is in the loras folder.")
    else:
        lines.append(f"Missing: {workflow.LORA}. Scan the ComfyUI folder to download it.")
        ok = False
    return lines, ok


# ----- the ComfyUI folder on disk -------------------------------------------------

def model_path(folder, item):
    return os.path.join(folder, "models", item["sub"], item["file"])


def is_present(folder, key):
    """Whether the model file with this key is in the ComfyUI folder"""
    item = next(m for m in MODEL_FILES if m["key"] == key)
    return bool(folder) and os.path.isfile(model_path(folder, item))


def scan_folder(folder):
    """Check the ComfyUI folder on disk.

    Returns (report lines, missing items). The missing list is None when the folder has no models folder.
    """
    if not folder or not os.path.isdir(os.path.join(folder, "models")):
        return (["No models folder in that folder. Choose the ComfyUI folder that contains models and custom_nodes."],
                None)
    lines, missing = [], []
    for item in MODEL_FILES:
        if os.path.isfile(model_path(folder, item)):
            size_gb = os.path.getsize(model_path(folder, item)) / 1e9
            lines.append(f"OK: {item['label']} ({size_gb:.2f} GB).")
        else:
            label = "Missing" if item["required"] else "Not downloaded (optional)"
            lines.append(f"{label}: {item['label']} (about {item['size_gb']} GB).")
            missing.append(item)
    return lines, missing


def download_file(url, dest, progress):
    """Download one file. progress(done_bytes, total_bytes) is called per chunk.

    Writes a .part file first, so an interrupted download is not mistaken for a complete one.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "IngeTrazoLite"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(8 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                progress(done, total)
        os.replace(tmp, dest)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return dest
