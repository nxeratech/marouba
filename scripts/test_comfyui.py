#!/usr/bin/env python3
"""End-to-end ComfyUI API smoke test for Marouba on Windows."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


COMFY_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8001").rstrip("/")
PROMPT_TEXT = "a red apple on a white table"
OUTPUT_DIR = Path(os.environ.get("COMFYUI_OUTPUT_DIR", r"C:\Users\Dave\Documents\ComfyUI\output"))
TIMEOUT_SECONDS = int(os.environ.get("COMFYUI_TEST_TIMEOUT", "600"))
CLIENT_ID = "marouba-comfyui-smoke-test"


def request_json(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{COMFY_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {path}: {body}") from error


def request_bytes(path: str) -> bytes:
    with urllib.request.urlopen(f"{COMFY_URL}{path}", timeout=30) as response:
        return response.read()


def require_option(options: list[str], preferred: list[str], label: str) -> str:
    for value in preferred:
        if value in options:
            return value
    raise RuntimeError(f"No compatible {label} found. Available: {', '.join(options[:20])}")


def list_model_options(object_info: dict) -> tuple[list[str], list[str], list[str]]:
    checkpoints = object_info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    vaes = object_info["VAELoader"]["input"]["required"]["vae_name"][0]
    unets = object_info["UNETLoader"]["input"]["required"]["unet_name"][0]
    return checkpoints, vaes, unets


def print_model_options(object_info: dict) -> None:
    checkpoints, vaes, unets = list_model_options(object_info)
    print("Available checkpoints:")
    for value in checkpoints:
        print(f"  - {value}")
    print("Available VAE models:")
    for value in vaes:
        print(f"  - {value}")
    print("Available UNet models:")
    for value in unets:
        print(f"  - {value}")


def build_procedural_prompt() -> dict:
    return {
        "1": {
            "class_type": "EmptyImage",
            "inputs": {
                "width": 512,
                "height": 512,
                "batch_size": 1,
                "color": 16777215,
            },
        },
        "2": {
            "class_type": "EmptyImage",
            "inputs": {
                "width": 170,
                "height": 150,
                "batch_size": 1,
                "color": 16711680,
            },
        },
        "3": {
            "class_type": "SolidMask",
            "inputs": {
                "value": 1.0,
                "width": 170,
                "height": 150,
            },
        },
        "4": {
            "class_type": "ImageCompositeMasked",
            "inputs": {
                "destination": ["1", 0],
                "source": ["2", 0],
                "x": 171,
                "y": 165,
                "resize_source": False,
                "mask": ["3", 0],
            },
        },
        "5": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["4", 0],
                "filename_prefix": "marouba_red_apple_test",
            },
        },
    }


def build_flux_prompt(object_info: dict) -> dict:
    unets = object_info["UNETLoader"]["input"]["required"]["unet_name"][0]
    clips1 = object_info["DualCLIPLoader"]["input"]["required"]["clip_name1"][0]
    clips2 = object_info["DualCLIPLoader"]["input"]["required"]["clip_name2"][0]
    vaes = object_info["VAELoader"]["input"]["required"]["vae_name"][0]

    unet = require_option(unets, ["flux1-dev.safetensors"], "Flux UNet")
    clip_l = require_option(clips1, ["clip_l.safetensors"], "Flux CLIP-L")
    t5 = require_option(clips2, ["t5xxl_fp16.safetensors"], "Flux T5 text encoder")
    # Prefer pixel_space for this smoke test because safetensors VAE loading on
    # this ComfyUI install currently trips comfy_aimdo's mmap symbol mismatch.
    vae = require_option(vaes, ["pixel_space", "ae.safetensors"], "Flux VAE")

    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": clip_l,
                "clip_name2": t5,
                "type": "flux",
                "device": "default",
            },
        },
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT_TEXT, "clip": ["2", 0]}},
        "4": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["3", 0], "guidance": 3.5}},
        "5": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["4", 0]}},
        "6": {"class_type": "RandomNoise", "inputs": {"noise_seed": 123456789}},
        "7": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "8": {"class_type": "BasicScheduler", "inputs": {"model": ["1", 0], "scheduler": "simple", "steps": 4, "denoise": 1.0}},
        "9": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "10": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["6", 0],
                "guider": ["5", 0],
                "sampler": ["7", 0],
                "sigmas": ["8", 0],
                "latent_image": ["9", 0],
            },
        },
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["11", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "marouba_red_apple_test"}},
    }


def queue_prompt(prompt: dict) -> str:
    response = request_json("POST", "/prompt", {"prompt": prompt, "client_id": CLIENT_ID})
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI did not return prompt_id: {response}")
    return prompt_id


def wait_for_history(prompt_id: str) -> dict:
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        history = request_json("GET", f"/history/{prompt_id}")
        if prompt_id in history:
            return history[prompt_id]
        queue = request_json("GET", "/queue")
        print(f"Waiting for prompt {prompt_id}; queue_running={len(queue.get('queue_running', []))} queue_pending={len(queue.get('queue_pending', []))}")
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")


def find_outputs(history_item: dict) -> list[dict]:
    outputs: list[dict] = []
    for node_output in history_item.get("outputs", {}).values():
        outputs.extend(node_output.get("images", []))
        outputs.extend(node_output.get("gifs", []))
    return outputs


def output_path(item: dict) -> Path:
    filename = item["filename"]
    subfolder = item.get("subfolder") or ""
    return OUTPUT_DIR / subfolder / filename


def verify_output(item: dict) -> Path:
    params = urllib.parse.urlencode(
        {
            "filename": item["filename"],
            "subfolder": item.get("subfolder") or "",
            "type": item.get("type") or "output",
        }
    )
    data = request_bytes(f"/view?{params}")
    if not data:
        raise RuntimeError(f"ComfyUI /view returned empty data for {item}")

    path = output_path(item)
    if not path.exists():
        raise RuntimeError(f"ComfyUI API returned output, but file was not found on disk: {path}")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"Output file exists but is empty: {path}")
    return path


def main() -> int:
    print(f"Connecting to ComfyUI: {COMFY_URL}")
    stats = request_json("GET", "/system_stats")
    print(f"ComfyUI version: {stats.get('system', {}).get('comfyui_version')}")
    print(f"Output directory: {OUTPUT_DIR}")

    object_info = request_json("GET", "/object_info")
    print_model_options(object_info)
    prompt = build_procedural_prompt()
    print(f"Queueing model-free ComfyUI smoke workflow for prompt: {PROMPT_TEXT!r}")
    prompt_id = queue_prompt(prompt)
    print(f"Queued prompt_id: {prompt_id}")

    history_item = wait_for_history(prompt_id)
    status = history_item.get("status", {})
    if status.get("status_str") != "success":
        raise RuntimeError(f"ComfyUI generation failed: {json.dumps(status, indent=2)}")

    outputs = find_outputs(history_item)
    if not outputs:
        raise RuntimeError(f"ComfyUI completed but returned no image outputs for prompt {prompt_id}")

    verified = [verify_output(item) for item in outputs]
    print("Generation completed.")
    for path in verified:
        print(f"Verified output image exists: {path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
