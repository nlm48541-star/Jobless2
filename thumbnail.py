# -*- coding: utf-8 -*-
import os, re, random
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = "Fonts"
PHOTOS_DIR = "Photos"

# 🌟 প্রতিটি ব্যাকগ্রাউন্ডের জন্য নিখুঁতভাবে পরিমাপ করা স্পেস (max_text_x) এবং ডিপ থিম কালার
BG_TEMPLATES = {
    "NonGov.png": {"max_text_x": 940, "theme_color": "#0e305d"},
    "Passport.png": {"max_text_x": 990, "theme_color": "#064a27"},
    "PostOffice.png": {"max_text_x": 1020, "theme_color": "#134e27"},
    "Food.png": {"max_text_x": 1040, "theme_color": "#0b4c25"},
    "RAB.png": {"max_text_x": 1040, "theme_color": "#0b4e28"},
    "PWD.jpeg": {"max_text_x": 1065, "theme_color": "#014382"},
    "PWD.png": {"max_text_x": 1065, "theme_color": "#014382"},
    "Ansar.png": {"max_text_x": 1070, "theme_color": "#214e1a"},
    "PrimaryTeacher.png": {"max_text_x": 1090, "theme_color": "#7a0d72"},
    "Navy.png": {"max_text_x": 1105, "theme_color": "#05366a"},
    "Police.png": {"max_text_x": 1110, "theme_color": "#032770"},
    "CoastGuard.png": {"max_text_x": 1110, "theme_color": "#024b82"},
    "FireService.png": {"max_text_x": 1115, "theme_color": "#084d2e"},
    "FamilyPlanning.png": {"max_text_x": 1115, "theme_color": "#0d4827"},
    "Army.png": {"max_text_x": 1125, "theme_color": "#094a2b"},
    "Govbd.png": {"max_text_x": 1135, "theme_color": "#01532b"},
    "Railway.png": {"max_text_x": 1135, "theme_color": "#0a4c24"},
    "Jail.png": {"max_text_x": 1135, "theme_color": "#054527"},
    "BGB.png": {"max_text_x": 1145, "theme_color": "#8f0415"},
    "AirForce.png": {"max_text_x": 1145, "theme_color": "#024e8c"},
    "BCS.png": {"max_text_x": 1190, "theme_color": "#275515"},
}

ORG_KEYWORD_RULES = [
    (['সেনাবাহিনী', 'সেনা', 'army', 'সৈনিক', 'কমিশনড অফিসার'], 'Army.png'),
    (['নৌবাহিনী', 'নৌ', 'navy', 'নাবিক', 'sailor'], 'Navy.png'),
    (['বিমান বাহিনী', 'বিমানবাহিনী', 'airforce', 'air force', 'এয়ারফোর্স'], 'AirForce.png'),
    (['বর্ডার গার্ড', 'বিজিবি', 'bgb', 'বিডিআর', 'bdr'], 'BGB.png'),
    (['পুলিশ', 'police', 'কনস্টেবল', 'এসআই', 'সার্জেন্ট', 'পুলিশ সুপারের'], 'Police.png'),
    (['আনসার', 'ansar', 'ভিডিপি', 'ব্যাটালিয়ন আনসার', 'গ্রাম প্রতিরক্ষা'], 'Ansar.png'),
    (['কোস্ট গার্ড', 'কোস্টগার্ড', 'coast guard', 'coastguard'], 'CoastGuard.png'),
    (['র‍্যাব', 'র‌্যাব', 'rab'], 'RAB.png'),
    (['ফায়ার সার্ভিস', 'ফায়ার সার্ভিস', 'fire service', 'ফায়ারম্যান', 'সিভিল ডিফেন্স'], 'FireService.png'),
    (['রেলওয়ে', 'রেলওয়ে', 'railway', 'বাংলাদেশ রেলওয়ে'], 'Railway.png'),
    (['বিসিএস', 'bcs', 'পিএসসি', 'bpsc', 'পাবলিক সার্ভিস', 'প্রশাসন একাডেমি'], 'BCS.png'),
    (['প্রাথমিক শিক্ষক', 'প্রাইমারি শিক্ষক', 'প্রাথমিক', 'প্রাইমারি', 'primary teacher', 'সহকারী শিক্ষক', 'প্রাথমিক শিক্ষা'], 'PrimaryTeacher.png'),
    (['খাদ্য অধিদপ্তর', 'খাদ্য', 'food'], 'Food.png'),
    (['ডাক বিভাগ', 'ডাক', 'পোস্ট অফিস', 'পোস্টাল', 'post office'], 'PostOffice.png'),
    (['কারা অধিদপ্তর', 'কারারক্ষী', 'কারাগার', 'jail', 'prison', 'বি ডি জে'], 'Jail.png'),
    (['পাসপোর্ট অধিদপ্তর', 'পাসপোর্ট', 'passport', 'ইমিগ্রেশন'], 'Passport.png'),
    (['পরিবার পরিকল্পনা', 'family planning'], 'FamilyPlanning.png'),
    (['গণপূর্ত', 'pwd', 'গণপূর্ত অধিদপ্তর'], 'PWD.jpeg'),
]

