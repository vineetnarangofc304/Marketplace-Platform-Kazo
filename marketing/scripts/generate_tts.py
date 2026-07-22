"""Generate TTS audio segments using OpenAI TTS via Emergent LLM key."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from emergentintegrations.llm.openai import OpenAITextToSpeech

load_dotenv("/app/backend/.env")

ROOT = Path("/app/marketing")
NARR = json.loads((ROOT / "scripts" / "narration.json").read_text())
OUT = ROOT / "audio"
OUT.mkdir(parents=True, exist_ok=True)


async def main():
    key = os.getenv("EMERGENT_LLM_KEY")
    if not key:
        print("ERROR: EMERGENT_LLM_KEY missing")
        sys.exit(1)
    tts = OpenAITextToSpeech(api_key=key)

    voice = NARR["voice"]
    model = NARR["model"]

    print(f"Generating {len(NARR['segments'])} TTS segments with voice={voice} model={model}")
    for seg in NARR["segments"]:
        seg_id = seg["id"]
        out_mp3 = OUT / f"{seg_id}.mp3"
        if out_mp3.exists() and out_mp3.stat().st_size > 5000:
            print(f"  ✓ {seg_id} already exists ({out_mp3.stat().st_size} bytes) — skip")
            continue
        text = seg["text"]
        print(f"  → {seg_id}: {len(text)} chars ... ", end="", flush=True)
        try:
            audio = await tts.generate_speech(
                text=text, model=model, voice=voice, response_format="mp3", speed=0.98
            )
            out_mp3.write_bytes(audio)
            # get duration
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(out_mp3)],
                capture_output=True, text=True,
            )
            dur = float(r.stdout.strip() or 0)
            print(f"OK ({len(audio)} bytes, {dur:.1f}s)")
            seg["_duration"] = dur
        except Exception as e:
            print(f"FAIL: {e}")
            raise

    # Persist durations back to narration.json (best-effort)
    for seg in NARR["segments"]:
        p = OUT / f"{seg['id']}.mp3"
        if p.exists():
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                capture_output=True, text=True,
            )
            seg["_duration"] = float(r.stdout.strip() or 0)
    (ROOT / "scripts" / "narration.json").write_text(json.dumps(NARR, indent=2))
    total = sum(s.get("_duration", 0) for s in NARR["segments"])
    print(f"\nTotal narration: {total:.1f}s ({total/60:.2f} min)")


if __name__ == "__main__":
    asyncio.run(main())
