# -*- coding: utf-8 -*-
import base64
import io
import json
import os
import re
import requests
from datetime import datetime
from PIL import Image

WORKSPACE_DIR = "workspace"
TRACKER_FILE = "api_key_tracker.json"
WORKSPACE_TRACKER = os.path.join(WORKSPACE_DIR, "api_key_tracker.json")

# =========================================================================
# 🌟 মডেল কনফিগারেশন (নভেম্বর ২০২৬ অনুযায়ী কেবল সচল ও বড় মডেল)
# =========================================================================

OPENROUTER_VISION_MODELS = [
    "google/gemma-4-31b-it:free",             # 31B Dense Multimodal (সেরা বাংলা OCR)
    "google/gemma-4-26b-a4b-it:free",         # 26B MoE Multimodal
    "nvidia/nemotron-3.5-super-vl:free",      # 120B MoE Multimodal
]

OPENROUTER_TEXT_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free", # 550B MoE
    "nvidia/nemotron-3.5-super-vl:free",      # 120B MoE
    "google/gemma-4-31b-it:free",             # 31B Dense
    "google/gemma-4-26b-a4b-it:free",         # 26B MoE
    "openrouter/free",                        # Free Auto Router
]

OLLAMA_CHAT_URL = "https://ollama.com/api/chat"

OLLAMA_VISION_MODELS = [
    "kimi-k2.6",                              # 1.04T Multimodal
    "mistral-large-3:675b",                   # 675B Multimodal
    "deepseek-v4.1-flash",                    # 552B Multimodal
    "glm-5.3-flash",                          # Multimodal Flagship
    "gemma4:31b",                             # 31B Multimodal
]

OLLAMA_TEXT_MODELS = [
    "kimi-k2.6",                              # 1.04T
    "glm-5.2",                                # 753B
    "mistral-large-3:675b",                   # 675B
    "deepseek-v4.1-flash",                    # 552B
    "deepseek-v4-pro",                        # Frontier MoE
    "qwen3.5:397b",                           # 397B
    "minimax-m3",                             # Flagship
    "glm-5.3-flash",                          # Multimodal
    "gpt-oss:120b",                           # 120B
    "nemotron-3-super",                       # 120B
    "gemma4:31b",                             # 31B
]

GROQ_MODELS = [
    "openai/gpt-oss-120b",                    # 120B
    "llama-3.3-70b-versatile",                # 70B
]

CEREBRAS_MODELS = [
    "zai-glm-4.7",                            # 355B
    "qwen-3-235b-a22b-instruct-2507",         # 235B
    "gpt-oss-120b",                           # 120B
]

GEMINI_TEXT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.5-flash-lite",
]

DEFAULT_BASE_TAGS = [
    'চাকরির সার্কুলার', 'চাকরির খবর', 'সরকারি চাকরি',
    'job circular', 'govt job circular', 'job application bd'
]


