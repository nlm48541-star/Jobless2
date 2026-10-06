# -*- coding: utf-8 -*-
import os, json, re, time, base64, requests, shutil

TRACKER_FILE = "api_key_tracker.json"

def parse_multiline_keys(env_var_name):
    raw = os.environ.get(env_var_name, "").strip()
    if not raw: return []
    return [k.strip() for k in raw.splitlines() if k.strip() and not k.strip().startswith('#')]

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f: 
                return json.load(f)
        except Exception: pass
    return {}

def save_tracker(data):
    try:
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception: pass

def get_audio_start_index(provider, total):
    if total == 0: return 0
    return load_tracker().get(f"{provider}_index", 0) % total

def set_audio_index(provider, next_idx, total):
    if total == 0: return
    t = load_tracker()
    t[f"{provider}_index"] = next_idx % total
    save_tracker(t)

def clean_script_for_speech(raw_text):
    if not raw_text: return ""
    text = re.sub(r'[\*\_\|\#\~]', '', raw_text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'[\<\>\{\}\(\)\@\$\^\&\+\=\_\\\/]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

# =========================================================================
# 🌟 ১. Gemini 3.8 Flash TTS
# =========================================================================

def synthesize_with_gemini(speech_text, output_audio_path):
    keys = parse_multiline_keys("GEMINI_API_KEYS") or parse_multiline_keys("GEMINI_API_KEY")
    total = len(keys)
    if total == 0: return False

    voice_id = os.environ.get("GEMINI_VOICE_ID", "voice_z3e67k0f8p8c").strip()
    try: 
        from google import genai
    except ImportError: 
        return False

    start_idx = get_audio_start_index("gemini", total)
    for offset in range(total):
        cur_idx = (start_idx + offset) % total
        api_key = keys[cur_idx]
        try:
            client = genai.Client(api_key=api_key)
            interaction = client.interactions.create(
                model="gemini-3.8-flash-tts",
                input=[{"type": "user_input", "content": [{"type": "text", "text": speech_text}]}],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice_id}]}
            )
            if hasattr(interaction, 'output_audio') and hasattr(interaction.output_audio, 'data'):
                audio_bytes = base64.b64decode(interaction.output_audio.data)
                if len(audio_bytes) > 1000:
                    with open(output_audio_path, "wb") as f: 
                        f.write(audio_bytes)
                    set_audio_index("gemini", cur_idx, total)
                    return True
        except Exception: pass
        set_audio_index("gemini", cur_idx + 1, total)
    return False

# =========================================================================
# 🌟 ২. ElevenLabs API
# =========================================================================

def synthesize_with_elevenlabs(speech_text, output_audio_path):
    keys = parse_multiline_keys("ELEVENLABS_API_KEYS")
    total = len(keys)
    if total == 0: return False

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    start_idx = get_audio_start_index("elevenlabs", total)
    for offset in range(total):
        cur_idx = (start_idx + offset) % total
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": keys[cur_idx]}
        payload = {"text": speech_text, "model_id": "eleven_multilingual_v2"}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(output_audio_path, "wb") as f: 
                    f.write(resp.content)
                set_audio_index("elevenlabs", cur_idx, total)
                return True
        except Exception: pass
        set_audio_index("elevenlabs", cur_idx + 1, total)
    return False

# =========================================================================
# 🌟 ৩. Microsoft Edge Neural Fallback
# =========================================================================

def synthesize_with_edge_fallback(speech_text, output_audio_path):
    try:
        import asyncio, edge_tts
        async def _make():
            c = edge_tts.Communicate(speech_text, "bn-BD-PradeepNeural", rate="+0%", pitch="+0Hz")
            await c.save(output_audio_path)
        asyncio.run(_make())
        return os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 1000
    except Exception: return False

# =========================================================================
# 🌟 এক্সপোর্ট করা মূল ফাংশনসমূহ (Exported Functions)
# =========================================================================

def synthesize_single_speech(text, output_path):
    """একটি নির্দিষ্ট টেক্সটের জন্য অডিও তৈরি করে"""
    speech_text = clean_script_for_speech(text)
    if not speech_text: return False
    if synthesize_with_gemini(speech_text, output_path): return True
    if synthesize_with_elevenlabs(speech_text, output_path): return True
    if synthesize_with_edge_fallback(speech_text, output_path): return True
    
    # লোকাল মিউজিক ব্যাকআপ
    for f in ["sample_voice.mp3", "sample_voice.wav", "Photos/bg_music.mp3"]:
        if os.path.exists(f) and os.path.getsize(f) > 1000:
            shutil.copyfile(f, output_path)
            return True
    return False

def generate_segmented_audio_pipeline(segments, tmp_dir):
    """প্রতিটি সেগমেন্টের অডিও তৈরি করে সঠিক টাইমস্ট্যাম্প সহ রিটার্ন করে"""
    audio_segments = []
    for idx, seg in enumerate(segments, start=1):
        seg_audio_file = os.path.join(tmp_dir, f"seg_{idx}.mp3")
        print(f"🎙️ [Audio Engine] Generating audio for Segment {idx}/{len(segments)}: '{seg['title'][:30]}'...")
        
        success = synthesize_single_speech(seg["script"], seg_audio_file)
        if success and os.path.exists(seg_audio_file):
            audio_segments.append({
                "audio_path": seg_audio_file,
                "box_2d": seg["box_2d"],
                "image_index": seg.get("image_index", 1)
            })
        else:
            print(f"⚠️ Failed audio for segment {idx}, continuing...")

    return audio_segments
