import os
import asyncio
import requests
import streamlit as st
import edge_tts

st.set_page_config(page_title="AI Shorts Generator", page_icon="🎬", layout="centered")
st.title("AI Shorts Video Generator")
st.caption("Auto 50-60s Shorts Generator")

GROQ_KEY = st.secrets.get("GROQ_KEY", "").strip()
PIXABAY_KEY = "57940136-a7d5b1dcfff829dec1a7d"

# 1. एरर-प्रूफ स्क्रिप्ट जनरेटर
def make_script(topic):
    prompt_text = f"Write an engaging 50-second spoken Hindi script for YouTube Shorts on: '{topic}'. Plain spoken Hindi words only in Devanagari script, strictly around 110 words."
    
    # कोशिश 1: Groq API
    if GROQ_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_KEY}",
                "Content-Type": "application/json; charset=utf-8"
            }
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt_text}]
            }
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            data = res.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
            elif "error" in data:
                st.warning(f"Groq Notice: {data['error'].get('message', 'Key issue')}, switching to backup AI...")
        except Exception:
            pass

    # कोशिश 2: फ्री बैकअप AI (ताकि काम कभी न रुके)
    try:
        backup_url = "https://text.pollinations.ai/" + requests.utils.quote(prompt_text)
        res_backup = requests.get(backup_url, timeout=20)
        if res_backup.status_code == 200 and len(res_backup.text) > 40:
            return res_backup.text.strip()
    except Exception:
        pass

    # कोशिश 3: इमरजेंसी स्क्रिप्ट
    return f"{topic} हमारे जीवन का एक अत्यंत महत्वपूर्ण और प्रेरणादायक पहलू है। जब हम इसके गहरे अर्थ को समझने का प्रयास करते हैं, तो हमें जीवन में एक नई ऊर्जा और शांति का अनुभव होता है। अपने मन को सकारात्मक रखें, निरंतर आगे बढ़ते रहें और अपने कर्म पर पूरा विश्वास रखें।"

# 2. हिंदी आवाज़
async def make_audio(text, output_audio="voice.mp3"):
    comm = edge_tts.Communicate(text, voice="hi-IN-MadhurNeural")
    await comm.save(output_audio)
    return output_audio

# 3. बैकग्राउंड वीडियो
def get_video(topic, output_video="bg.mp4"):
    clean_topic = topic.split()[0] if topic else "nature"
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q={clean_topic}&video_type=film"
    res = requests.get(url, timeout=20).json()
    
    if res.get("hits") and len(res["hits"]) > 0:
        v_url = res["hits"][0]["videos"]["medium"]["url"]
    else:
        fallback = requests.get(f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q=nature", timeout=20).json()
        v_url = fallback["hits"][0]["videos"]["medium"]["url"]
        
    video_bytes = requests.get(v_url, timeout=30).content
    with open(output_video, "wb") as f:
        f.write(video_bytes)
    return output_video

# 4. वीडियो रेंडरिंग
def render_video(v_path, a_path, out_path="final_reel.mp4"):
    cmd = (
        f'ffmpeg -y -stream_loop -1 -i "{v_path}" -i "{a_path}" '
        f'-vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" '
        f'-c:v libx264 -preset fast -c:a aac -shortest -map 0:v:0 -map 1:a:0 "{out_path}"'
    )
    os.system(cmd)
    return out_path

topic_input = st.text_input("Enter Topic:", placeholder="e.g. dharmik bhakti, space facts...")

if st.button("Generate Video", type="primary"):
    if not topic_input.strip():
        st.warning("Please enter a topic first!")
    else:
        status = st.empty()
        
        status.info("1/4: Generating script...")
        script = make_script(topic_input)
        
        status.info("2/4: Generating voiceover...")
        asyncio.run(make_audio(script))
        
        status.info("3/4: Fetching stock video...")
        get_video(topic_input)
        
        status.info("4/4: Merging and rendering final video...")
        render_video("bg.mp4", "voice.mp3", "final_reel.mp4")
        
        status.success("Done! Video is ready.")
        st.video("final_reel.mp4")
        
        with open("final_reel.mp4", "rb") as f:
            st.download_button(
                label="Download Video",
                data=f,
                file_name="shorts_video.mp4",
                mime="video/mp4"
            )
