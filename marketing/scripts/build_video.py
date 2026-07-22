"""V2 — Assemble marketing video with animated highlights on product segments.

Story segments (01_hook, 02_solution, 09_cta) → static image + audio + fade
Product segments (03..08) → base composite + animated drawbox/drawtext overlays
                            synced to narration timeline from highlights.json
"""
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
FADE = 0.4
FONT_LABEL = "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"

COLOR = {
    "gold": "0xF0B429",
    "cyan": "0x63B3ED",
    "mint": "0x38D97F",
}

HIGHLIGHTS = json.loads((ROOT / "scripts" / "highlights.json").read_text())


def ffprobe_duration(p):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def build_highlight_filters(hls):
    """Return the sequence of drawbox+drawtext filter strings for one segment.

    ffmpeg (5.x) drawbox does NOT accept expressions in `t` (thickness). So we
    fake a "pulse" by stacking two drawboxes with slightly staggered enable
    windows and different thicknesses.
    """
    filters = []
    for h in hls:
        t0, dur = h["t"], h["d"]
        t1 = t0 + dur
        col = COLOR[h["color"]]
        x, y, w, h_px = h["x"], h["y"], h["w"], h["h"]

        # Outer glow ring (thin, wider rect) — brackets the appearance
        filters.append(
            f"drawbox=x={x-3}:y={y-3}:w={w+6}:h={h_px+6}:color={col}@0.35:t=1:"
            f"enable='between(t,{t0:.2f},{t1:.2f})'"
        )
        # Main border
        filters.append(
            f"drawbox=x={x}:y={y}:w={w}:h={h_px}:color={col}@0.95:t=4:"
            f"enable='between(t,{t0:.2f},{t1:.2f})'"
        )
        # Corner "focus" ticks — solid mini bars
        tick = 22
        thick = 4
        for cx, cy in [(x, y), (x + w - tick, y), (x, y + h_px - tick), (x + w - tick, y + h_px - tick)]:
            filters.append(
                f"drawbox=x={cx}:y={cy}:w={tick}:h={thick}:color={col}:t=fill:"
                f"enable='between(t,{t0:.2f},{t1:.2f})'"
            )
            filters.append(
                f"drawbox=x={cx}:y={cy}:w={thick}:h={tick}:color={col}:t=fill:"
                f"enable='between(t,{t0:.2f},{t1:.2f})'"
            )
        # Label above the box (below if box is near top of frame)
        label = h["label"].replace("'", "").replace(":", " -")
        label_y = max(20, y - 46)
        if y < 100:
            label_y = min(H - 50, y + h_px + 12)
        filters.append(
            f"drawtext=fontfile='{FONT_LABEL}':text='{label}':x={x}:y={label_y}:"
            f"fontsize=26:fontcolor={col}:box=1:boxcolor=0x0B0F17@0.85:boxborderw=8:"
            f"enable='between(t,{t0:.2f},{t1:.2f})'"
        )
    return filters


def build_segment(seg_id, dur, is_first, is_last):
    slide = SLIDES / f"{seg_id}.png"
    audio = AUDIO / f"{seg_id}.mp3"
    out = TMP / f"{seg_id}.mp4"

    # Build filter chain
    vf_parts = []
    # Highlights (only for product segments)
    if seg_id in HIGHLIGHTS:
        vf_parts.extend(build_highlight_filters(HIGHLIGHTS[seg_id]))
    # Fade in/out
    fade_in_dur = FADE if is_first else 0.25
    vf_parts.append(f"fade=t=in:st=0:d={fade_in_dur}")
    fade_out_start = max(0.1, dur - FADE)
    vf_parts.append(f"fade=t=out:st={fade_out_start}:d={FADE}")
    vf = ",".join(vf_parts)

    a_fade_out = max(0.1, dur - 0.35)
    af = f"afade=t=in:st=0:d=0.15,afade=t=out:st={a_fade_out}:d=0.35"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(slide),
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
    print(f"  → {seg_id} ({dur:.1f}s)  highlights={len(HIGHLIGHTS.get(seg_id, []))}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG FAILED for", seg_id)
        print(r.stderr[-2500:])
        sys.exit(1)


def main():
    narr = json.loads((ROOT / "scripts" / "narration.json").read_text())
    segs = narr["segments"]

    print(f"Building {len(segs)} segments...")
    total = 0.0
    for i, s in enumerate(segs):
        dur = ffprobe_duration(AUDIO / f"{s['id']}.mp3") + 0.6
        s["_out_duration"] = dur
        total += dur
        build_segment(s["id"], dur, i == 0, i == len(segs) - 1)

    print(f"\nTotal video duration: {total:.1f}s ({total/60:.2f} min)")

    concat_file = TMP / "concat.txt"
    concat_file.write_text("\n".join(f"file '{TMP / (s['id'] + '.mp4')}'" for s in segs))

    print("\nConcatenating...")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
         "-c", "copy", "-movflags", "+faststart", str(FINAL)],
        capture_output=True, text=True,
    )
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
