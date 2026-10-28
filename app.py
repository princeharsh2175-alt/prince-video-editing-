
import os
import asyncio
import shutil
import subprocess
import uuid
from pathlib import Path

import edge_tts
from flask import Flask, request, jsonify, send_from_directory, render_template_string

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024

BASE = Path(__file__).resolve().parent
DATA = BASE / "video_editor_files"
UPLOADS = DATA / "uploads"
EXPORTS = DATA / "exports"
TEMP = DATA / "temp"

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
VOICE = "hi-IN-SwaraNeural"

for folder in (UPLOADS, EXPORTS, TEMP):
    folder.mkdir(parents=True, exist_ok=True)

HTML = r"""
<!doctype html>
<html lang="hi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prince Studio</title>
<style>
:root {
 --bg:#0b1020;--panel:#141d32;--line:#2e3d59;
 --teal:#42e8d5;--text:#edf4ff;--muted:#a9bad5;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:Arial,sans-serif}
header{padding:22px;background:#10172a;border-bottom:1px solid var(--line)}
header h1{margin:0;color:var(--teal);font-size:30px}
header p{color:var(--muted);margin-bottom:0}
main{max-width:1400px;margin:auto;padding:18px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:15px;padding:18px;margin-bottom:18px;min-width:0}
h2{font-size:19px;margin-top:0}
label{display:block;margin:12px 0 6px;color:#bcd0ed}
input,textarea,select{width:100%;padding:10px;border-radius:8px;border:1px solid #405473;background:#0c1426;color:white}
textarea{min-height:100px;resize:vertical}
button,.download{border:0;border-radius:9px;padding:11px 14px;font-weight:bold;cursor:pointer;display:inline-block;margin:5px 3px 5px 0}
button:disabled{opacity:.5;cursor:wait}
.primary{background:var(--teal);color:#071323}
.secondary{background:#293955;color:white}
.danger{background:#713449;color:white}
.download{background:var(--teal);color:#071323;text-decoration:none}
video{width:100%;max-height:460px;background:black;margin-top:12px}
.status{padding:12px;background:#0c1426;border-radius:8px;color:#bcd0ed;white-space:pre-wrap;overflow-wrap:anywhere}
.grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:18px}
.tablewrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:650px}
th,td{padding:8px;border-bottom:1px solid var(--line);text-align:left}
th{color:var(--teal)}
td input,td textarea{min-width:70px}
.small{font-size:12px;color:var(--muted);line-height:1.5}
.check{display:flex;gap:8px;align-items:center}
.check input{width:auto}
@media(max-width:850px){.grid{grid-template-columns:1fr}main{padding:10px}}
</style>
</head>
<body>
<header>
 <h1>▶ Prince Studio</h1>
 <p>Video Editor · Hindi Lyrics · Female AI Voice · Timed Captions · MP4 Export</p>
</header>

<main>
<section class="panel">
 <h2>01. 🎬 वीडियो अपलोड करें</h2>
 <input id="videoFile" type="file" accept="video/*">
 <video id="video" controls playsinline></video>
 <p id="videoInfo" class="status">अभी कोई वीडियो नहीं चुनी गई है।</p>
 <button class="primary" id="playBtn">▶ वीडियो चलाएं</button>
 <button class="secondary" id="pauseBtn">⏸ रोकें</button>
</section>

<div class="grid">
<section class="panel">
 <h2>02. 📝 Lyrics टाइमलाइन</h2>
 <label for="lyrics">हर लाइन को नई पंक्ति में लिखें</label>
 <textarea id="lyrics" placeholder="पहली लाइन&#10;दूसरी लाइन&#10;तीसरी लाइन"></textarea>
 <button class="primary" id="makeLines">Lyrics टाइमलाइन बनाएं</button>
 <button class="secondary" id="addLine">+ लाइन जोड़ें</button>

 <div class="tablewrap">
 <table>
 <thead><tr><th>#</th><th>Lyrics</th><th>Start (सेकंड)</th><th>End (सेकंड)</th><th>सुनें</th><th>हटाएं</th></tr></thead>
 <tbody id="lyricsRows"><tr><td colspan="6">पहले Lyrics लिखें।</td></tr></tbody>
 </table>
 </div>
 <p id="lineInfo" class="status">कोई Lyrics लाइन नहीं बनी है।</p>
</section>

<section class="panel">
 <h2>03. 🗣️ हिंदी Voice Studio</h2>
 <label for="voice">MP4 के लिए महिला AI आवाज़</label>
 <select id="voice">
  <option value="hi-IN-SwaraNeural">Swara — Hindi Female</option>
 </select>

 <label for="rate">बोलने की गति</label>
 <input id="rate" type="range" min="0.7" max="1.3" step="0.1" value="1">
 <p id="rateLabel">1.0x</p>
 <button class="primary" id="testVoice">🔊 ब्राउज़र आवाज़ टेस्ट</button>
 <p class="small">ब्राउज़र टेस्ट में Chrome की उपलब्ध हिंदी आवाज़ इस्तेमाल होगी। MP4 में ऑनलाइन AI महिला आवाज़ बनेगी। इंटरनेट जरूरी है।</p>

 <h2 style="margin-top:22px">04. 🎞️ Export Settings</h2>
 <label class="check"><input type="checkbox" id="keepOriginal" checked> मूल वीडियो की आवाज़ भी रखें</label>
 <label class="check"><input type="checkbox" id="burnCaptions" checked> वीडियो पर Lyrics दिखाएं</label>
 <label for="fontSize">Lyrics का आकार</label>
 <input id="fontSize" type="range" min="18" max="54" value="32">
 <button class="primary" id="exportBtn">⬇ आवाज़ सहित MP4 बनाएं</button>
 <a id="download" class="download" href="#" style="display:none">⬇ MP4 डाउनलोड करें</a>
 <p id="status" class="status">वीडियो अपलोड करें, Lyrics टाइमलाइन बनाएं और Export दबाएं।</p>
</section>
</div>
</main>

<script>
const $ = id => document.getElementById(id);
let rows = [], videoId = null, localURL = null;
let browserVoices = [];
const video = $("video");

$("rate").oninput = () => {
 $("rateLabel").textContent = Number($("rate").value).toFixed(1) + "x";
};

$("videoFile").onchange = async e => {
 const file = e.target.files[0];
 if (!file) return;

 videoId = null;
 $("download").style.display = "none";

 if (localURL) URL.revokeObjectURL(localURL);
 localURL = URL.createObjectURL(file);
 video.src = localURL;
 $("videoInfo").textContent = "वीडियो अपलोड हो रही है...";
 $("status").textContent = "कृपया अपलोड पूरा होने दें।";

 const form = new FormData();
 form.append("video", file);

 try {
  const res = await fetch("/upload", {method:"POST", body:form});
  const data = await res.json();
  if (!res.ok) throw Error(data.error || "Upload failed");

  videoId = data.id;
  $("videoInfo").textContent = "अपलोड पूरी: " + file.name;
  $("status").textContent = "अब Lyrics टाइमलाइन बनाएं।";
 } catch (err) {
  $("videoInfo").textContent = "Upload Error: " + err.message;
  $("status").textContent = "वीडियो अपलोड नहीं हुई। दोबारा कोशिश करें।";
 }
};

$("playBtn").onclick = () => video.play().catch(() => {});
$("pauseBtn").onclick = () => video.pause();

function renderLines() {
 const body = $("lyricsRows");
 body.innerHTML = "";

 if (!rows.length) {
  body.innerHTML = "<tr><td colspan='6'>पहले Lyrics लिखें।</td></tr>";
  $("lineInfo").textContent = "कोई Lyrics लाइन नहीं है।";
  return;
 }

 rows.forEach((r, i) => {
  const tr = document.createElement("tr");

  const number = document.createElement("td");
  number.textContent = i + 1;
  tr.appendChild(number);

  const textCell = document.createElement("td");
  const text = document.createElement("textarea");
  text.rows = 2;
  text.value = r.text;
  text.oninput = () => rows[i].text = text.value;
  textCell.appendChild(text);
  tr.appendChild(textCell);

  ["start","end"].forEach(key => {
   const td = document.createElement("td");
   const input = document.createElement("input");
   input.type = "number";
   input.min = 0;
   input.step = "0.1";
   input.value = r[key];
   input.onchange = () => rows[i][key] = Number(input.value);
   td.appendChild(input);
   tr.appendChild(td);
  });

  const listenCell = document.createElement("td");
  const listen = document.createElement("button");
  listen.className = "primary";
  listen.textContent = "▶";
  listen.onclick = () => browserSpeak(r.text);
  listenCell.appendChild(listen);
  tr.appendChild(listenCell);

  const deleteCell = document.createElement("td");
  const del = document.createElement("button");
  del.className = "danger";
  del.textContent = "✕";
  del.onclick = () => {
   rows.splice(i, 1);
   renderLines();
  };
  deleteCell.appendChild(del);
  tr.appendChild(deleteCell);

  body.appendChild(tr);
 });

 $("lineInfo").textContent = rows.length + " Lyrics लाइनें तैयार हैं।";
}

$("makeLines").onclick = () => {
 const text = $("lyrics").value.trim();
 if (!text) return alert("पहले Lyrics लिखें।");

 rows = text.split(/\r?\n/)
  .map(s => s.trim())
  .filter(Boolean)
  .map((text, i) => ({text, start:i*4, end:i*4+4}));

 renderLines();
};

$("addLine").onclick = () => {
 const start = rows.length ? Number(rows[rows.length - 1].end) : 0;
 rows.push({text:"नई Lyrics लाइन", start, end:start + 4});
 renderLines();
};

function loadVoices() {
 if ("speechSynthesis" in window) {
  browserVoices = speechSynthesis.getVoices();
 }
}

if ("speechSynthesis" in window) {
 loadVoices();
 speechSynthesis.onvoiceschanged = loadVoices;
}

function browserSpeak(text) {
 if (!("speechSynthesis" in window)) {
  return alert("इस ब्राउज़र में आवाज़ उपलब्ध नहीं है।");
 }

 speechSynthesis.cancel();

 const utterance = new SpeechSynthesisUtterance(text);
 utterance.lang = "hi-IN";
 utterance.rate = Number($("rate").value);

 const hindiVoice = browserVoices.find(
  v => v.lang.toLowerCase().startsWith("hi")
 );

 if (hindiVoice) utterance.voice = hindiVoice;
 speechSynthesis.speak(utterance);
}

$("testVoice").onclick = () => {
 browserSpeak("नमस्ते, यह हिंदी आवाज़ का टेस्ट है।");
};

$("exportBtn").onclick = async () => {
 if (!videoId) return alert("पहले वीडियो अपलोड होने दें।");
 if (!rows.length) return alert("पहले Lyrics टाइमलाइन बनाएं।");

 for (const r of rows) {
  if (!String(r.text).trim()) {
   return alert("Lyrics की कोई लाइन खाली है।");
  }

  if (!Number.isFinite(Number(r.start)) ||
      !Number.isFinite(Number(r.end)) ||
      Number(r.start) < 0 ||
      Number(r.end) <= Number(r.start)) {
   return alert("हर लाइन का End Time, Start Time से बड़ा होना चाहिए।");
  }
 }

 $("exportBtn").disabled = true;
 $("download").style.display = "none";
 $("status").textContent = "AI आवाज़ बन रही है और वीडियो तैयार हो रही है। इसमें समय लग सकता है...";

 try {
  const payload = {
   id: videoId,
   rows,
   voice: $("voice").value,
   rate: Number($("rate").value),
   keepOriginal: $("keepOriginal").checked,
   burnCaptions: $("burnCaptions").checked,
   fontSize: Number($("fontSize").value)
  };

  const res = await fetch("/export", {
   method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify(payload)
  });

  const data = await res.json();
  if (!res.ok) throw Error(data.error || "Export failed");

  $("status").textContent = "MP4 तैयार है! Download दबाएं।";
  $("download").href = data.url;
  $("download").style.display = "inline-block";
 } catch (err) {
  $("status").textContent = "Export Error:\n" + err.message;
 } finally {
  $("exportBtn").disabled = false;
 }
};
</script>
</body>
</html>
"""


