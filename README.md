# 🤖 Autonomous AI News Analyst

![AI Analyst](https://img.shields.io/github/actions/workflow/status/HeroicSpider/ai-news-analyst/daily.yml?label=Daily%20Briefing)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Astro](https://img.shields.io/badge/astro-4.0-orange)

An intelligent, autonomous agent that acts as a daily tech journalist. It scouts for trending stories, researches them using live web search, verifies facts, and publishes a daily briefing—completely without human intervention.

[**View Live Demo**](https://ai-news-analyst-sable.vercel.app/)

---

## 📖 The "Why"

This project was built as a proof of concept for a **Founding AI Product Engineer** role. The challenge was simple: "Build a website that summarizes the hottest tech news."

However, instead of building a simple wrapper around an LLM that just summarizes headlines, I wanted to demonstrate a production-grade **Agentic Workflow** that behaves like a real investigative reporter:

1.  **Skeptical:** It assumes headlines are misleading until proven otherwise.
2.  **Grounded:** It cannot write a bullet point unless it has a URL citation to back it up.
3.  **Autonomous:** It runs, retries, and publishes entirely on its own infrastructure.

---

## 🛠️ Architecture

This system uses a **Retrieval-Augmented Generation (RAG)** pipeline orchestrated by Python and GitHub Actions.

1.  **The Scout (Signal):**
    * Queries **Hacker News API** or **RSS Feeds** (TechCrunch, Wired, etc.).
    * Applies a custom **Hotness Algorithm**: `Score = (1 / Rank) * e^(-AgeHours / 24)`. This prioritizes breaking news over stale "top" posts.

2.  **The Researcher (Enrichment):**
    * Uses **Tavily API** to perform a live web search for each headline.
    * Extracts context, primary sources, and diverse viewpoints.
    * **Financial Data:** If specific major tech companies (e.g., NVIDIA, Tesla, Apple, Google, Microsoft, Amazon, Meta) are mentioned, it spins up a process to fetch real-time stock data via `yfinance`. This feature uses a strictly scoped **ticker allowlist** to ensure data quality.

3.  **The Editor (Validation Gate):**
    * This is the core innovation. A regex-based "Critic" reviews the AI's draft.
    * **Rule:** Every bullet point *must* end with a valid `[Source](URL)` citation.
    * **Strict Grounding:** The URL must be present in the search results. If the AI hallucinates a link or cites a source it didn't read, the draft is rejected and the agent retries.

4.  **The Publisher (Frontend):**
    * The approved report is saved as a Markdown file.
    * **Astro** (a static site generator) detects the new file and builds a blazing-fast HTML dashboard.

---

## 🚀 How to Run It

### Option A: Run Locally

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/HeroicSpider/ai-news-analyst.git
    cd ai-news-analyst
    ```

2.  **Set Up the Backend (Python)**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
    pip install -r agent/requirements.txt
    ```

3.  **Set Up the Frontend (Node.js)**
    ```bash
    npm install
    ```

4.  **Configure API Keys**
    You need free keys from [Google AI Studio](https://aistudio.google.com/) and [Tavily](https://tavily.com/). You can use either `GOOGLE_API_KEY` or `GEMINI_API_KEY`.

    ```bash
    # Linux/Mac
    export GOOGLE_API_KEY="your_key"
    export TAVILY_API_KEY="your_key"

    # Windows (PowerShell)
    $env:GOOGLE_API_KEY="your_key"
    $env:TAVILY_API_KEY="your_key"
    ```

5.  **Run the Agent**
    ```bash
    # Run for Hacker News (Default)
    python agent/main.py

    # OR Run for specific sources
    python agent/main.py --source techcrunch
    ```

6.  **View the Website**
    ```bash
    npm run dev
    ```
    Open `http://localhost:4321` to see your generated news.

### Option B: Run Your Own Fork (Free Cloud Hosting)

You can have your own personal news analyst running for free in 5 minutes.

1.  **Fork this Repository** (Click "Fork" in the top right).
2.  **Add Secrets:** Go to `Settings > Secrets and variables > Actions`. Add `TAVILY_API_KEY` and either `GOOGLE_API_KEY` or `GEMINI_API_KEY`.
3.  **Enable Workflows:** Go to the `Actions` tab and enable workflows.
4.  **Deploy Frontend:** Go to [Vercel](https://vercel.com), import your forked repo, and hit Deploy.
5.  **Done:** Your agent will now run every morning at 8:00 AM PST automatically.

**Note on artifacts:** The workflow commits a new markdown file to `src/content/news/` and uploads a `run_report.json` build artifact for debugging.

---

## 🧰 Supported Sources & Requirements

The agent includes built-in support for these presets, but you can also provide any **raw RSS URL** via the `--source` argument.

* `hackernews` (Default)
* `techcrunch`
* `theverge`
* `wired`
* `nytimes` (Technology section)
* `wsj` (Tech section)

**⚠️ Important:**
1.  **Paywalls:** Sources like WSJ or NYT may often result in skipped stories if the article text cannot be retrieved by Tavily. They are included as best-effort presets.
2.  **Publicly Accessible:** Custom RSS sources must not be behind a strict paywall.
3.  **Standard Formats:** Feeds must adhere to standard RSS/Atom XML formats.
4.  **Content Type:** The agent works best on text-based journalism.

---

## 🧠 Engineering Decisions & Tradeoffs

### 1) Strict Grounding vs. Best Guess
- **Decision:** Use a primary citation target plus an allowlisted citation set derived from retrieval results.
- **Tradeoff:** Legitimate stories can be skipped if Tavily can’t retrieve enough readable source text.
- **Why:** Zero hallucinations > maximum coverage.

### 2) Process-Based Timeouts
- **Challenge:** `yfinance` can stall on network/API issues, and Python threads can’t be force-killed safely.
- **Solution:** Wrap the fetch in `multiprocessing` and terminate the subprocess after 3 seconds.
- **Benefit:** The pipeline can’t freeze indefinitely.

### 3) Git as a Database (Flat-File CMS)
- **Decision:** Store briefings as Markdown committed to the repo.
- **Tradeoff:** Repo size grows over time.
- **Why:** Minimal infrastructure, simple deploy, and an auditable history of published content.


---

## 🐛 Challenges Faced

Building an autonomous agent isn't just about stringing APIs together. Here are the real-world problems I encountered and solved:

1.  **The "Trailing Period" Hallucination:**
    * *Problem:* The AI would frequently write perfect summaries but end them with `[Source](url).` (note the period). My strict regex validator rejected these because strict Markdown parsing failed on the trailing character.
    * *Solution:* Instead of weakening the code validator, I solved this via **Prompt Engineering**. I explicitly instructed the model in the System Prompt: *"DO NOT add a trailing period after the citation."* This solved the issue while keeping the validation logic tight.

2.  **Windows Multiprocessing vs. CI/CD:**
    * *Problem:* On Windows, `multiprocessing` spawns a fresh process that re-imports the environment, which behaves differently than the `fork` method used on Linux servers.
    * *Solution:* I standardized on `multiprocessing` for its hard-kill capabilities but documented specific execution requirements for Windows users to ensure environment variables are loaded correctly.

---

## 🔮 Future Work

This project is a Proof of Concept (PoC) that serves as a foundation. Here is what I would build next:

* **Event timeline view:** Render a timeline per topic across days using the markdown archive to visualize how a story evolves.
* **Multi-Agent Debate:** Have one agent write the story and a second agent (The "Critic") try to find flaws in it before publishing.
* **Vector Database:** Instead of searching the live web every time, build a knowledge base of past stories to link current events to historical context.

---

## 🤝 Acknowledgements

I utilized AI tools to critique my architectural ideas, accelerate development, and assist in debugging complex integration issues (especially around cross-platform multiprocessing and regex validation). All final code structure and architectural decisions were validated by me.

---

## 📜 License

MIT License. Free to use, learn from, and modify.
