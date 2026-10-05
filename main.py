# -*- coding: utf-8 -*-
import os, json, shutil, traceback
from feed_manager import check_new_articles_and_prepare_folders, clean_filename, is_forbidden_article, WORKSPACE_DIR
from ai_service import generate_job_content
from audio_engine import generate_segmented_audio_pipeline
from thumbnail import generate_dynamic_thumbnail
from video_editor import render_matched_video
from youtube_uploader import get_youtube_service, upload_to_youtube

TMP_DIR = "temp_assets"
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "history.txt")

def add_to_history(entry_text):
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
        except Exception: pass

def process_ready_videos(yt):
    print("\nScanning Workspace folders for 10-Minute Video Generation...")
    if not os.path.exists(WORKSPACE_DIR): return
    if not os.path.exists(TMP_DIR): os.makedirs(TMP_DIR, exist_ok=True)

    folders = [f for f in os.listdir(WORKSPACE_DIR) if os.path.isdir(os.path.join(WORKSPACE_DIR, f)) and f.lower() != "shorts"]
    
    for folder_name in folders:
        folder_path = os.path.join(WORKSPACE_DIR, folder_name)
        try:
            if is_forbidden_article(folder_name):
                shutil.rmtree(folder_path, ignore_errors=True)
                continue

            txt_path, link_path, article_path = None, None, None
            img_files = []
            
            for file in sorted(os.listdir(folder_path)):
                ext = file.lower().split('.')[-1]
                if file.lower() == "title.txt": txt_path = os.path.join(folder_path, file)
                elif file.lower() == "link.txt": link_path = os.path.join(folder_path, file)
                elif file.lower() == "article.txt": article_path = os.path.join(folder_path, file)
                elif ext in ['jpg', 'jpeg', 'png', 'webp']: img_files.append(os.path.join(folder_path, file))
                    
            if not img_files:
                shutil.rmtree(folder_path, ignore_errors=True)
                continue

            raw_title = folder_name
            if txt_path and os.path.exists(txt_path):
                with open(txt_path, 'r', encoding='utf-8') as tf: raw_title = tf.read().strip()

            article_link = ""
            if link_path and os.path.exists(link_path):
                with open(link_path, 'r', encoding='utf-8') as lf: article_link = lf.read().strip()

            article_text = ""
            if article_path and os.path.exists(article_path):
                with open(article_path, 'r', encoding='utf-8') as af: article_text = af.read().strip()

            print(f"\n========== In-depth Analysis Started: {folder_name} ==========")

            # ১. এআই থেকে ১০ মিনিটের সেগমেন্টেড স্ক্রিপ্ট ও বাউন্ডিং বক্স আনা
            opt_title, full_script, thumb_meta, video_desc, video_tags, segments = generate_job_content(
                raw_title, img_files, article_text=article_text
            )

            if not segments:
                print(f"⚠️ Could not generate segments for '{folder_name}'. Skipping...")
                continue

            video_title = opt_title

            # ২. সেগমেন্ট ভিত্তিক লং-অডিও জেনারেশন
            audio_segments = generate_segmented_audio_pipeline(segments, TMP_DIR)
            if not audio_segments:
                print("❌ Audio generation failed for all segments.")
                continue

            # ৩. থাম্বনেইল তৈরি
            thumbnail_path = os.path.join(TMP_DIR, "thumbnail.jpg")
            if os.path.exists(thumbnail_path): os.remove(thumbnail_path)
            generate_dynamic_thumbnail(raw_title, thumbnail_path, thumb_meta=thumb_meta)

            # ৪. অডিও-ভিজ্যুয়াল সিঙ্ক্রোনাইজড ভিডিও রেন্ডার
            out_video_file = os.path.join(TMP_DIR, "final_out.mp4")
            if os.path.exists(out_video_file): os.remove(out_video_file)

            print("🎬 Rendering 10-Minute Audio-Visual Matched Video...")
            render_matched_video(audio_segments, img_files, out_video_file)
            
            # ৫. ইউটিউব আপলোড
            upload_success = upload_to_youtube(
                yt, out_video_file, video_title, 
                thumbnail_path if os.path.exists(thumbnail_path) else None,
                description=video_desc,
                tags=video_tags,
                schedule_upload=True
            )
            
            if upload_success:
                add_to_history(raw_title)
                if article_link: add_to_history(article_link)
                shutil.rmtree(folder_path, ignore_errors=True)
                print(f"✅ 10-Minute Video Successfully Uploaded & Cleared: '{folder_name}'\n")

        except Exception as e:
            traceback.print_exc()

if __name__ == "__main__":
    print("\n====== [ 10-Minute In-Depth Video Automation Active ] ======\n")
    try:
        yt_service = get_youtube_service()
        try: check_new_articles_and_prepare_folders()
        except Exception: traceback.print_exc()

        try: process_ready_videos(yt_service)
        except Exception: traceback.print_exc()
    except Exception: traceback.print_exc()
    finally:
        if os.path.exists(TMP_DIR): shutil.rmtree(TMP_DIR, ignore_errors=True)
