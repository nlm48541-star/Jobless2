# -*- coding: utf-8 -*-
import os, shutil, subprocess
from PIL import Image

from ai_service import (
    generate_job_content, convert_all_numbers_in_script,
    generate_seo_metadata, detect_application_mode_from_text,
    sanitize_youtube_tags, DEFAULT_BASE_TAGS, clean_script_for_speech
)
from audio_engine import generate_voiceover_audio_pipeline
from thumbnail import generate_dynamic_thumbnail
from video_editor import render_video_slideshow
from youtube_uploader import upload_to_youtube
from feed_manager import (
    scrape_article_content_and_images,
    filter_and_download_circular_images,
    add_to_history
)

MANUAL_DIR = "workspace_manual"
TMP_DIR = "temp_assets"


def is_manual_mode_enabled():
    val = os.environ.get("ENABLE_MANUAL_FOLDER", "false").strip().lower()
    folder_id = os.environ.get("MANUAL_DRIVE_FOLDER_ID", "").strip()
    return val in ["true", "1", "yes", "on"] and bool(folder_id)


def sync_manual_folder_from_drive(folder_id):
    rclone_conf = os.path.expanduser('~/.config/rclone/rclone.conf')
    if not os.path.exists(rclone_conf):
        return False
    if os.path.exists(MANUAL_DIR):
        shutil.rmtree(MANUAL_DIR, ignore_errors=True)
    os.makedirs(MANUAL_DIR, exist_ok=True)
    cmd = ["rclone", "sync", "gdrive:", MANUAL_DIR, f"--drive-root-folder-id={folder_id}", "--fast-list"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return res.returncode == 0
    except Exception as e:
        print(f"⚠️ Error syncing manual folder from drive: {e}")
        return False


def clean_manual_folder_on_drive(folder_id):
    print(f"🧹 [DRIVE CLEANUP] Emptying Google Drive Folder (ID: {folder_id})...")
    cmd_delete = ["rclone", "delete", "gdrive:", f"--drive-root-folder-id={folder_id}", "--drive-use-trash=false", "--fast-list"]
    cmd_rmdirs = ["rclone", "rmdirs", "gdrive:", f"--drive-root-folder-id={folder_id}", "--leave-root"]
    try:
        subprocess.run(cmd_delete, check=True, capture_output=True, text=True, timeout=120)
        subprocess.run(cmd_rmdirs, capture_output=True, text=True, timeout=60)
        print("✅ Google Drive folder emptied successfully!")
    except Exception as e:
        print(f"⚠️ Drive cleanup notice: {e}")


def prepare_manual_drive_job():
    """ধাপ ১: ম্যানুয়াল ড্রাইভের ফাইল ও AI স্ক্রিপ্ট প্রস্তুত করে (অডিও এখনো বানাবে না)"""
    if not is_manual_mode_enabled():
        return None

    folder_id = os.environ.get("MANUAL_DRIVE_FOLDER_ID", "").strip()
    print("\n" + "=" * 65)
    print(f"📥 [MANUAL DRIVE] Checking Drive folder (ID: {folder_id})...")
    print("=" * 65)

    if not sync_manual_folder_from_drive(folder_id) or not os.path.exists(MANUAL_DIR):
        return None

    all_files = [f for f in os.listdir(MANUAL_DIR) if not f.startswith('.')]
    if not all_files:
        print("ℹ️ Manual Google Drive folder is empty.")
        return None

    print(f"🎯 [MANUAL DRIVE] Detected {len(all_files)} file(s): {all_files}")

    img_files = []
    custom_audio_file = None
    custom_thumb_path = None
    script_txt_path = None
    link_txt_path = None
    title_txt_path = None
    article_txt_path = None

    for f in sorted(all_files):
        f_path = os.path.join(MANUAL_DIR, f)
        if os.path.isdir(f_path):
            continue
        f_lower = f.lower()
        ext = f_lower.split('.')[-1]

        if f_lower in ["thumbnail.png", "thumbnail.jpg", "thumbnail.jpeg"] or (
            any(k in f_lower for k in ["thumbnail", "thumb"]) and ext in ['jpg', 'jpeg', 'png', 'webp']
        ):
            custom_thumb_path = f_path
            continue
        elif ext in ['jpg', 'jpeg', 'png', 'webp']:
            img_files.append(f_path)
        elif ext in ['mp3', 'wav', 'm4a', 'aac']:
            custom_audio_file = f_path
        elif f_lower == "script.txt":
            script_txt_path = f_path
        elif f_lower == "link.txt":
            link_txt_path = f_path
        elif f_lower == "title.txt":
            title_txt_path = f_path
        elif f_lower == "article.txt":
            article_txt_path = f_path

    article_link = ""
    scraped_title = ""
    article_text = ""

    if link_txt_path and os.path.exists(link_txt_path):
        try:
            with open(link_txt_path, "r", encoding="utf-8") as lf:
                article_link = lf.read().strip()
            if article_link:
                scraped_title, article_text, img_urls = scrape_article_content_and_images(article_link)
                if not img_files and img_urls:
                    img_files = filter_and_download_circular_images(
                        img_urls, MANUAL_DIR, referer_url=article_link, file_prefix="tmp_sc_", final_prefix="scraped_"
                    )
        except Exception as e:
            print(f"⚠️ Notice on link processing: {e}")

    if not article_text and article_txt_path and os.path.exists(article_txt_path):
        try:
            with open(article_txt_path, "r", encoding="utf-8") as af:
                article_text = af.read().strip()
        except Exception:
            pass

    user_provided_script = ""
    if script_txt_path and os.path.exists(script_txt_path):
        print("📄 [FOUND script.txt] Using user's custom script directly!")
        try:
            with open(script_txt_path, "r", encoding="utf-8") as sf:
                user_provided_script = sf.read().strip()
        except Exception:
            pass

    raw_title = "জরুরি নিয়োগ বিজ্ঞপ্তি"
    if title_txt_path and os.path.exists(title_txt_path):
        try:
            with open(title_txt_path, "r", encoding="utf-8") as tf:
                raw_title = tf.read().strip() or raw_title
        except Exception:
            pass
    elif scraped_title:
        raw_title = scraped_title
    elif user_provided_script:
        raw_title = user_provided_script.split("\n")[0][:80].strip() or raw_title

    if not img_files:
        print("❌ No circular images available. Aborting manual job.")
        return None

    thumb_meta = {}
    video_desc = ""
    video_tags = DEFAULT_BASE_TAGS
    voiceover_script = ""
    video_title = raw_title

    if user_provided_script:
        cleaned_user_script = clean_script_for_speech(user_provided_script)
        voiceover_script = convert_all_numbers_in_script(cleaned_user_script)
        app_mode = detect_application_mode_from_text(user_provided_script + " " + article_text)
        org_name = raw_title.split("নিয়োগ")[0].strip()[:35] if "নিয়োগ" in raw_title else raw_title[:35]
        is_priv = any(k in raw_title.lower() for k in ["লিমিটেড", "ফার্মা", "গ্রুপ", "কোম্পানি", "বেসরকারি", "ltd"])
        thumb_meta = {
            "application_mode": app_mode,
            "org_name": org_name,
            "job_type": "non-govt" if is_priv else "govt",
            "line1_text": "জরুরী নিয়োগ বিজ্ঞপ্তি",
        }
        try:
            stub = {"organization": org_name, "total_vacancies": "", "job_category": "বেসরকারি চাকরি" if is_priv else "সরকারি চাকরি", "posts": [{"post_name": "নিয়োগ"}]}
            seo = generate_seo_metadata(stub, raw_title, app_mode=app_mode)
            if seo:
                video_desc = seo.get("video_description") or (user_provided_script[:500] + "\n\nআবেদন করতে যোগাযোগ করুন আমাদের হোয়াটসঅ্যাপে।")
                video_tags = sanitize_youtube_tags(seo.get("specific_tags", []) + DEFAULT_BASE_TAGS)
            else:
                video_desc = user_provided_script[:500] + "\n\nআবেদন করতে যোগাযোগ করুন আমাদের হোয়াটসঅ্যাপে।"
        except Exception:
            video_desc = user_provided_script[:500] + "\n\nআবেদন করতে যোগাযোগ করুন আমাদের হোয়াটসঅ্যাপে।"
    else:
        print("🤖 [ARTICLE TEXT + VISION MODE] Generating full accurate script...")
        source_text = article_text if article_text else raw_title
        opt_title, voiceover_script, thumb_meta, video_desc, video_tags = generate_job_content(
            raw_title, img_files, article_text=source_text
        )
        if opt_title:
            video_title = opt_title

    if not voiceover_script and not custom_audio_file:
        print("❌ Failed to obtain voiceover script or audio.")
        return None

    return {
        "folder_id": folder_id,
        "raw_title": raw_title,
        "article_link": article_link,
        "video_title": video_title,
        "voiceover_script": voiceover_script,
        "thumb_meta": thumb_meta,
        "video_desc": video_desc,
        "video_tags": video_tags,
        "img_files": img_files,
        "custom_thumb_path": custom_thumb_path,
        "custom_audio_file": custom_audio_file,
    }


def finalize_manual_drive_job(yt, job, audio_path):
    """ধাপ ৩: প্রস্তুত হওয়া অডিও দিয়ে ম্যানুয়াল ড্রাইভ ভিডিও রেন্ডার ও আপলোড"""
    if not job or not audio_path or not os.path.exists(audio_path):
        return False

    os.makedirs(TMP_DIR, exist_ok=True)
    video_title = job["video_title"]
    first_circular_img = job["img_files"][0] if job["img_files"] else None

    custom_thumb_path = job["custom_thumb_path"]
    if custom_thumb_path and os.path.exists(custom_thumb_path):
        print(f"🖼️ [CUSTOM THUMBNAIL] Using '{os.path.basename(custom_thumb_path)}' directly.")
        final_thumb_path = os.path.join(TMP_DIR, "manual_thumbnail.jpg")
        with Image.open(custom_thumb_path) as c_thumb:
            c_thumb.convert("RGB").save(final_thumb_path, "JPEG", quality=100, subsampling=0)
    else:
        final_thumb_path = os.path.join(TMP_DIR, "manual_thumbnail.jpg")
        if os.path.exists(final_thumb_path):
            os.remove(final_thumb_path)
        generate_dynamic_thumbnail(
            job["raw_title"], final_thumb_path, thumb_meta=job["thumb_meta"], circular_img_path=first_circular_img
        )

    out_video_file = os.path.join(TMP_DIR, "manual_final.mp4")
    if os.path.exists(out_video_file):
        os.remove(out_video_file)

    print("🎬 Rendering Smooth Scrolling Video for Manual Task...")
    render_video_slideshow(audio_path, job["img_files"], out_video_file)

    upload_success = upload_to_youtube(
        yt, out_video_file, video_title, final_thumb_path,
        description=job["video_desc"], tags=job["video_tags"], schedule_upload=False
    )

    if upload_success:
        add_to_history(video_title)
        if job["article_link"]:
            add_to_history(job["article_link"])
        clean_manual_folder_on_drive(job["folder_id"])
        shutil.rmtree(MANUAL_DIR, ignore_errors=True)
        print("🎉 [SUCCESS] Manual Video Uploaded & Google Drive Emptied!\n")
        return True
    return False


def process_manual_drive_folder(yt):
    job = prepare_manual_drive_job()
    if not job:
        return False
    audio_path = job["custom_audio_file"]
    if not audio_path:
        os.makedirs(TMP_DIR, exist_ok=True)
        audio_path = os.path.join(TMP_DIR, "manual_voice.wav")
        if not generate_voiceover_audio_pipeline(job["voiceover_script"], audio_path):
            return False
    return finalize_manual_drive_job(yt, job, audio_path)
