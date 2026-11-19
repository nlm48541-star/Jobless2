# -*- coding: utf-8 -*-
import os, json, time, re, shutil, unicodedata, requests, feedparser
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup, NavigableString
from PIL import Image

WORKSPACE_DIR = "workspace"
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "history.txt")

# আগের প্রজেক্টের ব্লক করা কিওয়ার্ডসমূহ (বানানভেদসহ)
FORBIDDEN_KEYWORDS = ['এনজিও', 'ngo', 'ব্যাংক', 'ব্যাঙ্ক', 'bank', 'চলমান']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'bn-BD,bn;q=0.9,en-US;q=0.8,en;q=0.7',
}

# ওয়ার্ড বাউন্ডারি (\b) সহ নয়েজ ফিল্টার যাতে আর্টিকেল কনটেন্ট নিরাপদ থাকে
NOISE_SELECTOR_RE = re.compile(
    r'\b(sidebar|widget|widget-area|ez-toc|lwptoc|rank-math-toc|table-of-contents|'
    r'author-box|comments-area|comment-respond|sharedaddy|jp-relatedposts|yarpp|'
    r'crp_related|td-post-sharing|td-related-posts|related-posts|recent-posts|'
    r'popular-posts|social-share|share-buttons|newsletter|calculator|breadcrumb|'
    r'post-navigation|nav-links)\b',
    re.I,
)

# \bads\b ও \blogo\b ব্যবহার করা হয়েছে যাতে 'uploads' বা বৈধ সার্কুলার URL ব্লক না হয়!
BAD_IMG_RE = re.compile(
    r'(\blogo\b|\bavatar\b|\bgravatar\b|\bicon\b|\bemoji\b|share-button|social-share|'
    r'\bbutton\b|\bbadge\b|qrcode|qr-code|favicon|\bads\b|\badvert\b|adsense|'
    r'googlesyndication|\bpromo\b|author-avatar|whatsapp-icon|telegram-icon|'
    r'facebook-icon|messenger-icon|placeholder|150x150|300x169|300x200|'
    r'wp-content/themes|\.svg(?:\?|$)|\.gif(?:\?|$))',
    re.I,
)

VALID_IMG_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.jfif', '.bmp')


def is_forbidden_article(text):
    if not text:
        return False
    norm_text = unicodedata.normalize('NFC', str(text)).lower()
    for kw in FORBIDDEN_KEYWORDS:
        norm_kw = unicodedata.normalize('NFC', kw).lower()
        if norm_kw in norm_text:
            return True
    return False


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


def _is_valid_image_url(url_lower):
    if not url_lower.startswith('http'):
        return False
    if BAD_IMG_RE.search(url_lower):
        return False
    return (
        any(ext in url_lower for ext in VALID_IMG_EXTS)
        or 'uploads' in url_lower
        or 'googleusercontent' in url_lower
        or 'i.ibb.co' in url_lower
        or 'wp.com/' in url_lower
    )


def _pick_real_img_src(img_tag, base_url=""):
    candidates = [
        img_tag.get('data-lazy-src'),
        img_tag.get('data-src'),
        img_tag.get('data-original'),
        img_tag.get('data-orig-file'),
        img_tag.get('data-full-url'),
        img_tag.get('data-large_image'),
    ]
    for attr in ('data-lazy-srcset', 'data-srcset', 'srcset'):
        picked = _pick_largest_srcset_url(img_tag.get(attr))
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
        if _is_valid_image_url(url.lower()):
            return url
    return None


def _strip_noise_elements(container, remove_noscript=True):
    tags_to_remove = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'iframe', 'svg']
    if remove_noscript:
        tags_to_remove.append('noscript')
    for tag in container(tags_to_remove):
        tag.decompose()
    for el in list(container.find_all(['div', 'section', 'ul', 'aside'])):
        if not getattr(el, 'attrs', None):
            continue
        cls = " ".join(el.get('class', [])) if isinstance(el.get('class'), list) else str(el.get('class', ''))
        eid = str(el.get('id', ''))
        cls_lower = cls.lower()
        if any(w in cls_lower for w in ['wp-block-image', 'wp-block-gallery', 'circular-image', 'attachment']):
            continue
        if NOISE_SELECTOR_RE.search(f"{cls} {eid}"):
            el.decompose()


