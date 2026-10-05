# -*- coding: utf-8 -*-
import os, random
import numpy as np
from PIL import Image
from moviepy.editor import AudioFileClip, VideoClip, concatenate_videoclips, ImageClip, CompositeVideoClip

def crop_and_pan_box(pil_img, box_2d, target_w=1920, target_h=1080):
    """
    এআই এর দেওয়া বাউন্ডিং বক্স অনুযায়ী বিজ্ঞপ্তির নির্দিষ্ট অংশ কেটে ফুল স্ক্রিনে আনে
    """
    img_w, img_h = pil_img.size
    ymin, xmin, ymax, xmax = box_2d

    # নরম্যালাইজড 0-1000 স্কেল থেকে পিক্সেল স্কেল
    y1 = int((ymin / 1000.0) * img_h)
    x1 = int((xmin / 1000.0) * img_w)
    y2 = int((ymax / 1000.0) * img_h)
    x2 = int((xmax / 1000.0) * img_w)

    # মার্জিন ও সেফটি চেকিং
    pad_y = int((y2 - y1) * 0.15)
    pad_x = int((x2 - x1) * 0.08)
    crop_y1 = max(0, y1 - pad_y)
    crop_x1 = max(0, x1 - pad_x)
    crop_y2 = min(img_h, y2 + pad_y)
    crop_x2 = min(img_w, x2 + pad_x)

    if (crop_x2 - crop_x1) < 100 or (crop_y2 - crop_y1) < 80:
        crop_x1, crop_y1, crop_x2, crop_y2 = 0, 0, img_w, img_h

    cropped = pil_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
    cw, ch = cropped.size

    # ১৬:৯ অনুপাতে ক্যানভাসে বসানো
    scale = min(target_w / cw, target_h / ch)
    nw, nh = int(cw * scale), int(ch * scale)
    resized = cropped.resize((nw, nh), Image.LANCZOS)

    canvas = Image.new("RGB", (target_w, target_h), (245, 245, 248))
    canvas.paste(resized, ((target_w - nw) // 2, (target_h - nh) // 2))
    return canvas

def make_synchronized_clip(img_path, box_2d, duration, target_w=1920, target_h=1080):
    with Image.open(img_path) as raw_img:
        img_rgb = raw_img.convert("RGB")
        frame_canvas = crop_and_pan_box(img_rgb, box_2d, target_w, target_h)
        base_np = np.array(frame_canvas)

    # স্মুথ কেন-বার্নস সাবটল জুম ইফেক্ট (Ken Burns Dynamic Motion)
    def frame_getter(t):
        prog = min(1.0, max(0.0, t / duration if duration > 0 else 0))
        zoom = 1.0 + (0.04 * prog) # মৃদু ৪% জুম যাতে ভিডিও জীবন্ত মনে হয়
        zh, zw = int(target_h * zoom), int(target_w * zoom)
        
        # পিল দিয়ে রিসাইজ
        zoomed = Image.fromarray(base_np).resize((zw, zh), Image.BILINEAR)
        crop_x = (zw - target_w) // 2
        crop_y = (zh - target_h) // 2
        return np.array(zoomed.crop((crop_x, crop_y, crop_x + target_w, crop_y + target_h)))

    return VideoClip(frame_getter, duration=duration)

def apply_front_overlay(main_clip, target_w=1920, target_h=1080):
    for f in ["Front.png", "front.png", "Photos/Front.png"]:
        if os.path.exists(f):
            try:
                pil_front = Image.open(f).convert("RGBA")
                sw = int(target_w * 0.32)
                sh = int((sw / pil_front.width) * pil_front.height)
                resized = pil_front.resize((sw, sh), Image.LANCZOS)
                front_np = np.array(resized)
                pil_front.close()

                front_clip = ImageClip(front_np[:, :, :3]).set_duration(main_clip.duration)
                mask_clip = ImageClip(front_np[:, :, 3] / 255.0, ismask=True).set_duration(main_clip.duration)
                front_clip = front_clip.set_mask(mask_clip)

                pad = 30
                avail_w = max(1, target_w - sw - 2 * pad)
                avail_h = max(1, target_h - sh - 2 * pad)
                speed_x, speed_y = 20.0, 15.0

                def pos(t):
                    x = (speed_x * t) % (2 * avail_w)
                    y = (speed_y * t) % (2 * avail_h)
                    fx = x if x <= avail_w else (2 * avail_w - x)
                    fy = y if y <= avail_h else (2 * avail_h - y)
                    return (pad + int(fx), pad + int(fy))

                front_clip = front_clip.set_position(pos)
                return CompositeVideoClip([main_clip, front_clip]).set_audio(main_clip.audio)
            except Exception: pass
    return main_clip

def render_matched_video(audio_segments, img_files, output_video_path):
    """
    অডিও এবং বাউন্ডিং বক্স মিলিয়ে ১০ মিনিটের ফুল এইচডি ভিডিও তৈরি করে
    """
    clips = []
    for seg in audio_segments:
        audio_clip = AudioFileClip(seg["audio_path"])
        duration = audio_clip.duration
        
        img_idx = min(len(img_files), max(1, seg.get("image_index", 1))) - 1
        target_img = img_files[img_idx]

        v_clip = make_synchronized_clip(target_img, seg["box_2d"], duration)
        v_clip = v_clip.set_audio(audio_clip)
        clips.append(v_clip)

    final_video = concatenate_videoclips(clips)
    final_video = apply_front_overlay(final_video)

    final_video.write_videofile(
        output_video_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        threads=4,
        preset="ultrafast",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        logger=None
    )
    final_video.close()
    for c in clips: c.close()
