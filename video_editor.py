# -*- coding: utf-8 -*-
import os, random
import numpy as np
from PIL import Image
from moviepy.editor import AudioFileClip, VideoClip, concatenate_videoclips, ImageClip, CompositeVideoClip

def make_video_frame(img_path, duration, target_w=1920, target_h=1080):
    """
    নিয়োগ বিজ্ঞপ্তির পাতাটি পুরো অডিওর সময় অনুযায়ী ওপর থেকে নিচ পর্যন্ত স্মুথ স্ক্রল করবে
    """
    pil_img = Image.open(img_path).convert("RGB")
    w, h = pil_img.size
    ratio = w / h
    target_ratio = target_w / target_h

    # ১৬:৯ ফুল এইচডি অনুপাতে স্কেলিং
    if ratio >= target_ratio: 
        new_h = target_h
        new_w = int((target_h / h) * w)
    else: 
        new_w = target_w
        new_h = int((target_w / w) * h)

    if new_w < target_w: 
        new_w = target_w
        new_h = int((new_w / w) * h)
    if new_h < target_h: 
        new_h = target_h
        new_w = int((new_h / h) * w)

    img_np = np.array(pil_img.resize((new_w, new_h), Image.LANCZOS))
    pil_img.close()

    max_y_offset = max(0, new_h - target_h)
    max_x_offset = max(0, new_w - target_w)

    def frame_getter(t):
        prog = min(1.0, max(0.0, t / duration if duration > 0 else 0))
        y_start = int(prog * max_y_offset)
        x_start = int(prog * max_x_offset)
        return img_np[y_start : y_start + target_h, x_start : x_start + target_w]

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
                speed_x, speed_y = 22.0, 16.0

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

def render_video_slideshow(audio_path, img_files, out_file):
    """
    পুরো অডিওর সাথে ছবিগুলোর স্মুথ স্ক্রলিং ভিডিও রেন্ডার করে
    """
    if not img_files:
        raise ValueError("No images provided for slideshow rendering.")

    audio_clip = AudioFileClip(audio_path)
    per_img_duration = audio_clip.duration / len(img_files)

    clips = [make_video_frame(img, per_img_duration) for img in img_files]
    final_video = concatenate_videoclips(clips).set_audio(audio_clip)
    final_video = apply_front_overlay(final_video)

    final_video.write_videofile(
        out_file,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        threads=2,
        preset="ultrafast",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        logger=None
    )
    final_video.close()
    audio_clip.close()
    for c in clips: c.close()
