# -*- coding: utf-8 -*-
import os, json, time, re, shutil, requests, feedparser
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image

WORKSPACE_DIR = "workspace"
FORBIDDEN_KEYWORDS = ['এনজিও', 'ngo', 'ব্যাংক', 'bank', 'চলমান']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
}

def is_forbidden_article(text):
    if not text: return False
    t_lower = text.lower()
    return any(k in t_lower for k in FORBIDDEN_KEYWORDS)

def clean_filename(text):
    text = re.sub(r'[\\/*?:"<>|]', "", str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:90]

def extract_image_urls_from_html(html_content, base_url=""):
    if not html_content: return []
    soup = BeautifulSoup(html_content, 'html.parser')
    img_urls = []
    
    containers = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'(post-body|entry-content|post-content|article-body|td-post-content|main-content)', re.I))
    elements = containers if containers else [soup]

    for container in elements:
        for img in container.find_all('img'):
            src = (
                img.get('data-original') or 
                img.get('data-src') or 
                img.get('data-lazy-src') or 
                img.get('data-orig-file') or 
                img.get('src')
            )
            if not src:
                srcset = img.get('srcset')
                if srcset:
                    src = srcset.split(',')[0].split()[0]

            if src:
                src = src.strip()
                if base_url:
                    src = urljoin(base_url, src)
                    
                src_lower = src.lower()
                if any(ext in src_lower for ext in ['.jpg', '.jpeg', '.png', '.webp']) or 'uploads' in src_lower:
                    if not any(bad in src_lower for bad in ['logo', 'avatar', 'gravatar', 'icon', 'emoji', 'share', 'button', 'badge']):
                        if src.startswith("http") and src not in img_urls:
                            img_urls.append(src)
                            
    return img_urls

def scrape_page_details(page_url):
    try:
        req_headers = HEADERS.copy()
        req_headers["Referer"] = page_url
        resp = requests.get(page_url, headers=req_headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            img_urls = extract_image_urls_from_html(resp.text, base_url=page_url)
            text_container = soup.find(['div', 'article'], class_=re.compile(r'(post-body|entry-content|post-content|article-body)', re.I))
            article_text = text_container.get_text(separator=" ", strip=True) if text_container else soup.get_text(separator=" ", strip=True)
            return img_urls, article_text[:4000]
    except Exception: pass
    return [], ""

def download_image(url, output_path, referer_url=""):
    try:
        req_headers = HEADERS.copy()
        if referer_url: req_headers["Referer"] = referer_url
        req = requests.get(url, headers=req_headers, timeout=20)
        if req.status_code == 200 and len(req.content) > 3000:
            with open(output_path, 'wb') as f:
                f.write(req.content)
            return True
    except Exception: pass
    return False

def check_new_articles_and_prepare_folders():
    print("Checking for new RSS items (Last 24 Hours)...")
    if not os.path.exists(WORKSPACE_DIR): os.makedirs(WORKSPACE_DIR)
    if not os.path.exists('config.json'): return

    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            rss_links = config_data.get('rss_links', [])
    except Exception: return

    time_limit = datetime.now() - timedelta(hours=24)
    existing = [f for f in os.listdir(WORKSPACE_DIR) if os.path.isdir(os.path.join(WORKSPACE_DIR, f))]
    
    history_file = os.path.join(WORKSPACE_DIR, "history.txt")
    history_logs = set()
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as hf:
                history_logs = {line.strip().lower() for line in hf if line.strip()}
        except Exception: pass

    for feed_url in rss_links:
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=15)
            feed = feedparser.parse(resp.content) if resp.status_code == 200 else feedparser.parse(feed_url)
        except Exception: continue
        
        for entry in feed.entries:
            try: published_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            except Exception: continue

            if published_time >= time_limit:
                raw_title = entry.title.strip()
                folder_title = clean_filename(raw_title).strip()
                link = entry.get('link', '').strip()

                if folder_title.lower() == "shorts" or not folder_title or folder_title in existing:
                    continue

                if link.lower() in history_logs or raw_title.lower() in history_logs or folder_title.lower() in history_logs:
                    continue

                if is_forbidden_article(raw_title) or is_forbidden_article(folder_title):
                    continue

                content = entry.content[0].value if hasattr(entry, 'content') else getattr(entry, 'summary', "")
                valid_img_urls = extract_image_urls_from_html(content, base_url=link)
                article_body = BeautifulSoup(content, 'html.parser').get_text(separator=" ", strip=True) if content else ""

                if not valid_img_urls and link:
                    valid_img_urls, page_text = scrape_page_details(link)
                    if page_text: article_body = page_text

                if not valid_img_urls:
                    continue

                folder_path = os.path.join(WORKSPACE_DIR, folder_title)
                os.makedirs(folder_path, exist_ok=True)
                
                downloaded_temp_files = []
                for idx, src in enumerate(valid_img_urls, start=1):
                    temp_img_path = os.path.join(folder_path, f"temp_{idx}.jpg")
                    if download_image(src, temp_img_path, referer_url=link):
                        downloaded_temp_files.append(temp_img_path)

                if not downloaded_temp_files:
                    shutil.rmtree(folder_path, ignore_errors=True)
                    continue

                if len(downloaded_temp_files) > 1:
                    try:
                        with Image.open(downloaded_temp_files[0]) as first_img:
                            w, h = first_img.size
                            if (w / h) >= (16.0 / 9.0) - 0.05:
                                os.remove(downloaded_temp_files[0])
                                downloaded_temp_files.pop(0)
                    except Exception: pass

                final_img_count = 0
                for final_idx, temp_path in enumerate(downloaded_temp_files, start=1):
                    final_path = os.path.join(folder_path, f"{final_idx}.jpg")
                    try:
                        os.rename(temp_path, final_path)
                        final_img_count += 1
                    except Exception: pass

                if final_img_count == 0:
                    shutil.rmtree(folder_path, ignore_errors=True)
                    continue

                with open(os.path.join(folder_path, "title.txt"), "w", encoding="utf-8") as tf:
                    tf.write(raw_title)
                if link:
                    with open(os.path.join(folder_path, "link.txt"), "w", encoding="utf-8") as lf:
                        lf.write(link)
                if article_body:
                    with open(os.path.join(folder_path, "article.txt"), "w", encoding="utf-8") as af:
                        af.write(article_body)

                print(f"✅ Prepared New Circular: {folder_title} ({final_img_count} Images)")
                existing.append(folder_title)