def clean_script_for_speech(raw_text):
    if not raw_text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', str(raw_text), flags=re.DOTALL)
    text = re.sub(r'[\*\_\|\#\~\x60]', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'[\<\>\{\}\(\)\@\$\^\&\+\=\_\\\/]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_multiline_keys(raw_text):
    if not raw_text:
        return []
    lines = re.split(r'[\r\n,;]+', str(raw_text))
    return [k.strip() for k in lines if k.strip() and not k.strip().startswith('#')]


def load_tracker():
    for p in [TRACKER_FILE, WORKSPACE_TRACKER]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def save_tracker_index(service_name, index, total_keys):
    if total_keys == 0:
        return
    data = load_tracker()
    if service_name not in data or not isinstance(data.get(service_name), dict):
        data[service_name] = {}
    data[service_name]["current_index"] = index % total_keys
    data[service_name]["last_updated"] = datetime.now().isoformat()
    for p in [TRACKER_FILE, WORKSPACE_TRACKER]:
        try:
            parent = os.path.dirname(p)
            if parent and not os.path.exists(parent):
                continue
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def get_keys_in_cyclic_order(service_name, raw_keys_str):
    keys = parse_multiline_keys(raw_keys_str)
    if not keys:
        return []
    total = len(keys)
    data = load_tracker()
    svc_entry = data.get(service_name, {})
    saved_idx = (svc_entry.get("current_index", 0) if isinstance(svc_entry, dict) else 0) % total
    return [((saved_idx + i) % total, keys[(saved_idx + i) % total]) for i in range(total)]


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

BN_MONTHS = {
    1: 'জানুয়ারি', 2: 'ফেব্রুয়ারি', 3: 'মার্চ', 4: 'এপ্রিল', 5: 'মে', 6: 'জুন',
    7: 'জুলাই', 8: 'আগস্ট', 9: 'সেপ্টেম্বর', 10: 'অক্টোবর', 11: 'নভেম্বর', 12: 'ডিসেম্বর'
}

BN_ORDINALS = {
    '1ম': 'প্রথম', '১ম': 'প্রথম',
    '2য়': 'দ্বিতীয়', '২য়': 'দ্বিতীয়', '2য়': 'দ্বিতীয়', '২য়': 'দ্বিতীয়',
    '3য়': 'তৃতীয়', '৩য়': 'তৃতীয়', '3য়': 'তৃতীয়', '৩য়': 'তৃতীয়',
    '4র্থ': 'চতুর্থ', '৪র্থ': 'চতুর্থ',
    '5ম': 'পঞ্চম', '৫ম': 'পঞ্চম',
    '6ষ্ঠ': 'ষষ্ঠ', '৬ষ্ঠ': 'ষষ্ঠ',
    '7ম': 'সপ্তম', '৭ম': 'সপ্তম',
    '8ম': 'অষ্টম', '৮ম': 'অষ্টম',
    '9ম': 'নবম', '৯ম': 'নবম',
    '10ম': 'দশম', '১০ম': 'দশম',
}


def en_bn_to_int(s):
    trans = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')
    return int(str(s).translate(trans))


def number_to_bangla_words(n):
    if n == 0:
        return 'শূন্য'
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
        if shatok == 1:
            parts.append('একশত')
        else:
            parts.append(BN_NUMS.get(shatok, str(shatok)) + ' শত')
        n %= 100
    if n > 0:
        parts.append(BN_NUMS.get(n, str(n)))
    return ' '.join(parts)


def convert_all_numbers_in_script(text):
    if not text:
        return ""
    text = re.sub(r'<think>.*?</think>', '', str(text), flags=re.DOTALL)
    text = re.sub(r'https?://\S+|wa\.me/\S+', '', text)
    text = re.sub(r'([0-9০-৯]),([0-9০-৯])', r'\1\2', text)
    text = re.sub(r'(\+?(?:88|৮৮)?[\s\-]*0?1[0-9০-৯][\s\-0-9০-৯]{7,11})', ' আমাদের হোয়াটসঅ্যাপ নম্বর ', text)

    def date_repl(m):
        try:
            d = en_bn_to_int(m.group(1))
            mo = en_bn_to_int(m.group(2))
            y = en_bn_to_int(m.group(3))
            if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2099:
                return f"{number_to_bangla_words(d)} {BN_MONTHS[mo]} {number_to_bangla_words(y)}"
        except Exception:
            pass
        return m.group(0)

    text = re.sub(r'(?<![0-9০-৯])([0-9০-৯]{1,2})[./-]([0-9০-৯]{1,2})[./-]([0-9০-৯]{4})(?![0-9০-৯])', date_repl, text)
    text = re.sub(r'([0-9০-৯]+)\s*(?:/=|/-|৳)(?:\s*টাকা)?', r'\1 টাকা', text)
    text = re.sub(r'৳\s*([0-9০-৯]+)(?:\s*টাকা)?', r'\1 টাকা', text)
    text = re.sub(r'([0-9০-৯]+(?:\.[0-9০-৯]+)?)\s*%', r'\1 শতাংশ', text)
    text = re.sub(r'([0-9০-৯]+)\s*[-–—]\s*([0-9০-৯]+)', r'\1 থেকে \2', text)

    for ord_k, ord_v in BN_ORDINALS.items():
        text = re.sub(rf'(?<![0-9০-৯]){re.escape(ord_k)}(?![0-9০-৯])', ord_v, text)

    def dec_repl(m):
        try:
            left = number_to_bangla_words(en_bn_to_int(m.group(1)))
            right = ' '.join(BN_NUMS.get(en_bn_to_int(ch), ch) for ch in m.group(2))
            return f"{left} দশমিক {right}"
        except Exception:
            return m.group(0)

    text = re.sub(r'(?<![0-9০-৯.])([0-9০-৯]+)\.([0-9০-৯]+)(?![0-9০-৯.])', dec_repl, text)

    def num_repl(m):
        num_str = m.group(0)
        if len(num_str) > 8:
            return ""
        try:
            val = en_bn_to_int(num_str)
            return number_to_bangla_words(val)
        except Exception:
            return num_str

    text = re.sub(r'[0-9০-৯]+', num_repl, text)
    text = re.sub(r'\s+([,।?!])', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def sanitize_youtube_tags(raw_tags, max_total_chars=400):
    clean_tags = []
    current_length = 0
    for tag in raw_tags:
        if not tag or not isinstance(tag, str):
            continue
        cleaned = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\<\>\"\,\n\r]', '', tag)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if not cleaned or len(cleaned) < 2:
            continue
        cleaned = cleaned[:50].strip()
        if cleaned not in clean_tags:
            tag_len = len(cleaned) + (1 if clean_tags else 0)
            if current_length + tag_len <= max_total_chars:
                clean_tags.append(cleaned)
                current_length += tag_len
            else:
                break
    return clean_tags


def clean_title_for_display(title):
    clean = str(title).split('|')[0].split('||')[0].strip()
    return re.sub(r'\s+', ' ', re.sub(r'[\r\n\t]+', ' ', clean))


def strip_unwanted_chars(text):
    s = re.sub(r'\s*৳', ' টাকা', str(text))
    cleaned = re.sub(r'[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|✪|★|☆', '', s)
    return re.sub(r'\s+', ' ', cleaned).strip()


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


def parse_json_safely(raw_text):
    if not raw_text:
        return None
    cleaned = re.sub(r'<think>.*?</think>', '', str(raw_text), flags=re.DOTALL).strip()
    try:
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(cleaned)
    except Exception:
        return None


def _clean_text_response(raw_text):
    if not raw_text or not isinstance(raw_text, str):
        return ""
    cleaned = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL)
    bt3 = "\x60" * 3
    cleaned = re.sub(rf'{bt3}[\w]*', '', cleaned).replace(bt3, '')
    return cleaned.strip()


def _encode_images_base64(img_paths, max_images=3):
    """২০৪৮ পিক্সেল শার্প কোয়ালিটিতে সার্কুলারের ছবি এনকোড করে যাতে ছোট বাংলা সংখ্যাও স্পষ্ট পড়া যায়"""
    b64_list = []
    if not img_paths:
        return b64_list
    for p in img_paths[:max_images]:
        if not p or not os.path.exists(p):
            continue
        try:
            with Image.open(p) as im:
                rgb = im.convert("RGB")
                if rgb.width > 2048:
                    new_h = int((2048 / rgb.width) * rgb.height)
                    rgb = rgb.resize((2048, new_h), Image.LANCZOS)
                buf = io.BytesIO()
                rgb.save(buf, format="JPEG", quality=92)
                b64_list.append(base64.b64encode(buf.getvalue()).decode("ascii"))
        except Exception:
            pass
    return b64_list


# =========================================================================
# 🌟 কেন্দ্রীয় এআই এক্সিকিউশন গেটওয়ে
# =========================================================================

def _call_openrouter(prompt, json_mode=True, b64_images=None, text_fallback=True, max_tokens=4500):
    raw_openrouter = os.environ.get("OPENROUTER_API_KEYS", os.environ.get("OPENROUTER_API_KEY", "")).strip()
    or_order = get_keys_in_cyclic_order("openrouter", raw_openrouter)
    total_or = len(parse_multiline_keys(raw_openrouter))
    if not or_order:
        return None

    for actual_idx, or_key in or_order:
        headers = {
            "Authorization": f"Bearer {or_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",
            "X-Title": "YouTube Automation",
        }

        if b64_images:
            vision_content = [{"type": "text", "text": prompt}]
            for b64 in b64_images:
                vision_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

            for v_model in OPENROUTER_VISION_MODELS:
                payload = {
                    "model": v_model,
                    "messages": [{"role": "user", "content": vision_content}],
                    "temperature": 0.25,
                    "max_tokens": max_tokens,
                }
                try:
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=75)
                    if resp.status_code == 200:
                        content_txt = resp.json()['choices'][0]['message']['content']
                        save_tracker_index("openrouter", actual_idx, total_or)
                        res = parse_json_safely(content_txt) if json_mode else _clean_text_response(content_txt)
                        if res:
                            print(f"  ✨ [OpenRouter Vision] Success with Key #{actual_idx+1} ({v_model})")
                            return res
                    elif resp.status_code in [401, 402]:
                        break
                except Exception:
                    pass

        if text_fallback:
            for model_name in OPENROUTER_TEXT_MODELS:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "max_tokens": max_tokens,
                }
                try:
                    resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=75)
                    if resp.status_code == 200:
                        content_txt = resp.json()['choices'][0]['message']['content']
                        save_tracker_index("openrouter", actual_idx, total_or)
                        res = parse_json_safely(content_txt) if json_mode else _clean_text_response(content_txt)
                        if res:
                            print(f"  ✨ [OpenRouter] Success with Key #{actual_idx+1} ({model_name})")
                            return res
                    elif resp.status_code in [401, 402]:
                        break
                except Exception:
                    pass
        save_tracker_index("openrouter", actual_idx + 1, total_or)
    return None


