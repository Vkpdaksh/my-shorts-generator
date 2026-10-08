import os
import asyncio
import requests
import streamlit as st
from groq import Groq
import edge_tts

st.set_page_config(page_title="AI Shorts Generator", page_icon="🎬", layout="centered")
st.title("🎬 AI Shorts Video Generator")
st.caption("बिना किसी एरर या लोड के 50-60 सेकंड के वायरल शॉर्ट्स बनाएँ")

# Keys
GROQ_KEY = "यहाँ_अपनी_GROQ_KEY_पेस्ट_करें"
PIXABAY_KEY = "57940136-a7d5b1dcfff829dec1a7d"

# 1. 50 सेकंड की स्क्रिप्ट
def make_script(topic):
    client = Groq(api_key=GROQ_KEY)
    chat = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": f"Write an engaging 50-second spoken Hindi script for YouTube Shorts on: '{topic}'. Do not include scene directions, timestamps, or emojis. Strictly around 110-120 spoken words."
            }
        ],
        model="llama-3.3-70b-versatile",
    )
    return chat.choices[0].message.content.strip()

# 2. हिंदी वॉइसओवर
async def make_audio(text, output_audio="voice.mp3"):
    comm = edge_tts.Communicate(text, voice="hi-IN-MadhurNeural")
    await comm.save(output_audio)
    return output_audio

# 3. बैकग्राउंड वीडियो
def get_video(topic, output_video="bg.mp4"):
    query = topic.split()[0] if topic else "nature"
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q={query}&video_type=film"
    res = requests.get(url).json()
    
    if res.get("hits") and len(res["hits"]) > 0:
        v_url = res["hits"][0]["videos"]["medium"]["url"]
    else:
        v_url = requests.get(f"https://pixabay.com/api/videos/?key={PIXABAY_KEY}&q=nature").json()["hits"][0]["videos"]["medium"]["url"]
        
    data = requests.get(v_url).content
    with open(output_video, "wb") as f:
        f.write(data)
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

# वेब इंटरफ़ेस
topic_input = st.text_input("👉 वीडियो का टॉपिक लिखें:", placeholder="उदा. Amazing Space Facts, Motivational, सेहत के नुस्खे...")

if st.button("🚀 वीडियो बनाएँ (1-Click)", type="primary"):
    if not topic_input.strip():
        st.warning("कृपया पहले कोई टॉपिक लिखें!")
    else:
        status = st.empty()
        
        status.info("⏳ 1/4: स्क्रिप्ट लिखी जा रही है...")
        script = make_script(topic_input)
        
        status.info("⏳ 2/4: आवाज़ (Voiceover) तैयार हो रही है...")
        asyncio.run(make_audio(script))
        
        status.info("⏳ 3/4: HD बैकग्राउंड वीडियो लाया जा रहा है...")
        get_video(topic_input)
        
        status.info("⏳ 4/4: वीडियो रेंडर हो रहा है...")
        render_video("bg.mp4", "voice.mp3", "final_reel.mp4")
        
        status.success("✓ आपका वीडियो पूरी तरह तैयार है!")
        
        st.video("final_reel.mp4")
        
        with open("final_reel.mp4", "rb") as f:
            st.download_button(
                label="⬇️ वीडियो डाउनलोड करें",
                data=f,
                file_name=f"{topic_input[:15]}_shorts.mp4",
                mime="video/mp4"
            )
