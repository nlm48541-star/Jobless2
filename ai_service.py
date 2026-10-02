# -*- coding: utf-8 -*-
import os, json, re, base64, requests
from datetime import datetime
from PIL import Image

TRACKER_FILE = "api_key_tracker.json"
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://api.ollama.com").rstrip("/")

# 🌟 মডেল প্রায়োরিটি তালিকা (Ollama তে Gemma সবার আগে)
OLLAMA_MODELS = ["gemma4:31b", "gemma4", "gpt-oss:120b", "nemotron-3-nano:30b", "kimi-k3", "minimax-m3"]
OPENROUTER_MODELS = ["google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct", "mistralai/mistral-small-24b-instruct-2501"]
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
CEREBRAS_MODELS = ["llama3.3-70b", "llama3.1-8b"]

# =========================================================================
# 🌟 স্মার্ট কি-ট্র্যাকার ও রোটেশন লজিক
# =========================================================================

def parse_multiline_keys(env_var_name):
    """GitHub Secret থেকে এন্টার দিয়ে দেওয়া একাধিক কি আলাদা করে লিস্ট রিটার্ন করে"""
    raw = os.environ.get(env_var_name, "").strip()
    if not raw: return []
    return [k.strip() for k in raw.splitlines() if k.strip() and not k.strip().startswith('#')]

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return {}

def save_tracker(data):
    try:
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception: pass

def get_platform_start_index(platform_name, total_keys):
    if total_keys == 0: return 0
    tracker = load_tracker()
    return tracker.get(f"{platform_name}_index", 0) % total_keys

def set_platform_index(platform_name, next_idx, total_keys):
    if total_keys == 0: return
    tracker = load_tracker()
    tracker[f"{platform_name}_index"] = next_idx % total_keys
    save_tracker(tracker)

# =========================================================================
# 🌟 টেক্সট প্রসেসিং ও হেল্পার
# =========================================================================

DEFAULT_BASE_TAGS = [
    'চাকরির সার্কুলার', 'চাকরির খবর', 'সরকারি চাকরি',
    'job circular', 'govt job circular', 'job application bd'
]

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
        except Exception:
            return num_str

    text = re.sub(r'[0-9০-৯]+', num_repl, text)
    text = re.sub(r'ঘরে\s*বসে\s*', '', text)
    return text

def get_current_years():
    cur_year = datetime.now().year
    en_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
    cur_year_bn = str(cur_year).translate(en_to_bn)
    return str(cur_year), cur_year_bn

def normalize_outdated_years(text):
    if not text: return text
    cur_en, cur_bn = get_current_years()
    text = re.sub(r'\b202[0-5]\b', cur_en, str(text))
    text = re.sub(r'২০২[০-৫]', cur_bn, text)
    text = re.sub(r'ঘরে\s*বসে\s*', '', text)
    return text

def sanitize_youtube_tags(raw_tags, max_total_chars=400):
    clean_tags = []
    current_length = 0
    for tag in raw_tags:
        if not tag or not isinstance(tag, str): continue
        cleaned = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\<\>\"\,\n\r]', '', tag)
        cleaned = normalize_outdated_years(re.sub(r'\s+', ' ', cleaned).strip())
        if not cleaned or len(cleaned) < 2: continue
        cleaned = cleaned[:50].strip()
        if cleaned not in clean_tags:
            tag_len = len(cleaned) + (1 if clean_tags else 0)
            if current_length + tag_len <= max_total_chars:
                clean_tags.append(cleaned)
                current_length += tag_len
            else: break
    return clean_tags

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
    elif any(k in title for k in ["স্নাতক", "ডিগ্রী", "অনার্স", "Degree", "Honours"]): qual = "স্নাতক পাস"
    return vac_str, qual

def encode_image_base64(image_path, max_dim=1024):
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
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(raw_text)
    except Exception:
        return None

# =========================================================================
# 🌟 মাস্টার টেক্সট জেনারেশন ইঞ্জিন (Ollama -> OpenRouter -> Groq -> Cerebras)
# =========================================================================