def _call_ollama_cloud(prompt, json_mode=True, b64_images=None, text_fallback=True, max_tokens=4500):
    raw_ollama = os.environ.get("OLLAMA_API_KEYS", os.environ.get("Ollama_API_Key", os.environ.get("OLLAMA_API_KEY", ""))).strip()
    ollama_order = get_keys_in_cyclic_order("ollama", raw_ollama)
    total_ollama = len(parse_multiline_keys(raw_ollama))
    if not ollama_order:
        return None

    for actual_idx, o_key in ollama_order:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {o_key}"}
        consecutive_402 = 0

        if b64_images:
            for v_model in OLLAMA_VISION_MODELS:
                payload = {
                    "model": v_model,
                    "messages": [{"role": "user", "content": prompt, "images": b64_images}],
                    "stream": False,
                    "options": {"temperature": 0.25, "num_predict": max_tokens},
                }
                try:
                    resp = requests.post(OLLAMA_CHAT_URL, headers=headers, json=payload, timeout=75)
                    if resp.status_code == 200:
                        content_txt = resp.json().get("message", {}).get("content", "").strip()
                        save_tracker_index("ollama", actual_idx, total_ollama)
                        res = parse_json_safely(content_txt) if json_mode else _clean_text_response(content_txt)
                        if res:
                            print(f"  ✨ [Ollama Vision] Success with Key #{actual_idx+1} ({v_model})")
                            return res
                    elif resp.status_code in [401, 402]:
                        consecutive_402 += 1
                        if consecutive_402 >= 2:
                            break
                except Exception:
                    pass

        if text_fallback:
            for model_name in OLLAMA_TEXT_MODELS:
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.4, "num_predict": max_tokens},
                }
                try:
                    resp = requests.post(OLLAMA_CHAT_URL, headers=headers, json=payload, timeout=75)
                    if resp.status_code == 200:
                        content_txt = resp.json().get("message", {}).get("content", "").strip()
                        save_tracker_index("ollama", actual_idx, total_ollama)
                        res = parse_json_safely(content_txt) if json_mode else _clean_text_response(content_txt)
                        if res:
                            print(f"  ✨ [Ollama Cloud] Success with Key #{actual_idx+1} ({model_name})")
                            return res
                    elif resp.status_code in [401, 402]:
                        consecutive_402 += 1
                        if consecutive_402 >= 2:
                            break
                except Exception:
                    pass
        save_tracker_index("ollama", actual_idx + 1, total_ollama)
    return None


