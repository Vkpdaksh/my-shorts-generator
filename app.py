import os
import asyncio
import requests
import streamlit as st
from groq import Groq
import edge_tts

st.set_page_config(page_title="AI Shorts Generator", page_icon="🎬", layout="centered")
st.title("AI Shorts Video Generator")
st.caption("Auto 50-60s Shorts Generator")

GROQ_KEY = st.secrets.get("GROQ_KEY", "")
PIXABAY_KEY = "57940136-a7d5b1dcfff829dec1a7d"

def make_script(topic):
    client = Groq(api_key=GROQ_KEY)
    prompt_en = f"Write an engaging 50-second spoken Hindi script for YouTube Shorts on: '{topic}'. Plain spoken Hindi text only in Devanagari, strictly around 110 words."
    chat = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt_en
            }
        ],
        model="llama-3.3-70b-versatile",
    )
    return chat.choices[0].message.content.strip()

async def make_audio(text, output_audio="voice.mp3"):
    comm = edge_tts.Communicate(text, voice="hi-IN-MadhurNeural")
    await comm.save(output_audio)
    return output_audio

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
    if not GROQ_KEY:
        st.error("Please add GROQ_KEY in Streamlit Secrets!")
    elif not topic_input.strip():
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
