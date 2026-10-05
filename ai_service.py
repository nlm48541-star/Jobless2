# -*- coding: utf-8 -*-
import os, json, re, base64, requests
from datetime import datetime
from PIL import Image

TRACKER_FILE = "api_key_tracker.json"
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")

# 🌟 মডেল কনফিগারেশন (OpenRouter ১ম, Ollama লাস্ট)
OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct"
]
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
CEREBRAS_MODELS = ["llama3.3-70b", "llama3.1-8b"]
OLLAMA_MODELS = ["gemma4:31b", "gemma4", "gpt-oss:120b", "nemotron-3-nano:30b"]

def parse_multiline_keys(env_var_name):
    raw = os.environ.get(env_var_name, "").strip()
    if not raw: return []
    return [k.strip() for k in raw.splitlines() if k.strip() and not k.strip().startswith('#')]

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {}

def save_tracker(data):
    try:
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception: pass

def get_platform_start_index(platform_name, total_keys):
    if total_keys == 0: return 0
    return load_tracker().get(f"{platform_name}_index", 0) % total_keys

def set_platform_index(platform_name, next_idx, total_keys):
    if total_keys == 0: return
    t = load_tracker()
    t[f"{platform_name}_index"] = next_idx % total_keys
    save_tracker(t)

DEFAULT_BASE_TAGS = ['চাকরির সার্কুলার', 'চাকরির খবর', 'সরকারি চাকরি', 'job circular', 'govt job circular']

BN_NUMS = {
    0: 'শূন্য', 1: 'এক', 2: 'দুই', 3: 'তিন', 4: 'চার', 5: 'পাঁচ', 6: 'ছয়', 7: 'সাত', 8: 'আট', 9: 'নয়', 10: 'দশ',
    11: 'এগারো', 12: 'বারো', 13: 'তেরো', 14: 'চৌদ্দ', 15: 'পনেরো', 16: 'ষোলো', 17: 'সতেরো', 18: 'আঠারো', 19: 'উনিশ', 20: 'বিশ',
    21: 'একুশ', 22: 'বাইশ', 23: 'তেইশ', 24: 'চব্বিশ', 25: 'পঁচিশ', 26: 'ছাব্বিশ', 27: 'সাতাশ', 28: 'আঠাশ', 29: 'উনত্রিশ', 30: 'ত্রিশ',
    31: 'একত্রিশ', 32: 'বত্রিশ', 33: 'তেত্রিশ', 34: 'চৌত্রিশ', 35: 'পঁয়ত্রিশ', 36: 'ছত্রিশ', 37: 'সাঁইত্রিশ', 38: 'আটত্রিশ', 39: 'উনচল্লিশ', 40: 'চল্লিশ',
    41: 'একচল্লিশ', 42: 'বিয়াল্লিশ', 43: 'তেতাল্লিশ', 44: 'চুয়াল্লিশ', 45: 'পঁয়তাল্লিশ', 46: 'ছেচল্লিশ', 47: 'সাতচল্লিশ', 48: 'আটচল্লিশ', 49: 'উনপঞ্চাশ', 50: 'পঞ্চাশ',
    51: 'একান্ন', 52: 'বায়ান্ন', 53: 'তিপ্পান্ন', 54: 'চুয়ান্ন', 55: 'পঞ্চান্ন', 56: 'ছাপ্পান্ন', 57: 'সাতান্ন', 58: 'আটান্ন', 59: 'উনষাট', 60: 'ষাট',
    61: 'একষট্টি', 62: 'বাষট্টি', 63: 'তেষট্টি', 64: 'চৌষট্টি', 65: 'পঁয়ষট্টি', 66: 'ছেষট্টি', 67: 'সাতষট্টি', 68: 'আটষট্টি', 69: 'উনসত্তর', 70: 'সত্তর',
    71: 'একাত্তর', 72: 'বাহাত্তর', 73: 'তিয়াত্তর', 74: 'চৌহাত্তর', 75: 'পঁচাত্তর', 76: 'ছিয়াত্তর', 77: 'সাতাত্তর', 78: 'আটাত্তর', 79: 'উনআশি', 80: 'আশি',
    81: 'একাশি', 82: 'বিরাশি', 83: 'তিরাশি', 84: 'চুরাশি', 85: 'পঁচাশি', 86: 'ছিয়াশি', 87: 'সাতাশি', 88: 'অষ্টআশি', 89: 'ঊননব্বই', 90: 'নব্বই',
    91: 'একানব্বই', 92: 'বানব্বই', 93: 'তিরানব্বই', 94: 'চুরানব্বই', 95: 'পঁচানব্বই', 96: 'ছিয়ানব্বই', 97: 'সাতানব্বই', 98: 'আটানব্বই', 99: 'নিরানব্বই'
}