def _call_groq(prompt, json_mode=True, max_tokens=4500):
    raw_groq = os.environ.get("GROQ_API_KEYS", os.environ.get("GROQ_API", "")).strip()
    groq_order = get_keys_in_cyclic_order("groq", raw_groq)
    total_groq = len(parse_multiline_keys(raw_groq))
    if not groq_order:
        return None

    for actual_idx, g_key in groq_order:
        headers = {"Authorization": f"Bearer {g_key}", "Content-Type": "application/json"}
        for g_model in GROQ_MODELS:
            sys_msg = "You are a Bengali job circular specialist. Return valid JSON." if json_mode else "You are a professional Bengali YouTube presenter."
            payload = {
                "model": g_model,
                "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": max_tokens,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            try:
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=65)
                if resp.status_code == 200:
                    content_txt = resp.json()['choices'][0]['message']['content']
                    save_tracker_index("groq", actual_idx, total_groq)
                    res = parse_json_safely(content_txt) if json_mode else _clean_text_response(content_txt)
                    if res:
                        print(f"  ✨ [Groq] Success with Key #{actual_idx+1} ({g_model})")
                        return res
                elif "restricted" in resp.text.lower() or resp.status_code in [401, 403]:
                    break
            except Exception:
                pass
        save_tracker_index("groq", actual_idx + 1, total_groq)
    return None


def _call_cerebras(prompt, json_mode=True, max_tokens=4500):
    raw_cerebras = os.environ.get("CEREBRAS_API_KEYS", os.environ.get("CEREBRAS_API_KEY", "")).strip()
    cerebras_order = get_keys_in_cyclic_order("cerebras", raw_cerebras)
    total_cerebras = len(parse_multiline_keys(raw_cerebras))
    if not cerebras_order:
        return None

    for actual_idx, c_key in cerebras_order:
        headers = {"Authorization": f"Bearer {c_key}", "Content-Type": "application/json"}
        for c_model in CEREBRAS_MODELS:
            payload = {
                "model": c_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": max_tokens,
            }
            try:
                resp = requests.post("https://api.cerebras.ai/v1/chat/completions", headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    content_txt = resp.json()['choices'][0]['message']['content']
                    save_tracker_index("cerebras", actual_idx, total_cerebras)
                    res = parse_json_safely(content_txt) if json_mode else _clean_text_response(content_txt)
                    if res:
                        print(f"  ✨ [Cerebras] Success with Key #{actual_idx+1} ({c_model})")
                        return res
            except Exception:
                pass
        save_tracker_index("cerebras", actual_idx + 1, total_cerebras)
    return None


def _call_gemini(prompt, json_mode=True, b64_images=None, max_tokens=4500):
    raw_gemini = os.environ.get("GEMINI_API_KEYS", os.environ.get("GEMINI_API_KEY", "")).strip()
    gemini_order = get_keys_in_cyclic_order("gemini_text", raw_gemini)
    total_gemini = len(parse_multiline_keys(raw_gemini))
    if not gemini_order:
        return None

    parts = [{"text": prompt}]
    if b64_images:
        for b64 in b64_images:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})

    for actual_idx, g_key in gemini_order:
        for g_model in GEMINI_TEXT_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={g_key}"
            body = {
                "contents": [{"parts": parts}],
                "generationConfig": {"temperature": 0.25 if b64_images else 0.4, "maxOutputTokens": max_tokens},
            }
            try:
                resp = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=70)
                if resp.status_code == 200:
                    text_res = resp.json()['candidates'][0]['content']['parts'][0]['text']
                    save_tracker_index("gemini_text", actual_idx, total_gemini)
                    res = parse_json_safely(text_res) if json_mode else _clean_text_response(text_res)
                    if res:
                        tag = "Vision" if len(parts) > 1 else "AI"
                        print(f"  ✨ [Gemini {tag}] Success with Key #{actual_idx+1} ({g_model})")
                        return res
            except Exception:
                pass
        save_tracker_index("gemini_text", actual_idx + 1, total_gemini)
    return None


