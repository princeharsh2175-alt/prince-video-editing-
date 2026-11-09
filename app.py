
import re
import uuid
import time
import asyncio
import threading
import subprocess
import shutil
from pathlib import Path

import edge_tts
from flask import Flask, request, jsonify, send_from_directory, render_template_string

app = Flask(__name__)

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
TEMP = BASE / "temp"

for folder in (UPLOADS, OUTPUTS, TEMP):
    folder.mkdir(exist_ok=True)

jobs = {}

HTML = r"""
<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prince Video Editor</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b1425;color:white;font-family:Arial}
header{padding:20px 5%;background:#14233c}
header h1{margin:0;color:#53e0d4}
header p{color:#b5c5d9}
main{max-width:1250px;margin:22px auto;padding:0 15px}
.layout{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.panel{background:#15243c;border:1px solid #304563;border-radius:14px;padding:18px;margin-bottom:18px}
h2{font-size:19px;color:#5ce0d5;margin-top:0}
label{display:block;font-size:13px;color:#c3d0e1;margin:12px 0 6px}
input,select{width:100%;padding:11px;border-radius:8px;border:1px solid #405675;background:#0d192c;color:white}
input[type=color]{height:42px;padding:3px}
input[type=range]{padding:0}
button{border:0;border-radius:9px;padding:12px 16px;background:#10a99f;color:white;font-weight:bold;cursor:pointer;margin:7px 4px 0 0}
button:disabled{opacity:.5}
.secondary{background:#405675}
.danger{background:#b84b58}
.video-wrap{position:relative;background:#000;border-radius:12px;overflow:hidden;margin-top:14px}
video{width:100%;max-height:430px;display:block}
#lyricsOverlay{position:absolute;left:5%;right:5%;bottom:9%;text-align:center;font-weight:bold;font-size:30px;pointer-events:none;white-space:pre-wrap}
#overlayText{display:inline;padding:5px 12px;border-radius:7px}
.rowline{display:grid;grid-template-columns:65px 65px 1fr 32px;gap:6px;margin:9px 0}
.rowline input{min-width:0;padding:9px}
.rowline button{margin:0;padding:5px}
.progress{height:13px;background:#263955;border-radius:20px;overflow:hidden;margin:12px 0}
#progressBar{height:100%;width:0;background:linear-gradient(90deg,#08a99d,#62e7c8);transition:width .3s}
#status{color:#c5d6e9;font-size:14px;min-height:20px}
.small{font-size:12px;color:#9eafc7;line-height:1.5}
.download{display:inline-block;margin-top:14px;color:#65e8d6;font-weight:bold}
@media(max-width:850px){.layout{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
<h1>🎬 Arti Nova</h1>
<p>Fast Export | Hindi AI Voice | Lyrics Design | MP4 Editor</p>
</header>

<main>
<div class="layout">
<section>
<div class="panel">
<h2>1. Video Upload & Preview</h2>
<input type="file" id="videoFile" accept="video/*">
<div class="video-wrap">
<video id="video" controls playsinline></video>
<div id="lyricsOverlay"><span id="overlayText"></span></div>
</div>
<p class="small">वीडियो चलाकर Lyrics का Preview देखें।</p>
</div>

<div class="panel">
<h2>2. Lyrics Design</h2>
<label>Lyrics Colour</label>
<input type="color" id="fontColor" value="#ffffff">

<label>Background Colour</label>
<input type="color" id="bgColor" value="#000000">

<label>Background Transparency</label>
<input type="range" id="bgOpacity" min="0" max="100" value="55">

<label>Font Size</label>
<input type="range" id="fontSize" min="16" max="60" value="30">

<label>Outline Colour</label>
<input type="color" id="outlineColor" value="#000000">

<label>Lyrics Position</label>
<select id="position">
<option value="bottom">Bottom</option>
<option value="middle">Middle</option>
<option value="top">Top</option>
</select>
</div>
</section>

<section>
<div class="panel">
<h2>3. Lyrics & Timing</h2>
<p class="small">हर लाइन का Start और End Time सेकंड में डालें।</p>
<div id="lyricsRows"></div>
<button onclick="addLine()">+ Add Lyrics Line</button>
<button class="secondary" onclick="exampleLyrics()">Example Lyrics</button>
</div>

<div class="panel">
<h2>4. AI Voice Settings</h2>

<label>AI Voice</label>
<select id="voice">
<option value="hi-IN-SwaraNeural">Female Hindi - Swara</option>
<option value="hi-IN-MadhurNeural">Male Hindi - Madhur</option>
</select>

<label>Voice Speed</label>
<select id="speed">
<option value="+0%">Normal</option>
<option value="-15%">Slow</option>
<option value="+15%">Fast</option>
</select>

<label>AI Voice Volume</label>
<input type="range" id="volume" min="50" max="150" value="100">

<label>Original Video Voice</label>
<select id="originalAudio">
<option value="mute">Mute Original Voice - सिर्फ AI Voice</option>
<option value="keep">Keep Original Voice - दोनों आवाजें</option>
</select>

<label>Original Voice Volume (जब Keep चुना हो)</label>
<input type="range" id="originalVolume" min="0" max="100" value="25">

<label>Export Quality</label>
<select id="quality">
<option value="fast">FAST - जल्दी Export, छोटी फाइल</option>
<option value="normal">NORMAL - संतुलित</option>
<option value="high">HIGH - बेहतर Quality</option>
</select>

<button id="exportBtn" onclick="startExport()">🚀 Create Final MP4</button>
<div class="progress"><div id="progressBar"></div></div>
<div id="status">Ready to export.</div>
<div id="downloadArea"></div>
</div>
</section>
</div>
</main>

<script>
const $ = id => document.getElementById(id);
let uploadedName = "";
let jobId = "";
let pollTimer = null;

function addLine(start="",end="",text=""){
 const row=document.createElement("div");
 row.className="rowline";

 const a=document.createElement("input");
 a.type="number";a.className="start";
 a.min="0";a.step="0.1";a.placeholder="Start";a.value=start;

 const b=document.createElement("input");
 b.type="number";b.className="end";
 b.min="0";b.step="0.1";b.placeholder="End";b.value=end;

 const c=document.createElement("input");
 c.type="text";c.className="lyric";
 c.placeholder="Lyrics line...";c.value=text;

 const d=document.createElement("button");
 d.className="danger";d.textContent="×";
 d.onclick=()=>row.remove();

 row.append(a,b,c,d);
 $("lyricsRows").appendChild(row);
}

function exampleLyrics(){
 $("lyricsRows").innerHTML="";
 addLine(0,4,"तेरी यादों में खोया रहता हूँ");
 addLine(4,8,"हर पल तुझे ही सोचता हूँ");
 addLine(8,12,"तेरे बिना अधूरा लगता हूँ");
}

function getLines(){
 return [...document.querySelectorAll(".rowline")].map(r=>({
  start:Number(r.querySelector(".start").value),
  end:Number(r.querySelector(".end").value),
  text:r.querySelector(".lyric").value.trim()
 })).filter(x=>x.text && x.end>x.start);
}

function rgba(hex,opacity){
 const n=parseInt(hex.slice(1),16);
 return `rgba(${n>>16},${(n>>8)&255},${n&255},${opacity/100})`;
}

function updateDesign(){
 $("overlayText").style.color=$("fontColor").value;
 $("overlayText").style.background=rgba(
  $("bgColor").value,Number($("bgOpacity").value)
 );
 $("lyricsOverlay").style.fontSize=$("fontSize").value+"px";

 const outline=$("outlineColor").value;
 $("overlayText").style.textShadow=
  `-1px -1px 0 ${outline},1px 1px 0 ${outline},2px 2px 3px #000`;

 const p=$("position").value;
 $("lyricsOverlay").style.top=p==="top"?"8%":p==="middle"?"45%":"auto";
 $("lyricsOverlay").style.bottom=p==="bottom"?"9%":"auto";
}

["fontColor","bgColor","bgOpacity","fontSize","outlineColor","position"]
.forEach(id=>$(id).addEventListener("input",updateDesign));

$("videoFile").addEventListener("change",async e=>{
 const file=e.target.files[0];
 if(!file)return;

 $("video").src=URL.createObjectURL(file);
 $("status").textContent="Video Upload हो रहा है...";

 try{
  const fd=new FormData();
  fd.append("video",file);
  const r=await fetch("/upload",{method:"POST",body:fd});
  const d=await r.json();
  if(!r.ok)throw new Error(d.error||"Upload failed");
  uploadedName=d.filename;
  $("status").textContent="Video Upload हो गया।";
 }catch(err){
  $("status").textContent=err.message;
 }
});

$("video").addEventListener("timeupdate",()=>{
 const t=$("video").currentTime;
 const line=getLines().find(x=>t>=x.start && t<x.end);
 $("overlayText").textContent=line?line.text:"";
});

async function startExport(){
 if(!uploadedName){
  alert("पहले Video Upload करें।");
  return;
 }

 const lines=getLines();
 if(!lines.length){
  alert("कम से कम एक Lyrics Line डालें।");
  return;
 }

 for(const line of lines){
  if(line.start<0 || line.end<=line.start){
   alert("End Time, Start Time से बड़ा होना चाहिए।");
   return;
  }
 }

 const payload={
  filename:uploadedName,
  lines:lines,
  voice:$("voice").value,
  speed:$("speed").value,
  volume:Number($("volume").value),
  original_audio:$("originalAudio").value,
  original_volume:Number($("originalVolume").value),
  quality:$("quality").value,
  design:{
   color:$("fontColor").value,
   bg:$("bgColor").value,
   opacity:Number($("bgOpacity").value),
   size:Number($("fontSize").value),
   outline:$("outlineColor").value,
   position:$("position").value
  }
 };

 $("exportBtn").disabled=true;
 $("downloadArea").innerHTML="";
 $("progressBar").style.width="0%";
 $("status").textContent="Export शुरू हो रहा है...";

 try{
  const r=await fetch("/start-export",{
   method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify(payload)
  });
  const d=await r.json();
  if(!r.ok)throw new Error(d.error||"Export शुरू नहीं हुआ");

  jobId=d.job_id;
  pollTimer=setInterval(checkStatus,1000);
 }catch(e){
  $("status").textContent=e.message;
  $("exportBtn").disabled=false;
 }
}

async function checkStatus(){
 try{
  const r=await fetch("/status/"+jobId);
  const d=await r.json();

  $("progressBar").style.width=(d.progress||0)+"%";
  $("status").textContent=d.message||"Processing...";

  if(d.status==="done"){
   clearInterval(pollTimer);
   $("downloadArea").innerHTML="";
   const a=document.createElement("a");
   a.className="download";
   a.href=d.url;
   a.textContent="⬇ Download Final MP4";
   $("downloadArea").appendChild(a);
   $("exportBtn").disabled=false;
  }

  if(d.status==="error"){
   clearInterval(pollTimer);
   $("exportBtn").disabled=false;
  }
 }catch(e){
  $("status").textContent="Progress check में समस्या हुई।";
 }
}

addLine();
updateDesign();
</script>
</body>
</html>
"""


