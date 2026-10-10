# -*- coding: utf-8 -*-
import os, re
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONTS_DIR = "Fonts"
PHOTOS_DIR = "Photos"

# অনলাইন আবেদনের জন্য পূর্বের বিভাগীয় ব্যাকগ্রাউন্ড কনফিগ
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
    (['সেনাবাহিনী', 'সেনা', 'army', 'সৈনিক'], 'Army.png'),
    (['নৌবাহিনী', 'নৌ', 'navy', 'নাবিক'], 'Navy.png'),
    (['বিমান বাহিনী', 'বিমানবাহিনী', 'airforce'], 'AirForce.png'),
    (['বর্ডার গার্ড', 'বিজিবি', 'bgb'], 'BGB.png'),
    (['পুলিশ', 'police', 'কনস্টেবল'], 'Police.png'),
    (['আনসার', 'ansar', 'ভিডিপি'], 'Ansar.png'),
    (['কোস্ট গার্ড', 'কোস্টগার্ড'], 'CoastGuard.png'),
    (['র‍্যাব', 'র‌্যাব', 'rab'], 'RAB.png'),
    (['ফায়ার সার্ভিস', 'ফায়ার সার্ভিস'], 'FireService.png'),
    (['রেলওয়ে', 'রেলওয়ে', 'railway'], 'Railway.png'),
    (['বিসিএস', 'bcs', 'পিএসসি'], 'BCS.png'),
    (['প্রাথমিক শিক্ষক', 'প্রাইমারি শিক্ষক'], 'PrimaryTeacher.png'),
    (['খাদ্য অধিদপ্তর', 'খাদ্য'], 'Food.png'),
    (['ডাক বিভাগ', 'ডাক', 'পোস্ট অফিস'], 'PostOffice.png'),
    (['কারা অধিদপ্তর', 'কারারক্ষী', 'কারাগার'], 'Jail.png'),
    (['পাসপোর্ট অধিদপ্তর', 'পাসপোর্ট'], 'Passport.png'),
    (['পরিবার পরিকল্পনা'], 'FamilyPlanning.png'),
    (['গণপূর্ত', 'pwd'], 'PWD.jpeg'),
]

def find_background_for_circular(title_text, job_type="govt"):
    if not os.path.exists(PHOTOS_DIR):
        return None, {"max_text_x": 1050, "theme_color": "#01532b"}
    disk_files = {f.lower(): f for f in os.listdir(PHOTOS_DIR)}
    t_lower = str(title_text).lower()
    for keywords, filename in ORG_KEYWORD_RULES:
        if any(k in t_lower for k in keywords):
            fn_lower = filename.lower()
            if fn_lower in disk_files:
                actual = disk_files[fn_lower]
                return os.path.join(PHOTOS_DIR, actual), BG_TEMPLATES.get(filename, {"max_text_x": 1110, "theme_color": "#01532b"})
    is_non = str(job_type).strip().lower() in ["non-govt", "private", "বেসরকারি"]
    default_f = "NonGov.png" if is_non else "Govbd.png"
    if default_f.lower() in disk_files:
        return os.path.join(PHOTOS_DIR, disk_files[default_f.lower()]), BG_TEMPLATES.get(default_f, {"max_text_x": 1135, "theme_color": "#01532b"})
    return None, {"max_text_x": 1050, "theme_color": "#01532b"}

def get_bengali_font(size=80):
    candidates = [
        os.path.join(FONTS_DIR, "AkhandBengali-Extrabold.ttf"),
        os.path.join(FONTS_DIR, "Li Ador Noirrit Bold.ttf"),
        os.path.join(FONTS_DIR, "kalpurush.ttf")
    ]
    for p in candidates:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

def fit_font_size(text, max_w, max_h, start_size=200, min_size=60):
    for s in range(start_size, min_size, -4):
        font = get_bengali_font(s)
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_w and h <= max_h:
            return font, w, h
    return get_bengali_font(min_size), max_w, max_h

