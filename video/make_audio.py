"""Generates one voice-over clip per scene with edge-tts and records when each {cue} is spoken.
Writes work/audio/<scene>.mp3 and work/timing.json."""
import asyncio
import json
import re
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

from scenes import RATE, SCENES, VOICE

HERE = Path(__file__).parent
OUT = HERE / "work" / "audio"
OUT.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
CUE = re.compile(r"\{(\w+)\}")


def duration(path: Path) -> float:
    err = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


async def one(name: str, text: str) -> dict:
    # word index (counting spoken words) at which each cue sits
    cues, words, clean_parts = {}, 0, []
    for part in re.split(r"(\{\w+\})", text):
        m = CUE.fullmatch(part)
        if m:
            cues[m.group(1)] = words
        else:
            clean_parts.append(part)
            words += len(re.findall(r"[A-Za-z0-9']+", part))
    clean = "".join(clean_parts)
    comm = edge_tts.Communicate(clean, VOICE, rate=RATE, boundary="WordBoundary")
    path = OUT / f"{name}.mp3"
    bounds = []
    with open(path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                bounds.append(chunk["offset"] / 1e7)
    dur = duration(path)
    times = {}
    for cue, idx in cues.items():
        if bounds:
            times[cue] = round(bounds[min(idx, len(bounds) - 1)], 2) if idx < len(bounds) else round(dur, 2)
        else:
            times[cue] = round(dur * idx / max(words, 1), 2)
    return {"audio": str(path), "duration": round(dur, 2), "cues": times, "text": clean}


async def main():
    timing = {}
    for name, _, text in SCENES:
        for attempt in range(4):
            try:
                timing[name] = await one(name, text)
                break
            except edge_tts.exceptions.NoAudioReceived:
                if attempt == 3:
                    raise
                await asyncio.sleep(3 * (attempt + 1))
        print(f"{name:16s} {timing[name]['duration']:6.1f}s  cues={timing[name]['cues']}")
    (HERE / "work" / "timing.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")
    print("total", round(sum(t["duration"] for t in timing.values()), 1), "s")


asyncio.run(main())