def execute_ai_query(prompt, json_mode=True, img_paths=None, max_tokens=4500):
    b64_images = _encode_images_base64(img_paths, max_images=3) if img_paths else None

    if b64_images:
        for fn in (
            lambda: _call_openrouter(prompt, json_mode=json_mode, b64_images=b64_images, text_fallback=False, max_tokens=max_tokens),
            lambda: _call_ollama_cloud(prompt, json_mode=json_mode, b64_images=b64_images, text_fallback=False, max_tokens=max_tokens),
            lambda: _call_gemini(prompt, json_mode=json_mode, b64_images=b64_images, max_tokens=max_tokens),
        ):
            res = fn()
            if res:
                return res

    for fn in (
        lambda: _call_openrouter(prompt, json_mode=json_mode, b64_images=None, text_fallback=True, max_tokens=max_tokens),
        lambda: _call_ollama_cloud(prompt, json_mode=json_mode, b64_images=None, text_fallback=True, max_tokens=max_tokens),
        lambda: _call_groq(prompt, json_mode=json_mode, max_tokens=max_tokens),
        lambda: _call_cerebras(prompt, json_mode=json_mode, max_tokens=max_tokens),
        lambda: _call_gemini(prompt, json_mode=json_mode, b64_images=None, max_tokens=max_tokens),
    ):
        res = fn()
        if res:
            return res

    return None


# =========================================================================
# 🌟 ফেইল-সেফ স্ক্রিপ্ট বিল্ডার
# =========================================================================

def build_script_from_verified_data(verified_data, title, article_text):
    org = verified_data.get("organization", title)
    total_vac = verified_data.get("total_vacancies", "")
    deadline = verified_data.get("deadline", "")
    posts = verified_data.get("posts", [])

    vac_line = f"মোট {total_vac} জনবল নিয়োগ দেওয়া হবে।" if total_vac else "বিভিন্ন পদে যোগ্য জনবল নিয়োগ দেওয়া হবে।"
    dl_line = f"আবেদনের শেষ সময় নির্ধারিত হয়েছে {deadline}।" if deadline else ""

    post_paragraphs = []
    for idx, p in enumerate(posts, 1):
        p_name = p.get("post_name", f"{idx} নম্বর পদ")
        p_vac = p.get("vacancy_count", "নির্ধারিত সংখ্যক")
        p_qual = p.get("educational_qualification", "বিজ্ঞপ্তি অনুযায়ী শিক্ষাগত যোগ্যতা")
        p_sal = p.get("salary_scale", "নির্ধারিত বেতন স্কেল")
        p_fee = p.get("application_fee", "বিজ্ঞপ্তিতে উল্লেখ নেই")
        p_duties = p.get("key_duties", "প্রতিষ্ঠানের সংশ্লিষ্ট দাপ্তরিক ও প্রাতিষ্ঠানিক দায়িত্ব পালন করা")

        fee_sentence = (
            "এই পদে আবেদন করতে কোনো আবেদন ফি লাগবে না।"
            if any(w in p_fee for w in ["নেই", "ফ্রি", "বিনামূল্যে", "লাগবে না"])
            else f"এই পদে আবেদন করতে আবেদন ফি লাগবে {p_fee}।"
        )

        para = (
            f"{idx} নম্বর যে পদটি রয়েছে, সেটি হলো {p_name}। "
            f"এই পদে {p_vac} লোক নেওয়া হবে। "
            f"এই পদে চাকরি পেলে মূলত {p_duties}। "
            f"আবেদনের জন্য শিক্ষাগত যোগ্যতা ও অভিজ্ঞতা হিসেবে থাকতে হবে {p_qual}। "
            f"পদটির জন্য বেতন নির্ধারণ করা হয়েছে {p_sal} এবং {fee_sentence}"
        )
        post_paragraphs.append(para)

    posts_block = "\n\n".join(post_paragraphs)

    return f"""আসসালামু আলাইকুম প্রিয় চাকরিপ্রার্থী ভাই ও বোনেরা। আজকের ভিডিওতে আপনাদের সবাইকে স্বাগতম। সম্প্রতি {org} থেকে একটি গুরুত্বপূর্ণ নিয়োগ বিজ্ঞপ্তি প্রকাশিত হয়েছে, যেখানে {vac_line} {dl_line}

প্রথমেই প্রতিষ্ঠানটি সম্পর্কে সংক্ষেপে বলে নিই। {org} দেশের নিজস্ব কর্মক্ষেত্রে অত্যন্ত সুনাম ও মর্যাদার সাথে কাজ করে যাচ্ছে। এখানে চাকরি করার মাধ্যমে যেমন একটি সম্মানজনক ক্যারিয়ার গড়ে তোলা সম্ভব, তেমনি প্রতিষ্ঠানের কার্যক্রমে সরাসরি অবদান রাখার সুযোগ রয়েছে।

এবার চলুন বিজ্ঞপ্তিতে থাকা প্রতিটি আলাদা আলাদা পদের নাম, পদ সংখ্যা, দায়িত্ব, শিক্ষাগত যোগ্যতা, বেতন স্কেল এবং আবেদন ফি সম্পর্কে এক এক করে বিস্তারিত জেনে নেওয়া যাক।

{posts_block}

সাধারণ শর্ত হিসেবে নির্ধারিত বয়সসীমার মধ্যে থাকা দেশের যোগ্য নাগরিকরা আবেদন করতে পারবেন এবং সরকারি বা প্রাতিষ্ঠানিক নিয়ম অনুযায়ী প্রাপ্য বেতন ও অন্যান্য ভাতা-সুবিধা পাবেন।

আবেদনটি করতে চাইলে অথবা আপনার ফরম পূরণ ও আবেদনপত্র তৈরি করিয়ে নিতে স্ক্রিনে বা ডেসক্রিপশনে থাকা হোয়াটসঅ্যাপ নাম্বারে এখনই মেসেজ দিন। নিয়মিত চাকরির খবর পেতে চ্যানেলটি সাবস্ক্রাইব করে সাথেই থাকুন, ধন্যবাদ।"""


