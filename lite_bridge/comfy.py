"""HTTP calls to the local ComfyUI server, using only the Python standard library.

Plain Python with no Qt dependency.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid


class ComfyError(Exception):
    pass


def _open(req, timeout):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:800]
        raise ComfyError(f"ComfyUI answered HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ComfyError(f"Could not reach ComfyUI: {e.reason}") from e


def get_json(url, timeout=10):
    with _open(urllib.request.Request(url), timeout) as r:
        return json.loads(r.read())


def get_bytes(url, timeout=60):
    with _open(urllib.request.Request(url), timeout) as r:
        return r.read()


def post_json(url, payload, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with _open(req, timeout) as r:
        return json.loads(r.read())


def upload_image(base, path, timeout=60):
    """Upload a PNG to ComfyUI's input folder. Returns the stored file name."""
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        file_bytes = f.read()
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + file_bytes + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
        "true\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    with _open(req, timeout) as r:
        return json.loads(r.read())["name"]


def queue_prompt(base, workflow, client_id=None):
    """Queue a workflow. Returns the prompt id."""
    payload = {"prompt": workflow, "client_id": client_id or uuid.uuid4().hex}
    return post_json(base.rstrip("/") + "/prompt", payload)["prompt_id"]


def history_entry(base, prompt_id):
    """The history entry for a prompt, or None while it is still running"""
    return get_json(base.rstrip("/") + f"/history/{prompt_id}").get(prompt_id)


def interrupt(base):
    """Ask ComfyUI to stop the running prompt"""
    req = urllib.request.Request(base.rstrip("/") + "/interrupt", data=b"{}",
                                 headers={"Content-Type": "application/json"}, method="POST")
    with _open(req, 10):
        return True


def fetch_image(base, image):
    """Download one output image from ComfyUI's output or temp folder"""
    query = urllib.parse.urlencode({
        "filename": image["filename"],
        "subfolder": image.get("subfolder", ""),
        "type": image.get("type", "output"),
    })
    return get_bytes(base.rstrip("/") + f"/view?{query}")


def object_info(base, node):
    """Node definition from ComfyUI. Empty when the node type isn't installed."""
    return get_json(base.rstrip("/") + f"/object_info/{node}")


def system_stats(base):
    return get_json(base.rstrip("/") + "/system_stats", timeout=5)
