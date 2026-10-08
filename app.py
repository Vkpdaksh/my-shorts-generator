import os
import time
import asyncio
import subprocess
import requests
import streamlit as st
import edge_tts
import imageio_ffmpeg

st.set_page_config(page_title="AI Shorts & Talking Face Generator", page_icon="🎬", layout="centered")
st.title("🎬 AI Shorts & Talking Face Generator")
st.caption("फोटो से बोलता हुआ वीडियो या AI रील्स 1-क्लिक में बनाएँ")

GROQ_KEY = st.secrets.get("GROQ_KEY", "").strip()
DID_KEY = st.secrets.get("DID_KEY", "").strip()
PIXABAY_KEY = "57940136-a7d5b1dcfff829dec1a7d"

# 1. AI Script Generator
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

    return f"{topic} हमारे जीवन का एक अत्यंत महत्वपूर्ण और प्रेरणादायक पहलू है। अपने विचारों को सकारात्मक रखें और निरंतर आगे बढ़ते रहें।"

# 2. Hindi Audio
async def make_audio(text, output_audio="voice.mp3"):
    comm = edge_tts.Communicate(text, voice="hi-IN-MadhurNeural")
    await comm.save(output_audio)
    return output_audio

# 3. Direct D-ID Talking Face Generator (No Third-Party Uploads)
def generate_talking_face(image_file, script_text, out_path="final_reel.mp4"):
    headers_auth = {"Authorization": f"Basic {DID_KEY}"}

    # Step A: Direct upload to D-ID
    upload_url = "https://api.d-id.com/images"
    files = {"image": (image_file.name, image_file.getvalue(), image_file.type)}
    up_res = requests.post(upload_url, headers=headers_auth, files=files, timeout=30)
    
    if up_res.status_code not in [200, 201]:
        st.error(f"Image Upload Failed: {up_res.text}")
        return None
        
    img_url = up_res.json().get("url")

    # Step B: Request Talking Avatar Video
    talks_url = "https://api.d-id.com/talks"
    headers_json = {
        "Authorization": f"Basic {DID_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "source_url": img_url,
        "script": {
            "type": "text",
            "subtitles": "false",
            "provider": {"type": "microsoft", "voice_id": "hi-IN-MadhurNeural"},
            "input": script_text
        },
        "config": {"fluent": "false", "pad_audio": "0.0"}
    }
    
    talk_res = requests.post(talks_url, json=payload, headers=headers_json, timeout=20)
    if talk_res.status_code not in [200, 201]:
        st.error(f"D-ID Creation Notice: {talk_res.text}")
        return None
        
    talk_id = talk_res.json().get("id")

    # Step C: Poll for finished video
    for _ in range(40):
        time.sleep(3)
        chk = requests.get(f"{talks_url}/{talk_id}", headers=headers_json).json()
        if chk.get("status") == "done":
            video_url = chk.get("result_url")
            v_data = requests.get(video_url).content
            with open(out_path, "wb") as f:
                f.write(v_data)
            return out_path
        elif chk.get("status") == "error":
            st.error("Face animation processing error.")
            return None
            
    return None

# 4. Background Video Fetch (Normal Mode)
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

# 5. FFmpeg Merge (Normal Mode)
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

    cmd_fallback = [
        ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30",
        "-i", a_path, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_path
    ]
    subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return out_path

# UI Controls
topic_input = st.text_input("👉 वीडियो का टॉपिक लिखें:", placeholder="उदा. Daily Motivation, Dharmik Gyaan...")
uploaded_face = st.file_uploader("📸 फोटो अपलोड करें (चेहरा बुलवाने के लिए - Optional):", type=["jpg", "png", "jpeg"])

if st.button("🚀 वीडियो बनाएँ", type="primary"):
    if not topic_input.strip():
        st.warning("कृपया पहले कोई टॉपिक लिखें!")
    else:
        status = st.empty()
        
        status.info("1/3: स्क्रिप्ट लिखी जा रही है...")
        script = make_script(topic_input)
        
        if uploaded_face is not None:
            if not DID_KEY:
                st.error("Photo video के लिए DID_KEY Secrets में जोड़ना ज़रूरी है!")
            else:
                status.info("2/3: AI आपकी फोटो में लिप-सिंक और चेहरे के हाव-भाव जोड़ रहा है...")
                res_path = generate_talking_face(uploaded_face, script, "final_reel.mp4")
                if res_path and os.path.exists("final_reel.mp4"):
                    status.success("Done! फोटो से बोलता हुआ AI वीडियो तैयार है!")
                    st.video("final_reel.mp4")
                    with open("final_reel.mp4", "rb") as f:
                        st.download_button("⬇️ Download Talking Video", f, file_name="talking_shorts.mp4", mime="video/mp4")
        else:
            status.info("2/4: हिंदी आवाज़ तैयार हो रही है...")
            asyncio.run(make_audio(script))
            
            status.info("3/4: बैकग्राउंड वीडियो लाया जा रहा है...")
            get_video(topic_input)
            
            status.info("4/4: वीडियो तैयार किया जा रहा है...")
            render_video("bg.mp4", "voice.mp3", "final_reel.mp4")
            
            if os.path.exists("final_reel.mp4"):
                status.success("Done! वीडियो पूरी तरह तैयार है!")
                st.video("final_reel.mp4")
                with open("final_reel.mp4", "rb") as f:
                    st.download_button("⬇️ Download Video", f, file_name="shorts_video.mp4", mime="video/mp4")
