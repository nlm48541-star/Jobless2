# -*- coding: utf-8 -*-
import os, json, re, base64, requests
from datetime import datetime
from PIL import Image

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

# =========================================================================
# 🌟 আবেদন পদ্ধতি স্বয়ংক্রিয় শনাক্তকরণ (Heuristic + AI Analysis)
# =========================================================================

def detect_application_mode_from_text(article_text):
    """আর্টিকেলের লেখা পড়ে নিশ্চিত হয় যে আবেদনটি ফরম পূরণ, আবেদনপত্র নাকি অনলাইন"""
    t = article_text.lower()
    
    # ডাকযোগ বা কুরিয়ারের উল্লেখ থাকলে নিশ্চিত অফলাইন
    has_offline_hints = any(k in t for k in ["ডাকযোগ", "কুরিয়ার", "কুরিয়ার", "বরাবর পাঠাতে", "খামের উপর", "অফিসে জমা"])
    
    if any(k in t for k in ["ফরম পূরণ", "নির্ধারিত ফরম", "আবেদন ফরম", "ফরম ডাউনলোড"]):
        return "form_fill"
    if any(k in t for k in ["আবেদনপত্র তৈরি", "সাদা কাগজে আবেদন", "লিখিত আবেদনপত্র", "হাতে লেখা আবেদন"]):
        return "letter_write"
    if has_offline_hints:
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
   Read the article content carefully to determine how the candidate must apply:
   - "form_fill": Candidate must download or fill out a prescribed application form (নির্ধারিত ফরম পূরণ করে জমা/ডাকযোগে পাঠানো).
   - "letter_write": Candidate must write a formal application letter on white paper (সাদা কাগজে আবেদনপত্র লিখে ডাকযোগে পাঠানো).
   - "online": Candidate applies directly online through a website portal (e.g. teletalk or official website).

2. TITLE, DESCRIPTION & TAGS REQUIREMENT:
   - If "form_fill": The YouTube title MUST include the phrase 'ফরম পূরণ' (e.g. "{org_name} নিয়োগ বিজ্ঞপ্তি | ফরম পূরণ করার নিয়ম"). Tags & description must also emphasize 'ফরম পূরণ'.
   - If "letter_write": The YouTube title MUST include the phrase 'আবেদনপত্র তৈরি' (e.g. "{org_name} নিয়োগ বিজ্ঞপ্তি | আবেদনপত্র তৈরি করার নিয়ম"). Tags & description must also emphasize 'আবেদনপত্র তৈরি'.
   - If "online": Standard online circular title.

3. SCRIPT INSTRUCTIONS:
   - Generate a 10-MINUTE LONG detailed analysis script (At least 1350 words).
   - EXCLUSIVELY EXPLAIN THE POSTS: Duties of each role, required qualifications, GPA/grades, vacancies, salary grade, and benefits.
   - DO NOT explain the application process in the body.
   - CALL TO ACTION AT THE END:
     "আবেদনটি করতে চাইলে অথবা আপনার ফরম পূরণ ও আবেদনপত্র তৈরি করিয়ে নিতে স্ক্রিনে বা ডেসক্রিপশনে থাকা হোয়াটসঅ্যাপ নাম্বারে এখনই মেসেজ দিন।"

Return strictly valid JSON:
{{
  "application_mode": "{initial_mode}", // "form_fill" OR "letter_write" OR "online"
  "org_name": "{org_name}",
  "job_type": "govt", // or "non-govt"
  "optimized_title": "...",
  "video_description": "...",
  "specific_tags": ["..."],
  "segments": [
    {{
      "segment_title": "ভূমিকা",
      "script_chunk": "...",
      "box_2d": [0, 0, 300, 1000]
    }},
    {{
      "segment_title": "পদসমূহের বিবরণ",
      "script_chunk": "...",
      "box_2d": [250, 0, 850, 1000]
    }},
    {{
      "segment_title": "সমাপনী ও হোয়াটসঅ্যাপ কল টু অ্যাকশন",
      "script_chunk": "...",
      "box_2d": [750, 0, 1000, 1000]
    }}
  ]
}}"""

    def extract_final_payload(data):
        app_mode = data.get("application_mode", initial_mode).lower()
        if app_mode not in ["form_fill", "letter_write", "online"]:
            app_mode = initial_mode

        opt_title = normalize_outdated_years(data.get("optimized_title", clean_title).strip()[:100])
        
        # টাইটেলে বাধ্যতামূলক 'ফরম পূরণ' বা 'আবেদনপত্র তৈরি' নিশ্চিত করা
        if app_mode == "form_fill" and "ফরম পূরণ" not in opt_title:
            opt_title = f"{opt_title} | ফরম পূরণ"[:100]
        elif app_mode == "letter_write" and "আবেদনপত্র তৈরি" not in opt_title:
            opt_title = f"{opt_title} | আবেদনপত্র তৈরি"[:100]

        desc = normalize_outdated_years(data.get("video_description", "").strip())
        raw_tags = data.get("specific_tags", [])
        if app_mode == "form_fill": raw_tags += ['ফরম পূরণ', 'চাকরির ফরম পূরণ']
        elif app_mode == "letter_write": raw_tags += ['আবেদনপত্র তৈরি', 'চাকরির আবেদনপত্র']
        tags = [re.sub(r'\s+', ' ', t).strip()[:50] for t in raw_tags if t][:20]

        thumb_meta = {
            "application_mode": app_mode,
            "org_name": data.get("org_name", org_name),
            "job_type": data.get("job_type", "govt")
        }

        clean_segments = []
        for seg in data.get("segments", []):
            chunk = normalize_outdated_years(seg.get("script_chunk", "").strip())
            if chunk:
                clean_segments.append({
                    "title": seg.get("segment_title", "পদের বিবরণ"),
                    "script": chunk,
                    "box_2d": seg.get("box_2d", [150, 0, 850, 1000])
                })

        return opt_title, "", thumb_meta, desc, tags, clean_segments

    # OpenRouter ➔ Groq ➔ Cerebras ➔ Ollama রোটেশন
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
                        if data and data.get("segments"):
                            set_platform_index("openrouter", cur_idx, len(openrouter_keys))
                            return extract_final_payload(data)
                except Exception: pass
            set_platform_index("openrouter", cur_idx + 1, len(openrouter_keys))

    # Groq ফলব্যাক
    groq_keys = parse_multiline_keys("GROQ_API_KEYS")
    if groq_keys:
        for k in groq_keys:
            try:
                headers = {"Authorization": f"Bearer {k}", "Content-Type": "application/json"}
                payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = parse_json_safely(resp.json()['choices'][0]['message']['content'])
                    if data and data.get("segments"): return extract_final_payload(data)
            except Exception: pass

    return clean_title, "", {"application_mode": initial_mode, "org_name": org_name}, "", [], []
