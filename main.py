# -*- coding: utf-8 -*-
import os, json, re, shutil, traceback, subprocess
from feed_manager import (
    check_new_articles_and_prepare_folders,
    clean_filename,
    is_forbidden_article,
    scrape_page_details,
    download_image,
    WORKSPACE_DIR
)
from ai_service import generate_job_content, convert_all_numbers_in_script, detect_application_mode_from_text
from audio_engine import generate_segmented_audio_pipeline
from thumbnail import generate_dynamic_thumbnail
from video_editor import render_matched_video
from youtube_uploader import get_youtube_service, upload_to_youtube

TMP_DIR = "temp_assets"
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "history.txt")

# 🌟 ১০ মিনিটের ভিডিও হওয়ার কারণে প্রতি রানে সর্বোচ্চ ২টি ভিডিও প্রসেস হবে
# এতে ১৫-২৫ মিনিটের মধ্যে রান সফলভাবে শেষ হবে এবং টাইমআউট বা ক্যানসেল হবে না
MAX_VIDEOS_PER_RUN = 2

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
            print(f"📝 [HISTORY] Saved: '{clean_val[:60]}'")
        except Exception: pass

def empty_google_drive_folder(folder_id):
    print(f"🧹 [DRIVE CLEANUP] Emptying Google Drive Folder (ID: {folder_id})...")
    try:
        subprocess.run([
            "rclone", "delete", "gdrive:",
            f"--drive-root-folder-id={folder_id}",
            "--drive-use-trash=false",
            "--fast-list"
        ], check=True, timeout=120)

        subprocess.run([
            "rclone", "rmdirs", "gdrive:",
            f"--drive-root-folder-id={folder_id}",
            "--leave-root"
        ], timeout=60)
        print("✅ Google Drive folder emptied successfully!")
    except Exception as e:
        print(f"⚠️ Drive cleanup notice: {e}")

# =========================================================================
# 🌟 ১. ম্যানুয়াল গুগল ড্রাইভ টাস্ক
# =========================================================================

