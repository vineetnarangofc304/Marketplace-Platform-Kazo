"""Assemble final video by combining slides + audio segments with fades."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/app/marketing")
SLIDES = ROOT / "slides"
AUDIO = ROOT / "audio"
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)
TMP = ROOT / "tmp_segments"
TMP.mkdir(parents=True, exist_ok=True)

FINAL = OUT / "fundle_finance_os.mp4"

W, H = 1920, 1080
FPS = 30
FADE = 0.5


def ffprobe_duration(p):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def build_segment(seg_id, dur, is_first, is_last):
    """Render a single slide+audio pair to a segment .mp4 with fade in/out."""
    slide = SLIDES / f"{seg_id}.png"
    audio = AUDIO / f"{seg_id}.mp3"
    out = TMP / f"{seg_id}.mp4"

    # Video filter: fade-in at start, fade-out at end
    fades = []
    if is_first:
        fades.append(f"fade=t=in:st=0:d={FADE}")
    else:
        fades.append(f"fade=t=in:st=0:d=0.25")
    fade_out_start = max(0.1, dur - FADE)
    fades.append(f"fade=t=out:st={fade_out_start}:d={FADE}")
    vf = ",".join(fades)

    # Audio filter: mild fade to prevent clicks
    a_fade_out = max(0.1, dur - 0.35)
    af = f"afade=t=in:st=0:d=0.15,afade=t=out:st={a_fade_out}:d=0.35"

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(slide),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-vf", vf,
        "-c:a", "aac", "-b:a", "192k",
        "-af", af,
        "-t", f"{dur:.3f}",
        "-movflags", "+faststart",
        str(out),
    ]
    print(f"  → {seg_id} ({dur:.1f}s)")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG FAILED:", r.stderr[-2000:])
        sys.exit(1)


def main():
    narr = json.loads((ROOT / "scripts" / "narration.json").read_text())
    segs = narr["segments"]

    print(f"Building {len(segs)} segments...")
    total = 0.0
    for i, s in enumerate(segs):
        dur = ffprobe_duration(AUDIO / f"{s['id']}.mp3")
        # Add small tail buffer so voice doesn't cut
        dur = dur + 0.6
        s["_out_duration"] = dur
        total += dur
        build_segment(s["id"], dur, i == 0, i == len(segs) - 1)

    print(f"\nTotal video duration: {total:.1f}s ({total/60:.2f} min)")

    # Concat via concat demuxer
    concat_file = TMP / "concat.txt"
    concat_file.write_text("\n".join(f"file '{TMP / (s['id'] + '.mp4')}'" for s in segs))

    print("\nConcatenating...")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", "-movflags", "+faststart", str(FINAL),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("CONCAT FAILED:", r.stderr[-2000:])
        sys.exit(1)

    size_mb = FINAL.stat().st_size / (1024 * 1024)
    dur = ffprobe_duration(FINAL)
    print(f"\n✅ FINAL: {FINAL}")
    print(f"   Size: {size_mb:.1f} MB")
    print(f"   Duration: {dur:.1f}s ({dur/60:.2f} min)")


if __name__ == "__main__":
    main()
