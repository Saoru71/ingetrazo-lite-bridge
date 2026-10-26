# Lite Bridge for IngeTrazo: installation guide (v0.1.0)

Lite Bridge is a free demo of the workflow. It captures the IngeTrazo viewport, sends it to your local ComfyUI server, and redraws it with one Stable Diffusion 1.5 checkpoint, **realarchvis SD 1.5 V2**, and an **LCM LoRA** that speeds up sampling. It has one prompt, one size setting and one "how much to change" setting.

It doesn't include the lighting grid, the material reference, the control maps or the other models. For those, use the full Flux Bridge.


## Download size

| Item | Size |
|---|---|
| Plugin (`IngeTrazoLiteBridge.zip`) | under 0.1 MB |
| realarchvis SD 1.5 V2 checkpoint (`realarchvis_sd15V2.safetensors`) | about 2.1 GB |
| LCM LoRA for SD 1.5 (`lcm-lora-sdv1-5.safetensors`) | about 0.13 GB |
| Real-ESRGAN x4plus upscaler (`RealESRGAN_x4plus.pth`, optional, for 2x upscale) | about 0.07 GB |

Plus ComfyUI itself.

## Requirements

- **IngeTrazo** 0.x, with its plugin folder.
- **ComfyUI** running at `http://127.0.0.1:8188`. Install it from the ComfyUI site and start it once.
- **realarchvis SD 1.5 V2** in `ComfyUI/models/checkpoints/`, with the file name `realarchvis_sd15V2.safetensors`. Download it from <https://huggingface.co/75dhsx/jjhuang>.
- **LCM LoRA for SD 1.5** in `ComfyUI/models/loras/`, with the file name `lcm-lora-sdv1-5.safetensors`. Download it from <https://huggingface.co/latent-consistency/lcm-lora-sdv1-5>.

## Step 1: Install the plugin