DIGIT_TO_ENG_BN = {
    '0': 'জিরো', '1': 'ওয়ান', '2': 'টু', '3': 'থ্রি', '4': 'ফোর',
    '5': 'ফাইভ', '6': 'সিক্স', '7': 'সেভেন', '8': 'এইট', '9': 'নাইন',
    '০': 'জিরো', '১': 'ওয়ান', '২': 'টু', '৩': 'থ্রি', '৪': 'ফোর',
    '৫': 'ফাইভ', '৬': 'সিক্স', '৭': 'সেভেন', '৮': 'এইট', '৯': 'নাইন'
}

def en_bn_to_int(s):
    trans = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')
    return int(str(s).translate(trans))

def number_to_bangla_words(n):
    if n == 0: return 'শূন্য'
    parts = []
    koti = n // 10000000
    if koti > 0:
        parts.append(number_to_bangla_words(koti) + ' কোটি')
        n %= 10000000
    lakh = n // 100000
    if lakh > 0:
        parts.append(BN_NUMS.get(lakh, str(lakh)) + ' লাখ')
        n %= 100000
    hajar = n // 1000
    if hajar > 0:
        parts.append(BN_NUMS.get(hajar, str(hajar)) + ' হাজার')
        n %= 1000
    shatok = n // 100
    if shatok > 0:
        if shatok == 1: parts.append('একশত')
        else: parts.append(BN_NUMS.get(shatok, str(shatok)) + ' শত')
        n %= 100
    if n > 0:
        parts.append(BN_NUMS.get(n, str(n)))
    return ' '.join(parts)

def convert_all_numbers_in_script(text):
    if not text: return ""
    text = re.sub(r'(\d+),(\d+)', r'\1\2', text)
    text = re.sub(r'([০-৯]+),([০-৯]+)', r'\1\2', text)
    def phone_repl(m):
        raw_phone = m.group(0)
        digits = re.findall(r'[0-9০-৯]', raw_phone)
        return ' '.join(DIGIT_TO_ENG_BN.get(d, d) for d in digits)
    text = re.sub(r'(\+?(?:88|৮৮)?\s*0?1[0-9০-৯]{8,10})', phone_repl, text)
    def num_repl(m):
        num_str = m.group(0)
        try:
            val = en_bn_to_int(num_str)
            return number_to_bangla_words(val)
        except Exception: return num_str
    text = re.sub(r'[0-9০-৯]+', num_repl, text)
    return text

def get_current_years():
    cur_year = datetime.now().year
    en_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    return str(cur_year), str(cur_year).translate(en_to_bn)

def normalize_outdated_years(text):
    if not text: return text
    cur_en, cur_bn = get_current_years()
    text = re.sub(r'\b202[0-5]\b', cur_en, str(text))
    text = re.sub(r'২০২[০-৫]', cur_bn, text)
    return text

def clean_title_for_display(title):
    clean = title.split('|')[0].split('||')[0].strip()
    return re.sub(r'\s+', ' ', re.sub(r'[\r\n\t]+', ' ', clean))

def strip_unwanted_chars(text):
    cleaned = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|✪|★|☆', '', str(text))
    return normalize_outdated_years(cleaned.strip())

