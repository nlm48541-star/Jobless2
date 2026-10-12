# -*- coding: utf-8 -*-
import os, re
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONTS_DIR = "Fonts"
PHOTOS_DIR = "Photos"

# অনলাইন আবেদনের জন্য বিভাগীয় ব্যাকগ্রাউন্ড কনফিগ
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

# =========================================================================
# 🌟 বাংলা ও ইংরেজি বাইলিঙ্গুয়াল ফন্ট ইঞ্জিন (Tofu / Box সমস্যা সমাধান)
# =========================================================================

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

def get_english_bold_font(size=80):
    eng_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
    ]
    for p in eng_paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception: return ImageFont.load_default()

def split_text_by_script(text):
    tokens = re.split(r'([A-Za-z0-9/&,.\-]+)', str(text))
    segments = []
    for t in tokens:
        if not t: continue
        is_eng = bool(re.match(r'^[A-Za-z0-9/&,.\-]+$', t))
        segments.append((t, is_eng))
    return segments

def measure_mixed_text(text, font_size):
    bn_f = get_bengali_font(font_size)
    en_f = get_english_bold_font(font_size)
    total_w, max_h = 0, 0
    for seg_text, is_eng in split_text_by_script(text):
        f = en_f if is_eng else bn_f
        bbox = f.getbbox(seg_text)
        total_w += (bbox[2] - bbox[0])
        h = bbox[3] - bbox[1]
        if h > max_h: max_h = h
    return total_w, max_h

def get_best_fitted_mixed_font_size(text, max_w, max_h, start_size=150, min_size=40):
    for fs in range(start_size, min_size, -3):
        w, h = measure_mixed_text(text, fs)
        if w <= max_w and h <= max_h:
            return fs, w, h
    return min_size, max_w, max_h

