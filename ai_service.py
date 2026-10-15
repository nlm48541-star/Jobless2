# -*- coding: utf-8 -*-
import os, json, re, requests
from datetime import datetime

TRACKER_FILE = "api_key_tracker.json"
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")

OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct"
]
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
CEREBRAS_MODELS = ["llama3.3-70b", "llama3.1-8b"]
OLLAMA_MODELS = ["gemma4:31b", "gemma4", "gpt-oss:120b"]

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

def clean_title_for_display(title):
    clean = title.split('|')[0].split('||')[0].strip()
    return re.sub(r'\s+', ' ', re.sub(r'[\r\n\t]+', ' ', clean))

def normalize_outdated_years(text):
    if not text: return text
    cur_year = str(datetime.now().year)
    cur_bn = cur_year.translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))
    text = re.sub(r'\b202[0-5]\b', cur_year, str(text))
    text = re.sub(r'২০২[০-৫]', cur_bn, text)
    return text

def parse_json_safely(raw_text):
    try:
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match: return json.loads(json_match.group(0))
        return json.loads(raw_text)
    except Exception: return None

def detect_application_mode_from_text(article_text):
    t = str(article_text).lower()
    has_offline = any(k in t for k in ["ডাকযোগ", "কুরিয়ার", "কুরিয়ার", "বরাবর পাঠাতে", "খামের উপর", "অফিসে জমা", "হাতে হাতে"])
    if any(k in t for k in ["ফরম পূরণ", "নির্ধারিত ফরম", "আবেদন ফরম", "ফরম ডাউনলোড"]):
        return "form_fill"
    if any(k in t for k in ["আবেদনপত্র তৈরি", "সাদা কাগজে আবেদন", "লিখিত আবেদনপত্র", "হাতে লেখা আবেদন"]):
        return "letter_write"
    if has_offline:
        return "form_fill" if "ফরম" in t else "letter_write"
    return "online"

def generate_job_content(title, img_paths=None, article_text=""):
    clean_title = clean_title_for_display(title)
    words = clean_title.split()
    org_name = clean_title.split("নিয়োগ")[0].strip() if "নিয়োগ" in clean_title else " ".join(words[:min(3, len(words))])
    initial_mode = detect_application_mode_from_text(article_text)

    prompt = f"""You are a professional Bengali job circular specialist and TV presenter.
You are given the COMPLETE ARTICLE TEXT of a job circular. 

Circular Title: "{clean_title}"
Detected Organization: "{org_name}"
Full Article Text Content:
---
{article_text[:4000] if article_text else clean_title}
---

CRITICAL SCRIPT & METADATA RULES:
1. APPLICATION METHOD AUDIT:
   - "form_fill": Prescribed form fill-up (নির্ধারিত ফরম পূরণ করে জমা/ডাকযোগে পাঠানো).
   - "letter_write": Written application letter (সাদা কাগজে আবেদনপত্র লিখে ডাকযোগে পাঠানো).
   - "online": Apply online directly via web portal.

2. TITLE, DESCRIPTION & TAGS:
   - If "form_fill": The title MUST include 'ফরম পূরণ'.
   - If "letter_write": The title MUST include 'আবেদনপত্র তৈরি'.
   - If "online": Standard online circular title.

3. SCRIPT INSTRUCTIONS:
   - Generate a continuous 10-MINUTE LONG spoken Bengali script (At least 1350 to 1500 words).
   - Deeply explain every single post/position: Daily duties, qualifications, GPA/grades, vacancies, salary grade, and institutional allowances.
   - STRICTLY DO NOT explain the application process in the body.
   - MANDATORY CALL TO ACTION AT THE END:
     "আবেদনটি করতে চাইলে অথবা আপনার ফরম পূরণ ও আবেদনপত্র তৈরি করিয়ে নিতে স্ক্রিনে বা ডেসক্রিপশনে থাকা হোয়াটসঅ্যাপ নাম্বারে এখনই মেসেজ দিন।"

Return strictly valid JSON:
{{
  "application_mode": "{initial_mode}",
  "org_name": "{org_name}",
  "job_type": "govt",
  "optimized_title": "...",
  "voiceover_script": "...",
  "video_description": "...",
  "specific_tags": ["..."],
  "line1_text": "জরুরী নিয়োগ বিজ্ঞপ্তি"
}}"""

    def extract_final_payload(data):
        app_mode = data.get("application_mode", initial_mode).lower()
        if app_mode not in ["form_fill", "letter_write", "online"]:
            app_mode = initial_mode

        opt_title = normalize_outdated_years(data.get("optimized_title", clean_title).strip()[:100])
        if app_mode == "form_fill" and "ফরম পূরণ" not in opt_title:
            opt_title = f"{opt_title} | ফরম পূরণ"[:100]
        elif app_mode == "letter_write" and "আবেদনপত্র তৈরি" not in opt_title:
            opt_title = f"{opt_title} | আবেদনপত্র তৈরি"[:100]

        desc = normalize_outdated_years(data.get("video_description", "").strip())
        raw_tags = data.get("specific_tags", [])
        if app_mode == "form_fill": raw_tags += ['ফরম পূরণ', 'চাকরির ফরম পূরণ']
        elif app_mode == "letter_write": raw_tags += ['আবেদনপত্র তৈরি', 'চাকরির আবেদনপত্র']
        tags = [re.sub(r'\s+', ' ', t).strip()[:50] for t in raw_tags if t][:20]

        raw_script = normalize_outdated_years(data.get("voiceover_script", "").strip())
        converted_script = convert_all_numbers_in_script(raw_script)

        thumb_meta = {
            "application_mode": app_mode,
            "org_name": data.get("org_name", org_name),
            "job_type": data.get("job_type", "govt"),
            "line1_text": data.get("line1_text", "জরুরী নিয়োগ বিজ্ঞপ্তি")
        }

        return opt_title, converted_script, thumb_meta, desc, tags

    # OpenRouter ➔ Groq ➔ Cerebras ➔ Ollama
    openrouter_keys = parse_multiline_keys("OPENROUTER_API_KEYS")
    if openrouter_keys:
        start_or = get_platform_start_index("openrouter", len(openrouter_keys))
        for offset in range(len(openrouter_keys)):
            cur_idx = (start_or + offset) % len(openrouter_keys)
            headers = {"Authorization": f"Bearer {openrouter_keys[cur_idx]}", "Content-Type": "application/json"}
            for model in OPENROUTER_MODELS:
                try:
                    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                        if data and data.get("voiceover_script"):
                            set_platform_index("openrouter", cur_idx, len(openrouter_keys))
                            return extract_final_payload(data)
                except Exception: pass
            set_platform_index("openrouter", cur_idx + 1, len(openrouter_keys))

    groq_keys = parse_multiline_keys("GROQ_API_KEYS")
    if groq_keys:
        for k in groq_keys:
            try:
                headers = {"Authorization": f"Bearer {k}", "Content-Type": "application/json"}
                payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                    if data and data.get("voiceover_script"): return extract_final_payload(data)
            except Exception: pass

    return clean_title, "", {"application_mode": initial_mode, "org_name": org_name}, "", []