def run_cmd(args, cwd=None):
    result = subprocess.run(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:] or "FFmpeg Error")
    return result


def get_duration(path):
    result = run_cmd([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])
    return max(1.0, float(result.stdout.strip()))


def has_audio(path):
    result = run_cmd([
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        str(path)
    ])
    return bool(result.stdout.strip())


async def create_voice(text, voice, speed, output):
    communicator = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=speed
    )
    await communicator.save(str(output))


async def create_all_voices(lines, voice, speed, folder):
    tasks = []
    for i, line in enumerate(lines):
        output = folder / f"voice_{i}.mp3"
        tasks.append(create_voice(
            line["text"], voice, speed, output
        ))
    await asyncio.gather(*tasks)


def ass_color(hex_value):
    value = hex_value.lstrip("#")
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H00{b}{g}{r}".upper()


def ass_background(hex_value, opacity):
    value = hex_value.lstrip("#")
    r, g, b = value[0:2], value[2:4], value[4:6]
    alpha = round(255 * (100 - opacity) / 100)
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def srt_time(seconds):
    ms = int(max(0, seconds) * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def export_worker(job_id, data):
    folder = TEMP / job_id
    folder.mkdir(exist_ok=True)

    try:
        jobs[job_id].update(
            status="working",
            progress=2,
            message="Video की जाँच हो रही है..."
        )

        source = UPLOADS / Path(data["filename"]).name
        if not source.exists():
            raise RuntimeError("Uploaded video नहीं मिला।")

        duration = get_duration(source)
        source_has_audio = has_audio(source)

        lines = []
        for line in data["lines"]:
            start = max(0, float(line["start"]))
            end = min(duration, float(line["end"]))
            text = str(line["text"]).strip()

            if text and end > start:
                lines.append({
                    "start": start,
                    "end": end,
                    "text": text
                })

        if not lines:
            raise RuntimeError("Valid Lyrics Timing नहीं मिली।")

        voice = data.get("voice", "hi-IN-SwaraNeural")
        speed = data.get("speed", "+0%")

        jobs[job_id].update(
            progress=8,
            message="Hindi AI Voice तैयार हो रही है..."
        )

        # सभी Voice Lines साथ में तैयार करना
        asyncio.run(create_all_voices(
            lines, voice, speed, folder
        ))

        jobs[job_id].update(
            progress=30,
            message="Lyrics Subtitle तैयार हो रही है..."
        )

        srt_path = folder / "lyrics.srt"
        with open(srt_path, "w", encoding="utf-8-sig") as f:
            for i, line in enumerate(lines, start=1):
                f.write(
                    f"{i}\n"
                    f"{srt_time(line['start'])} --> "
                    f"{srt_time(line['end'])}\n"
                    f"{line['text']}\n\n"
                )

        design = data.get("design", {})
        color = ass_color(design.get("color", "#ffffff"))
        outline = ass_color(design.get("outline", "#000000"))
        bg = ass_background(
            design.get("bg", "#000000"),
            int(design.get("opacity", 55))
        )

        size = max(12, min(90, int(design.get("size", 30))))
        position = design.get("position", "bottom")
        alignment = {
            "bottom": 2,
            "middle": 5,
            "top": 8
        }.get(position, 2)

        subtitle_filter = (
            "subtitles=lyrics.srt:"
            "force_style='"
            f"FontName=Arial,FontSize={size},"
            f"PrimaryColour={color},"
            f"OutlineColour={outline},"
            "Outline=2,BorderStyle=3,"
            f"BackColour={bg},"
            f"Alignment={alignment},MarginV=40'"
        )

        ai_volume = max(
            0.1,
            min(2.0, float(data.get("volume", 100)) / 100)
        )

        original_mode = data.get("original_audio", "mute")
        original_volume = max(
            0,
            min(1, float(data.get("original_volume", 25)) / 100)
        )

        command = ["ffmpeg", "-y", "-i", str(source)]
        filters = []
        voice_labels = []

        for i, line in enumerate(lines):
            audio_path = folder / f"voice_{i}.mp3"
            command += ["-i", str(audio_path)]

            input_no = i + 1
            label = f"v{i}"
            delay = int(line["start"] * 1000)

            filters.append(
                f"[{input_no}:a]"
                f"adelay={delay}|{delay},"
                f"volume={ai_volume}[{label}]"
            )
            voice_labels.append(f"[{label}]")

        # Original Video Audio ON/OFF
        if original_mode == "keep" and source_has_audio:
            filters.append(
                f"[0:a]volume={original_volume}[original]"
            )
            voice_labels.append("[original]")

        filters.append(
            "".join(voice_labels)
            + f"amix=inputs={len(voice_labels)}:"
              "duration=longest:dropout_transition=0[aout]"
        )

        quality = data.get("quality", "fast")

        if quality == "high":
            preset, crf, bitrate = "slow", "18", "192k"
        elif quality == "normal":
            preset, crf, bitrate = "medium", "23", "160k"
        else:
            preset, crf, bitrate = "ultrafast", "28", "128k"

        output_name = f"LyricsStudio_{job_id}.mp4"
        output_path = OUTPUTS / output_name
        progress_file = folder / "progress.txt"
        error_file = folder / "ffmpeg-error.txt"

        command += [
            "-filter_complex", ";".join(filters),
            "-map", "0:v:0",
            "-map", "[aout]",
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", crf,
            "-threads", "0",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", bitrate,
            "-t", str(duration),
            "-movflags", "+faststart",
            "-progress", str(progress_file),
            "-nostats",
            "-loglevel", "error",
            str(output_path)
        ]

        jobs[job_id].update(
            progress=35,
            message=f"{quality.upper()} Mode में Video Render हो रहा है..."
        )

        with open(error_file, "w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=str(folder),
                stdout=subprocess.DEVNULL,
                stderr=log
            )

            while process.poll() is None:
                if progress_file.exists():
                    try:
                        content = progress_file.read_text(
                            encoding="utf-8", errors="ignore"
                        )
                        matches = re.findall(
                            r"out_time_ms=(\d+)", content
                        )
                        if matches:
                            seconds = int(matches[-1]) / 1_000_000
                            percent = min(
                                98,
                                35 + int(63 * seconds / duration)
                            )
                            jobs[job_id].update(
                                progress=percent,
                                message=f"Video तैयार हो रहा है... {percent}%"
                            )
                    except Exception:
                        pass
                time.sleep(0.7)

        if process.returncode != 0:
            error = error_file.read_text(
                encoding="utf-8", errors="replace"
            )
            raise RuntimeError(error[-3000:] or "FFmpeg Error")

        jobs[job_id].update(
            status="done",
            progress=100,
            message="आपका Final MP4 तैयार है!",
            url=f"/download/{output_name}"
        )

    except Exception as e:
        jobs[job_id].update(
            status="error",
            message=f"Error: {e}"
        )

    finally:
        shutil.rmtree(folder, ignore_errors=True)


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("video")

    if not file or not file.filename:
        return jsonify(error="पहले Video चुनें।"), 400

    extension = Path(file.filename).suffix.lower()
    allowed = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

    if extension not in allowed:
        return jsonify(
            error="MP4, MOV, MKV, AVI या WEBM वीडियो चुनें।"
        ), 400

    filename = f"{uuid.uuid4().hex}{extension}"
    file.save(UPLOADS / filename)

    return jsonify(filename=filename)


@app.route("/start-export", methods=["POST"])
def start_export():
    data = request.get_json(silent=True) or {}

    if not data.get("filename") or not data.get("lines"):
        return jsonify(error="Video और Lyrics जरूरी हैं।"), 400

    job_id = uuid.uuid4().hex

    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Export शुरू हो रहा है..."
    }

    thread = threading.Thread(
        target=export_worker,
        args=(job_id, data),
        daemon=True
    )
    thread.start()

    return jsonify(job_id=job_id)


@app.route("/status/<job_id>")
def status(job_id):
    if job_id not in jobs:
        return jsonify(error="Job नहीं मिला।"), 404
    return jsonify(jobs[job_id])


@app.route("/download/<path:filename>")
def download(filename):
    return send_from_directory(
        OUTPUTS,
        filename,
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True
    )