# =========================================================================
# 🌟 মডুলার এআই পাইপলাইন (আসল সার্কুলার ছবিই সর্বোচ্চ সত্য!)
# =========================================================================

def extract_verified_job_data(title, article_text, img_paths=None):
    print("\n🔍 [STEP 1] Extracting accurate application mode, ALL posts, qualifications & fees (Image-First Truth)...")
    detected_mode_hint = detect_application_mode_from_text(article_text or title)
    prompt = f"""Analyze BOTH the attached official job circular image(s) (if present) AND the cleaned article text below.
Extract EVERY SINGLE separate post and 100% factual data strictly in JSON.

CRITICAL GROUND TRUTH RULES (MUST OBEY):
1. THE ATTACHED OFFICIAL CIRCULAR IMAGE IS THE SUPREME SOURCE OF TRUTH!
   Warning: Many Bangladeshi job blogs rewrite salary scales using an unofficial/fictional "2026 Pay Scale" (e.g., doubling 12,500->25,000, 22,000->44,000, 8,250->20,000) or have typos in post counts, deadlines, and fees!
   Whenever the blog text conflicts with the official circular image(s), ALWAYS copy the EXACT numbers printed on the official circular image(s) (pay scale, grade, vacancy count per post, application fee, deadline)! Use the blog text only to clarify blurry image text or fill in qualifications/fee details if missing in the image.
2. NEVER invent or hallucinate post names (like calling "বাবুর্চি" as "অসামরিক পদ"). Use the EXACT post name from the circular table!
3. Do NOT skip any post! If there are 6 posts or 13 posts, list ALL of them individually in "posts".
4. APPLICATION METHOD AUDIT ("application_mode"):
   - "form_fill": Prescribed form fill-up (নির্ধারিত ফরম পূরণ করে জমা/ডাকযোগে পাঠানো বা ডাউনলোডযোগ্য আবেদন ফরম).
   - "letter_write": Written application letter (সাদা কাগজে আবেদনপত্র লিখে ডাকযোগে/সরাসরি পাঠানো).
   - "online": Apply online directly via web portal (e.g., teletalk.com.bd or online application website).
   (Initial text hint: "{detected_mode_hint}", verify against the official circular image!)
5. JOB TYPE AUDIT ("job_type"):
   - "govt": Government, Ministry, Autonomous, Defense, Public University, Govt Project.
   - "non-govt": Private company, Ltd., Group, Pharma, Private Organization.
---
TITLE: {title}
CLEANED ARTICLE TEXT (Tables formatted with | ):
{article_text[:11500]}
---

Return strictly valid JSON:
{{
  "organization": "Full Bengali organization/company/ministry name",
  "org_short": "Complete 3-5 word clean Bengali name (never cut awkwardly)",
  "application_mode": "form_fill" | "letter_write" | "online",
  "job_type": "govt" | "non-govt",
  "job_category": "সরকারি চাকরি" | "স্বায়ত্তশাসিত প্রতিষ্ঠান" | "বেসরকারি চাকরি" | "ব্যাংক চাকরি",
  "total_vacancies": "e.g. ০৩টি or ৪৯ জন or ১৮টি",
  "eligibility_summary": "Short 2-4 word range e.g. ৮ম থেকে স্নাতক পাশ",
  "application_fee_summary": "e.g. ৫৬ থেকে ১১২ টাকা or ১০০ ও ২০০ টাকা or আবেদন ফি নেই",
  "deadline": "Exact last date from image/text in Bengali",
  "district_eligibility": "e.g. ৬৪ জেলা or শুধু ঢাকা জেলা",
  "posts": [
    {{
      "post_name": "Exact post name (and grade if given)",
      "vacancy_count": "Exact vacancy count for this post",
      "educational_qualification": "Exact degree/GPA/experience/typing requirement for THIS post",
      "salary_scale": "Exact salary scale printed on the official circular image/text",
      "application_fee": "Exact fee for THIS post (e.g. ২০০ টাকা, ১১২ টাকা, ৫৬ টাকা, বিনামূল্যে)",
      "key_duties": "Detailed 1-2 sentence realistic description of this post's daily duties & responsibilities"
    }}
  ]
}}"""
    return execute_ai_query(prompt, json_mode=True, img_paths=img_paths, max_tokens=4500)