def draw_mixed_text_centered(draw, center_x, center_y, text, font_size, fill_color):
    bn_f = get_bengali_font(font_size)
    en_f = get_english_bold_font(font_size)
    segments = split_text_by_script(text)
    total_w = 0
    seg_widths = []
    for seg_text, is_eng in segments:
        f = en_f if is_eng else bn_f
        bbox = f.getbbox(seg_text)
        w = bbox[2] - bbox[0]
        seg_widths.append(w)
        total_w += w

    cur_x = center_x - (total_w // 2)
    for (seg_text, is_eng), w in zip(segments, seg_widths):
        f = en_f if is_eng else bn_f
        draw.text((cur_x, center_y), seg_text, font=f, fill=fill_color, anchor="lm")
        cur_x += w

# =========================================================================
# 🌟 ১. ডেমো অনুরূপ স্পেশাল থাম্বনেইল ("ফরম পূরণ" / "আবেদনপত্র তৈরি")
# =========================================================================

def render_demo_style_thumbnail(output_path, circular_img_path, top_hook, org_name, badge_text, bg_color):
    W, H = 1920, 1080
    thumb = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(thumb)

    # ১. বাম পাশে মূল সার্কুলার পাতা (কালো বর্ডার ও স্ট্রোক সহ)
    if circular_img_path and os.path.exists(circular_img_path):
        try:
            with Image.open(circular_img_path) as c_img:
                c_img = c_img.convert("RGB")
                max_doc_w = 750
                max_doc_h = 920
                scale = min(max_doc_w / c_img.width, max_doc_h / c_img.height)
                doc_w, doc_h = int(c_img.width * scale), int(c_img.height * scale)
                doc_resized = c_img.resize((doc_w, doc_h), Image.LANCZOS)

                # চারপাশের সলিড কালো স্ট্রোক (Border)
                stroke_width = 8
                doc_with_border = ImageOps.expand(doc_resized, border=stroke_width, fill="#000000")

                pos_x = 75
                pos_y = (H - doc_with_border.height) // 2
                thumb.paste(doc_with_border, (pos_x, pos_y))
        except Exception as e:
            print(f"⚠️ Circular paper render warning: {e}")

    # ২. ডান পাশের টেক্সট এরিয়া
    text_area_x_start = 850
    text_area_w = W - text_area_x_start - 60
    center_text_x = text_area_x_start + (text_area_w // 2)

    # ৩. লাইন ১: শীর্ষ হুক (উজ্জ্বল হলুদ রঙে "জরুরী নিয়োগ বিজ্ঞপ্তি")
    hook_text = top_hook if top_hook else "জরুরী নিয়োগ বিজ্ঞপ্তি"
    fs_top, _, _ = get_best_fitted_mixed_font_size(hook_text, max_w=text_area_w - 60, max_h=110, start_size=105, min_size=55)
    draw_mixed_text_centered(draw, center_text_x, 180, hook_text, fs_top, "#fedd00")

    # ৪. লাইন ২: প্রতিষ্ঠানের নাম (মাঝখানের অংশে বড় সাদা টেক্সট)
    words = org_name.split()
    if len(words) >= 4:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        
        fs_l1, _, _ = get_best_fitted_mixed_font_size(line1, max_w=text_area_w - 40, max_h=150, start_size=155, min_size=70)
        draw_mixed_text_centered(draw, center_text_x, 370, line1, fs_l1, "#ffffff")
        
        fs_l2, _, _ = get_best_fitted_mixed_font_size(line2, max_w=text_area_w - 40, max_h=150, start_size=155, min_size=70)
        draw_mixed_text_centered(draw, center_text_x, 520, line2, fs_l2, "#ffffff")
    else:
        fs_org, _, _ = get_best_fitted_mixed_font_size(org_name, max_w=text_area_w - 40, max_h=230, start_size=165, min_size=75)
        draw_mixed_text_centered(draw, center_text_x, 440, org_name, fs_org, "#ffffff")

    # ৫. লাইন ৩: নিচে বড় উজ্জ্বল হলুদ পিল ব্যাজ (Pill Badge)
    badge_fs, b_w, b_h = get_best_fitted_mixed_font_size(badge_text, max_w=text_area_w - 120, max_h=130, start_size=130, min_size=65)
    pill_w = min(text_area_w, max(b_w + 140, 680))
    pill_h = 175
    pill_y1 = 730
    pill_y2 = pill_y1 + pill_h
    pill_x1 = center_text_x - (pill_w // 2)
    pill_x2 = center_text_x + (pill_w // 2)

    draw.rounded_rectangle([pill_x1, pill_y1, pill_x2, pill_y2], radius=pill_h // 2, fill="#fedd00")
    draw_mixed_text_centered(draw, center_text_x, (pill_y1 + pill_y2) // 2, badge_text, badge_fs, bg_color)

    thumb.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"✅ Generated Demo Thumbnail: [{hook_text} | {org_name} | {badge_text}]")

# =========================================================================
# 🌟 ২. সাধারণ (অনলাইন আবেদন) থাম্বনেইল ফিক্স
# =========================================================================

def render_standard_online_thumbnail(title, output_path, thumb_meta):
    W, H = 1920, 1080
    bg_path, bg_cfg = find_background_for_circular(title, job_type=thumb_meta.get("job_type", "govt"))
    if bg_path and os.path.exists(bg_path):
        base_img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        base_img = Image.new("RGB", (W, H), "#ffffff")

    draw = ImageDraw.Draw(base_img)
    theme_color = bg_cfg.get("theme_color", "#01532b")
    max_text_x = bg_cfg.get("max_text_x", 1110)
    margin_left = 90
    available_w = max_text_x - margin_left
    center_x = (margin_left + max_text_x) // 2

    l1 = thumb_meta.get("line1_text", "জরুরি নিয়োগ বিজ্ঞপ্তি")
    l2 = thumb_meta.get("line2_text") or thumb_meta.get("org_name") or title.split("নিয়োগ")[0].strip()[:35]
    l3 = thumb_meta.get("line3_text", "বিভিন্ন পদে আবেদন")
    l4 = thumb_meta.get("line4_text", "বেতন স্কেল ও সুযোগ-সুবিধা")
    l5 = thumb_meta.get("line5_text", "অনলাইনে আবেদন শুরু")

    # লাইন ১: শীর্ষ হুক (থিম কালার)
    fs1, _, _ = get_best_fitted_mixed_font_size(l1, max_w=available_w - 40, max_h=120, start_size=115, min_size=55)
    draw_mixed_text_centered(draw, center_x, 150, l1, fs1, theme_color)

    # 🌟 লাইন ২ ফিক্স: ওভারলে উপরে ওঠানো হয়েছে এবং প্রস্থ ডায়নামিক করা হয়েছে
    fs2, w2, h2 = get_best_fitted_mixed_font_size(l2, max_w=available_w - 80, max_h=125, start_size=120, min_size=50)
    box_w2 = min(available_w, w2 + 90) # লেখার সাইজ অনুযায়ী ওভারলে বড় হবে
    box_h2 = max(h2 + 45, 150)
    box_y1 = 235  # উপরে তোলা হলো যাতে ৩য় লাইনের ওপর না আসে
    box_y2 = box_y1 + box_h2
    box_center_y = (box_y1 + box_y2) // 2

    draw.rounded_rectangle([center_x - (box_w2 // 2), box_y1, center_x + (box_w2 // 2), box_y2], radius=26, fill=theme_color)
    draw_mixed_text_centered(draw, center_x, box_center_y, l2, fs2, "#ffffff")

    # 🌟 লাইন ৩: ৩য় লাইনের জন্য সম্পূর্ণ ক্লিয়ার ফাঁকা জায়গা (y = 515)
    fs3, _, _ = get_best_fitted_mixed_font_size(l3, max_w=available_w - 40, max_h=125, start_size=125, min_size=55)
    draw_mixed_text_centered(draw, center_x, 515, l3, fs3, "#000000")

    # লাইন ৪: বেতন স্কেল
    fs4, _, _ = get_best_fitted_mixed_font_size(l4, max_w=available_w - 40, max_h=115, start_size=105, min_size=50)
    draw_mixed_text_centered(draw, center_x, 660, l4, fs4, "#000000")

    # 🌟 লাইন ৫ ফিক্স: নিচের পিল ওভারলের প্রস্থ লেখার দৈর্ঘ্যের সাথে ডায়নামিক করা হয়েছে
    fs5, w5, h5 = get_best_fitted_mixed_font_size(l5, max_w=available_w - 80, max_h=100, start_size=82, min_size=42)
    pill_w5 = min(available_w, w5 + 100) # লেখা অনুযায়ী পিল ওভারলে বড় হবে
    pill_h5 = max(h5 + 35, 110)
    pill_y1 = 780
    pill_y2 = pill_y1 + pill_h5
    pill_center_y = (pill_y1 + pill_y2) // 2

    draw.rounded_rectangle([center_x - (pill_w5 // 2), pill_y1, center_x + (pill_w5 // 2), pill_y2], radius=pill_h5 // 2, fill=theme_color)
    draw_mixed_text_centered(draw, center_x, pill_center_y, l5, fs5, "#ffffff")

    base_img.save(output_path, "JPEG", quality=100, subsampling=0)
    print(f"✅ Generated Fixed Standard Thumbnail for '{title[:35]}'")

# =========================================================================
# 🌟 মাস্টার রাউটার
# =========================================================================

def generate_dynamic_thumbnail(title, output_path, thumb_meta=None, circular_img_path=None):
    if not thumb_meta: thumb_meta = {}
    app_mode = str(thumb_meta.get("application_mode", "online")).lower()
    org_name = thumb_meta.get("org_name") or title.split("নিয়োগ")[0].strip()[:35]
    top_hook = thumb_meta.get("line1_text", "জরুরী নিয়োগ বিজ্ঞপ্তি")

    # ফরম পূরণ হলে (ডেমো ২ এর রয়্যাল নেভি ব্লু)
    if app_mode == "form_fill":
        render_demo_style_thumbnail(
            output_path=output_path,
            circular_img_path=circular_img_path,
            top_hook=top_hook,
            org_name=org_name,
            badge_text="ফরম পূরণ",
            bg_color="#003580"
        )
    # আবেদনপত্র তৈরি হলে (ডেমো ১ এর ফরেস্ট গ্রিন)
    elif app_mode == "letter_write":
        render_demo_style_thumbnail(
            output_path=output_path,
            circular_img_path=circular_img_path,
            top_hook=top_hook,
            org_name=org_name,
            badge_text="আবেদনপত্র তৈরি",
            bg_color="#004d25"
        )
    # অনলাইনে আবেদন হলে (সংশোধিত স্বাভাবিক মেথড)
    else:
        render_standard_online_thumbnail(title, output_path, thumb_meta)
