# -*- coding: utf-8 -*-
import os, json, time, re, shutil, requests, feedparser
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup, NavigableString
from PIL import Image

WORKSPACE_DIR = "workspace"
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "history.txt")
FORBIDDEN_KEYWORDS = ['এনজিও', 'ngo', 'ব্যাংক', 'bank', 'চলমান']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
}

# ৩টি ওয়েবসাইটের অপ্রয়োজনীয় উইজেট, শেয়ার বাটন ও সাইডবার ফিল্টার
NOISE_SELECTOR_RE = re.compile(
    r'(sidebar|widget|toc|table-of-contents|ez-toc|lwptoc|rank-math-toc|author-box|comment|'
    r'share|social|newsletter|disclaimer|calculator|breadcrumb|post-meta|navigation|'
    r'nav-links|yarpp|crp_related|td-post-sharing|sharedaddy|jp-relatedposts)',
    re.I,
)

BAD_IMG_RE = re.compile(
    r'(logo|avatar|gravatar|icon|emoji|share|button|badge|qrcode|qr-code|favicon|'
    r'ads|promo|author|whatsapp|telegram|facebook|messenger|placeholder|'
    r'150x150|300x169|300x200|wp-content/themes|\.svg(?:\?|$)|\.gif(?:\?|$))',
    re.I,
)


def is_forbidden_article(text):
    if not text:
        return False
    return any(k in str(text).lower() for k in FORBIDDEN_KEYWORDS)


def clean_filename(text):
    text = re.sub(r'[\\/*?:"<>|]', "", str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:90]


def add_to_history(entry_text):
    if not entry_text or not str(entry_text).strip():
        return
    clean_val = str(entry_text).strip()
    existing_records = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as hf:
                existing_records = {line.strip().lower() for line in hf if line.strip()}
        except Exception:
            pass

    if clean_val.lower() not in existing_records:
        try:
            os.makedirs(WORKSPACE_DIR, exist_ok=True)
            with open(HISTORY_FILE, "a", encoding="utf-8") as hf:
                hf.write(f"{clean_val}\n")
            print(f"📝 [HISTORY] Saved: '{clean_val[:60]}'")
        except Exception:
            pass


def _pick_largest_srcset_url(srcset_str):
    if not srcset_str:
        return None
    best_url = None
    best_w = -1
    parts = [p.strip() for p in srcset_str.split(',') if p.strip()]
    for part in parts:
        tokens = part.split()
        if not tokens:
            continue
        url = tokens[0]
        w_val = 0
        if len(tokens) > 1 and tokens[1].lower().endswith('w'):
            try:
                w_val = int(tokens[1][:-1])
            except Exception:
                w_val = 0
        if w_val >= best_w:
            best_w = w_val
            best_url = url
    return best_url or (parts[-1].split()[0] if parts else None)


def _pick_real_img_src(img_tag, base_url=""):
    """WordPress Lazy-Load থেকে আসল ইমেজের হাই-রেজোলিউশন URL বের করা"""
    candidates = [
        img_tag.get('data-lazy-src'),
        img_tag.get('data-src'),
        img_tag.get('data-original'),
        img_tag.get('data-orig-file'),
        img_tag.get('data-full-url'),
        img_tag.get('data-large_image'),
    ]
    for attr in ('data-lazy-srcset', 'data-srcset', 'srcset'):
        ss = img_tag.get(attr)
        picked = _pick_largest_srcset_url(ss)
        if picked:
            candidates.append(picked)
    candidates.append(img_tag.get('src'))

    for raw in candidates:
        if not raw:
            continue
        url = str(raw).strip()
        if not url or url.startswith('data:'):
            continue
        if base_url:
            url = urljoin(base_url, url)
        u_lower = url.lower()
        if not u_lower.startswith('http'):
            continue
        if BAD_IMG_RE.search(u_lower):
            continue
        if any(ext in u_lower for ext in ('.jpg', '.jpeg', '.png', '.webp')) or 'uploads' in u_lower or 'googleusercontent' in u_lower or 'i.ibb.co' in u_lower:
            return url
    return None


def _strip_noise_elements(container):
    """আর্টিকেলের কনটেন্ট অক্ষুণ্ণ রেখে শুধু অপ্রয়োজনীয় ট্যাগ ডিকম্পোজ করা"""
    for tag in container(['script', 'style', 'noscript', 'nav', 'footer', 'header', 'aside', 'form', 'iframe', 'svg']):
        tag.decompose()
    for el in list(container.find_all(['div', 'section', 'ul', 'aside'])):
        if not getattr(el, 'attrs', None):
            continue
        cls = " ".join(el.get('class', [])) if isinstance(el.get('class'), list) else str(el.get('class', ''))
        eid = str(el.get('id', ''))
        # ইমেজ র‍্যাপার যেন ভুলবশত ডিলিট না হয়
        if any(w in cls for w in ['wp-block-image', 'image', 'attachment', 'gallery']):
            continue
        if NOISE_SELECTOR_RE.search(f"{cls} {eid}"):
            el.decompose()