def run_command(command, cwd=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if result.returncode:
        message = result.stderr or result.stdout or "Command failed"
        raise RuntimeError(message[-4000:])
    return result


def srt_time(seconds):
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


async def make_voice(text, voice, rate, output_path):
    percent = round((rate - 1) * 100)
    rate_text = f"{percent:+d}%"

    await edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate_text
    ).save(str(output_path))


def video_has_audio(video_file):
    """Check whether the uploaded video contains an audio stream."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(video_file)
        ],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            "वीडियो जाँच नहीं हो सकी। FFprobe/FFmpeg इंस्टॉल होने की जाँच करें।"
        )
    return bool(result.stdout.strip())


@app.get("/")
def home():
    return render_template_string(HTML)


@app.get("/health")
def health():
    return jsonify(status="ok", app="Prince Studio")


@app.post("/upload")
def upload():
    file = request.files.get("video")

    if not file or not file.filename:
        return jsonify(error="वीडियो फ़ाइल नहीं मिली।"), 400

    suffix = Path(file.filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        return jsonify(
            error="यह फ़ॉर्मेट सपोर्ट नहीं है। MP4, MOV, MKV, AVI, WEBM या M4V चुनें।"
        ), 400

    name = uuid.uuid4().hex + suffix

    try:
        file.save(UPLOADS / name)
    except Exception as error:
        return jsonify(error=f"वीडियो सेव नहीं हुई: {error}"), 500

    return jsonify(id=name)


@app.post("/export")
def export():
    data = request.get_json(silent=True) or {}

    video_id = Path(str(data.get("id", ""))).name
    video_file = UPLOADS / video_id

    if not video_id or not video_file.is_file():
        return jsonify(error="वीडियो नहीं मिली। दोबारा अपलोड करें।"), 400

    rows = data.get("rows", [])

    if not isinstance(rows, list) or not rows:
        return jsonify(error="पहले Lyrics टाइमलाइन बनाएं।"), 400

    try:
        rate = float(data.get("rate", 1))
        rate = max(0.7, min(1.3, rate))
        keep_original = data.get("keepOriginal", True) is True
        captions = data.get("burnCaptions", True) is True
        font_size = int(data.get("fontSize", 32))
        font_size = max(18, min(54, font_size))

        clean = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            text = str(row.get("text", "")).strip()
            if not text:
                continue

            start = float(row.get("start", 0))
            end = float(row.get("end", 0))

            if start < 0 or end <= start:
                raise ValueError(f"गलत टाइमिंग: {text}")

            clean.append({
                "text": text,
                "start": start,
                "end": end
            })

        if not clean:
            raise ValueError("Lyrics खाली हैं।")

        clean.sort(key=lambda item: item["start"])

    except (ValueError, TypeError) as error:
        return jsonify(error=f"इनपुट की जाँच करें: {error}"), 400

    job_id = uuid.uuid4().hex
    job = TEMP / job_id
    job.mkdir(parents=True, exist_ok=True)

    output_name = f"PrinceStudio_{job_id[:8]}.mp4"
    output_file = EXPORTS / output_name

    try:
        has_audio = video_has_audio(video_file)

        audio_paths = []

        for i, item in enumerate(clean):
            audio = job / f"line_{i:03}.mp3"

            asyncio.run(
                make_voice(
                    item["text"],
                    VOICE,
                    rate,
                    audio
                )
            )

            if not audio.is_file() or audio.stat().st_size == 0:
                raise RuntimeError("AI आवाज़ की फ़ाइल नहीं बन सकी।")

            audio_paths.append(audio)

        if captions:
            with (job / "lyrics.srt").open(
                "w", encoding="utf-8-sig"
            ) as srt:
                for i, item in enumerate(clean, 1):
                    srt.write(
                        f"{i}\n"
                        f"{srt_time(item['start'])} --> "
                        f"{srt_time(item['end'])}\n"
                        f"{item['text']}\n\n"
                    )

        command = ["ffmpeg", "-y", "-i", str(video_file)]

        for audio in audio_paths:
            command.extend(["-i", str(audio)])

        filters = []
        voice_labels = []

        for i, item in enumerate(clean):
            delay = round(item["start"] * 1000)
            label = f"v{i}"

            filters.append(
                f"[{i + 1}:a]adelay={delay}|{delay}[{label}]"
            )
            voice_labels.append(f"[{label}]")

        filters.append(
            "".join(voice_labels)
            + f"amix=inputs={len(voice_labels)}:"
              "duration=longest:normalize=0,apad[tts]"
        )

        if keep_original and has_audio:
            filters.append("[0:a:0]volume=0.25,apad[orig]")
            filters.append(
                "[orig][tts]amix=inputs=2:"
                "duration=longest:normalize=0[aout]"
            )
        else:
            filters.append("[tts]anull[aout]")

        command.extend([
            "-filter_complex", ";".join(filters),
            "-map", "0:v:0",
            "-map", "[aout]"
        ])

        if captions:
            style = (
                f"FontName=Noto Sans Devanagari,FontSize={font_size},"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=35"
            )

            subtitle_filter = (
                "subtitles=lyrics.srt:"
                f"force_style='{style}'"
            )

            command.extend(["-vf", subtitle_filter])

        command.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-shortest",
            str(output_file)
        ])

        run_command(command, cwd=str(job))

        if not output_file.is_file() or output_file.stat().st_size == 0:
            raise RuntimeError("MP4 फ़ाइल तैयार नहीं हुई।")

        return jsonify(
            url=f"/download/{output_name}",
            filename=output_name
        )

    except Exception as error:
        output_file.unlink(missing_ok=True)
        return jsonify(error=str(error)), 500

    finally:
        shutil.rmtree(job, ignore_errors=True)


@app.get("/download/<path:name>")
def download(name):
    safe_name = Path(name).name
    file_path = EXPORTS / safe_name

    if not file_path.is_file():
        return jsonify(error="यह MP4 फ़ाइल नहीं मिली। दोबारा Export करें।"), 404

    return send_from_directory(
        EXPORTS,
        safe_name,
        as_attachment=True
    )


if __name__ == "__main__":
    print("Prince Studio chal raha hai.")
    print("Browser mein kholen: http://127.0.0.1:10000")
    print("Band karne ke liye CMD mein Ctrl+C dabayen.")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        debug=False
    )