def extract_vacancy_and_qual(title):
    vac_match = re.search(r'(\d+|[০-৯]+)\s*(টি\s*)?পদে', title)
    vac_str = vac_match.group(0) if vac_match else ""
    qual = ""
    if any(k in title.upper() for k in ["SSC", "এসএসসি"]): qual = "এসএসসি পাস"
    elif any(k in title.upper() for k in ["HSC", "এইচএসসি"]): qual = "এইচএসসি পাস"
    elif any(k in title for k in ["৮ম", "অষ্টম"]): qual = "৮ম শ্রেণি পাস"
    elif any(k in title for k in ["স্নাতক", "ডিগ্রী", "অনার্স"]): qual = "স্নাতক পাস"
    return vac_str, qual

def encode_image_base64(image_path, max_dim=1200):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            if max(img.size) > max_dim: img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception: return None

def parse_json_safely(raw_text):
    try:
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match: return json.loads(json_match.group(0))
        return json.loads(raw_text)
    except Exception: return None

# =========================================================================
# 🌟 ১০ মিনিটের দীর্ঘ ও সেগমেন্টেড স্ক্রিপ্ট তৈরি
# =========================================================================

def generate_job_content(title, img_paths, article_text=""):
    clean_title = clean_title_for_display(title)
    words = clean_title.split()
    org_name = clean_title.split("নিয়োগ")[0].strip() if "নিয়োগ" in clean_title else " ".join(words[:min(3, len(words))])
    vac_str, qual_str = extract_vacancy_and_qual(clean_title)

    prompt = f"""You are a senior Bengali TV news analyst and career consultant producing a COMPREHENSIVE 10-MINUTE LONG VIDEO (At least 1350 to 1500 words).
Target Circular: "{clean_title}"
Organization: "{org_name}"
Article Reference Text: "{article_text[:2500]}"

CRITICAL SCRIPT RULES:
1. TARGET DURATION: Minimum 10 Minutes (1350+ Bengali words). Continuous, articulate, formal spoken Bengali.
2. STRICTLY NO APPLICATION PROCEDURES: Do NOT talk about how/where/when to apply, bank drafts, websites, postal address, or exam procedures in the body.
3. IN-DEPTH POSITION EXPLANATION: Deeply explain every single post/position mentioned in the circular:
   - What are the daily responsibilities and nature of work for this role?
   - Number of vacancies and rank/grade.
   - Required educational qualifications, CGPA/class, and preferred technical skills.
   - Salary scale, basic pay, allowances (house rent, medical, festival bonuses).
   - Age limits and district requirements.
4. OUTRO (MANDATORY CALL TO ACTION): Only at the very end of the video, state:
   "আবেদনটি করতে চাইলে অথবা অভিজ্ঞ কম্পিউটার অপারেটর দ্বারা আপনার আবেদনপত্র ও প্রফেশনাল সিভি তৈরি করিয়ে নিতে স্ক্রিনে বা ভিডিও ডেসক্রিপশনে থাকা হোয়াটসঅ্যাপ নাম্বারে এখনই মেসেজ দিন।"
5. VISUAL BOUNDING BOXES FOR EACH SEGMENT:
   For every segment/post, identify which part of the circular image contains that post information.
   Return coordinates in 0-1000 scale: [ymin, xmin, ymax, xmax]. If image is unknown, default to [150, 0, 850, 1000].

Return strictly valid JSON:
{{
  "job_type": "govt", // or "non-govt"
  "optimized_title": "...",
  "video_description": "...",
  "specific_tags": ["..."],
  "line1_text": "{vac_str if vac_str else 'বিশাল'} নিয়োগ বিজ্ঞপ্তি",
  "line2_text": "{org_name}",
  "line3_text": "{qual_str if qual_str else 'বিভিন্ন পদে আবেদন'}",
  "line4_text": "বেতন স্কেল ও সুযোগ-সুবিধা",
  "line5_text": "অনলাইনে আবেদন শুরু",
  "segments": [
    {{
      "segment_title": "ভূমিকা ও সার্কুলার পরিচিতি",
      "script_chunk": "...", // 100-120 words
      "image_index": 1,
      "box_2d": [0, 0, 300, 1000] // Header region
    }},
    {{
      "segment_title": "১ম পদের বিস্তারিত কাজের বিবরণ ও যোগ্যতা",
      "script_chunk": "...", // 300-350 words in-depth
      "image_index": 1,
      "box_2d": [250, 0, 550, 1000] // Row region of Post 1
    }},
    {{
      "segment_title": "২য় পদের বিস্তারিত কাজের বিবরণ ও সুবিধা",
      "script_chunk": "...", // 300-350 words
      "image_index": 1,
      "box_2d": [500, 0, 800, 1000] // Row region of Post 2
    }},
    {{
      "segment_title": "সমাপনী ও হোয়াটসঅ্যাপ সার্ভিস কল টু অ্যাকশন",
      "script_chunk": "...", // 150-180 words ending with WhatsApp CTA
      "image_index": 1,
      "box_2d": [750, 0, 1000, 1000]
    }}
  ]
}}"""

    base64_images = [encode_image_base64(p) for p in img_paths[:3] if encode_image_base64(p)]

    def extract_final_payload(data):
        opt_title = normalize_outdated_years(data.get("optimized_title", clean_title).strip()[:100])
        desc = normalize_outdated_years(data.get("video_description", "").strip())
        raw_tags = data.get("specific_tags", []) + DEFAULT_BASE_TAGS
        tags = [re.sub(r'\s+', ' ', t).strip()[:50] for t in raw_tags if t][:20]

        j_type = str(data.get("job_type", "govt")).strip().lower()
        if j_type not in ["govt", "non-govt"]:
            j_type = "non-govt" if any(w in clean_title.lower() for w in ["কোম্পানি", "লিমিটেড", "limited", "ltd", "private", "বেসরকারি"]) else "govt"

        thumb_meta = {
            "job_type": j_type,
            "line1_text": strip_unwanted_chars(data.get("line1_text", f"{vac_str} নিয়োগ বিজ্ঞপ্তি")),
            "line2_text": strip_unwanted_chars(data.get("line2_text", org_name)),
            "line3_text": strip_unwanted_chars(data.get("line3_text", qual_str if qual_str else "এসএসসি পাস")),
            "line4_text": strip_unwanted_chars(data.get("line4_text", "বেতন স্কেল ও পদসমূহ")),
            "line5_text": strip_unwanted_chars(data.get("line5_text", "অনলাইনে আবেদন শুরু"))
        }

        raw_segments = data.get("segments", [])
        clean_segments = []
        full_script_chunks = []

        for seg in raw_segments:
            chunk = normalize_outdated_years(seg.get("script_chunk", "").strip())
            converted_chunk = convert_all_numbers_in_script(chunk)
            if converted_chunk:
                full_script_chunks.append(converted_chunk)
                box = seg.get("box_2d", [0, 0, 1000, 1000])
                if not isinstance(box, list) or len(box) != 4:
                    box = [0, 0, 1000, 1000]
                clean_segments.append({
                    "title": seg.get("segment_title", "পদের বিবরণ"),
                    "script": converted_chunk,
                    "image_index": seg.get("image_index", 1),
                    "box_2d": box
                })

        full_voiceover_script = " ".join(full_script_chunks)
        print(f"📊 [Script Stats] Total Segments: {len(clean_segments)} | Word Count: {len(full_voiceover_script.split())}")
        return opt_title, full_voiceover_script, thumb_meta, desc, tags, clean_segments

    # =========================================================================
    # 🌟 ১. প্রথম প্রায়োরিটি: OpenRouter Cloud API
    # =========================================================================
    openrouter_keys = parse_multiline_keys("OPENROUTER_API_KEYS")
    total_or = len(openrouter_keys)
    if total_or > 0:
        start_or = get_platform_start_index("openrouter", total_or)
        for offset in range(total_or):
            cur_idx = (start_or + offset) % total_or
            k = openrouter_keys[cur_idx]
            headers = {"Authorization": f"Bearer {k}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com"}
            for model in OPENROUTER_MODELS:
                print(f"🤖 [Priority 1: OpenRouter] Key #{cur_idx+1}/{total_or} (Model: '{model}')")
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("segments"):
                            set_platform_index("openrouter", cur_idx, total_or)
                            return extract_final_payload(data)
                    elif resp.status_code in [401, 402, 429]: break
                except Exception as e: print(f"⚠️ OpenRouter Error: {e}")
            set_platform_index("openrouter", cur_idx + 1, total_or)

    # =========================================================================
    # 🌟 ২. দ্বিতীয় প্রায়োরিটি: Groq Cloud API
    # =========================================================================
    groq_keys = parse_multiline_keys("GROQ_API_KEYS") or parse_multiline_keys("GROQ_API")
    total_g = len(groq_keys)
    if total_g > 0:
        start_g = get_platform_start_index("groq", total_g)
        for offset in range(total_g):
            cur_idx = (start_g + offset) % total_g
            k = groq_keys[cur_idx]
            headers = {"Authorization": f"Bearer {k}", "Content-Type": "application/json"}
            for model in GROQ_MODELS:
                print(f"🤖 [Priority 2: Groq] Key #{cur_idx+1}/{total_g} (Model: '{model}')")
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "system", "content": "You are a professional Bengali job circular writer. Output valid JSON only."}, {"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }
                    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("segments"):
                            set_platform_index("groq", cur_idx, total_g)
                            return extract_final_payload(data)
                    elif resp.status_code in [401, 429]: break
                except Exception as e: print(f"⚠️ Groq Error: {e}")
            set_platform_index("groq", cur_idx + 1, total_g)

    # =========================================================================
    # 🌟 ৩. তৃতীয় প্রায়োরিটি: Cerebras Cloud API
    # =========================================================================
    cerebras_keys = parse_multiline_keys("CEREBRAS_API_KEYS")
    total_c = len(cerebras_keys)
    if total_c > 0:
        start_c = get_platform_start_index("cerebras", total_c)
        for offset in range(total_c):
            cur_idx = (start_c + offset) % total_c
            k = cerebras_keys[cur_idx]
            headers = {"Authorization": f"Bearer {k}", "Content-Type": "application/json"}
            for model in CEREBRAS_MODELS:
                print(f"🤖 [Priority 3: Cerebras] Key #{cur_idx+1}/{total_c} (Model: '{model}')")
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "system", "content": "Output strictly valid JSON."}, {"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }
                    resp = requests.post("https://api.cerebras.ai/v1/chat/completions", headers=headers, json=payload, timeout=60)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("segments"):
                            set_platform_index("cerebras", cur_idx, total_c)
                            return extract_final_payload(data)
                    elif resp.status_code in [401, 429]: break
                except Exception as e: print(f"⚠️ Cerebras Error: {e}")
            set_platform_index("cerebras", cur_idx + 1, total_c)

    # =========================================================================
    # 🌟 ৪. সর্বশেষ প্রায়োরিটি: Ollama Cloud API (Gemma প্রাধান্যপ্রাপ্ত)
    # =========================================================================
    ollama_keys = parse_multiline_keys("OLLAMA_API_KEYS") or parse_multiline_keys("Ollama_API_Key")
    total_o = len(ollama_keys)
    if total_o > 0:
        start_o = get_platform_start_index("ollama", total_o)
        for offset in range(total_o):
            cur_idx = (start_o + offset) % total_o
            k = ollama_keys[cur_idx]
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {k}"}
            for model in OLLAMA_MODELS:
                print(f"🤖 [Priority 4 (Last): Ollama] Key #{cur_idx+1}/{total_o} (Model: '{model}')")
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt, "images": base64_images}],
                        "stream": False, "options": {"temperature": 0.3}
                    }
                    resp = requests.post(f"{OLLAMA_API_URL}/api/chat", headers=headers, json=payload, timeout=75)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                        if data and data.get("segments"):
                            set_platform_index("ollama", cur_idx, total_o)
                            return extract_final_payload(data)
                    elif resp.status_code in [401, 429]: break
                except Exception as e: print(f"⚠️ Ollama Error: {e}")
            set_platform_index("ollama", cur_idx + 1, total_o)

    return None, None, None, None, None, []
