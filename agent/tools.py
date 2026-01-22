import re
import math
import requests
import logging
import xml.etree.ElementTree as ET
import yfinance as yf
import warnings
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, unquote
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Suppress the "Timestamp.utcnow" warning from yfinance internals
warnings.filterwarnings("ignore", category=FutureWarning, message=".*Timestamp.utcnow is deprecated.*")

logger = logging.getLogger(__name__)

# --- 1. SIGNAL (THE SCOUT) ---

def fetch_rss_feed(feed_url, limit=3):
    """Generic fetcher for ANY RSS feed."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        resp = requests.get(feed_url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        root = ET.fromstring(resp.content)
        items = root.findall("./channel/item")
        namespace = ""
        if not items:
            namespace = "{http://www.w3.org/2005/Atom}"
            items = root.findall(f"{namespace}entry")

        candidates = []
        for i, item in enumerate(items[:limit]):
            title_tag = item.find(f"{namespace}title")
            if title_tag is None: title_tag = item.find("title")
            title = title_tag.text if (title_tag is not None and title_tag.text) else "Untitled Story"

            url = ""
            link_tag = item.find(f"{namespace}link")
            if link_tag is not None:
                url = link_tag.attrib.get("href") or link_tag.text
            if not url:
                 link_tag = item.find("link")
                 if link_tag is not None: url = link_tag.text

            if url:
                candidates.append({"title": title, "url": url, "score": 100 - i})
        return candidates
    except Exception as e:
        logger.error(f"RSS Fetch failed for {feed_url}: {e}")
        return []

def fetch_hn_top_stories(limit=3, scan_depth=30):
    try:
        def calculate_hotness(rank, time_posted_unix):
            if rank == 0: return 0 
            try:
                age_hours = (datetime.now(timezone.utc).timestamp() - time_posted_unix) / 3600
                if age_hours < 0: age_hours = 0
                return (1 / rank) * math.exp(-age_hours / 24)
            except: return 0

        resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
        resp.raise_for_status()
        top_ids = resp.json()[:scan_depth]
        candidates = []
        for rank, sid in enumerate(top_ids, start=1):
            try:
                item_resp = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=10)
                if item_resp.status_code == 200:
                    data = item_resp.json()
                    if "url" in data and "title" in data:
                        score = calculate_hotness(rank, data.get("time", 0))
                        candidates.append({"title": data["title"], "url": data["url"], "score": score})
            except Exception: continue
        candidates.sort(key=lambda x: x['score'], reverse=True)
        return candidates[:limit]
    except Exception as e:
        logger.error(f"HN Fetch failed: {e}")
        return []

# --- 2. URL NORMALIZATION ---
# Fix: Robust regex that ignores brackets/parentheses at the boundaries
URL_RE = re.compile(r'https?://[^ \s\]\[")>]+')

def _clean_raw_url(u: str) -> str:
    try: u = unquote(u)
    except: pass
    # Fix: Aggressively strip markdown artifacts
    if "](" in u: u = u.split("](")[0]
    u = u.lstrip("<").rstrip(".,]\"')> ")
    
    # Fix: Recursive parenthesis balancing
    while u.endswith(")") and u.count(")") > u.count("("):
        u = u[:-1]
    return u

def normalize_url(u: str) -> str:
    if not u: return ""
    try:
        u = unquote(u)
        p = urlparse(u)
        scheme = "https" if p.scheme in ("http", "https") else p.scheme
        netloc = p.netloc.lower()
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source"}]
        query = urlencode(q, doseq=True)
        path = p.path.rstrip("/") if len(p.path) > 1 else p.path
        return urlunparse((scheme, netloc, path, p.params, query, ""))
    except: return u

def extract_urls(text: str) -> list[str]:
    urls = []
    for m in URL_RE.finditer(text):
        raw = _clean_raw_url(m.group(0))
        norm = normalize_url(raw)
        if norm: urls.append(norm)
    return urls

# --- 3. ROBUST VALIDATION ---

def terminal_citation_url(bullet: str) -> str | None:
    """Finds the last URL in the string, regardless of formatting."""
    candidates = extract_urls(bullet)
    if not candidates:
        return None
    # Assume the very last URL mentioned is the citation
    return candidates[-1]

def validate_analysis(analysis_dict: dict, allowed_urls: list[str]) -> bool:
    normalized_allowed = {normalize_url(u) for u in allowed_urls}
    bullets = analysis_dict.get("bullets") or []
    if not bullets: return True

    for bullet in bullets:
        # 1. Find the last URL (Citation)
        cited_url_norm = terminal_citation_url(bullet)
        
        if not cited_url_norm:
             raise ValueError(f"Bullet has no citation URL. Text: {bullet[-50:]}")

        # 2. Check if Citation is Allowed
        if cited_url_norm not in normalized_allowed:
            raise ValueError(f"Citation URL not in allowlist: {cited_url_norm}")

        # 3. Hallucination Check (Body links)
        found_urls = extract_urls(bullet)
        for u in found_urls:
            # We allow the terminal link to appear multiple times
            if u != cited_url_norm and u not in normalized_allowed:
                 raise ValueError(f"Hallucinated URL in text body: {u}")
    return True

# --- 4. FINANCIALS (THREADED FOR WINDOWS) ---
def _fetch_ticker_info(ticker):
    stock = yf.Ticker(ticker)
    info = stock.fast_info
    def get_val(obj, key):
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
    return get_val(info, 'last_price'), get_val(info, 'previous_close')

def safe_get_market_snapshot(text: str, timeout=5) -> str:
    ticker_map = {"NVIDIA": "NVDA", "Tesla": "TSLA", "Apple": "AAPL", "Google": "GOOGL", 
                  "Microsoft": "MSFT", "Amazon": "AMZN", "Meta": "META", "Facebook": "META"}
    
    text_lower = text.lower()
    
    # Improved Matching (Word Boundary)
    found_ticker = None
    for company, ticker in ticker_map.items():
        pattern = r'\b' + re.escape(company.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found_ticker = ticker
            break
            
    if not found_ticker: return ""

    # Threaded Execution (Fast on Windows)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch_ticker_info, found_ticker)
            price, prev = future.result(timeout=timeout)
            
        if not price or not prev or prev == 0: return ""
        pct = ((price - prev) / prev) * 100
        return f" ({found_ticker}: ${price:.2f} {pct:+.1f}%)"
        
    except TimeoutError:
        logger.warning(f"Market data timed out for {found_ticker}")
        return ""
    except Exception as e:
        logger.warning(f"Market data failed for {found_ticker}: {e}")
        return ""
