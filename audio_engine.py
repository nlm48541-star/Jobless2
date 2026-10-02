# -*- coding: utf-8 -*-
import os, re, time, base64, requests, shutil

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
    t = load_tracker()
    return t.get(f"{provider}_index", 0) % total

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
# 🌟 ১. প্রথম প্রায়োরিটি: Gemini 3.8 Flash TTS
# =========================================================================

def synthesize_with_gemini(speech_text, output_audio_path):
    print("\n--- [VOICE ENGINE 1: Gemini 3.8 Flash TTS] ---")
    keys = parse_multiline_keys("GEMINI_API_KEYS") or parse_multiline_keys("GEMINI_API_KEY")
    total = len(keys)
    if total == 0: return False

    voice_id = os.environ.get("GEMINI_VOICE_ID", "voice_z3e67k0f8p8c").strip()
    delivery_style = "Natural, calm, warm and articulate Bengali pronunciation"

    try:
        from google import genai
    except ImportError:
        print("  ⚠️ 'google-genai' library not installed.")
        return False

    start_idx = get_audio_start_index("gemini", total)
    for offset in range(total):
        cur_idx = (start_idx + offset) % total
        api_key = keys[cur_idx]
        print(f"  🚀 Attempting Gemini Key #{cur_idx+1}/{total} (ends in ...{api_key[-4:]})")
        start_t = time.time()
        try:
            client = genai.Client(api_key=api_key)
            interaction = client.interactions.create(
                model="gemini-3.8-flash-tts",
                input=[{
                    "type": "user_input",
                    "content": [{
                        "type": "text",
                        "text": speech_text,
                        "annotations": [{"type": "speech_metadata", "style": delivery_style}]
                    }]
                }],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice_id}]}
            )

            if hasattr(interaction, 'output_audio') and hasattr(interaction.output_audio, 'data'):
                audio_bytes = base64.b64decode(interaction.output_audio.data)
                if len(audio_bytes) > 2000:
                    with open(output_audio_path, "wb") as f:
                        f.write(audio_bytes)
                    set_audio_index("gemini", cur_idx, total)
                    print(f"  ✅ [SUCCESS] Generated via Gemini TTS in {round(time.time() - start_t, 2)}s!")
                    return True
        except Exception as e:
            print(f"  ⚠️ Gemini Key #{cur_idx+1} error: {e}")
        set_audio_index("gemini", cur_idx + 1, total)

    return False

# =========================================================================
# 🌟 ২. দ্বিতীয় প্রায়োরিটি: ElevenLabs API
# =========================================================================

def synthesize_with_elevenlabs(speech_text, output_audio_path):
    print("\n--- [VOICE ENGINE 2: ElevenLabs API] ---")
    keys = parse_multiline_keys("ELEVENLABS_API_KEYS")
    total = len(keys)
    if total == 0: return False

    # ডিফল্ট বাংলা সমর্থিত মাল্টিলিঙ্গুয়াল ভয়েস (Adam/George/Rachel)
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    start_idx = get_audio_start_index("elevenlabs", total)
    for offset in range(total):
        cur_idx = (start_idx + offset) % total
        api_key = keys[cur_idx]
        print(f"  🚀 Attempting ElevenLabs Key #{cur_idx+1}/{total}")
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        payload = {
            "text": speech_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 2000:
                with open(output_audio_path, "wb") as f:
                    f.write(resp.content)
                set_audio_index("elevenlabs", cur_idx, total)
                print(f"  ✅ [SUCCESS] Generated via ElevenLabs Voice Engine!")
                return True
            elif resp.status_code in [401, 429]:
                print(f"  ⚠️ ElevenLabs Key #{cur_idx+1} exhausted (Status {resp.status_code}).")
        except Exception as e:
            print(f"  ⚠️ ElevenLabs Key error: {e}")
        set_audio_index("elevenlabs", cur_idx + 1, total)

    return False

# =========================================================================
# 🌟 ৩. তৃতীয় ব্যাকআপ: Microsoft Edge Neural TTS
# =========================================================================

def synthesize_with_edge_fallback(speech_text, output_audio_path):
    print("\n--- [VOICE ENGINE 3: Microsoft Edge Neural Fallback] ---")
    try:
        import asyncio, edge_tts
        async def _make():
            c = edge_tts.Communicate(speech_text, "bn-BD-PradeepNeural", rate="+0%", pitch="+0Hz")
            await c.save(output_audio_path)
        asyncio.run(_make())
        if os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 1000:
            print("  ✅ [SUCCESS] Generated via Microsoft Edge Neural Engine!")
            return True
    except Exception as e:
        print(f"  ⚠️ Edge fallback error: {e}")
    return False

# =========================================================================
# 🌟 ৪. চতুর্থ চূড়ান্ত ব্যাকআপ: লোকাল অডিও / মিউজিক
# =========================================================================

def fallback_to_local_audio(output_audio_path):
    print("\n--- [FINAL BACKUP: Local Music Fallback] ---")
    for f in ["sample_voice.mp3", "sample_voice.wav", "Photos/bg_music.mp3"]:
        if os.path.exists(f) and os.path.getsize(f) > 1000:
            shutil.copyfile(f, output_audio_path)
            print(f"  ✅ Copied local audio '{f}' to prevent video crash!")
            return True
    return False

# =========================================================================
# 🌟 মাস্টার অডিও পাইপলাইন
# =========================================================================

def generate_voiceover_audio_pipeline(text, output_audio_path):
    speech_text = clean_script_for_speech(text)

    # ১. Gemini 3.8 TTS
    if synthesize_with_gemini(speech_text, output_audio_path):
        return True

    # ২. ElevenLabs
    if synthesize_with_elevenlabs(speech_text, output_audio_path):
        return True

    # ৩. Microsoft Edge
    if synthesize_with_edge_fallback(speech_text, output_audio_path):
        return True

    # ৪. লোকাল ব্যাকগ্রাউন্ড অডিও
    if fallback_to_local_audio(output_audio_path):
        return True

    return False