def find_background_for_circular(title_text, job_type="govt"):
    """
    সার্কুলারের কিওয়ার্ড অনুযায়ী সঠিক ব্যাকগ্রাউন্ড ফাইল ও কনফিগ নির্বাচন করে।
    যদি কোনো কিওয়ার্ড না মেলে:
      - সরকারি চাকরির ক্ষেত্রে: 'Govbd.png'
      - বেসরকারি চাকরির ক্ষেত্রে: 'NonGov.png'
    """
    if not os.path.exists(PHOTOS_DIR):
        return None, {"max_text_x": 1050, "theme_color": "#01532b"}

    disk_files = {f.lower(): f for f in os.listdir(PHOTOS_DIR)}
    t_lower = str(title_text).lower()

    # ১. নির্দিষ্ট কিওয়ার্ড ম্যাচিং
    for keywords, filename in ORG_KEYWORD_RULES:
        if any(k in t_lower for k in keywords):
            fn_lower = filename.lower()
            if fn_lower in disk_files:
                actual_name = disk_files[fn_lower]
                cfg = BG_TEMPLATES.get(filename, BG_TEMPLATES.get(actual_name, {"max_text_x": 1110, "theme_color": "#01532b"}))
                return os.path.join(PHOTOS_DIR, actual_name), cfg

    # ২. কিওয়ার্ড না মিললে সরকারি বা বেসরকারি অনুযায়ী ফলব্যাক
    is_non_govt = str(job_type).strip().lower() in ["non-govt", "private", "nongovt", "বেসরকারি", "কোম্পানি"]
    default_filename = "NonGov.png" if is_non_govt else "Govbd.png"

    for cand in [default_filename, default_filename.lower()]:
        if cand.lower() in disk_files:
            actual_name = disk_files[cand.lower()]
            cfg = BG_TEMPLATES.get(default_filename, {"max_text_x": 940 if is_non_govt else 1135, "theme_color": "#0e305d" if is_non_govt else "#01532b"})
            return os.path.join(PHOTOS_DIR, actual_name), cfg

    # ড্রাইভে ফাইল না পেলে প্রথম যেকোনো বৈধ ছবি
    any_file = list(disk_files.values())[0] if disk_files else "Govbd.png"
    return os.path.join(PHOTOS_DIR, any_file), {"max_text_x": 1050, "theme_color": "#01532b"}

def is_valid_bengali_font(font_path):
    try:
        test_font = ImageFont.truetype(font_path, 40)
        mask = test_font.getmask("বাংলাদেশ চাকরি")
        return mask.size[0] > 0 and mask.size[1] > 0
    except Exception:
        return False

def get_verified_bengali_fonts():
    verified = []
    if os.path.exists(FONTS_DIR):
        for f in sorted(os.listdir(FONTS_DIR)):
            if f.lower().endswith(('.ttf', '.otf')):
                p = os.path.join(FONTS_DIR, f)
                if f.lower() == "akhand.ttf": continue
                if is_valid_bengali_font(p):
                    verified.append(p)
    return verified

def get_primary_bold_font():
    fonts = get_verified_bengali_fonts()
    for f in fonts:
        bn = os.path.basename(f).lower()
        if "akhandbengali" in bn or "extrabold" in bn or "ador" in bn:
            return f
    return fonts[0] if fonts else "Kalpurush.ttf"

def get_english_bold_font(font_size):
    eng_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
    ]
    for p in eng_paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, font_size)
            except Exception: pass
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except Exception: return ImageFont.load_default()

def split_text_by_script(text):
    tokens = re.split(r'([A-Za-z0-9/,.-]+)', str(text))
    segments = []
    for t in tokens:
        if not t: continue
        is_eng = bool(re.match(r'^[A-Za-z0-9/,.-]+$', t))
        segments.append((t, is_eng))
    return segments