def extract_image_urls_from_html(html_content, base_url=""):
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    container = soup.find(
        ['div', 'article', 'main', 'section'],
        class_=re.compile(r'(post-body|entry-content|post-content|article-body|td-post-content|main-content|inside-article)', re.I)
    ) or soup

    _strip_noise_elements(container)

    img_urls = []
    for img in container.find_all('img'):
        parent_a = img.find_parent('a')
        if parent_a and parent_a.get('href'):
            href = urljoin(base_url, parent_a.get('href').strip())
            if any(ext in href.lower() for ext in ('.jpg', '.jpeg', '.png', '.webp')) and not BAD_IMG_RE.search(href):
                if href not in img_urls:
                    img_urls.append(href)
                continue

        real_url = _pick_real_img_src(img, base_url=base_url)
        if real_url and real_url not in img_urls:
            img_urls.append(real_url)

    return img_urls


def _clean_article_text(container):
    """
    ৩টি ওয়েবসাইটের পদের বিবরণ (টেবিল এবং H2/H3 হেডিং) সুন্দরভাবে সাজানো।
    মাঝপথে কোনো break দিয়ে টেক্সট কাটা যাবে না!
    """
    # ১. টেবিল সুন্দরভাবে সাজানো
    for table in container.find_all('table'):
        rows_txt = []
        for tr in table.find_all('tr'):
            cells = [re.sub(r'\s+', ' ', c.get_text(" ", strip=True)) for c in tr.find_all(['th', 'td'])]
            cells = [c for c in cells if c]
            if cells:
                rows_txt.append(" | ".join(cells))
        table.replace_with(NavigableString("\n[টেবিল শুরু]\n" + "\n".join(rows_txt) + "\n[টেবিল শেষ]\n"))

    # ২. হেডিংগুলোকে স্পষ্টভাবে চিহ্নিত করা
    for h in container.find_all(['h2', 'h3', 'h4']):
        h_txt = h.get_text(strip=True)
        if h_txt:
            h.replace_with(NavigableString(f"\n### {h_txt}\n"))

    # ৩. লিস্ট আইটেমগুলোকে বুলেট পয়েন্টে রূপান্তর
    for li in container.find_all('li'):
        li_txt = li.get_text(strip=True)
        if li_txt:
            li.replace_with(NavigableString(f"- {li_txt}\n"))

    raw_text = container.get_text(separator='\n', strip=True)

    # শুধু কমেন্ট বা ফুটারের একেবারে শেষ অংশ বাদ দেওয়া
    final_stop_markers = [
        "Leave a Comment",
        "আপনার মন্তব্য বা প্রশ্ন লিখুন",
        "Your email address will not be published",
        "মন্তব্য করুন",
    ]

    cleaned_lines = []
    for line in raw_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if any(marker in s for marker in final_stop_markers):
            break
        # অন্য চাকরির অযাচিত লিংক ফিল্টার
        if any(bad in s for bad in ["আরও দেখুন -", "হট জব সার্কুলার", "গত ৭ দিনের জনপ্রিয়"]):
            continue
        cleaned_lines.append(s)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def scrape_article_content_and_images(page_url):
    title = ""
    clean_text = ""
    img_urls = []
    if not page_url:
        return title, clean_text, img_urls
    try:
        req_headers = HEADERS.copy()
        req_headers["Referer"] = page_url
        resp = requests.get(page_url, headers=req_headers, timeout=20)
        if resp.status_code == 200:
            if not resp.encoding or resp.encoding.lower() == 'iso-8859-1':
                resp.encoding = resp.apparent_encoding or 'utf-8'

            img_urls = extract_image_urls_from_html(resp.text, base_url=page_url)

            soup = BeautifulSoup(resp.text, 'html.parser')
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
            elif soup.title:
                title = soup.title.get_text(strip=True).split('-')[0].split('|')[0].strip()

            target = soup.find(
                ['div', 'article', 'main', 'section'],
                class_=re.compile(r'(post-body|entry-content|post-content|article-body|td-post-content|main-content|inside-article)', re.I)
            ) or soup

            _strip_noise_elements(target)
            clean_text = _clean_article_text(target)
    except Exception as e:
        print(f"⚠️ Error scraping article: {e}")
    return title, clean_text, img_urls


def scrape_page_details(page_url):
    _, clean_text, img_urls = scrape_article_content_and_images(page_url)
    return img_urls, clean_text


def download_image(url, output_path, referer_url=""):
    try:
        req_headers = HEADERS.copy()
        if referer_url:
            req_headers["Referer"] = referer_url
        req = requests.get(url, headers=req_headers, timeout=20)
        if req.status_code == 200 and len(req.content) > 8000:
            with open(output_path, 'wb') as f:
                f.write(req.content)
            with Image.open(output_path) as im:
                w, h = im.size
                if w < 400 or h < 300:
                    os.remove(output_path)
                    return False
                im.convert("RGB").save(output_path, "JPEG", quality=92)
            return True
    except Exception:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
    return False


