# -*- coding: utf-8 -*-
import asyncio
import base64
import io
import json
import os
import re
import requests
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

TRACKER_FILE = "api_key_tracker.json"


def parse_multiline_keys(env_var_name):
    raw = os.environ.get(env_var_name, "").strip()
    if not raw:
        return []
    lines = re.split(r'[\r\n,;]+', raw)
    return [k.strip() for k in lines if k.strip() and not k.strip().startswith('#')]


def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_tracker(data):
    try:
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_audio_start_index(provider, total):
    if total == 0:
        return 0
    val = load_tracker().get(f"{provider}_index", 0)
    return (val if isinstance(val, int) else 0) % total


def set_audio_index(provider, next_idx, total):
    if total == 0:
        return
    t = load_tracker()
    t[f"{provider}_index"] = next_idx % total
    save_tracker(t)


def clean_script_for_speech(raw_text):
    if not raw_text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', str(raw_text), flags=re.DOTALL)
    text = re.sub(r'[\*\_\|\#\~\x60]', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'[\<\>\{\}\(\)\@\$\^\&\+\=\_\\\/]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def split_text_into_chunks(text, max_chars=900):
    raw_parts = re.split(r'([।\?\!\n]+)', str(text))
    sentences = []
    buf = ""
    for p in raw_parts:
        buf += p
        if any(sym in p for sym in ('।', '?', '!', '\n')):
            if buf.strip():
                sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())

    chunks = []
    current = ""
    for sent in sentences:
        if len(sent) > max_chars:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            words = sent.split()
            w_buf = ""
            for w in words:
                if len(w_buf) + len(w) + 1 <= max_chars:
                    w_buf = f"{w_buf} {w}".strip()
                else:
                    if w_buf:
                        chunks.append(w_buf)
                    w_buf = w
            if w_buf:
                current = w_buf
            continue

        if not current:
            current = sent
        elif len(current) + len(sent) + 1 <= max_chars:
            current = f"{current} {sent}"
        else:
            chunks.append(current.strip())
            current = sent

    if current.strip():
        chunks.append(current.strip())
    return chunks