# =========================================================================
# 🌟 ডেমো অনুরূপ স্পেশাল থাম্বনেইল রেন্ডারার (আবেদনপত্র তৈরি / ফরম পূরণ)
# =========================================================================

def render_demo_style_thumbnail(output_path, circular_img_path, org_name, badge_text, bg_color):
    """
    ডেমো ১ ও ২ এর হুবহু ডিজাইন:
    বামে কালো বর্ডারযুক্ত সার্কুলার পেজ, ডানে সাদা টেক্সট ও নিচে হলুদ পিল ব্যাজ।
    """
    W, H = 1920, 1080
    thumb = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(thumb)

    # ১. বাম পাশে সার্কুলারের পাতা স্থাপন (কালো স্ট্রোক ও ফ্রেম সহ)
    if circular_img_path and os.path.exists(circular_img_path):
        try:
            with Image.open(circular_img_path) as c_img:
                c_img = c_img.convert("RGB")
                
                # ডকুমেন্টের অনুপাত ঠিক রেখে মার্জিন অনুযায়ী রিসাইজ
                max_doc_w = 750
                max_doc_h = 920
                scale = min(max_doc_w / c_img.width, max_doc_h / c_img.height)
                doc_w, doc_h = int(c_img.width * scale), int(c_img.height * scale)
                doc_resized = c_img.resize((doc_w, doc_h), Image.LANCZOS)

                # চারপাশের কালো স্ট্রোক (Border/Stroke)
                stroke_width = 8
                doc_with_border = ImageOps.expand(doc_resized, border=stroke_width, fill="#000000")

                # পেপার ড্রপ শ্যাডো / প্যাডিং
                pos_x = 80
                pos_y = (H - doc_with_border.height) // 2
                thumb.paste(doc_with_border, (pos_x, pos_y))
        except Exception as e:
            print(f"⚠️ Circular paper render warning: {e}")

    # ২. ডান পাশের টেক্সট এরিয়া (ডকুমেন্টের পর থেকে ডান প্রান্ত পর্যন্ত)
    text_area_x_start = 860
    text_area_w = W - text_area_x_start - 60
    center_text_x = text_area_x_start + (text_area_w // 2)

    # প্রতিষ্ঠানের নামকে সুন্দরভাবে ১ বা ২ লাইনে বিন্যস্ত করা
    words = org_name.split()
    if len(words) >= 2:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
    else:
        line1 = org_name
        line2 = ""

    # ৩. প্রতিষ্ঠানের নামের লাইন দুটি আঁকা (সাদা রঙ)
    f1, _, h1 = fit_font_size(line1, max_w=text_area_w - 40, max_h=190, start_size=180, min_size=80)
    y_cursor = 210
    draw.text((center_text_x, y_cursor), line1, font=f1, fill="#ffffff", anchor="mm")
    
    if line2:
        y_cursor += 170
        f2, _, _ = fit_font_size(line2, max_w=text_area_w - 40, max_h=190, start_size=180, min_size=80)
        draw.text((center_text_x, y_cursor), line2, font=f2, fill="#ffffff", anchor="mm")

    # ৪. হলুদ পিল ব্যাজ (Yellow Pill Badge)
    pill_w = min(text_area_w, 920)
    pill_h = 175
    pill_y1 = 660
    pill_y2 = pill_y1 + pill_h
    pill_x1 = center_text_x - (pill_w // 2)
    pill_x2 = center_text_x + (pill_w // 2)

    # উজ্জ্বল হলুদ ব্যাকগ্রাউন্ড (#ffd700 / #fbc02d)
    yellow_color = "#fbc02d" if "ফরম" in badge_text else "#f9a825"
    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2], radius=pill_h // 2, fill="#fedd00")

    # পিল ব্যাজের ভেতরের লেখা (ব্যাকগ্রাউন্ডের সাথে মেলানো ডিপ রঙে)
    badge_font, _, _ = fit_font_size(badge_text, max_w=pill_w - 80, max_h=pill_h - 40, start_size=130, min_size=60)
    draw.text((center_text_x, (pill_y1 + pill_y2) // 2), badge_text, font=badge_font, fill=bg_color, anchor="mm")

    thumb.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"✅ Generated Demo-Style Thumbnail: [{badge_text}] for '{org_name}'")

# =========================================================================
# 🌟 মাস্টার থাম্বনেইল রাউটার
# =========================================================================

def generate_dynamic_thumbnail(title, output_path, thumb_meta=None, circular_img_path=None):
    if not thumb_meta: thumb_meta = {}
    app_mode = thumb_meta.get("application_mode", "online").lower()
    org_name = thumb_meta.get("org_name") or title.split("নিয়োগ")[0].strip()[:35]

    # ১. যদি "ফরম পূরণ" হয় (ডেমো ২ এর হুবহু নীল ব্যাকগ্রাউন্ড ডিজাইন)
    if app_mode == "form_fill":
        render_demo_style_thumbnail(
            output_path=output_path,
            circular_img_path=circular_img_path,
            org_name=org_name,
            badge_text="ফরম পূরণ",
            bg_color="#003580" # ডেমো ২ এর রয়্যাল নেভি ব্লু
        )
        return

    # ২. যদি "আবেদনপত্র তৈরি" হয় (ডেমো ১ এর হুবহু সবুজ ব্যাকগ্রাউন্ড ডিজাইন)
    elif app_mode == "letter_write":
        render_demo_style_thumbnail(
            output_path=output_path,
            circular_img_path=circular_img_path,
            org_name=org_name,
            badge_text="আবেদনপত্র তৈরি",
            bg_color="#004d25" # ডেমো ১ এর ফরেস্ট গ্রিন
        )
        return

    # ৩. যদি সরাসরি "অনলাইন আবেদন" হয় (পূর্বের সাধারণ ৫-লাইনের ডিজাইন)
    bg_path, bg_cfg = find_background_for_circular(title, job_type=thumb_meta.get("job_type", "govt"))
    if bg_path and os.path.exists(bg_path):
        base_img = Image.open(bg_path).convert("RGB").resize((1920, 1080), Image.LANCZOS)
    else:
        base_img = Image.new("RGB", (1920, 1080), "#ffffff")

    draw = ImageDraw.Draw(base_img)
    theme_color = bg_cfg.get("theme_color", "#01532b")
    center_x = (90 + bg_cfg.get("max_text_x", 1110)) // 2
    f_main = get_bengali_font(100)

    l1 = thumb_meta.get("line1_text", "জরুরি নিয়োগ বিজ্ঞপ্তি")
    l2 = thumb_meta.get("line2_text", org_name)
    l3 = thumb_meta.get("line3_text", "বিভিন্ন পদে আবেদন")
    l4 = thumb_meta.get("line4_text", "বেতন স্কেল ও সুযোগ-সুবিধা")
    l5 = thumb_meta.get("line5_text", "অনলাইনে আবেদন শুরু")

    draw.text((center_x, 165), l1, font=f_main, fill=theme_color, anchor="mm")
    draw.rounded_rectangle([center_x - 450, 265, center_x + 450, 440], radius=28, fill=theme_color)
    draw.text((center_x, 352), l2, font=f_main, fill="#ffffff", anchor="mm")
    draw.text((center_x, 515), l3, font=f_main, fill="#000000", anchor="mm")
    draw.text((center_x, 660), l4, font=f_main, fill="#000000", anchor="mm")
    draw.rounded_rectangle([center_x - 300, 775, center_x + 300, 895], radius=60, fill=theme_color)
    draw.text((center_x, 835), l5, font=f_main, fill="#ffffff", anchor="mm")

    base_img.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"✅ Generated Standard Online Thumbnail for '{title[:35]}'")
