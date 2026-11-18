# -*- coding: utf-8 -*-
import io
import os
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")


def clean_script_for_speech(raw_text):
    if not raw_text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', str(raw_text), flags=re.DOTALL)
    text = re.sub(r'[\*\_\|\#\~\x60]', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'[\<\>\{\}\(\)\@\$\^\&\+\=\_\\\/]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def split_text_into_chunks(text, max_chars=450):
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


def _merge_wav_chunks_bytes(wav_bytes_list, out_wav_path, pause_sec=0.12):
    if not wav_bytes_list:
        return False

    params = None
    frames = []
    silence = b""

    for idx, wb in enumerate(wav_bytes_list):
        if not wb or len(wb) < 44:
            continue
        with wave.open(io.BytesIO(wb), "rb") as wf:
            cur_params = wf.getparams()
            if params is None:
                params = cur_params
                silence_frames = int(params.framerate * pause_sec)
                silence = b"\x00" * (silence_frames * params.nchannels * params.sampwidth)
            elif (cur_params.nchannels, cur_params.sampwidth, cur_params.framerate) != (
                params.nchannels, params.sampwidth, params.framerate
            ):
                raise ValueError("WAV format mismatch across Ninada chunks")
            frames.append(wf.readframes(wf.getnframes()))
            if idx < len(wav_bytes_list) - 1 and silence:
                frames.append(silence)

    if params is None or not frames:
        return False

    with wave.open(str(out_wav_path), "wb") as out_wf:
        out_wf.setparams(params)
        for fr in frames:
            out_wf.writeframes(fr)

    return Path(out_wav_path).exists() and Path(out_wav_path).stat().st_size > 1000


def _postprocess_ninada_audio(raw_wav_path: Path, final_output_path: Path):
    """Ninada ব্যাকআপ: atempo=0.92 ও স্টুডিও মাস্টারিং প্রয়োগ করে চূড়ান্ত অডিও তৈরি"""
    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    if not shutil.which("ffmpeg"):
        shutil.copy2(raw_wav_path, final_output_path)
        return final_output_path.exists() and final_output_path.stat().st_size > 1000

    tempo = os.environ.get("NINADA_ATEMPO", "0.92").strip() or "0.92"
    use_mastering = os.environ.get("NINADA_STUDIO_MASTERING", "true").strip().lower() in ("true", "1", "yes", "on")

    af_chain = f"atempo={tempo}"
    if use_mastering:
        af_chain += (
            ",highpass=f=80"
            ",equalizer=f=250:t=q:w=1.2:g=2.5"
            ",equalizer=f=4500:t=q:w=1.5:g=-3.5"
            ",acompressor=threshold=-18dB:ratio=2.5:attack=10:release=100"
            ",loudnorm=I=-16:TP=-1.5:LRA=11"
        )

    cmd = ["ffmpeg", "-y", "-i", str(raw_wav_path), "-af", af_chain]
    if str(final_output_path).lower().endswith(".mp3"):
        cmd.extend(["-codec:a", "libmp3lame", "-b:a", "192k", str(final_output_path)])
    else:
        cmd.extend(["-c:a", "pcm_s16le", str(final_output_path)])

    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode == 0 and final_output_path.exists() and final_output_path.stat().st_size > 1000:
        return True

    fallback_cmd = [
        "ffmpeg", "-y", "-i", str(raw_wav_path),
        "-filter:a", f"atempo={tempo}", "-c:a", "pcm_s16le", str(final_output_path)
    ]
    res2 = subprocess.run(fallback_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res2.returncode == 0 and final_output_path.exists() and final_output_path.stat().st_size > 1000:
        return True

    shutil.copy2(raw_wav_path, final_output_path)
    return final_output_path.exists() and final_output_path.stat().st_size > 1000


def synthesize_with_ninada(tts_engine, speech_text, output_audio_path):
    """Priority 2 (Backup): Ninada v5.1.2 জেনারেশন"""
    if not speech_text:
        return False

    out_path = Path(output_audio_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_raw_wav = out_path.with_suffix(".ninada_raw.wav")

    voice_gender = os.environ.get("NINADA_VOICE", "male").strip().lower() or "male"
    chunks = split_text_into_chunks(speech_text, max_chars=450)
    wav_chunks = []

    try:
        start_t = time.time()
        for ch in chunks:
            wb = tts_engine.speak(ch, lang="bn", voice=voice_gender)
            if wb and len(wb) > 100:
                wav_chunks.append(wb)

        if not wav_chunks:
            return False

        if not _merge_wav_chunks_bytes(wav_chunks, tmp_raw_wav):
            return False

        if _postprocess_ninada_audio(tmp_raw_wav, out_path):
            audio_mb = round(out_path.stat().st_size / (1024 * 1024), 2)
            print(f"  ✅ [SUCCESS] Generated via Ninada v5.1.2 Backup ({voice_gender})! ({audio_mb} MB in {round(time.time() - start_t, 2)}s)")
            return True
    except Exception as e:
        print(f"  ❌ Ninada Backup TTS Error: {e}")
    finally:
        if tmp_raw_wav.exists():
            try:
                tmp_raw_wav.unlink()
            except Exception:
                pass

    return False


def has_kaggle_credentials():
    return bool(
        os.environ.get("KAGGLE_API_TOKEN", "").strip()
        or (Path.home() / ".kaggle" / "kaggle.json").exists()
        or (Path.home() / ".kaggle" / "access_token").exists()
    )


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
    """
    🌟 হাইব্রিড অডিও পাইপলাইন:
    ১ম অগ্রাধিকার (Primary): Kaggle IndicF5_Bangladeshi (ডুয়াল T4 GPU ব্যাচ)
    ২য় অগ্রাধিকার (Backup): Ninada v5.1.2 Neural TTS (atempo=0.92 + Studio Mastering)
    ৩য় অগ্রাধিকার (Fallback): লোকাল স্যাম্পল অডিও
    """
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

    print("\n" + "=" * 65)
    print("🎙️ [AUDIO ENGINE] Primary: Kaggle IndicF5 | Backup: Ninada v5.1.2")
    print(f"📦 Total Scripts Queued: {len(cleaned_tasks)}")
    for idx, t in enumerate(cleaned_tasks, 1):
        print(f"  #{idx}: {t['filename']} | {len(t['text'].split())} words | {len(t['text'])} chars")
    print("=" * 65)

    results = {}

    # =========================================================================
    # 🌟 ধাপ ১: ১ম অগ্রাধিকার (Primary) - Kaggle IndicF5 (এককালীন ব্যাচ কল)
    # =========================================================================
    if has_kaggle_credentials():
        try:
            from kaggle_tts import generate_voices_batch
            default_voice = os.environ.get("KAGGLE_DEFAULT_VOICE", "male").strip().lower()
            speech_speed = float(os.environ.get("KAGGLE_SPEECH_SPEED", "0.93"))
            nfe_step = int(os.environ.get("KAGGLE_NFE_STEP", "16"))
            print("🚀 [Kaggle TTS] Submitting batch to Kaggle dual-GPU cluster...")
            generated_map = generate_voices_batch(
                tasks=[{"filename": t["filename"], "text": t["text"]} for t in cleaned_tasks],
                output_dir=batch_work_dir,
                default_voice=default_voice,
                speech_speed=speech_speed,
                nfe_step=nfe_step,
            )
            for t in cleaned_tasks:
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

            if len(results) == len(cleaned_tasks):
                return results
        except Exception as e:
            print(f"\n⚠️ [Kaggle TTS Failed] ({e}) — Switching to Backup Engine: Ninada v5.1.2...")
    else:
        print("ℹ️ KAGGLE_API_TOKEN পাওয়া যায়নি। সরাসরি ব্যাকআপ ইঞ্জিন (Ninada v5.1.2) ব্যবহার করা হচ্ছে...")

    # =========================================================================
    # 🌟 ধাপ ২: ২য় অগ্রাধিকার (Backup) - Ninada v5.1.2
    # =========================================================================
    pending = [t for t in cleaned_tasks if t["filename"] not in results and t["text"]]
    if pending:
        try:
            from ninada import Ninada
            tts_engine = Ninada(lang="bn")
            for t in pending:
                dst = t["target_path"]
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                if synthesize_with_ninada(tts_engine, t["text"], dst):
                    results[t["filename"]] = dst
        except Exception as e:
            print(f"⚠️ Ninada backup initialization failed: {e}")

    # =========================================================================
    # 🌟 ধাপ ৩: লোকাল ফলব্যাক (যদি কোনো কারণে দুটোই ব্যর্থ হয়)
    # =========================================================================
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
