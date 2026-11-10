import json, uuid, threading, subprocess, shutil
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from faster_whisper import WhisperModel

BASE=Path(__file__).parent
OUT=BASE/"outputs"; TMP=BASE/"tmp"
OUT.mkdir(exist_ok=True); TMP.mkdir(exist_ok=True)
app=FastAPI(title="ClipForge AI")
origins=[x.strip() for x in __import__("os").getenv("FRONTEND_ORIGIN","https://iridescent-zuccutto-70dd74.netlify.app").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=["GET","POST","OPTIONS"],allow_headers=["Content-Type"])
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")
app.mount("/outputs",StaticFiles(directory=OUT),name="outputs")
jobs={}
model=None

class Request(BaseModel):
    youtube_url:str
    count:int=Field(5,ge=1,le=10)
    max_duration:int=Field(45,ge=15,le=90)
    ratio:str="9:16"
    quality:int=1080
    captions:bool=True

def cmd(args):
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-1400:])
    return p.stdout

def stamp(t):
    n=round(t*1000); h,n=divmod(n,3600000); m,n=divmod(n,60000); s,n=divmod(n,1000)
    return f"{h:02}:{m:02}:{s:02},{n:03}"

def worker(jid,r):
    global model
    folder=TMP/jid; folder.mkdir()
    try:
        jobs[jid].update(state="working",message="Descargando el video autorizado…")
        video=folder/"source.mp4"
        cmd(["yt-dlp","--no-playlist","-f","bv*[height<=1080]+ba/b[height<=1080]","--merge-output-format","mp4","-o",str(video),r.youtube_url])
        if not video.exists(): video=next(folder.glob("source.*"))
        meta=json.loads(cmd(["ffprobe","-v","quiet","-print_format","json","-show_format",str(video)]))
        total=float(meta["format"]["duration"])
        jobs[jid]["message"]="Transcribiendo audio con IA…"
        if model is None: model=WhisperModel("small",device="cpu",compute_type="int8")
        stream,_=model.transcribe(str(video),vad_filter=True)
        segs=[{"start":s.start,"end":s.end,"text":s.text.strip()} for s in stream]
        if not segs: raise RuntimeError("No se detectó voz en el video.")
        candidates=[]
        step=max(8,r.max_duration//3)
        for start in range(0,max(1,int(total-r.max_duration+1)),step):
            end=min(total,start+r.max_duration)
            ss=[s for s in segs if s["end"]>start and s["start"]<end]
            score=sum(len(s["text"].split()) for s in ss)/max(1,end-start)
            candidates.append((score,start,end))
        chosen=[]
        for item in sorted(candidates,reverse=True):
            if all(abs(item[1]-x[1])>r.max_duration*.65 for x in chosen): chosen.append(item)
            if len(chosen)>=r.count: break
        if not chosen: chosen=[(1,0,min(total,r.max_duration))]
        clips=[]
        for i,(_,start,end) in enumerate(sorted(chosen,key=lambda x:x[1]),1):
            jobs[jid]["message"]=f"Exportando clip {i} de {len(chosen)}…"
            end=min(end,total); length=end-start
            if r.ratio=="9:16": w,h=(720,1280) if r.quality==720 else (1080,1920)
            elif r.ratio=="1:1": w,h=(720,720) if r.quality==720 else (1080,1080)
            else: w,h=(1280,720) if r.quality==720 else (1920,1080)
            vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
            if r.captions:
                srt=folder/f"{i}.srt"; lines=[]
                selected=[s for s in segs if s["end"]>start and s["start"]<end]
                for n,s in enumerate(selected,1):
                    a=max(0,s["start"]-start); z=min(length,s["end"]-start)
                    if z>a: lines += [str(n),f"{stamp(a)} --> {stamp(z)}",s["text"].replace("-->","→"),""]
                srt.write_text("\n".join(lines),encoding="utf-8")
                safe=str(srt).replace("\\","/").replace(":","\\:")
                vf += f",subtitles='{safe}':force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,BorderStyle=1,Outline=2,Alignment=2,MarginV=90'"
            target=OUT/f"{jid}-{i}.mp4"
            cmd(["ffmpeg","-y","-ss",str(start),"-i",str(video),"-t",str(length),"-vf",vf,"-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-movflags","+faststart",str(target)])
            clips.append({"url":f"/outputs/{target.name}"})
        jobs[jid].update(state="done",message="Descarga tus clips MP4.",clips=clips)
    except Exception as e:
        jobs[jid].update(state="error",message=str(e)[:1000])
    finally:
        shutil.rmtree(folder,ignore_errors=True)

@app.get("/")
def home(): return FileResponse(BASE/"index.html")

@app.post("/api/jobs")
def create(r:Request):
    p=urlparse(r.youtube_url)
    if p.scheme not in ("http","https") or p.hostname not in ("youtube.com","www.youtube.com","m.youtube.com","youtu.be"):
        raise HTTPException(400,"Enlace de YouTube no válido.")
    if r.ratio not in ("9:16","1:1","16:9") or r.quality not in (720,1080):
        raise HTTPException(400,"Ajustes no válidos.")
    jid=uuid.uuid4().hex[:12]
    jobs[jid]={"state":"queued","message":"Trabajo en cola.","clips":[]}
    threading.Thread(target=worker,args=(jid,r),daemon=True).start()
    return {"job_id":jid}

@app.get("/api/jobs/{jid}")
def status(jid):
    if jid not in jobs: raise HTTPException(404,"Trabajo no encontrado.")
    return jobs[jid]