1. Copy the `lite_bridge` folder into the IngeTrazo plugins folder:
   - **Windows:** `%APPDATA%\ingetrazo\plugins\`
   - Or open **Extensions > Open plugins folder** in IngeTrazo.
2. If you already have an older copy of `lite_bridge`, delete it first, so the plugin doesn't load twice.
3. Restart IngeTrazo. If the plugin shows ⚠, hover over it to see the error.

The folder should end up as `plugins/lite_bridge/__init__.py`, with the other files beside it.

## Step 2: Check the setup

1. Open **Extensions > Lite Bridge**, or the Lite Bridge tab in the side tray.
2. Start ComfyUI, then click **Test connection**. The report shows whether ComfyUI is running and whether it can see the checkpoint.
3. Choose your **ComfyUI folder** (the one with `models` and `custom_nodes`), then click **Scan ComfyUI folder**. It checks the file on disk.
4. If a file is missing, click **Download missing files**. The panel lists the files and their sizes, and asks first. The download runs in the background, and its progress shows under the button. The checkpoint goes to `models/checkpoints/realarchvis_sd15V2.safetensors`, and the LCM LoRA to `models/loras/lcm-lora-sdv1-5.safetensors`, and the upscaler to `models/upscale_models/RealESRGAN_x4plus.pth`.

## Step 3: Generate

1. Write the prompt. The default describes an architectural visualisation with natural daylight.
2. Set the **Longest side**. The view keeps its own shape. 768 px is a good start on an 8 GB card. Sides are rounded to multiples of 8. Then choose **Proportion** to crop the capture to a shape such as 1:1, 4:3 or 16:9, so the result shows only that frame. **Viewport** keeps the shape of the view.
3. Set **How much to change**. The default is 0.4, which keeps the building and pool in place and still adds shading and materials. Lower values (0.3) keep more of the view but look more like a line drawing. Higher values (0.6 and up) change the layout.
4. Optional: tick **Upscale 2x with Real-ESRGAN**. The result is then twice the size, for example 1536 px instead of 768 px. It needs the upscaler file from step 2.
5. Click **Capture and generate**. The status line shows the progress. The first run loads the model, which is slow.

Choose the **Output folder** with **Browse...**. The default is `Pictures\IngeTrazoLite`. The result is saved as `ingetrazo_lite_<time>.png`, and the capture beside it as `ingetrazo_lite_capture_<time>.png`.

The two previews show the **capture** (what was sent to the model) and the **result**, side by side. **Open last result** opens the newest result in your default image viewer.

## How it works

1. **Capture:** the panel grabs the IngeTrazo viewport as it is drawn, scaled to the longest side you chose.
2. **Upload:** the capture is sent to ComfyUI.
3. **Encode:** ComfyUI encodes the capture into the model's latent space. This is the starting point of the image.
4. **Redraw:** the LCM sampler (8 steps, CFG 1.5) adds noise to that starting point and denoises it again, guided by the prompt. **How much to change** sets the amount of noise: a low value keeps more of the view.
5. **Decode and save:** the result is decoded to an image, shown in the preview, and saved.

This is image-to-image redrawing. **It doesn't use ControlNet** and doesn't use a depth or edge map. The layout is kept only because the starting point is the capture, so with a high **How much to change**, the layout can drift. A ControlNet depth model would keep the layout more strictly; that's a possible later step, not part of this version.

## Notes

- **Upscale:** Real-ESRGAN makes the image 4 times larger, and the plugin scales it back to 2 times. It adds detail to the image that's already there.
- **Stable Diffusion 1.5 is lighter than FLUX.2 Klein**, so the results are simpler and less detailed. Use Flux Bridge for the detailed results.
- **Layout:** the result follows the view when **How much to change** is low. Very high values can drift from the view.
- **Settings** are saved between sessions.
- **Plugin API:** IngeTrazo's plugin API is marked unstable in its 0.x series. If IngeTrazo changes it, the plugin may need updating.

## Files

- `lite_bridge/__init__.py`: the entry point, `setup(app)`.
- `lite_bridge/panel.py`: the panel and its controls.
- `lite_bridge/capture.py`: the viewport capture.
- `lite_bridge/worker.py`: the background threads for generation and the connection test.
- `lite_bridge/workflow.py`: the ComfyUI workflow (plain Python).
- `lite_bridge/comfy.py`: the ComfyUI client (plain Python).
- `lite_bridge/models.py`: the connection check, the ComfyUI folder scan and the checkpoint download (plain Python).


## Licence and allowed use

**Plugin: GPL-3.0-or-later.** Lite Bridge is free software. You may use, study, share and change it under GPL-3.0-or-later. If you share it, you must share its source code under the same licence. The full licence text is in `LICENSE.txt`.

**Demo use only.** Lite Bridge is a free demo of the workflow. It is not for commercial work. The models it uses
allow commercial use of their outputs under their licences, but this plugin is not the product for that.
For commercial work, buy the Flux or Nano Banana add-ons.

**Models: realarchvis SD 1.5 V2 and the LCM LoRA for SD 1.5.** Like most Stable Diffusion 1.5 community merges, the checkpoint is governed by the CreativeML Open RAIL-M (licence text: https://huggingface.co/spaces/CompVis/stable-diffusion-license) licence. The LCM LoRA is under OpenRAIL++. The models are not included in the plugin. You download it yourself from its model page. Its licence sets use restrictions, which in summary:
- **Allowed:** using the model to make images, including images for commercial work, under the licence's terms.
- **Not allowed:** using the model to make illegal or harmful content, or content that breaks the restrictions listed in the licence. The licence also covers what you may not do with the model itself.
- **If you share the model or a modified copy:** you must pass these restrictions on to the people you give it to, and include a copy of the licence.

Read the full licence on each model page before you use the models: https://huggingface.co/75dhsx/jjhuang and https://huggingface.co/latent-consistency/lcm-lora-sdv1-5

**IngeTrazo: GPL-3.0-or-later** (its author, Marco Sumari Tellez, confirmed this). Lite Bridge runs inside IngeTrazo.

**Real-ESRGAN x4plus upscaler:** its weights are listed as BSD-3-Clause, from https://github.com/xinntao/Real-ESRGAN. Check the licence file in that repository before you publish.

**ComfyUI: GPL-3.0.** It's installed separately and isn't included.

This summary is not legal advice. Check the licence texts yourself, and have a lawyer confirm them before you publish the plugin or use it in a commercial product.
