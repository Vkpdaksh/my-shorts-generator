import os
import time
import base64
import asyncio
import subprocess
import requests
import streamlit as st
import edge_tts
import imageio_ffmpeg

st.set_page_config(page_title="AI Shorts & Face Video Generator", page_icon="🎬", layout="centered")
st.title("AI Shorts & Talking Face Video Generator")
st.caption("Auto Script, Voiceover, Stock Video & Talking Photo")

GROQ_KEY = st.secrets.get("GROQ_KEY", "").strip()
DID_KEY = st.secrets.get("DID_KEY", "").strip()
PIXABAY_KEY = "57940136-a7d5b1dcfff829dec1a7d"

# 1. Groq Script Generator
def make_script(topic):
    prompt_text = f"Write an engaging 40-50 second spoken Hindi script for YouTube Shorts on: '{topic}'. Plain spoken Hindi text only in Devanagari script, strictly around 90-100 words."
    models = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"]
    
    if GROQ_KEY:
        for m in models:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json; charset=utf-8"}
                payload = {"model": m, "messages": [{"role": "user", "content": prompt_text}]}
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"].strip()
            except Exception:
                continue

    try:
        backup_url = "https://text.pollinations.ai/" + requests.utils.quote(prompt_text)
        res_backup = requests.get(backup_url, timeout=15)
        if res_backup.status_code == 200 and len(res_backup.text) > 40:
            return res_backup.text.strip()
    except Exception:
        pass

    return f"{topic} par baat karein to yeh hamare jeevan ka ek mahatvapurna hissa hai. Hamesha mehnat karte rahein aur aage badhein."

# 2. Hindi Audio
async def make_audio(text, output_audio="voice.mp3"):
    comm = edge_tts.Communicate(text, voice="hi-IN-MadhurNeural")
    await comm.save(output_audio)
    return output_audio

# 3. Photo se Talking Face Video (D-ID API)
def generate_talking_face(image_file, script_text, out_path="final_reel.mp4"):
    # Image ko temporary save karein
    with open("temp_face.jpg", "wb") as f:
        f.write(image_file.getbuffer())

    # Free image host (ImgBB ya free service par upload karna for URL)
    with open("temp_face.jpg", "rb") as file:
        img_res = requests.post(
            "https://api.imgbb.com/1/upload?key=8e68c9ff09c5dc2bc178876c16ce6dc0",
            files={"image": file},
            timeout=30
        )
    img_url = img_res.json()["data"]["url"]

    # D-ID API Call
    url = "https://api.d-id.com/talks"
    headers = {
        "Authorization": f"Basic {DID_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "source_url": img_url,
        "script": {
            "type": "text",
            "subtitles": "false",
            "provider": {
                "type": "microsoft",
                "voice_id": "hi-IN-MadhurNeural"
            },
            "input": script_text
        },
        "config": {
            "fluent": "false",
            "pad_audio": "0.0"
        }
    }
    
    response = requests.post(url, json=payload, headers=headers)
    talk_id = response.json().get("id")
    
    if not talk_id:
        st.error(f"D-ID Error: {response.text}")
        return None

    # Wait for talking video to finish rendering
    for _ in range(40):
        time.sleep(3)
        chk = requests.get(f"{url}/{talk_id}", headers=headers).json()
        if chk.get("status") == "done":
            video_url = chk.get("result_url")
            v_data = requests.get(video_url).content
            with open(out_path, "wb") as f:
                f.write(v_data)
            return out_path
        elif chk.get("status") == "error":
            st.error("Face animation failed.")
            return None
            
    return None

# 4. Normal Stock Video Fetch (Fallback / No-Photo mode)
def get_video(topic, output_video="bg.mp4"):
    if os.path.exists(output_video):
        try:
            os.remove(output_video)
        except Exception:
            pass

    clean_topic = topic.split()[0] if topic else "nature"
    p_url = f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q={clean_topic}&video_type=film"
    v_url = None
    try:
        res = requests.get(p_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if res.status_code == 200:
            hits = res.json().get("hits", [])
            if hits:
                v_url = hits[0]["videos"]["medium"]["url"]
    except Exception:
        pass

    if not v_url:
        v_url = "https://assets.mixkit.co/videos/preview/mixkit-tree-branches-in-the-breeze-1188-large.mp4"

    try:
        with requests.get(v_url, stream=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=25) as r:
            with open(output_video, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
    except Exception:
        pass

    return output_video

# 5. FFmpeg Merge for normal mode
def render_video(v_path, a_path, out_path="final_reel.mp4"):
    if os.path.exists(out_path):
        os.remove(out_path)
    
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if os.path.exists(v_path) and os.path.getsize(v_path) > 50000:
        cmd = [
            ffmpeg_exe, "-y", "-stream_loop", "-1", "-i", v_path, "-i", a_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and os.path.exists(out_path):
            return out_path

    # Fallback pattern
    cmd_fallback = [
        ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30",
        "-i", a_path, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_path
    ]
    subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return out_path

# UI Controls
topic_input = st.text_input("Enter Topic:", placeholder="e.g. Daily Motivation, Dharmik Gyaan...")
uploaded_face = st.file_uploader("Upload Face/Photo (Optional - for talking face video):", type=["jpg", "png", "jpeg"])

if st.button("Generate Video", type="primary"):
    if not topic_input.strip():
        st.warning("Pehle koi topic likhein!")
    else:
        status = st.empty()
        
        status.info("1/3: Script likhi ja rahi hai...")
        script = make_script(topic_input)
        
        if uploaded_face is not None:
            if not DID_KEY:
                st.error("Photo video ke liye DID_KEY Secrets me daalna zaroori hai!")
            else:
                status.info("2/3: Photo me lip-sync aur face motion add ho raha hai...")
                res_path = generate_talking_face(uploaded_face, script, "final_reel.mp4")
                if res_path and os.path.exists("final_reel.mp4"):
                    status.success("Done! Talking Face Video taiyar hai.")
                    st.video("final_reel.mp4")
                    with open("final_reel.mp4", "rb") as f:
                        st.download_button("⬇️ Download Talking Video", f, file_name="talking_shorts.mp4", mime="video/mp4")
        else:
            status.info("2/4: Hindi voiceover ban raha hai...")
            asyncio.run(make_audio(script))
            
            status.info("3/4: Background video laya ja raha hai...")
            get_video(topic_input)
            
            status.info("4/4: Video merge kiya ja raha hai...")
            render_video("bg.mp4", "voice.mp3", "final_reel.mp4")
            
            if os.path.exists("final_reel.mp4"):
                status.success("Done! Video taiyar hai.")
                st.video("final_reel.mp4")
                with open("final_reel.mp4", "rb") as f:
                    st.download_button("⬇️ Download Video", f, file_name="shorts_video.mp4", mime="video/mp4")