def _save_merged_wav_bytes(wav_chunks, output_audio_path):
    """একাধিক WAV চাংকের PCM ফ্রেম সঠিকভাবে জোড়া লাগিয়ে একটি সম্পূর্ণ অডিও ফাইল তৈরি করে"""
    if not wav_chunks:
        return False

    os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
    tmp_wav = str(output_audio_path) + ".merged.wav"

    try:
        params = None
        frames = []
        for wb in wav_chunks:
            with wave.open(io.BytesIO(wb), "rb") as wf:
                cur_params = wf.getparams()
                if params is None:
                    params = cur_params
                elif (cur_params.nchannels, cur_params.sampwidth, cur_params.framerate) != (
                    params.nchannels, params.sampwidth, params.framerate
                ):
                    raise ValueError("WAV parameter mismatch across chunks")
                frames.append(wf.readframes(wf.getnframes()))

        if params is None or not frames:
            return False

        with wave.open(tmp_wav, "wb") as out_wf:
            out_wf.setparams(params)
            for fr in frames:
                out_wf.writeframes(fr)

    except Exception:
        if not shutil.which("ffmpeg"):
            return False
        with tempfile.TemporaryDirectory() as cdir:
            list_txt = os.path.join(cdir, "files.txt")
            with open(list_txt, "w", encoding="utf-8") as lf:
                for i, wb in enumerate(wav_chunks):
                    cp = os.path.join(cdir, f"c_{i:04d}.wav")
                    with open(cp, "wb") as cf:
                        cf.write(wb)
                    lf.write(f"file '{cp}'\n")
            res = subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", tmp_wav],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if res.returncode != 0 or not os.path.exists(tmp_wav):
                return False

    try:
        if str(output_audio_path).lower().endswith(".mp3") and shutil.which("ffmpeg"):
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_wav, "-codec:a", "libmp3lame", "-b:a", "192k", str(output_audio_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.remove(tmp_wav)
        else:
            os.replace(tmp_wav, output_audio_path)
        return os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 1000
    finally:
        if os.path.exists(tmp_wav):
            try:
                os.remove(tmp_wav)
            except Exception:
                pass


def _finalize_mp3_to_target(raw_mp3_path, output_audio_path):
    os.makedirs(os.path.dirname(output_audio_path) or ".", exist_ok=True)
    if str(output_audio_path).lower().endswith(".wav") and shutil.which("ffmpeg"):
        subprocess.run(
            ["ffmpeg", "-y", "-i", raw_mp3_path, "-ar", "24000", "-ac", "1", str(output_audio_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.remove(raw_mp3_path)
    else:
        os.replace(raw_mp3_path, output_audio_path)
    return os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 1000


def has_kaggle_credentials():
    return bool(
        os.environ.get("KAGGLE_API_TOKEN", "").strip()
        or (Path.home() / ".kaggle" / "kaggle.json").exists()
        or (Path.home() / ".kaggle" / "access_token").exists()
    )


def _extract_gemini_audio_bytes(interaction):
    if hasattr(interaction, 'output_audio') and getattr(interaction.output_audio, 'data', None):
        return base64.b64decode(interaction.output_audio.data)
    for out in getattr(interaction, 'outputs', []) or []:
        if getattr(out, 'type', None) == 'audio' and getattr(out, 'data', None):
            return base64.b64decode(out.data)
    return None


def synthesize_chunk_gemini(chunk_text, client, voice_id, model_name="gemini-3.8-flash-tts"):
    try:
        interaction = client.interactions.create(
            model=model_name,
            input=[{"type": "user_input", "content": [{"type": "text", "text": chunk_text}]}],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice_id}]}
        )
        return _extract_gemini_audio_bytes(interaction)
    except Exception as e:
        err_msg = str(e).lower()
        if voice_id != "Puck" and any(k in err_msg for k in ("voice", "not found", "404", "permission")):
            interaction = client.interactions.create(
                model=model_name,
                input=[{"type": "user_input", "content": [{"type": "text", "text": chunk_text}]}],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": "Puck"}]}
            )
            return _extract_gemini_audio_bytes(interaction)
        raise


def synthesize_with_gemini(speech_text, output_audio_path):
    keys = parse_multiline_keys("GEMINI_API_KEYS") or parse_multiline_keys("GEMINI_API_KEY")
    total = len(keys)
    if total == 0:
        return False

    voice_id = os.environ.get("GEMINI_VOICE_ID", "voice_z3e67k0f8p8c").strip() or "voice_z3e67k0f8p8c"
    try:
        from google import genai
    except ImportError:
        return False

    chunks = split_text_into_chunks(speech_text, max_chars=900)
    start_idx = get_audio_start_index("gemini", total)

    for offset in range(total):
        cur_idx = (start_idx + offset) % total
        api_key = keys[cur_idx]
        for model_name in ("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"):
            try:
                client = genai.Client(api_key=api_key)
                audio_bytes_list = []
                failed = False

                for c in chunks:
                    b = synthesize_chunk_gemini(c, client, voice_id, model_name=model_name)
                    if b and len(b) > 500:
                        audio_bytes_list.append(b)
                    else:
                        failed = True
                        break

                if not failed and len(audio_bytes_list) == len(chunks):
                    if _save_merged_wav_bytes(audio_bytes_list, output_audio_path):
                        set_audio_index("gemini", cur_idx, total)
                        print(f"  ✅ [SUCCESS] Voice generated via {model_name} (Key #{cur_idx + 1})!")
                        return True
            except Exception as e:
                print(f"  ⚠️ Gemini TTS ({model_name}, Key #{cur_idx + 1}) notice: {e}")
        set_audio_index("gemini", cur_idx + 1, total)

    return False


def synthesize_with_elevenlabs(speech_text, output_audio_path):
    keys = parse_multiline_keys("ELEVENLABS_API_KEYS")
    total = len(keys)
    if total == 0:
        return False

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip() or "21m00Tcm4TlvDq8ikWAM"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    chunks = split_text_into_chunks(speech_text, max_chars=450)
    start_idx = get_audio_start_index("elevenlabs", total)

    for offset in range(total):
        cur_idx = (start_idx + offset) % total
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": keys[cur_idx]}
        audio_bytes_list = []
        failed = False

        for c in chunks:
            payload = {"text": c, "model_id": "eleven_multilingual_v2"}
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=60)
                if resp.status_code == 200 and len(resp.content) > 500:
                    audio_bytes_list.append(resp.content)
                else:
                    failed = True
                    break
            except Exception:
                failed = True
                break

        if not failed and len(audio_bytes_list) == len(chunks):
            raw_mp3 = str(output_audio_path) + ".el.mp3"
            try:
                with open(raw_mp3, "wb") as f:
                    for ab in audio_bytes_list:
                        f.write(ab)
                if _finalize_mp3_to_target(raw_mp3, output_audio_path):
                    set_audio_index("elevenlabs", cur_idx, total)
                    print("  ✅ [SUCCESS] Generated via ElevenLabs API!")
                    return True
            finally:
                if os.path.exists(raw_mp3):
                    try:
                        os.remove(raw_mp3)
                    except Exception:
                        pass
        set_audio_index("elevenlabs", cur_idx + 1, total)

    return False