def measure_mixed_text(text, bn_font_path, font_size):
    try: bn_font = ImageFont.truetype(bn_font_path, font_size)
    except Exception: bn_font = ImageFont.load_default()
    eng_font = get_english_bold_font(font_size)

    total_w, max_h = 0, 0
    for seg_text, is_eng in split_text_by_script(text):
        f = eng_font if is_eng else bn_font
        bbox = f.getbbox(seg_text)
        total_w += (bbox[2] - bbox[0])
        h = bbox[3] - bbox[1]
        if h > max_h: max_h = h
    return total_w, max_h

def get_best_fitted_font_size(text, max_w, max_h, bn_font_path, start_size=150, min_size=40):
    for fs in range(start_size, min_size, -3):
        w, h = measure_mixed_text(text, bn_font_path, fs)
        if w <= max_w and h <= max_h:
            return fs, w, h
    return min_size, max_w, max_h

def draw_mixed_text_centered(draw, center_x, center_y, text, bn_font_path, font_size, fill_color):
    try: bn_font = ImageFont.truetype(bn_font_path, font_size)
    except Exception: bn_font = ImageFont.load_default()
    eng_font = get_english_bold_font(font_size)

    segments = split_text_by_script(text)
    total_w = 0
    seg_widths = []
    for seg_text, is_eng in segments:
        f = eng_font if is_eng else bn_font
        bbox = f.getbbox(seg_text)
        w = bbox[2] - bbox[0]
        seg_widths.append(w)
        total_w += w

    cur_x = center_x - (total_w // 2)
    for (seg_text, is_eng), w in zip(segments, seg_widths):
        f = eng_font if is_eng else bn_font
        draw.text((cur_x, center_y), seg_text, font=f, fill=fill_color, anchor="lm")
        cur_x += w

def generate_dynamic_thumbnail(title, output_path, thumb_meta=None):
    W, H = 1920, 1080
    if not thumb_meta: thumb_meta = {}

    job_type = thumb_meta.get("job_type", "govt")
    bg_path, bg_cfg = find_background_for_circular(title, job_type=job_type)

    # ব্যাকগ্রাউন্ড লোড ও রিসাইজ (Full HD 1920x1080)
    if bg_path and os.path.exists(bg_path):
        base_img = Image.open(bg_path).convert("RGB")
        if base_img.size != (W, H):
            base_img = base_img.resize((W, H), Image.LANCZOS)
    else:
        base_img = Image.new("RGB", (W, H), "#ffffff")

    draw = ImageDraw.Draw(base_img)
    theme_color = bg_cfg.get("theme_color", "#01532b")
    max_text_x = bg_cfg.get("max_text_x", 1110)
    margin_left = 90
    available_w = max_text_x - margin_left
    center_x = (margin_left + max_text_x) // 2

    main_font = get_primary_bold_font()

    # টেক্সট ফিল্ডগুলো উদ্ধার করা (নতুন ও পুরোনো ফিল্ড উভয়ের সাপোর্ট)
    l1 = thumb_meta.get("line1_text") or thumb_meta.get("row2_text") or "জরুরি নিয়োগ বিজ্ঞপ্তি"
    if "বিজ্ঞপ্তি" not in l1 and "পদের" not in l1:
        l1 = f"{l1} বিজ্ঞপ্তি"

    l2 = thumb_meta.get("line2_text") or thumb_meta.get("top_text") or "বাংলাদেশ সরকারি চাকরি"
    l3 = thumb_meta.get("line3_text") or thumb_meta.get("sub_text") or "এসএসসি পাস"
    l4 = thumb_meta.get("line4_text") or thumb_meta.get("row1_text") or "বেতন স্কেল ১২,০০০ টাকা"
    l5 = thumb_meta.get("line5_text") or thumb_meta.get("bot_text") or "অনলাইনে আবেদন শুরু"

    # ড্যাশ বা অপ্রয়োজনীয় প্রতীক থাকলে ক্লিন করা
    l5_clean = re.sub(r'^[—\-\s]+|[—\-\s]+$', '', l5).strip()

    # =========================================================================
    # 🌟 লাইন ১: বিজ্ঞপ্তি / শূন্যপদ হুক (গাঢ় থিম কালার)
    # =========================================================================
    fs1, _, _ = get_best_fitted_font_size(l1, max_w=available_w - 40, max_h=120, bn_font_path=main_font, start_size=115, min_size=55)
    draw_mixed_text_centered(draw, center_x, 165, l1, main_font, fs1, theme_color)

    # =========================================================================
    # 🌟 লাইন ২: প্রতিষ্ঠানের নাম (থিম কালার ওভারলে বক্স + সাদা টেক্সট)
    # =========================================================================
    box_h = 175
    box_y1 = 265
    box_y2 = box_y1 + box_h
    fs2, t2_w, _ = get_best_fitted_font_size(l2, max_w=available_w - 60, max_h=box_h - 40, bn_font_path=main_font, start_size=135, min_size=60)
    
    # বক্সের দৈর্ঘ্য টেক্সটের সাথে সামঞ্জস্য রেখে সুন্দর মার্জিন দেওয়া
    box_w = min(available_w, max(t2_w + 120, int(available_w * 0.88)))
    box_x1 = center_x - (box_w // 2)
    box_x2 = box_x1 + box_w

    draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=28, fill=theme_color)
    draw_mixed_text_centered(draw, center_x, (box_y1 + box_y2) // 2, l2, main_font, fs2, "#ffffff")

    # =========================================================================
    # 🌟 লাইন ৩: শিক্ষাগত যোগ্যতা (কালো টেক্সট)
    # =========================================================================
    fs3, _, _ = get_best_fitted_font_size(l3, max_w=available_w - 40, max_h=130, bn_font_path=main_font, start_size=130, min_size=60)
    draw_mixed_text_centered(draw, center_x, 515, l3, main_font, fs3, "#000000")

    # =========================================================================
    # 🌟 লাইন ৪: বেতন স্কেল ও সুবিধা (হুবহু ডেমোর মতো স্প্লিট স্টাইল)
    # =========================================================================
    fs4, _, _ = get_best_fitted_font_size(l4, max_w=available_w - 40, max_h=120, bn_font_path=main_font, start_size=105, min_size=50)
    if "বেতন স্কেল" in l4:
        parts = l4.split("বেতন স্কেল", 1)
        w_prefix, _ = measure_mixed_text("বেতন স্কেল ", main_font, fs4)
        w_suffix, _ = measure_mixed_text(parts[1].strip(), main_font, fs4)
        total_l4_w = w_prefix + w_suffix
        start_l4_x = center_x - (total_l4_w // 2)

        # "বেতন স্কেল" থিম কালারে এবং বাকি অংশ কালো কালারে
        draw.text((start_l4_x, 660), "বেতন স্কেল ", font=ImageFont.truetype(main_font, fs4), fill=theme_color, anchor="lm")
        draw_mixed_text_centered(draw, start_l4_x + w_prefix + (w_suffix // 2), 660, parts[1].strip(), main_font, fs4, "#000000")
    else:
        draw_mixed_text_centered(draw, center_x, 660, l4, main_font, fs4, "#000000")

    # =========================================================================
    # 🌟 লাইন ৫: পিল ব্যাজ (Pill Badge) ও দুই পাশের থিম ড্যাশ লাইন
    # =========================================================================
    pill_h = 115
    pill_y_center = 835
    pill_y1 = pill_y_center - (pill_h // 2)
    pill_y2 = pill_y_center + (pill_h // 2)

    fs5, t5_w, _ = get_best_fitted_font_size(l5_clean, max_w=available_w - 180, max_h=pill_h - 35, bn_font_path=main_font, start_size=82, min_size=42)
    pill_w = min(available_w - 80, t5_w + 90)
    pill_x1 = center_x - (pill_w // 2)
    pill_x2 = pill_x1 + pill_w

    # সেন্টারের পিল ব্যাজ
    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2], radius=pill_h // 2, fill=theme_color)
    draw_mixed_text_centered(draw, center_x, pill_y_center, l5_clean, main_font, fs5, "#ffffff")

    # ডানে ও বামে সংযুক্ত ড্যাশ/লাইন (ডেমোর মতো)
    line_w = 9
    dash_margin = 25
    if pill_x1 - dash_margin > margin_left:
        draw.line([(margin_left, pill_y_center), (pill_x1 - dash_margin, pill_y_center)], fill=theme_color, width=line_w)
    if max_text_x > pill_x2 + dash_margin:
        draw.line([(pill_x2 + dash_margin, pill_y_center), (max_text_x, pill_y_center)], fill=theme_color, width=line_w)

    base_img.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"✅ Generated Dynamic 2-Panel Thumbnail on '{os.path.basename(bg_path)}': [{l2} | {l1}]")
