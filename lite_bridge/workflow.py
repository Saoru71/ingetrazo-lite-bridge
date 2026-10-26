"""The free ComfyUI workflow: the viewport capture is the start image, and one Stable Diffusion 1.5 checkpoint
(realarchvis SD 1.5 V2, about 2 GB) with an LCM LoRA redraws it from the prompt. An optional 2x upscale with Real-ESRGAN follows.

Plain Python with no Qt dependency.
"""

CHECKPOINT = "realarchvis_sd15V2.safetensors"  # in ComfyUI/models/checkpoints
CHECKPOINT_URL = "https://huggingface.co/75dhsx/jjhuang/resolve/main/realarchvis_sd15V2.safetensors"
LORA = "lcm-lora-sdv1-5.safetensors"  # in ComfyUI/models/loras (renamed from the original pytorch_lora_weights.safetensors)
LORA_URL = "https://huggingface.co/latent-consistency/lcm-lora-sdv1-5/resolve/main/pytorch_lora_weights.safetensors"
LORA_STRENGTH = 1.0
UPSCALE_FILE = "RealESRGAN_x4plus.pth"  # in ComfyUI/models/upscale_models
UPSCALE_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
GEN_NODE_ID = "9"  # PreviewImage: the result is fetched from here
# The LCM LoRA needs few steps and a low CFG; these are a starting point to test, not final values
SAMPLER, SCHEDULER = "lcm", "sgm_uniform"
STEPS, CFG = 8, 1.5
DEFAULT_PROMPT = ("photorealistic architectural visualization, blue sky with soft clouds, natural daylight, "
                  "soft shadows, high-end materials, realistic glass reflections, sharp detail, "
                  "professional architectural photography")
NEGATIVE = "blurry, low quality, distorted, watermark, text, cartoon, painting, sketch, line drawing, wireframe"
DEFAULT_CHANGE = 0.4  # 0 keeps the capture, 1 ignores it
DEFAULT_CHANGE = 0.6  # 0 keeps the capture, 1 ignores it


def generation_size(view_w, view_h, max_side):
    """The viewport's shape with the longest side capped at max_side. Sides are multiples of 8, as SD 1.5 needs."""
    scale = min(1.0, max_side / max(view_w, view_h))
    w = max(64, int(view_w * scale) // 8 * 8)
    h = max(64, int(view_h * scale) // 8 * 8)
    return w, h


# Proportion options for the capture. "VIEW" keeps the shape of the viewport.
ASPECT_ITEMS = [
    ("VIEW", "Viewport (the shape of the view)"),
    ("1_1", "1:1 (square)"),
    ("4_3", "4:3"),
    ("3_2", "3:2"),
    ("16_9", "16:9 (widescreen)"),
    ("9_16", "9:16 (portrait widescreen)"),
    ("3_4", "3:4 (portrait)"),
]


def aspect_ratio(value):
    """(width, height) for a proportion option, or None for the viewport's own shape."""
    if value == "VIEW":
        return None
    a, b = value.split("_")
    return int(a), int(b)


def fit_to_ratio(view_w, view_h, ratio):
    """The largest size with the ratio that fits inside the view. The view's size when ratio is None."""
    if ratio is None:
        return view_w, view_h
    rw, rh = ratio
    if view_w * rh > view_h * rw:
        return view_h * rw // rh, view_h  # too wide: trim the sides
    return view_w, view_w * rh // rw  # too tall: trim the top and bottom


def build(params, input_name):
    """The graph for one job. params: prompt, width, height, seed, change, upscale (bool)."""
    wf = {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_name}},
        "2": {"class_type": "ImageScale", "inputs": {
            "image": ["1", 0], "upscale_method": "lanczos", "width": params["width"],
            "height": params["height"], "crop": "disabled"}},
        "3": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        # The LCM LoRA sits between the checkpoint and the sampler, on both the model and the text encoder
        "13": {"class_type": "LoraLoader", "inputs": {
            "model": ["3", 0], "clip": ["3", 1], "lora_name": LORA,
            "strength_model": LORA_STRENGTH, "strength_clip": LORA_STRENGTH}},
        "4": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["3", 2]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": params["prompt"], "clip": ["13", 1]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["13", 1]}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["13", 0], "seed": params["seed"], "steps": STEPS, "cfg": CFG,
            "sampler_name": SAMPLER, "scheduler": SCHEDULER, "positive": ["5", 0], "negative": ["6", 0],
            "latent_image": ["4", 0], "denoise": params["change"]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 2]}},
    }
    final = ["8", 0]
    if params.get("upscale"):
        # Real-ESRGAN makes 4x; the result is scaled back to 2x so it isn't larger than needed
        wf["10"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALE_FILE}}
        wf["11"] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["10", 0], "image": ["8", 0]}}
        wf["12"] = {"class_type": "ImageScale", "inputs": {
            "image": ["11", 0], "upscale_method": "lanczos", "width": params["width"] * 2,
            "height": params["height"] * 2, "crop": "disabled"}}
        final = ["12", 0]
    wf[GEN_NODE_ID] = {"class_type": "PreviewImage", "inputs": {"images": final}}
    return wf