def synthesize_with_edge_fallback(speech_text, output_audio_path):
    """ব্যাকআপ: Microsoft Edge TTS (bn-BD-PradeepNeural) — সামান্য ধীর ও স্পষ্ট গতি (-7%)"""
    print("\n--- [BACKUP AUDIO] Microsoft Edge TTS (bn-BD-PradeepNeural) ---")
    if not speech_text:
        return False

    raw_mp3 = str(output_audio_path) + ".edge.mp3"
    try:
        import edge_tts

        voice_name = os.environ.get("EDGE_TTS_VOICE", "bn-BD-PradeepNeural").strip() or "bn-BD-PradeepNeural"
        rate_str = os.environ.get("EDGE_TTS_RATE", "-7%").strip() or "-7%"
        start_t = time.time()

        async def _make():
            communicate = edge_tts.Communicate(speech_text, voice_name, rate=rate_str, pitch="+0Hz")
            await communicate.save(raw_mp3)

        asyncio.run(_make())

        if os.path.exists(raw_mp3) and os.path.getsize(raw_mp3) > 1000:
            if _finalize_mp3_to_target(raw_mp3, output_audio_path):
                audio_mb = round(os.path.getsize(output_audio_path) / (1024 * 1024), 2)
                print(f"  ✅ [SUCCESS] Generated via Edge TTS Backup (rate={rate_str})! ({audio_mb} MB in {round(time.time() - start_t, 2)}s)")
                return True
    except Exception as e:
        print(f"  ⚠️ Edge TTS backup failed: {e}")
    finally:
        if os.path.exists(raw_mp3):
            try:
                os.remove(raw_mp3)
            except Exception:
                pass

    return False