def filter_and_download_circular_images(img_urls, target_dir, referer_url="", file_prefix="temp_", final_prefix=""):
    """
    ব্লগের আলংকারিক কভার ব্যানার (রেশিও >= ১.৪২) বাদ দিয়ে আসল খাড়া সার্কুলার পাতাগুলো রাখা
    """
    downloaded_info = []
    for idx, src in enumerate(img_urls, start=1):
        temp_img_path = os.path.join(target_dir, f"{file_prefix}{idx}.jpg")
        if download_image(src, temp_img_path, referer_url=referer_url):
            try:
                with Image.open(temp_img_path) as im:
                    w, h = im.size
                downloaded_info.append((temp_img_path, w, h, w / float(h)))
            except Exception:
                pass

    if not downloaded_info:
        return []

    # খাড়া বা সার্কুলার পাতা (aspect ratio < 1.42)
    non_banners = [item for item in downloaded_info if item[3] < 1.42]
    if non_banners:
        for item in downloaded_info:
            if item[3] >= 1.42:
                try:
                    os.remove(item[0])
                    print(f"✂️ [Cover Banner Removed] Dropped blog banner ({item[1]}x{item[2]}).")
                except Exception:
                    pass
        kept_files = [item[0] for item in non_banners]
    else:
        best = max(downloaded_info, key=lambda x: x[1] * x[2])
        for item in downloaded_info:
            if item[0] != best[0]:
                try:
                    os.remove(item[0])
                except Exception:
                    pass
        kept_files = [best[0]]

    final_paths = []
    for final_idx, temp_path in enumerate(kept_files, start=1):
        final_path = os.path.join(target_dir, f"{final_prefix}{final_idx}.jpg")
        try:
            if os.path.abspath(temp_path) != os.path.abspath(final_path):
                os.replace(temp_path, final_path)
            final_paths.append(final_path)
        except Exception:
            pass

    return final_paths


def check_new_articles_and_prepare_folders():
    print("Checking for new RSS items (Last 24 Hours)...")
    if not os.path.exists(WORKSPACE_DIR):
        os.makedirs(WORKSPACE_DIR)
    if not os.path.exists('config.json'):
        return

    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            rss_links = json.load(f).get('rss_links', [])
    except Exception:
        return

    time_limit = datetime.now() - timedelta(hours=24)
    existing = [f for f in os.listdir(WORKSPACE_DIR) if os.path.isdir(os.path.join(WORKSPACE_DIR, f))]

    history_logs = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as hf:
                history_logs = {line.strip().lower() for line in hf if line.strip()}
        except Exception:
            pass

    for feed_url in rss_links:
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=20)
            feed = feedparser.parse(resp.content) if resp.status_code == 200 else feedparser.parse(feed_url)
        except Exception:
            continue

        for entry in feed.entries:
            parsed_t = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
            if not parsed_t:
                continue
            try:
                published_time = datetime.fromtimestamp(time.mktime(parsed_t))
            except Exception:
                continue

            if published_time >= time_limit:
                raw_title = entry.title.strip()
                folder_title = clean_filename(raw_title).strip()
                link = entry.get('link', '').strip()

                if folder_title.lower() == "shorts" or not folder_title or folder_title in existing:
                    continue
                if link.lower() in history_logs or raw_title.lower() in history_logs or folder_title.lower() in history_logs:
                    continue
                if is_forbidden_article(raw_title) or is_forbidden_article(folder_title):
                    print(f"🚫 [FILTERED] Skipping '{folder_title}'.")
                    continue

                scraped_title, article_text, img_urls = scrape_article_content_and_images(link)

                if not img_urls or not article_text:
                    rss_html = entry.content[0].value if hasattr(entry, 'content') and entry.content else getattr(entry, 'summary', "")
                    if rss_html:
                        if not img_urls:
                            img_urls = extract_image_urls_from_html(rss_html, base_url=link)
                        if not article_text:
                            rss_soup = BeautifulSoup(rss_html, 'html.parser')
                            _strip_noise_elements(rss_soup)
                            article_text = _clean_article_text(rss_soup)

                if is_forbidden_article(scraped_title):
                    print(f"🚫 [FILTERED] Skipping '{folder_title}'.")
                    continue

                if not img_urls:
                    print(f"⏩ Skipping '{folder_title}' (No valid circular images found).")
                    continue

                folder_path = os.path.join(WORKSPACE_DIR, folder_title)
                os.makedirs(folder_path, exist_ok=True)

                final_imgs = filter_and_download_circular_images(img_urls, folder_path, referer_url=link)
                if not final_imgs:
                    shutil.rmtree(folder_path, ignore_errors=True)
                    continue

                with open(os.path.join(folder_path, "title.txt"), "w", encoding="utf-8") as tf:
                    tf.write(raw_title)
                if link:
                    with open(os.path.join(folder_path, "link.txt"), "w", encoding="utf-8") as lf:
                        lf.write(link)
                if article_text:
                    with open(os.path.join(folder_path, "article.txt"), "w", encoding="utf-8") as af:
                        af.write(article_text)

                print(f"✅ Prepared Article: {folder_title} ({len(final_imgs)} Circular Image(s), {len(article_text)} Chars)")
                existing.append(folder_title)
