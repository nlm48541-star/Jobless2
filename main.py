# -*- coding: utf-8 -*-
import os, json, shutil, traceback
from datetime import datetime
from feed_manager import check_new_articles_and_prepare_folders, clean_filename, is_forbidden_article, WORKSPACE_DIR
from ai_service import generate_job_content
from audio_engine import generate_voiceover_audio_pipeline
from thumbnail import generate_dynamic_thumbnail
from video_editor import render_video_slideshow
from youtube_uploader import get_youtube_service, upload_to_youtube

TMP_DIR = "temp_assets"
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "history.txt")
SKIPPED_JOBS_FILE = "skipped_jobs.json"

def add_to_history(entry_text):
    """সফলভাবে আপলোড হওয়া ভিডিওর হিস্টোরি সংরক্ষণ করে"""
    if not entry_text or not str(entry_text).strip(): return
    clean_val = str(entry_text).strip()
    existing_records = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as hf:
                existing_records = {line.strip().lower() for line in hf if line.strip()}
        except Exception: pass

    if clean_val.lower() not in existing_records:
        try:
            os.makedirs(WORKSPACE_DIR, exist_ok=True)
            with open(HISTORY_FILE, "a", encoding="utf-8") as hf:
                hf.write(f"{clean_val}\n")
            print(f"📝 [HISTORY] Saved: '{clean_val[:60]}'")
        except Exception: pass