def synthesize_local_fallback(output_audio_path):
    for f in ["sample_voice.mp3", "sample_voice.wav", "Photos/bg_music.mp3"]:
        if os.path.exists(f) and os.path.getsize(f) > 1000:
            if str(output_audio_path).lower().endswith(".wav") and f.lower().endswith(".mp3") and shutil.which("ffmpeg"):
                subprocess.run(
                    ["ffmpeg", "-y", "-i", f, "-ar", "24000", "-ac", "1", str(output_audio_path)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                shutil.copyfile(f, output_audio_path)
            print(f"  ✅ Copied local fallback audio '{f}'!")
            return True
    return False


def generate_voiceover_batch_pipeline(batch_items, batch_work_dir):
    if not batch_items:
        return {}

    os.makedirs(batch_work_dir, exist_ok=True)
    cleaned_tasks = []
    for item in batch_items:
        sp_text = clean_script_for_speech(item["text"])
        cleaned_tasks.append({
            "filename": item["filename"],
            "text": sp_text,
            "target_path": item["target_path"],
        })

    default_prio = "kaggle,gemini,elevenlabs,edge"
    prio_list = [
        p.strip().lower()
        for p in os.environ.get("TTS_PROVIDER_PRIORITY", default_prio).split(",")
        if p.strip()
    ]

    print("\n" + "=" * 65)
    print(f"🎙️ [AUDIO ENGINE] Provider Chain: {' ➔ '.join(p.upper() for p in prio_list)}")
    print(f"📦 Total Scripts Queued: {len(cleaned_tasks)}")
    for idx, t in enumerate(cleaned_tasks, 1):
        print(f"  #{idx}: {t['filename']} | {len(t['text'].split())} words | {len(t['text'])} chars")
    print("=" * 65)

    results = {}

    for provider in prio_list:
        pending = [t for t in cleaned_tasks if t["filename"] not in results and t["text"]]
        if not pending:
            break

        if provider == "kaggle":
            if not has_kaggle_credentials():
                print("ℹ️ [Kaggle TTS] KAGGLE_API_TOKEN not set — skipping Kaggle batch.")
                continue
            try:
                from kaggle_tts import generate_voices_batch
                default_voice = os.environ.get("KAGGLE_DEFAULT_VOICE", "male").strip().lower()
                speech_speed = float(os.environ.get("KAGGLE_SPEECH_SPEED", "0.93"))
                nfe_step = int(os.environ.get("KAGGLE_NFE_STEP", "16"))
                generated_map = generate_voices_batch(
                    tasks=[{"filename": t["filename"], "text": t["text"]} for t in pending],
                    output_dir=batch_work_dir,
                    default_voice=default_voice,
                    speech_speed=speech_speed,
                    nfe_step=nfe_step,
                )
                for t in pending:
                    src = generated_map.get(t["filename"])
                    dst = Path(t["target_path"])
                    if src and Path(src).exists() and Path(src).stat().st_size > 1000:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        if str(dst).lower().endswith(".mp3") and shutil.which("ffmpeg"):
                            subprocess.run(
                                ["ffmpeg", "-y", "-i", str(src), "-codec:a", "libmp3lame", "-b:a", "192k", str(dst)],
                                check=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            os.remove(src)
                        else:
                            shutil.move(str(src), str(dst))
                        results[t["filename"]] = str(dst)
                        print(f"  🎵 Saved '{t['filename']}' -> {dst}")
            except Exception as e:
                print(f"\n⚠️ [Kaggle TTS Failed] ({e}) — Trying next audio provider...")

        elif provider == "gemini":
            for t in pending:
                dst = t["target_path"]
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                if synthesize_with_gemini(t["text"], dst):
                    results[t["filename"]] = dst

        elif provider == "elevenlabs":
            for t in pending:
                dst = t["target_path"]
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                if synthesize_with_elevenlabs(t["text"], dst):
                    results[t["filename"]] = dst

        elif provider == "edge":
            for t in pending:
                dst = t["target_path"]
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                if synthesize_with_edge_fallback(t["text"], dst):
                    results[t["filename"]] = dst

    for t in cleaned_tasks:
        if t["filename"] not in results:
            dst = t["target_path"]
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            if synthesize_local_fallback(dst):
                results[t["filename"]] = dst

    return results


def generate_voiceover_audio_pipeline(text, output_audio_path):
    """একক অডিও জেনারেশনের হেল্পার ফাংশন"""
    fname = os.path.basename(output_audio_path)
    res = generate_voiceover_batch_pipeline(
        [{"filename": fname, "text": text, "target_path": output_audio_path}],
        batch_work_dir=os.path.join("temp_assets", "single_audio"),
    )
    return fname in res