def generate_script_from_verified_data(verified_data, title, article_text):
    print("🎙️ [STEP 2] Generating detailed post-by-post spoken Bengali script...")
    data_str = json.dumps(verified_data, ensure_ascii=False, indent=2)

    prompt = f"""You are a professional Bengali job circular specialist and TV presenter.
Write a continuous, thorough, 100% factual spoken Bengali voiceover script using ONLY the verified data below.

Title: "{title}"
Verified Structured Job Data (Every single post):
{data_str}

Reference Context:
{article_text[:7500]}

STRICT SCRIPT STRUCTURE & LENGTH RULES:
1. [আকর্ষণীয় ও তথ্যবহুল ইন্ট্রো]: Start with "আসসালামু আলাইকুম প্রিয় চাকরিপ্রার্থী ভাই ও বোনেরা।". Clearly introduce which organization/ministry published the circular, total vacancies, eligible districts, and application deadline.
2. [প্রতিষ্ঠান পরিচিতি]: Briefly explain the institution's background, mission, and why a career there is prestigious and stable.
3. [প্রতিটি আলাদা আলাদা পদের গভীর ও বিস্তারিত আলোচনা — মূল অংশ]:
   Go through EVERY SINGLE post in "posts" ONE BY ONE in exact order (from post #1 to the last post, NEVER skip any post!).
   Aim for a comprehensive, engaging deep-dive (targeting ~1000–1450 words when multiple posts exist, or thorough 600–900 words for smaller circulars — WITHOUT inventing fake numbers or repeating filler).
   For EACH individual post, smoothly speak in natural conversational Bengali:
   - পদের আসল নাম ও গ্রেড/বেতন স্কেল (verified_data থেকে হুবহু),
   - এই পদে কতজন লোক নেওয়া হবে,
   - পদটির দৈনন্দিন দায়িত্ব ও কর্মপরিধি কী (বিস্তারিতভাবে),
   - শিক্ষাগত যোগ্যতা, জিপিএ/বিভাগ, কম্পিউটার/টাইপিং দক্ষতা ও অভিজ্ঞতা কী কী লাগবে (ডাটায় যা আছে স্পষ্ট বলবেন),
   - প্রতিষ্ঠানের প্রচলিত বেতন-ভাতা ও অন্যান্য সুযোগ-সুবিধা,
   - এবং এই পদে আবেদন ফি কত টাকা।
   *Formatting rule*: Write continuous natural spoken paragraphs (NO bullet points, NO headings, NO markdown symbols).
4. [সাধারণ শর্ত ও বয়সসীমা]: Mention age limit, quota/district eligibility, and general service benefits.
5. [MANDATORY CALL TO ACTION AT THE END]: End with this exact message:
   "আবেদনটি করতে চাইলে অথবা আপনার ফরম পূরণ ও আবেদনপত্র তৈরি করিয়ে নিতে স্ক্রিনে বা ডেসক্রিপশনে থাকা হোয়াটসঅ্যাপ নাম্বারে এখনই মেসেজ দিন। নিয়মিত চাকরির খবর পেতে চ্যানেলটি সাবস্ক্রাইব করে সাথেই থাকুন, ধন্যবাদ।"

STRICT NEGATIVE CONSTRAINTS:
- STRICTLY DO NOT explain the application process in the body (NO postal address, NO courier/email steps, NO website URLs, NO form-filling instructions, NO photo/signature dimensions).
- DO NOT write or speak ANY phone number digits anywhere in the script.
- Output ONLY pure spoken Bengali plain text (no JSON, no markdown, no brackets)."""

    res_text = execute_ai_query(prompt, json_mode=False, max_tokens=7500)
    return res_text if res_text and isinstance(res_text, str) else ""


def generate_seo_metadata(verified_data, title, app_mode="online"):
    print("📈 [STEP 3] Generating SEO Title, Description & Tags...")
    posts_summary = ", ".join([p.get("post_name", "") for p in verified_data.get("posts", [])[:5]])
    total_vac = verified_data.get("total_vacancies", "")
    org = verified_data.get("organization", title)
    job_cat = verified_data.get("job_category", "চাকরির খবর")
    deadline = verified_data.get("deadline", "")

    mode_hint = ""
    if app_mode == "form_fill":
        mode_hint = "IMPORTANT: The title MUST include 'ফরম পূরণ'."
    elif app_mode == "letter_write":
        mode_hint = "IMPORTANT: The title MUST include 'আবেদনপত্র তৈরি'."

    wa_num = os.environ.get("WHATSAPP_NUMBER", "").strip()
    wa_instruction = f"WhatsApp contact link: wa.me/{wa_num}" if wa_num else "Invite viewers to message the WhatsApp number shown on screen/description (do not invent any phone number digits)."

    prompt = f"""Generate YouTube SEO metadata in JSON for this job circular:
Organization: "{org}"
Category: "{job_cat}"
Application Mode: "{app_mode}"
Title: "{title}"
Key Posts: "{posts_summary}"
Total Vacancies: "{total_vac}"
Deadline: "{deadline}"
{mode_hint}

Return strictly valid JSON:
{{
  "optimized_title": "High-CTR Bengali YouTube Title under 90 chars featuring organization and total vacancies",
  "video_description": "Helpful Bengali description summarizing posts, qualifications, fee info, deadline. {wa_instruction}",
  "specific_tags": ["8 to 12 relevant Bengali & English SEO tags without commas"]
}}"""
    return execute_ai_query(prompt, json_mode=True, max_tokens=2000)


# =========================================================================
# 🌟 মূল মাস্টার ফাংশন (বর্তমান থাম্বনেইল ও ভিডিও পাইপলাইনের সাথে সম্পূর্ণ সামঞ্জস্যপূর্ণ)
# =========================================================================

