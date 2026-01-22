````markdown
# 🤖 Autonomous AI News Analyst

![Daily Briefing](https://img.shields.io/github/actions/workflow/status/HeroicSpider/ai-news-analyst/daily.yml?label=Daily%20Briefing)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Astro](https://img.shields.io/badge/astro-4.0-orange)

An autonomous agent that acts as a daily tech journalist. It finds trending stories, researches them via live web search, enforces strict citation/grounding rules, and publishes a daily briefing—without human intervention.

[**View Live Demo**](https://ai-news-analyst-sable.vercel.app/)

---

## 📖 The "Why"

This project was built as a proof of concept for a **Founding AI Product Engineer** role. The prompt was simple: “Build a website that summarizes the hottest tech news.”

Instead of a headline summarizer, I built a production-oriented **agentic workflow** with reporter-like constraints:

1. **Skeptical:** Treats headlines as untrusted until corroborated.
2. **Grounded:** Refuses to publish bullets without URL citations.
3. **Autonomous:** Runs on a schedule, retries safely, and publishes via CI.

---

## 🛠️ Architecture

A **Retrieval-Augmented Generation (RAG)** pipeline orchestrated by Python and GitHub Actions.

### 1) The Scout (Signal)
- Pulls candidates from **Hacker News** or **RSS feeds** (TechCrunch, Wired, etc.).
- Scores recency with a hotness function: `Score = (1 / Rank) * e^(-AgeHours / 24)`.

### 2) The Researcher (Enrichment)
- Uses **Tavily** to fetch multiple sources for each story.
- Builds a bounded context window from retrieved article text.
- **Market snapshot:** If a story mentions one of a small set of major tech companies, it fetches a stock snapshot via `yfinance` using a strict ticker allowlist (quality + predictability).

### 3) The Editor (Validation Gate)
- A regex-based “critic” validates the draft:
  - Every bullet must end with a valid `[Source](URL)` citation.
  - The cited URL must be in the allowlist derived from retrieval results.
- If citations don’t validate, the agent retries or skips (no “best guess” publishing).

### 4) The Publisher (Frontend)
- Writes an approved report as a Markdown file.
- **Astro** builds a static site from the Markdown archive.

---

## 🚀 How to Run It

### Option A: Run Locally

1) **Clone**
```bash
git clone https://github.com/HeroicSpider/ai-news-analyst.git
cd ai-news-analyst
````

2. **Backend (Python)**

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r agent/requirements.txt
```

3. **Frontend (Node.js)**

```bash
npm install
```

4. **Configure API keys**
   Get keys from Google AI Studio and Tavily. You can use either `GOOGLE_API_KEY` or `GEMINI_API_KEY`.

```bash
# Linux/Mac
export GOOGLE_API_KEY="your_key"
export TAVILY_API_KEY="your_key"

# Windows (PowerShell)
$env:GOOGLE_API_KEY="your_key"
$env:TAVILY_API_KEY="your_key"
```

5. **Run the agent**

```bash
# Hacker News (default)
python agent/main.py

# Or choose a preset / RSS source
python agent/main.py --source techcrunch
```

6. **View the site**

```bash
npm run dev
```

Open `http://localhost:4321`.

---

### Option B: Run Your Own Fork (Free Cloud Hosting)

1. Fork the repo
2. Add GitHub Actions secrets:

* `TAVILY_API_KEY`
* and either `GOOGLE_API_KEY` or `GEMINI_API_KEY`

3. Enable workflows in the Actions tab
4. Deploy the frontend on Vercel (import the repo)
5. Done — it runs every morning at **8:00 AM PST**

**Artifacts:** Each run commits a new markdown file to `src/content/news/` and uploads `run_report.json` for debugging.

---

## 🧰 Supported Sources & Requirements

The agent supports presets and also accepts any **raw RSS URL** via `--source`.

Presets:

* `hackernews` (default)
* `techcrunch`
* `theverge`
* `wired`
* `nytimes` (Technology section)
* `wsj` (Tech section)

**Important notes**

1. **Paywalls:** NYT/WSJ may be skipped frequently if Tavily can’t retrieve readable article text. These are best-effort presets.
2. **Public access:** Custom RSS sources should not be behind strict paywalls.
3. **Standard RSS/Atom:** Feeds should use standard `<item><link>...</link></item>` structure.
4. **Text-first works best:** Video/image-heavy sources may fail the “insufficient context” gate.

---

## 🧠 Engineering Decisions & Tradeoffs

### 1) Strict Grounding vs. Best Guess

* **Decision:** Use a primary citation target plus an allowlisted citation set derived from retrieval results.
* **Tradeoff:** Legitimate stories can be skipped if Tavily can’t retrieve enough readable source text.
* **Why:** Zero hallucinations > maximum coverage.

### 2) Process-Based Timeouts

* **Challenge:** `yfinance` can stall on network/API issues, and Python threads can’t be force-killed safely.
* **Solution:** Wrap the fetch in `multiprocessing` and terminate the subprocess after 3 seconds.
* **Benefit:** The pipeline can’t freeze indefinitely.

### 3) Git as a Database (Flat-File CMS)

* **Decision:** Store briefings as Markdown committed to the repo.
* **Tradeoff:** Repo size grows over time.
* **Why:** Minimal infrastructure, simple deploy, and an auditable history of published content.

---

## 🐛 Challenges Faced

1. **Trailing punctuation after citations**

* **Problem:** The model sometimes produced `[Source](url).` and strict validation rejected it.
* **Solution:** Kept validation strict and solved it via prompt constraints (explicitly forbidding trailing punctuation after citations).

2. **Windows multiprocessing vs. Linux CI**

* **Problem:** Windows uses `spawn` (fresh interpreter) while Linux CI often uses `fork`, so behavior and performance differ.
* **Solution:** Standardized on `multiprocessing` for hard-kill guarantees and documented Windows setup expectations.

3. **Dependency drift**

* **Problem:** Rapid ecosystem changes can break integrations.
* **Solution:** Pinned dependencies to compatible version ranges.

---

## 🔮 Future Work

* **Event timeline view:** Show how topics evolve across days using the Markdown archive.
* **Multi-agent debate:** Draft writer + adversarial critic before publishing.
* **Local knowledge base:** Use embeddings over historical briefings to add “what changed since last time” context.

---

## 🤝 Acknowledgements

AI tools were used to critique architecture, accelerate implementation, and debug tricky integration issues (notably multiprocessing behavior and citation validation). Final code structure and architectural decisions were reviewed and validated by me.

---

## 📜 License

MIT License. Free to use, learn from, and modify.

```
::contentReference[oaicite:0]{index=0}
```
