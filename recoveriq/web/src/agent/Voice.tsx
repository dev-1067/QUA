import clsx from "clsx";
import { Mic, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const SR: any = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
const LOCALE: Record<string, string> = { hi: "hi-IN", mr: "mr-IN", en: "en-IN" };

/** Records audio (MediaRecorder) and, where the browser supports it, transcribes live in Hindi,
 * Marathi or English (Web Speech API). The transcript stays editable before saving. */
export function VoiceCapture({ language, text, setText, onAudio }: {
  language: string; text: string; setText: (s: string) => void; onAudio: (b: Blob | null) => void;
}) {
  const [rec, setRec] = useState(false);
  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [interim, setInterim] = useState("");
  const mr = useRef<MediaRecorder | null>(null);
  const sr = useRef<any>(null);
  const chunks = useRef<Blob[]>([]);
  const base = useRef("");
  const timer = useRef<number>();

  useEffect(() => () => stop(), []); // eslint-disable-line

  const start = async () => {
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const m = new MediaRecorder(stream);
      chunks.current = [];
      m.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      m.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        onAudio(chunks.current.length ? new Blob(chunks.current, { type: m.mimeType || "audio/webm" }) : null);
      };
      m.start();
      mr.current = m;
    } catch {
      setErr("Microphone not available. You can still type the note.");
      return;
    }
    if (SR) {
      try {
        const r = new SR();
        r.lang = LOCALE[language] ?? "en-IN";
        r.continuous = true;
        r.interimResults = true;
        base.current = text ? text.trim() + " " : "";
        r.onresult = (e: any) => {
          let fin = "", tmp = "";
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const t = e.results[i][0].transcript;
            e.results[i].isFinal ? (fin += t) : (tmp += t);
          }
          if (fin) { base.current += fin.trim() + " "; setText(base.current.trim()); }
          setInterim(tmp);
        };
        r.onerror = (e: any) => { if (e.error !== "no-speech" && e.error !== "aborted") setErr(`Speech-to-text: ${e.error}. Recording continues; type the transcript.`); };
        r.start();
        sr.current = r;
      } catch { /* transcription optional */ }
    } else {
      setErr("This browser has no built-in speech-to-text. Audio is recorded; please type the transcript.");
    }
    setSecs(0);
    timer.current = window.setInterval(() => setSecs((s) => {
      if (s >= 59) { stop(); return s; }
      return s + 1;
    }), 1000);
    setRec(true);
  };

  function stop() {
    clearInterval(timer.current);
    try { sr.current?.stop(); } catch { /* ignore */ }
    try { if (mr.current?.state === "recording") mr.current.stop(); } catch { /* ignore */ }
    sr.current = null; mr.current = null;
    setInterim("");
    setRec(false);
  }

  return (
    <div>
      <div className="flex items-center gap-3">
        <button type="button" onClick={rec ? stop : start}
          className={clsx("h-12 w-12 rounded-full flex items-center justify-center text-white shrink-0 transition active:scale-95",
            rec ? "bg-bad shadow-[0_0_0_6px_rgb(var(--bad)/0.15)]" : "bg-brand")} aria-label={rec ? "Stop recording" : "Start recording"}>
          {rec ? <Square size={18} fill="currentColor" /> : <Mic size={20} />}
        </button>
        <div className="text-[12.5px] leading-5">
          {rec ? <span className="text-bad font-medium num">● Recording 0:{String(secs).padStart(2, "0")} · speak in {LOCALE[language]}</span>
            : <span className="text-muted">Tap to record up to 60 s. Live transcript in {LOCALE[language]} where supported.</span>}
        </div>
      </div>
      {interim && <div className="mt-2 text-[13px] text-muted italic animate-fade">{interim}…</div>}
      {err && <div className="mt-2 text-[12px] text-warn">{err}</div>}
    </div>
  );
}
