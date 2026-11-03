"""Builds title cards and captions, then cuts each recorded scene to its voice-over and joins
everything into RecoverIQ_Demo.mp4."""
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
WORK = HERE / "work"
CARDS = WORK / "cards"
SEGS = WORK / "segments"
CARDS.mkdir(parents=True, exist_ok=True)
SEGS.mkdir(parents=True, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()
TIMING = json.loads((WORK / "timing.json").read_text(encoding="utf-8"))
STATE = json.loads((WORK / "state.json").read_text())
W, H = 1920, 1080
PINE, PINE2, MINT, TEXT, MUTED = (16, 32, 27), (9, 20, 17), (45, 212, 191), (240, 245, 242), (150, 180, 170)
F = "C:/Windows/Fonts/"


def font(size, weight="regular"):
    name = {"bold": "segoeuib.ttf", "semi": "seguisb.ttf", "regular": "segoeui.ttf", "mono": "consola.ttf"}[weight]
    return ImageFont.truetype(F + name, size)


def background():
    img = Image.new("RGB", (W, H), PINE)
    px = img.load()
    for y in range(H):  # vertical gradient + soft teal glow top-left
        for x in range(0, W, 1):
            t = y / H
            g = max(0.0, 1 - ((x / W) ** 2 + (y / H) ** 2) * 1.6)
            r = int(PINE[0] * (1 - t) + PINE2[0] * t + 20 * g)
            gg = int(PINE[1] * (1 - t) + PINE2[1] * t + 60 * g)
            b = int(PINE[2] * (1 - t) + PINE2[2] * t + 50 * g)
            px[x, y] = (r, gg, b)
    d = ImageDraw.Draw(img)
    for i in range(9):  # faint concentric rings, bottom-right
        r = 140 + i * 70
        d.ellipse([W - 260 - r, H - 120 - r, W - 260 + r, H - 120 + r], outline=(34, 56, 49), width=2)
    return img


def logo(d, x, y, size=46):
    d.rounded_rectangle([x, y, x + size, y + size], radius=size * 0.24, fill=(244, 239, 227))
    d.text((x + size * 0.5, y + size * 0.52), "R", font=font(int(size * 0.62), "bold"), fill=PINE, anchor="mm")
    d.ellipse([x + size * 0.70, y + size * 0.14, x + size * 0.88, y + size * 0.32], fill=MINT)
    f = font(int(size * 0.62), "bold")
    d.text((x + size + 18, y + size * 0.52), "Recover", font=f, fill=TEXT, anchor="lm")
    w = d.textlength("Recover", font=f)
    d.text((x + size + 18 + w, y + size * 0.52), "IQ", font=f, fill=MINT, anchor="lm")


def card(path, draw_fn):
    img = background()
    d = ImageDraw.Draw(img)
    logo(d, 120, 100)
    draw_fn(d)
    img.save(path)


def intro_a(d):
    d.text((120, 300), "THE PROBLEM", font=font(30, "bold"), fill=MINT)
    d.text((120, 350), "300 overdue loans.", font=font(104, "bold"), fill=TEXT)
    d.text((120, 480), "No idea which 20 matter.", font=font(104, "bold"), fill=(170, 200, 190))
    for i, line in enumerate(["Field visits nobody can verify", "Promises lost in notebooks",
                              "Payments marked paid before the money arrives"]):
        y = 700 + i * 70
        d.ellipse([124, y + 14, 140, y + 30], fill=(194, 65, 12))
        d.text((165, y), line, font=font(40), fill=MUTED)


def intro_b(d):
    d.text((120, 330), "QUASAR 5.0  ·  PS-01 FINTECH  ·  AI-POWERED DEBT COLLECTIONS", font=font(30, "bold"), fill=MINT)
    d.text((120, 390), "One case. One trail.", font=font(120, "bold"), fill=TEXT)
    d.text((120, 535), "Full visibility.", font=font(120, "bold"), fill=MINT)
    d.text((120, 730), "Score every overdue account with reasons, work it offline in the field,",
           font=font(40), fill=MUTED)
    d.text((120, 785), "and mark it paid only when the payment gateway confirms.", font=font(40), fill=MUTED)


def outro_a(d):
    d.text((120, 270), "WHAT'S BUILT", font=font(30, "bold"), fill=MINT)
    stats = [("18 / 18", "essential requirements"), ("27", "automated tests passing"),
             ("34", "browser test steps passing"), ("0", "payments marked paid without the gateway")]
    for i, (k, v) in enumerate(stats):
        x, y = 120 + (i % 2) * 820, 340 + (i // 2) * 250
        d.rounded_rectangle([x, y, x + 760, y + 210], radius=28, fill=(24, 44, 38))
        d.text((x + 44, y + 30), k, font=font(92, "bold"), fill=MINT)
        d.text((x + 44, y + 145), v, font=font(36), fill=TEXT)
    d.text((120, 880), "github.com/dev-1067/QUA", font=font(40, "mono"), fill=TEXT)
    d.text((120, 940), "Run it:  python run.py", font=font(34, "mono"), fill=MUTED)


def outro_b(d):
    d.text((120, 400), "One case. One trail.", font=font(120, "bold"), fill=TEXT)
    d.text((120, 545), "Full visibility.", font=font(120, "bold"), fill=MINT)
    d.text((120, 760), "Thank you.", font=font(56, "semi"), fill=MUTED)
    d.text((120, 940), "RecoverIQ  ·  QUASAR 5.0  ·  PS-01 Fintech", font=font(32), fill=MUTED)


CAPTIONS = {
    "s01_dashboard": "Manager dashboard", "s02_intake": "Case intake  ·  one case per account",
    "s03_case": "Explainable risk score", "s04_rules": "Versioned routing rules", "s05_allocation": "Allocation & workload",
    "s06_agent": "Field agent app  ·  works offline", "s07_fieldmap": "Live field map  ·  GPS verification",
    "s08_qr": "Collect payment", "s09_borrower": "Borrower pays  ·  gateway confirms", "s10_paid": "Payment truth  ·  no double posting",
    "s11_compliance": "Compliance by design  ·  8 AM to 7 PM", "s12_audit": "Tamper-evident audit trail",
    "s13_promises": "Promises & escalations", "s14_insight": "Sentiment, leaderboard & learning loop",
}


def caption(path, text, n):
    f = font(30, "semi")
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    num = f"{n:02d}"
    w = int(tmp.textlength(text, font=f)) + 130
    img = Image.new("RGBA", (w, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, 63], radius=32, fill=(16, 32, 27, 232))
    d.ellipse([10, 10, 54, 54], fill=MINT)
    d.text((32, 33), num, font=font(22, "bold"), fill=PINE, anchor="mm")
    d.text((72, 32), text, font=f, fill=(240, 245, 242, 255), anchor="lm")
    img.save(path)


def run(args):
    r = subprocess.run([FF, "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-1500:])


ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def card_segment(name, a, b, out):
    t = TIMING[name]
    t1 = t["cues"][next(iter(t["cues"]))]
    total = t["duration"] + 1.2
    t2 = total - t1 + 0.6
    run(["-loop", "1", "-t", f"{t1 + 0.6:.2f}", "-i", str(a), "-loop", "1", "-t", f"{t2:.2f}", "-i", str(b), "-i", t["audio"],
         "-filter_complex",
         f"[0:v]scale={W}:{H},setsar=1,fps=30[a];[1:v]scale={W}:{H},setsar=1,fps=30[b];"
         f"[a][b]xfade=transition=fade:duration=0.6:offset={t1:.2f},fade=t=in:st=0:d=0.5,fade=t=out:st={total - 0.5:.2f}:d=0.5[v];"
         f"[2:a]adelay=200|200,apad,atrim=0:{total:.2f},afade=t=out:st={total - 0.4:.2f}:d=0.4[aud]",
         "-map", "[v]", "-map", "[aud]", "-t", f"{total:.2f}", *ENC, str(out)])


def app_segment(name, n, out):
    t, seg = TIMING[name], STATE["segments"][name]
    length = max(seg["length"], t["duration"] + 0.6)
    cap = CARDS / f"cap_{name}.png"
    caption(cap, CAPTIONS[name], n)
    run(["-ss", f"{seg['offset']:.2f}", "-t", f"{length:.2f}", "-i", str(WORK / "rec" / f"{name}.webm"), "-i", t["audio"],
         "-i", str(cap), "-filter_complex",
         f"[0:v]fps=30,crop=1536:864:0:0,scale={W}:{H}:flags=lanczos,setsar=1,tpad=stop_mode=clone:stop_duration=2[v0];"
         f"[v0][2:v]overlay=48:H-h-44,fade=t=in:st=0:d=0.35,fade=t=out:st={length - 0.4:.2f}:d=0.4[v];"
         f"[1:a]adelay=150|150,apad,atrim=0:{length:.2f},afade=t=out:st={length - 0.3:.2f}:d=0.3[aud]",
         "-map", "[v]", "-map", "[aud]", "-t", f"{length:.2f}", *ENC, str(out)])


def main():
    card(CARDS / "intro_a.png", intro_a)
    card(CARDS / "intro_b.png", intro_b)
    card(CARDS / "outro_a.png", outro_a)
    card(CARDS / "outro_b.png", outro_b)
    parts = []
    out = SEGS / "s00_intro.mp4"
    card_segment("s00_intro", CARDS / "intro_a.png", CARDS / "intro_b.png", out)
    parts.append(out)
    for n, name in enumerate(CAPTIONS, start=1):
        out = SEGS / f"{name}.mp4"
        app_segment(name, n, out)
        parts.append(out)
        print("segment", name)
    out = SEGS / "s15_outro.mp4"
    card_segment("s15_outro", CARDS / "outro_a.png", CARDS / "outro_b.png", out)
    parts.append(out)
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    final = HERE / "RecoverIQ_Demo.mp4"
    run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)])
    print("wrote", final)


if __name__ == "__main__":
    main()