def add_to_skipped_jobs(link, title, reason="ডাকযোগ / সরাসরি অফিসে আবেদন"):
    """অফলাইন আবেদনের জন্য বাদ পড়া পোস্টগুলো JSON ফাইলে সংরক্ষণ করে"""
    if not link: return
    data = {}
    if os.path.exists(SKIPPED_JOBS_FILE):
        try:
            with open(SKIPPED_JOBS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception: data = {}

    data[link.strip()] = {
        "title": title,
        "reason": reason,
        "skipped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        with open(SKIPPED_JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"📁 [SAVED TO JSON] Logged skipped offline job in '{SKIPPED_JOBS_FILE}'.")
    except Exception as e:
        print(f"⚠️ Failed to write to {SKIPPED_JOBS_FILE}: {e}")

def process_ready_videos(yt):
    print("\nScanning Workspace folders for Videos / AI Processing...")
    if not os.path.exists(WORKSPACE_DIR): return
    if not os.path.exists(TMP_DIR): os.makedirs(TMP_DIR, exist_ok=True)

    folders = [f for f in os.listdir(WORKSPACE_DIR) if os.path.isdir(os.path.join(WORKSPACE_DIR, f)) and f.lower() != "shorts"]
    
    for folder_name in folders:
        folder_path = os.path.join(WORKSPACE_DIR, folder_name)
        try:
            if is_forbidden_article(folder_name):
                shutil.rmtree(folder_path, ignore_errors=True)
                continue

            existing_audio_file, txt_path, link_path, article_path = None, None, None, None
            img_files = []
            
            for file in sorted(os.listdir(folder_path)):
                ext = file.lower().split('.')[-1]
                if ext in ['mp3', 'wav', 'm4a', 'aac']:
                    existing_audio_file = file
                elif file.lower() == "title.txt":
                    txt_path = os.path.join(folder_path, file)
                elif file.lower() == "link.txt":
                    link_path = os.path.join(folder_path, file)
                elif file.lower() == "article.txt":
                    article_path = os.path.join(folder_path, file)
                elif ext in ['jpg', 'jpeg', 'png', 'webp']: 
                    img_files.append(os.path.join(folder_path, file))
                    
            if not img_files:
                shutil.rmtree(folder_path, ignore_errors=True)
                continue

            raw_title = folder_name
            if txt_path and os.path.exists(txt_path):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as tf:
                        raw_title = tf.read().strip()
                except Exception: pass

            article_link = ""
            if link_path and os.path.exists(link_path):
                try:
                    with open(link_path, 'r', encoding='utf-8') as lf:
                        article_link = lf.read().strip()
                except Exception: pass

            article_text = ""
            if article_path and os.path.exists(article_path):
                try:
                    with open(article_path, 'r', encoding='utf-8') as af:
                        article_text = af.read().strip()
                except Exception: pass

            if is_forbidden_article(raw_title):
                shutil.rmtree(folder_path, ignore_errors=True)
                continue

            print(f"\n========== Analyzing circular: {folder_name} ==========")

            opt_title, voiceover_script, thumb_meta, video_desc, video_tags = generate_job_content(
                raw_title, img_files, article_text=article_text
            )

            # 🌟 [অফলাইন আবেদন ফিল্টারিং]: ডাকযোগ/কুরিয়ার/সরাসরি অফিসে আবেদন হলে স্কিপ
            if thumb_meta and thumb_meta.get("is_offline"):
                reason = thumb_meta.get("reason", "ডাকযোগ / সরাসরি অফিসে আবেদন")
                print(f"🚫 [SKIPPED - OFFLINE APPLICATION] '{raw_title}' requires offline submission ({reason}).")
                add_to_skipped_jobs(article_link, raw_title, reason=reason)
                shutil.rmtree(folder_path, ignore_errors=True)
                continue

            if not opt_title:
                continue

            video_title = opt_title

            # অডিও তৈরি
            if existing_audio_file:
                audio_path = os.path.join(folder_path, existing_audio_file)
            else:
                if not voiceover_script: continue
                gen_audio_path = os.path.join(folder_path, "voiceover.mp3")
                audio_success = generate_voiceover_audio_pipeline(voiceover_script, gen_audio_path)
                if not audio_success or not os.path.exists(gen_audio_path):
                    continue
                audio_path = gen_audio_path

            # থাম্বনেইল তৈরি
            thumbnail_path = os.path.join(TMP_DIR, "thumbnail.jpg")
            if os.path.exists(thumbnail_path): os.remove(thumbnail_path)
            generate_dynamic_thumbnail(raw_title, thumbnail_path, thumb_meta=thumb_meta)

            # ভিডিও রেন্ডারিং
            out_video_file = os.path.join(TMP_DIR, "final_out.mp4")
            if os.path.exists(out_video_file): os.remove(out_video_file)

            print("Rendering 16:9 Landscape slideshow for YouTube upload...")
            render_video_slideshow(audio_path, img_files, out_video_file, is_vertical=False)
            
            # ইউটিউবে আপলোড
            upload_success = upload_to_youtube(
                yt, out_video_file, video_title, 
                thumbnail_path if os.path.exists(thumbnail_path) else None,
                description=video_desc,
                tags=video_tags,
                schedule_upload=True
            )
            
            # সফল হলে হিস্টোরি সেভ ও লোকাল ফাইল রিমুভ
            if upload_success:
                add_to_history(raw_title)
                if article_link:
                    add_to_history(article_link)

                shutil.rmtree(folder_path, ignore_errors=True)
                print(f"✅ Folder '{folder_name}' successfully uploaded and cleaned.\n")

        except Exception as folder_error:
            traceback.print_exc()

def process_shorts_folder(yt):
    shorts_dir = None
    if os.path.exists(WORKSPACE_DIR):
        for f in os.listdir(WORKSPACE_DIR):
            if f.lower() == "shorts" and os.path.isdir(os.path.join(WORKSPACE_DIR, f)):
                shorts_dir = os.path.join(WORKSPACE_DIR, f)
                break
    if not shorts_dir: return

    for file in os.listdir(shorts_dir):
        if file == ".keep": continue
        file_path = os.path.join(shorts_dir, file)
        if os.path.isdir(file_path): continue 
        
        ext = file.lower().split('.')[-1]
        if ext in ['mp4', 'mov', 'mkv', 'avi']:
            video_title = os.path.splitext(file)[0]
            upload_success = upload_to_youtube(
                yt, file_path, video_title, thumbnail_path=None, 
                description=video_title, tags=None, schedule_upload=True
            )
            if upload_success:
                add_to_history(f"[SHORTS] {video_title}")
                try: os.remove(file_path)
                except Exception: pass

if __name__ == "__main__":
    print("\n====== [ YouTube Direct Automation Active | Smart Offline Filter ] ======\n")
    try:
        yt_service = get_youtube_service()
        try: check_new_articles_and_prepare_folders()
        except Exception: traceback.print_exc()

        try: process_ready_videos(yt_service)
        except Exception: traceback.print_exc()

        try: process_shorts_folder(yt_service)
        except Exception: traceback.print_exc()
    except Exception:
        traceback.print_exc()
    finally:
        if os.path.exists(TMP_DIR): shutil.rmtree(TMP_DIR, ignore_errors=True)
        print("\nAll Tasks Finalized Perfectly.\n======================================")