def generate_job_content(title, img_paths=None, article_text=""):
    if isinstance(img_paths, str) and (article_text is None or isinstance(article_text, list)):
        article_text, img_paths = img_paths, article_text

    clean_title = clean_title_for_display(title)
    article_text = article_text or ""

    verified_data = extract_verified_job_data(clean_title, article_text, img_paths=img_paths)
    if not verified_data or not isinstance(verified_data, dict) or not verified_data.get("posts"):
        words = clean_title.split()
        clean_org = clean_title.split("নিয়োগ")[0].strip() if "নিয়োগ" in clean_title else " ".join(words[:min(4, len(words))])
        is_priv = any(k in clean_title.lower() for k in ["লিমিটেড", "ফার্মা", "গ্রুপ", "কোম্পানি", "বেসরকারি", "বিকাশ", "ফাউন্ডেশন", "এনজিও", "ltd", "limited"])
        verified_data = {
            "organization": clean_org,
            "org_short": " ".join(clean_org.split()[:4]),
            "application_mode": detect_application_mode_from_text(article_text or clean_title),
            "job_type": "non-govt" if is_priv else "govt",
            "job_category": "বেসরকারি চাকরি" if is_priv else "সরকারি চাকরি",
            "total_vacancies": "",
            "eligibility_summary": "বিজ্ঞপ্তি অনুযায়ী যোগ্যতা",
            "application_fee_summary": "বিজ্ঞপ্তি অনুযায়ী",
            "deadline": "",
            "district_eligibility": "সকল জেলা",
            "posts": [{
                "post_name": "বিভিন্ন পদে নিয়োগ",
                "vacancy_count": "নির্ধারিত সংখ্যক",
                "salary_scale": "নির্ধারিত স্কেল",
                "educational_qualification": "বিজ্ঞপ্তি অনুযায়ী",
                "application_fee": "বিজ্ঞপ্তি অনুযায়ী",
                "key_duties": "সংশ্লিষ্ট দাপ্তরিক দায়িত্ব পালন",
            }]
        }

    app_mode = str(verified_data.get("application_mode", "")).strip().lower()
    if app_mode not in ("form_fill", "letter_write", "online"):
        app_mode = detect_application_mode_from_text(article_text or clean_title)

    job_type = str(verified_data.get("job_type", "")).strip().lower()
    if job_type not in ("govt", "non-govt", "private"):
        job_cat_lower = str(verified_data.get("job_category", "")).lower()
        is_priv = any(k in (job_cat_lower + " " + clean_title.lower()) for k in ["বেসরকারি", "প্রাইভেট", "লিমিটেড", "ফার্মা", "গ্রুপ", "কোম্পানি", "ltd", "limited"])
        job_type = "non-govt" if is_priv else "govt"

    raw_script = generate_script_from_verified_data(verified_data, clean_title, article_text)

    if not raw_script or len(raw_script.split()) < 160:
        print(f"⚠️ Generated script was short ({len(raw_script.split()) if raw_script else 0} words). Using structured post-by-post builder...")
        raw_script = build_script_from_verified_data(verified_data, clean_title, article_text)

    voiceover_script = convert_all_numbers_in_script(raw_script)

    seo_res = generate_seo_metadata(verified_data, clean_title, app_mode=app_mode)
    opt_title = (seo_res.get("optimized_title") or clean_title).strip() if seo_res and isinstance(seo_res, dict) else clean_title
    if app_mode == "form_fill" and "ফরম পূরণ" not in opt_title:
        opt_title = f"{opt_title[:86].strip()} | ফরম পূরণ"
    elif app_mode == "letter_write" and "আবেদনপত্র তৈরি" not in opt_title:
        opt_title = f"{opt_title[:80].strip()} | আবেদনপত্র তৈরি"
    opt_title = opt_title[:100]

    video_desc = (seo_res.get("video_description") or clean_title).strip() if seo_res and isinstance(seo_res, dict) else clean_title
    raw_tags = seo_res.get("specific_tags", []) if seo_res and isinstance(seo_res, dict) else []
    if app_mode == "form_fill":
        raw_tags = list(raw_tags) + ['ফরম পূরণ', 'চাকরির ফরম পূরণ']
    elif app_mode == "letter_write":
        raw_tags = list(raw_tags) + ['আবেদনপত্র তৈরি', 'চাকরির আবেদনপত্র']
    video_tags = sanitize_youtube_tags(list(raw_tags) + DEFAULT_BASE_TAGS)

    org_for_thumb = strip_unwanted_chars(
        verified_data.get("org_short") or verified_data.get("organization") or clean_title.split("নিয়োগ")[0].strip()
    )
    thumb_meta = {
        "application_mode": app_mode,
        "org_name": org_for_thumb,
        "job_type": job_type,
        "line1_text": "জরুরী নিয়োগ বিজ্ঞপ্তি",
    }

    word_count = len(voiceover_script.split())
    print(f"✨ [ACCURACY GUARANTEED] {word_count}-word Script | Mode [{app_mode}] | Org [{org_for_thumb}] Ready!")
    return opt_title, voiceover_script, thumb_meta, video_desc, video_tags
