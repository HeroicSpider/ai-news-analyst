import os
import json
import logging
import re
import time
import argparse
from datetime import datetime
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from tavily import TavilyClient
from schema import StoryAnalysis
from tools import fetch_hn_top_stories, fetch_rss_feed, validate_analysis, safe_get_market_snapshot, normalize_url

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path Anchoring
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
REPORT_PATH = BASE_DIR / "run_report.json"
OUTPUT_DIR = REPO_ROOT / "src/content/news"

# Constants
MAX_RETRIES = 2
MIN_CONTENT_LENGTH = 300 

# Source Registry
SOURCE_PRESETS = {
    "hackernews": "hn", 
    "techcrunch": "https://techcrunch.com/feed/",
    "theverge": "https://www.theverge.com/rss/index.xml",
    "wired": "https://www.wired.com/feed/rss",
    "nytimes": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "wsj": "https://feeds.a.dj.com/rss/RSSWSJD.xml"
}

run_report = {
    "timestamp": datetime.now().isoformat(),
    "status": "started",
    "metrics": {"seeded": 0, "processed": 0, "failed": 0, "skipped": 0},
    "trace": [] 
}

def save_report():
    os.makedirs(REPORT_PATH.parent, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(run_report, f, indent=2)

def coerce_llm_text(response) -> str:
    """Safely extracts text from various LangChain message formats."""
    raw = getattr(response, "content", None)
    if raw is None:
        raw = getattr(response, "text", "")
    if isinstance(raw, str): return raw
    if isinstance(raw, list):
        parts = []
        for x in raw:
            if isinstance(x, str): parts.append(x)
            elif isinstance(x, dict): parts.append(x.get("text") or x.get("content") or str(x))
            else: parts.append(getattr(x, "text", None) or getattr(x, "content", None) or str(x))
        return " ".join(p for p in parts if p)
    return str(raw)

def extract_json_block(text):
    text = text.strip()
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        try: return json.loads(match.group(1))
        except: pass 
    try: return json.loads(text[text.index('{'):text.rindex('}')+1])
    except: pass
    try: return json.loads(text[text.index('['):text.rindex(']')+1])
    except: return None

def _coerce_tavily_result(r):
    if isinstance(r, dict): return r
    return {
        "url": getattr(r, "url", None),
        "content": getattr(r, "content", None),
        "raw_content": getattr(r, "raw_content", None),
        "title": getattr(r, "title", None),
    }

def get_seeds(source_arg):
    """Determines seeds based on the command-line argument."""
    source_input = source_arg.lower()
    
    # 1. Check presets
    if source_input in SOURCE_PRESETS:
        url = SOURCE_PRESETS[source_input]
        if url == "hn":
            logger.info("Source: Hacker News (API)")
            return fetch_hn_top_stories(limit=3)
        else:
            logger.info(f"Source: {source_input} (RSS: {url})")
            return fetch_rss_feed(url, limit=3)
            
    # 2. Check if raw URL
    if source_input.startswith("http"):
        logger.info(f"Source: Custom RSS ({source_input})")
        return fetch_rss_feed(source_input, limit=3)
        
    # 3. Default fallback
    logger.warning(f"Unknown source '{source_input}', defaulting to Hacker News")
    return fetch_hn_top_stories(limit=3)

def main():
    # --- ARGUMENT PARSING ---
    parser = argparse.ArgumentParser(description="Run the AI News Analyst.")
    parser.add_argument(
        "--source", 
        type=str, 
        default="hackernews", 
        help="News source preset (techcrunch, wired) or raw RSS URL."
    )
    args = parser.parse_args()

    # --- SETUP ---
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key: raise RuntimeError("Missing GOOGLE_API_KEY")
    if "TAVILY_API_KEY" not in os.environ: raise RuntimeError("Missing TAVILY_API_KEY")

    save_report()
    
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=api_key)
        tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        
        # DYNAMIC FETCHING
        seeds = get_seeds(args.source)
        
        run_report["metrics"]["seeded"] = len(seeds)
        save_report()

        final_stories = []

        for seed in seeds:
            time.sleep(10) # Rate limit protection
            
            title = seed.get('title', 'Untitled Story')
            seed_url = normalize_url(seed.get('url', ''))
            
            if not seed_url:
                logger.warning(f"Skipping {title}: Missing URL")
                run_report["metrics"]["skipped"] += 1
                save_report()
                continue

            try:
                logger.info(f"Enriching: {title}")
                raw_results_list = []
                try:
                    search_result = tavily.search(query=title, search_depth="basic", max_results=3)
                    if isinstance(search_result, dict): raw_results_list = search_result.get("results", []) or []
                    elif isinstance(search_result, list): raw_results_list = search_result
                    else: raw_results_list = getattr(search_result, "results", []) or []
                except Exception as e:
                    logger.warning(f"Tavily search failed: {e}")
                
                tavily_results = [_coerce_tavily_result(r) for r in raw_results_list]
                valid_results = [r for r in tavily_results if r.get('url') and r.get('content')]
                
                total_content = "".join([str(r.get('content', '') or "") for r in valid_results])
                if len(total_content) < MIN_CONTENT_LENGTH:
                    logger.info(f"Skipping {title}: Insufficient content")
                    run_report["metrics"]["skipped"] += 1
                    save_report()
                    continue

                raw_allowed_urls = [normalize_url(str(r.get('url', ''))) for r in valid_results]
                seen = set()
                allowed_urls = [u for u in raw_allowed_urls if not (u in seen or seen.add(u))]
                
                if not allowed_urls:
                    logger.info(f"Skipping {title}: No valid allowed URLs")
                    run_report["metrics"]["skipped"] += 1
                    save_report()
                    continue

                primary_allowed_url = seed_url if seed_url in allowed_urls else allowed_urls[0]
                seed_url_redacted = seed_url.replace("https://", "hxxps://").replace("http://", "hxxp://")

                context_lines = []
                for r in valid_results:
                    content = str(r.get('content', '') or '').replace("\n", " ").strip()[:600]
                    url_str = normalize_url(str(r.get('url', '')))
                    context_lines.append(f"- {content} (Source: {url_str})")
                context_text = "\n".join(context_lines)

                story_success = False
                last_err = None

                for attempt in range(MAX_RETRIES + 1):
                    try:
                        prompt = f"""
                        You are a strict financial analyst. 
                        STORY: {title}
                        CONTEXT: {context_text}
                        
                        SEED URL (Reference Only): {seed_url_redacted}
                        PRIMARY CITATION TARGET: {primary_allowed_url}
                        
                        TASK: Write 2-3 bullet points summarizing the story.
                        
                        CRITICAL RULES:
                        1. Return ONLY a valid JSON object.
                        2. Every bullet MUST end with the citation format: [Source Name](URL)
                        3. DO NOT add a trailing period after the citation.
                        4. Use URLs from this list ONLY: {json.dumps(allowed_urls)}
                        5. If context is insufficient, return "bullets": []
                        
                        OUTPUT SCHEMA: {{"bullets": ["Bullet text [Source](URL)", "Another bullet [Source](URL)"]}}
                        """.strip()
                        
                        response = llm.invoke(prompt)
                        data = extract_json_block(coerce_llm_text(response))
                        if data is None: raise ValueError("Failed to parse JSON")
                        
                        analysis = StoryAnalysis(**data) 
                        if len(analysis.bullets) == 0:
                            logger.info(f"Skipping {title} (LLM returned empty)")
                            run_report["metrics"]["skipped"] += 1
                            story_success = True 
                            break

                        validate_analysis(analysis.model_dump(), allowed_urls)
                        market_str = safe_get_market_snapshot(title)
                        
                        final_stories.append({
                            "title": title,
                            "market_data": market_str,
                            "bullets": analysis.bullets,
                            "source": primary_allowed_url,
                            "seed_canonical": seed_url
                        })
                        
                        run_report["metrics"]["processed"] += 1
                        run_report["trace"].append({"title": title, "status": "success"})
                        story_success = True
                        break 
                    except Exception as e:
                        last_err = str(e)
                        time.sleep(5 * (attempt + 1)) 
                        logger.warning(f"Attempt {attempt+1} failed for '{title}': {e}")

                if not story_success:
                    run_report["metrics"]["failed"] += 1
                    run_report["trace"].append({"title": title, "status": "failed", "error": last_err})
            except Exception as e:
                 logger.error(f"Critical error: {e}")
                 run_report["metrics"]["failed"] += 1
            save_report() 

        if not final_stories:
            logger.warning("No stories generated.")
            run_report["status"] = "completed_empty"
            save_report()
            return

        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = OUTPUT_DIR / f"{date_str}.md"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        md_content = f"""---
title: "Daily Briefing: {date_str}"
pubDate: "{date_str}"
description: "AI-curated analysis of {len(final_stories)} tech stories."
tags: ["tech", "ai"]
---
# ☕ Daily Tech Briefing
"""
        for s in final_stories:
            md_content += f"## [{s['title']}]({s['source']}){s['market_data']}\n"
            for b in s['bullets']:
                md_content += f"* {b}\n"
            md_content += "\n"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        logger.info(f"Published to {filename}")
        run_report["status"] = "success"
        save_report()

    except Exception as e:
        logger.critical(f"Run failed: {e}")
        run_report["status"] = "failed"
        run_report["error"] = str(e)
        save_report()
        exit(1)

if __name__ == "__main__":
    main()