def process_manual_drive_task(yt):
    enable_manual = os.environ.get("ENABLE_MANUAL_FOLDER", "false").strip().lower() == "true"
    folder_id = os.environ.get("MANUAL_DRIVE_FOLDER_ID", "").strip()

    if not enable_manual or not folder_id:
        return False

    rclone_conf = os.path.expanduser('~/.config/rclone/rclone.conf')
    if not os.path.exists(rclone_conf):
        print("ℹ️ Rclone config file not found. Skipping manual drive scan.")
        return False

    manual_dir = "workspace_manual"
    if os.path.exists(manual_dir): shutil.rmtree(manual_dir, ignore_errors=True)
    os.makedirs(manual_dir, exist_ok=True)

    print(f"\n📥 [MANUAL DRIVE] Checking Drive folder (ID: {folder_id})...")
    try:
        res = subprocess.run([
            "rclone", "sync", "gdrive:", manual_dir,
            f"--drive-root-folder-id={folder_id}",
            "--fast-list"
        ], capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            print(f"ℹ️ Rclone notice: {res.stderr[:120]}")
            return False
    except Exception as e:
        print(f"ℹ️ Rclone check skipped: {e}")
        return False

    drive_files = [f for f in os.listdir(manual_dir) if not f.startswith(".")]
    if not drive_files:
        print("ℹ️ Google Drive folder is currently EMPTY. Proceeding to RSS...")
        return False

    print(f"🎯 [MANUAL DRIVE] Detected {len(drive_files)} file(s): {drive_files}")

    try:
        script_file, link_file, custom_thumb, title_file = None, None, None, None
        img_files = []

        for f in drive_files:
            fl = f.lower()
            fp = os.path.join(manual_dir, f)
            if fl == "script.txt": script_file = fp
            elif fl == "link.txt": link_file = fp
            elif fl == "title.txt": title_file = fp
            elif fl in ["thumbnail.png", "thumbnail.jpg", "thumbnail.jpeg"]: custom_thumb = fp
            elif fl.endswith(('.jpg', '.jpeg', '.png', '.webp')): img_files.append(fp)

        scraped_text, article_link = "", ""
        if link_file and os.path.exists(link_file):
            with open(link_file, "r", encoding="utf-8") as lf: article_link = lf.read().strip()
            if article_link:
                scraped_imgs, page_body = scrape_page_details(article_link)
                scraped_text = page_body
                if not img_files and scraped_imgs:
                    for s_idx, s_url in enumerate(scraped_imgs[:3], start=1):
                        tgt_p = os.path.join(manual_dir, f"scraped_{s_idx}.jpg")
                        if download_image(s_url, tgt_p, referer_url=article_link):
                            img_files.append(tgt_p)

        user_script = None
        if script_file and os.path.exists(script_file):
            with open(script_file, "r", encoding="utf-8") as sf: user_script = sf.read().strip()
            print("📝 [CUSTOM SCRIPT] Using provided 'script.txt' directly.")

        raw_title = "জরুরি নিয়োগ বিজ্ঞপ্তি"
        if title_file and os.path.exists(title_file):
            with open(title_file, "r", encoding="utf-8") as tf: raw_title = tf.read().strip()
        elif user_script:
            raw_title = user_script.split("\n")[0][:80].strip()

        if not img_files:
            print("❌ No circular images found in manual folder.")
            return False

        if not os.path.exists(TMP_DIR): os.makedirs(TMP_DIR, exist_ok=True)

        if user_script:
            video_title = raw_title
            video_desc = user_script[:500] + "\n\nআবেদন করতে যোগাযোগ করুন আমাদের হোয়াটসঅ্যাপে।"
            video_tags = ['চাকরির সার্কুলার', 'চাকরির খবর', 'job circular']
            
            paragraphs = [p.strip() for p in user_script.split("\n\n") if p.strip()]
            if len(paragraphs) < 3:
                paragraphs = [p.strip() for p in re.split(r'[।\n]+', user_script) if len(p.strip()) > 30]
            
            segments = []
            for p_idx, para in enumerate(paragraphs, start=1):
                clean_chunk = convert_all_numbers_in_script(para)
                segments.append({
                    "title": f"অংশ {p_idx}",
                    "script": clean_chunk,
                    "image_index": 1,
                    "box_2d": [100, 0, 900, 1000]
                })

            app_mode = detect_application_mode_from_text(user_script + " " + scraped_text)
            thumb_meta = {
                "application_mode": app_mode,
                "org_name": raw_title.split("নিয়োগ")[0].strip()[:35],
                "job_type": "govt"
            }
        else:
            opt_title, _, thumb_meta, video_desc, video_tags, segments = generate_job_content(
                raw_title, img_files, article_text=scraped_text
            )
            video_title = opt_title

        if not segments: return False

        audio_segments = generate_segmented_audio_pipeline(segments, TMP_DIR)
        if not audio_segments: return False

        final_thumb_path = None
        first_circular_img = img_files[0] if img_files else None

        if custom_thumb and os.path.exists(custom_thumb):
            final_thumb_path = custom_thumb
        else:
            gen_thumb = os.path.join(TMP_DIR, "thumbnail.jpg")
            if os.path.exists(gen_thumb): os.remove(gen_thumb)
            generate_dynamic_thumbnail(
                raw_title, gen_thumb, thumb_meta=thumb_meta, circular_img_path=first_circular_img
            )
            final_thumb_path = gen_thumb

        out_video_file = os.path.join(TMP_DIR, "manual_final.mp4")
        if os.path.exists(out_video_file): os.remove(out_video_file)
        render_matched_video(audio_segments, img_files, out_video_file)

        upload_success = upload_to_youtube(
            yt, out_video_file, video_title, final_thumb_path,
            description=video_desc, tags=video_tags, schedule_upload=False
        )

        if upload_success:
            print("🎉 [MANUAL SUCCESS] Video uploaded to YouTube!")
            add_to_history(video_title)
            if article_link: add_to_history(article_link)
            empty_google_drive_folder(folder_id)
            shutil.rmtree(manual_dir, ignore_errors=True)
            return True

    except Exception as me:
        print(f"❌ Error in manual drive task: {me}")
        traceback.print_exc()

    return False

# =========================================================================
# 🌟 ২. নিয়মিত আরএসএস অটোমেশন
# =========================================================================

def process_ready_videos(yt):
    print("\nScanning Workspace folders for Scheduled Videos...")
    if not os.path.exists(WORKSPACE_DIR): return
    if not os.path.exists(TMP_DIR): os.makedirs(TMP_DIR, exist_ok=True)

    folders = [f for f in sorted(os.listdir(WORKSPACE_DIR)) if os.path.isdir(os.path.join(WORKSPACE_DIR, f)) and f.lower() != "shorts"]
    
    processed_count = 0

    for folder_name in folders:
        # 🌟 ব্যাচ লিমিট: এক রানে সর্বোচ্চ ২টি ১০ মিনিটের ভিডিও হবে
        if processed_count >= MAX_VIDEOS_PER_RUN:
            print(f"\n⏸️ Batch limit ({MAX_VIDEOS_PER_RUN} videos) reached for this run. Remaining circulars will process in next hourly run.\n")
            break

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

            print(f"\n========== Processing [{processed_count+1}/{MAX_VIDEOS_PER_RUN}]: {folder_name} ==========")

            opt_title, _, thumb_meta, video_desc, video_tags, segments = generate_job_content(
                raw_title, img_files, article_text=article_text
            )

            if not segments:
                print(f"⚠️ Could not generate segments for '{folder_name}'. Skipping...")
                continue

            video_title = opt_title

            audio_segments = generate_segmented_audio_pipeline(segments, TMP_DIR)
            if not audio_segments:
                print("❌ Audio generation failed.")
                continue

            first_circular_img = img_files[0] if img_files else None
            thumbnail_path = os.path.join(TMP_DIR, "thumbnail.jpg")
            if os.path.exists(thumbnail_path): os.remove(thumbnail_path)
            
            generate_dynamic_thumbnail(
                raw_title, thumbnail_path, thumb_meta=thumb_meta, circular_img_path=first_circular_img
            )

            out_video_file = os.path.join(TMP_DIR, "final_out.mp4")
            if os.path.exists(out_video_file): os.remove(out_video_file)

            render_matched_video(audio_segments, img_files, out_video_file)
            
            upload_success = upload_to_youtube(
                yt, out_video_file, video_title, 
                thumbnail_path if os.path.exists(thumbnail_path) else None,
                description=video_desc, tags=video_tags, schedule_upload=True
            )
            
            if upload_success:
                add_to_history(raw_title)
                if article_link: add_to_history(article_link)
                shutil.rmtree(folder_path, ignore_errors=True)
                processed_count += 1
                print(f"✅ Video Uploaded & Local Folder Cleared: '{folder_name}'\n")

        except Exception as e:
            traceback.print_exc()

# =========================================================================
# 🌟 ৩. শর্টস হ্যান্ডলার
# =========================================================================

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
    print("\n====== [ Hybrid Video Automation Active (Manual Drive + RSS) ] ======\n")
    try:
        yt_service = get_youtube_service()

        # ১. জরুরি ম্যানুয়াল ড্রাইভ
        try:
            process_manual_drive_task(yt_service)
        except Exception:
            traceback.print_exc()

        # ২. নিয়মিত আরএসএস
        try:
            check_new_articles_and_prepare_folders()
        except Exception:
            traceback.print_exc()

        try:
            process_ready_videos(yt_service)
        except Exception:
            traceback.print_exc()

        # ৩. শর্টস
        try:
            process_shorts_folder(yt_service)
        except Exception:
            traceback.print_exc()

    except Exception:
        traceback.print_exc()
    finally:
        if os.path.exists(TMP_DIR): shutil.rmtree(TMP_DIR, ignore_errors=True)
        print("\nAll Tasks Finalized Perfectly.\n======================================")