def generate_job_content(title, img_paths, article_text=""):
    clean_title = clean_title_for_display(title)
    words = clean_title.split()
    org_name = clean_title.split("নিয়োগ")[0].strip() if "নিয়োগ" in clean_title else " ".join(words[:min(3, len(words))])
    vac_str, qual_str = extract_vacancy_and_qual(clean_title)

    prompt = f"""You are a professional Bengali YouTube SEO specialist, scriptwriter, and circular auditor.
Context:
- Circular Title: "{clean_title}"
- Detected Org: "{org_name}"
- Article Text Context: "{article_text[:1200]}"

CRITICAL AUDIT TASK:
Examine the attached circular image(s) AND the article text carefully to determine how candidate applies:
- "application_method":
    - "online" -> Candidates apply via website/portal (e.g. teletalk.com.bd, web form, online portal).
    - "offline" -> Candidates MUST send application by Postal Mail (ডাকযোগে), Courier (কুরিয়ার), or submit in person / physical office visit (সরাসরি অফিসে / হাতে হাতে জমা).
- "offline_reason": Brief reason in Bengali if "offline" (e.g. "আবেদন ডাকযোগে প্রেরণের নির্দেশ").

IF "application_method" IS "online", GENERATE FULL DETAILS:
1. SCRIPT: Exactly 3 minutes (380 to 440 words). Continuous spoken Bengali. Do NOT mention any year.
2. JOB TYPE: "govt" or "non-govt".
3. THUMBNAIL 5-LINE LAYOUT:
   - "line1_text": 2-3 words (e.g. "{vac_str} নিয়োগ বিজ্ঞপ্তি" or "বিশাল নিয়োগ বিজ্ঞপ্তি")
   - "line2_text": 2-3 words. Org name (e.g. "{org_name}")
   - "line3_text": 2-3 words. Qualification (e.g. "{qual_str if qual_str else 'এসএসসি পাস'}")
   - "line4_text": 2-4 words. Salary (e.g. "বেতন স্কেল ১২,০০০ টাকা")
   - "line5_text": 2-3 words. Deadline (e.g. "৩০ অক্টোবর পর্যন্ত")

Return strictly valid JSON:
{{
  "application_method": "online",
  "offline_reason": "",
  "job_type": "govt",
  "optimized_title": "...",
  "voiceover_script": "...",
  "video_description": "...",
  "specific_tags": ["..."],
  "line1_text": "...",
  "line2_text": "...",
  "line3_text": "...",
  "line4_text": "...",
  "line5_text": "..."
}}"""

    base64_images = [encode_image_base64(p) for p in img_paths[:3] if encode_image_base64(p)]

    def extract_final_payload(data):
        app_method = str(data.get("application_method", "online")).strip().lower()
        offline_reason = data.get("offline_reason", "ডাকযোগ / সরাসরি অফিসে আবেদনের নির্দেশ")

        if app_method == "offline":
            return None, None, {"is_offline": True, "reason": offline_reason}, None, None

        opt_title = normalize_outdated_years(data.get("optimized_title", clean_title).strip()[:100])
        raw_script = normalize_outdated_years(re.sub(r'[\r\n]+', ' ', data.get("voiceover_script", "").strip()))
        script = convert_all_numbers_in_script(raw_script)
        desc = normalize_outdated_years(data.get("video_description", "").strip())
        raw_tags = data.get("specific_tags", []) + DEFAULT_BASE_TAGS
        tags = sanitize_youtube_tags(raw_tags)

        j_type = str(data.get("job_type", "govt")).strip().lower()
        if j_type not in ["govt", "non-govt"]:
            j_type = "non-govt" if any(w in clean_title.lower() for w in ["কোম্পানি", "লিমিটেড", "limited", "ltd", "private", "বেসরকারি"]) else "govt"

        l1 = data.get("line1_text") or (f"{vac_str} নিয়োগ বিজ্ঞপ্তি" if vac_str else "বিশাল নিয়োগ বিজ্ঞপ্তি")
        l2 = data.get("line2_text") or data.get("top_text") or org_name
        l3 = data.get("line3_text") or data.get("sub_text") or (qual_str if qual_str else "এসএসসি পাস")
        l4 = data.get("line4_text") or data.get("row1_text") or "বেতন স্কেল ১২,০০০ টাকা"
        l5 = data.get("line5_text") or data.get("bot_text") or "অনলাইনে আবেদন শুরু"

        thumb_meta = {
            "is_offline": False,
            "job_type": j_type,
            "line1_text": strip_unwanted_chars(l1),
            "line2_text": strip_unwanted_chars(l2),
            "line3_text": strip_unwanted_chars(l3),
            "line4_text": strip_unwanted_chars(l4),
            "line5_text": strip_unwanted_chars(l5)
        }
        return opt_title, script, thumb_meta, desc, tags

    # =========================================================================
    # 🌟 ১. প্রথম প্রায়োরিটি: Ollama Cloud (Gemma প্রাধান্যপ্রাপ্ত)
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
                print(f"🤖 [Priority 1: Ollama] Key #{cur_idx+1}/{total_o} (Model: '{model}')")
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt, "images": base64_images}],
                        "stream": False, "options": {"temperature": 0.3}
                    }
                    resp = requests.post(f"{OLLAMA_API_URL}/api/chat", headers=headers, json=payload, timeout=45)
                    if resp.status_code == 200:
                        data = parse_json_safely(resp.json().get("message", {}).get("content", ""))
                        if data and ("application_method" in data or "voiceover_script" in data):
                            set_platform_index("ollama", cur_idx, total_o)
                            return extract_final_payload(data)
                    elif resp.status_code in [401, 429]:
                        print(f"⚠️ Ollama Key #{cur_idx+1} limit/expired (Status: {resp.status_code}). Trying next key...")
                        break
                except Exception as e:
                    print(f"⚠️ Ollama connection error: {e}")
            set_platform_index("ollama", cur_idx + 1, total_o)

    # =========================================================================
    # 🌟 ২. দ্বিতীয় প্রায়োরিটি: OpenRouter Cloud
    # =========================================================================
    openrouter_keys = parse_multiline_keys("OPENROUTER_API_KEYS")
    total_or = len(openrouter_keys)
    if total_or > 0:
        start_or = get_platform_start_index("openrouter", total_or)
        for offset in range(total_or):
            cur_idx = (start_or + offset) % total_or
            k = openrouter_keys[cur_idx]
            headers = {
                "Authorization": f"Bearer {k}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com",
                "X-Title": "Bengali Job Bot"
            }
            for model in OPENROUTER_MODELS:
                print(f"🤖 [Priority 2: OpenRouter] Key #{cur_idx+1}/{total_or} (Model: '{model}')")
                try:
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=35)
                    if resp.status_code == 200:
                        content = resp.json()['choices'][0]['message']['content']
                        data = parse_json_safely(content)
                        if data and ("application_method" in data or "voiceover_script" in data):
                            set_platform_index("openrouter", cur_idx, total_or)
                            return extract_final_payload(data)
                    elif resp.status_code in [401, 402, 429]:
                        break
                except Exception as e:
                    print(f"⚠️ OpenRouter error: {e}")
            set_platform_index("openrouter", cur_idx + 1, total_or)

    # =========================================================================
    # 🌟 ৩. তৃতীয় প্রায়োরিটি: Groq Cloud
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
                print(f"🤖 [Priority 3: Groq] Key #{cur_idx+1}/{total_g} (Model: '{model}')")
                try:
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "You are a professional Bengali circular auditor. Output valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }
                    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
                    if resp.status_code == 200:
                        content = resp.json()['choices'][0]['message']['content']
                        data = parse_json_safely(content)
                        if data and ("application_method" in data or "voiceover_script" in data):
                            set_platform_index("groq", cur_idx, total_g)
                            return extract_final_payload(data)
                    elif resp.status_code in [401, 429]:
                        break
                except Exception as e:
                    print(f"⚠️ Groq error: {e}")
            set_platform_index("groq", cur_idx + 1, total_g)

    # =========================================================================
    # 🌟 ৪. চতুর্থ প্রায়োরিটি: Cerebras Cloud
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
                print(f"🤖 [Priority 4: Cerebras] Key #{cur_idx+1}/{total_c} (Model: '{model}')")
                try:
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "You are a professional Bengali circular auditor. Output valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3
                    }
                    resp = requests.post("https://api.cerebras.ai/v1/chat/completions", headers=headers, json=payload, timeout=30)
                    if resp.status_code == 200:
                        content = resp.json()['choices'][0]['message']['content']
                        data = parse_json_safely(content)
                        if data and ("application_method" in data or "voiceover_script" in data):
                            set_platform_index("cerebras", cur_idx, total_c)
                            return extract_final_payload(data)
                    elif resp.status_code in [401, 429]:
                        break
                except Exception as e:
                    print(f"⚠️ Cerebras error: {e}")
            set_platform_index("cerebras", cur_idx + 1, total_c)

    return None, None, None, None, None
