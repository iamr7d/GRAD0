"""Generate a synthetic (not a real person) news-presenter portrait for the realistic anchor.

Runs Stable Diffusion 1.5 "Realistic Vision" locally on the GPU (fits in 4 GB at fp16) and writes
candidates to bucket/media/anchor/candidates/; copy the one you like to bucket/media/anchor/anchor.png.
Run it with SadTalker's Python, after:  <venv python> -m pip install diffusers==0.27.2 transformers==4.38.2 accelerate==0.27.2

    C:\\Users\\rahul\\SadTalker\\venv\\Scripts\\python.exe tools\\make_anchor_face.py --n 6 --seed 7
"""
import argparse
from pathlib import Path

import torch
from diffusers import AutoencoderKL, DPMSolverMultistepScheduler, StableDiffusionPipeline

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bucket" / "media" / "anchor" / "candidates"

PROMPT = ("professional studio photograph of a {who} television news anchor, head and shoulders, "
          "facing the camera directly, looking into the lens, calm confident expression, lips closed, "
          "{wear}, soft key light, news studio background softly out of focus with red and blue lights, "
          "85mm lens, sharp focus on the eyes, natural skin texture, high detail")
NEGATIVE = ("cartoon, illustration, 3d render, painting, deformed, disfigured, extra limbs, hands, "
            "open mouth, teeth, glasses, hat, head turned, profile, tilted head, blurry face, watermark, text, logo")
LOOKS = [("female", "navy blazer over a white blouse"), ("male", "dark navy suit, white shirt and red tie")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--steps", type=int, default=30)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=torch.float16)
    pipe = StableDiffusionPipeline.from_pretrained("SG161222/Realistic_Vision_V5.1_noVAE", vae=vae,
                                                   torch_dtype=torch.float16, safety_checker=None)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, use_karras_sigmas=True)
    pipe.enable_attention_slicing()
    pipe.enable_model_cpu_offload()   # keeps peak VRAM low on 4 GB cards
    for i in range(a.n):
        who, wear = LOOKS[i % len(LOOKS)]
        g = torch.Generator("cpu").manual_seed(a.seed + i)
        img = pipe(PROMPT.format(who=who, wear=wear), negative_prompt=NEGATIVE, width=512, height=640,
                   num_inference_steps=a.steps, guidance_scale=5.5, generator=g).images[0]
        p = OUT / f"anchor_{who}_{a.seed + i}.png"
        img.save(p)
        print(p)


if __name__ == "__main__":
    main()