def _find_article_containers(soup):
    containers = soup.find_all(
        ['div', 'article', 'main', 'section'],
        class_=re.compile(r'(post-body|entry-content|post-content|article-body|td-post-content|inside-article)', re.I)
    )
    if not containers:
        containers = soup.find_all(
            ['div', 'article', 'main', 'section'],
            class_=re.compile(r'(main-content|content-area|single-content|post-wrapper)', re.I)
        )
    if not containers:
        containers = [soup.find('article') or soup.find('main') or soup]
    return containers


def extract_image_urls_from_html(html_content, base_url=""):
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    containers = _find_article_containers(soup)

    img_urls = []
    for container in containers:
        _strip_noise_elements(container, remove_noscript=False)
        for img in container.find_all('img'):
            parent_a = img.find_parent('a')
            if parent_a and parent_a.get('href'):
                href = urljoin(base_url, parent_a.get('href').strip())
                if any(ext in href.lower() for ext in VALID_IMG_EXTS) and not BAD_IMG_RE.search(href):
                    if href not in img_urls:
                        img_urls.append(href)
                    continue

            real_url = _pick_real_img_src(img, base_url=base_url)
            if real_url and real_url not in img_urls:
                img_urls.append(real_url)

    return img_urls


def _clean_article_text(container):
    for table in container.find_all('table'):
        rows_txt = []
        for tr in table.find_all('tr'):
            cells = [re.sub(r'\s+', ' ', c.get_text(" ", strip=True)) for c in tr.find_all(['th', 'td'])]
            cells = [c for c in cells if c]
            if cells:
                rows_txt.append(" | ".join(cells))
        table.replace_with(NavigableString("\n[টেবিল শুরু]\n" + "\n".join(rows_txt) + "\n[টেবিল শেষ]\n"))

    for h in container.find_all(['h2', 'h3', 'h4']):
        h_txt = h.get_text(strip=True)
        if h_txt:
            h.replace_with(NavigableString(f"\n### {h_txt}\n"))

    for li in container.find_all('li'):
        li_txt = li.get_text(strip=True)
        if li_txt:
            li.replace_with(NavigableString(f"- {li_txt}\n"))

    raw_text = container.get_text(separator='\n', strip=True)

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

            targets = _find_article_containers(soup)
            text_parts = []
            for t in targets:
                _strip_noise_elements(t, remove_noscript=True)
                txt = _clean_article_text(t)
                if txt:
                    text_parts.append(txt)
            clean_text = "\n\n".join(text_parts).strip()
        else:
            print(f"⚠️ HTTP {resp.status_code} while scraping: {page_url}")
    except Exception as e:
        print(f"⚠️ Error scraping article ({page_url}): {e}")
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
        if req.status_code == 200 and len(req.content) > 6000:
            with open(output_path, 'wb') as f:
                f.write(req.content)
            with Image.open(output_path) as im:
                w, h = im.size
                if w < 380 or h < 280:
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
    ব্লগের আলংকারিক ১৬:৯ কভার ব্যানার (ratio >= 1.58) বাদ দিয়ে আসল সার্কুলার ছবিগুলো রাখা
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

    non_banners = [item for item in downloaded_info if item[3] < 1.58]
    if non_banners:
        for item in downloaded_info:
            if item[3] >= 1.58:
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
                    print(f"🚫 [FILTERED] Skipping '{folder_title}' (Forbidden keyword matched).")
                    continue

                scraped_title, article_text, img_urls = scrape_article_content_and_images(link)

                if not img_urls or not article_text:
                    rss_html = entry.content[0].value if hasattr(entry, 'content') and entry.content else getattr(entry, 'summary', "")
                    if rss_html:
                        if not img_urls:
                            img_urls = extract_image_urls_from_html(rss_html, base_url=link)
                        if not article_text:
                            rss_soup = BeautifulSoup(rss_html, 'html.parser')
                            _strip_noise_elements(rss_soup, remove_noscript=True)
                            article_text = _clean_article_text(rss_soup)

                if is_forbidden_article(scraped_title):
                    print(f"🚫 [FILTERED] Skipping '{folder_title}' (Forbidden keyword in page title).")
                    continue

                if not img_urls:
                    print(f"⏩ Skipping '{folder_title}' (No valid circular images found in HTML/RSS).")
                    continue

                folder_path = os.path.join(WORKSPACE_DIR, folder_title)
                os.makedirs(folder_path, exist_ok=True)

                final_imgs = filter_and_download_circular_images(img_urls, folder_path, referer_url=link)
                if not final_imgs:
                    print(f"⏩ Skipping '{folder_title}' (Found {len(img_urls)} URL(s), but none downloaded cleanly).")
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
