# 🤖 Autonomous AI News Analyst

![AI Analyst](https://github.com/HeroicSpider/ai-news-analyst.git)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Astro](https://img.shields.io/badge/astro-4.0-orange)

An intelligent, autonomous agent that acts as a 24/7 tech journalist. It scouts for trending stories, researches them using live web search, verifies facts, and publishes a daily briefing—completely without human intervention.

**[View Live Demo](https://ai-news-analyst-sable.vercel.app/?_vercel_share=4Xb9Er7toU4eL48KvWsS2gD2cMX4ABL7)** *(Replace with your Vercel URL)*

---

## 📖 The "Why"

Most "AI News" bots are just summarizers—they read a headline and hallucinate the rest. I wanted to build an **Agentic Workflow** that behaves like a real investigative reporter:
1.  **Skeptical:** It assumes headlines are misleading until proven otherwise.
2.  **Grounded:** It cannot write a sentence unless it has a URL citation to back it up.
3.  **Autonomous:** It runs, heals, and publishes entirely on its own infrastructure.

---

## 🛠️ Architecture

This system uses a **Retrieval-Augmented Generation (RAG)** pipeline orchestrated by Python and GitHub Actions.

![Architecture Diagram](https://via.placeholder.com/800x400?text=Autonomous+AI+Pipeline+Diagram)

1.  **The Scout (Signal):**
    * Queries **Hacker News API** or **RSS Feeds** (TechCrunch, Wired).
    * Applies a custom **Hotness Algorithm**: `Score = (1 / Rank) * e^(-AgeHours / 24)`. This prioritizes breaking news over stale "top" posts.

2.  **The Researcher (Enrichment):**
    * Uses **Tavily API** to perform a live web search for each headline.
    * Extracts context, primary sources, and diverse viewpoints.
    * **Financial Data:** If a public company is mentioned, it spins up a process to fetch real-time stock data via `yfinance`.

3.  **The Editor (Validation Gate):**
    * This is the core innovation. A regex-based "Critic" reviews the AI's draft.
    * **Rule:** Every bullet point *must* end with a valid `[Source](URL)` citation.
    * **Strict Grounding:** The URL must be present in the search results. If the AI hallucinates a link, the draft is rejected and the agent retries.

4.  **The Publisher (Frontend):**
    * The approved report is saved as a Markdown file.
    * **Astro** (a static site generator) detects the new file and builds a blazing-fast HTML dashboard.

---

## 🚀 How to Run It

### Option A: Run Locally

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/ai-news-analyst.git](https://github.com/YOUR_USERNAME/ai-news-analyst.git)
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
    You need free keys from [Google AI Studio](https://aistudio.google.com/) and [Tavily](https://tavily.com/).
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
    python agent/main.py
    # Or specify a source:
    python agent/main.py --source techcrunch
    ```

6.  **View the Website**
    ```bash
    npm run dev
    ```
    Open `http://localhost:4321` to see your generated news.

---

### Option B: Run Your Own Fork (Free Cloud Hosting)

You can have your own personal news analyst running for free in 5 minutes.

1.  **Fork this Repository** (Click "Fork" in the top right).
2.  **Add Secrets:** Go to `Settings > Secrets and variables > Actions` and add `GOOGLE_API_KEY` and `TAVILY_API_KEY`.
3.  **Enable Workflows:** Go to the `Actions` tab and enable workflows.
4.  **Deploy Frontend:** Go to [Vercel](https://vercel.com), import your forked repo, and hit Deploy.
5.  **Done:** Your agent will now run every morning at 8:00 AM PST automatically.

---

## 🧠 Engineering Decisions & Tradeoffs

During development, several critical architectural choices were made to ensure robustness.

### 1. **"Strict Grounding" vs. "Best Guess"**
* **Decision:** I implemented a "Primary Citation Target" logic. The AI is explicitly told *which* URL is the primary source.
* **Tradeoff:** Sometimes legitimate news is skipped if the search tool (Tavily) can't find the exact article text.
* **Why:** I prioritized **zero hallucinations** over 100% coverage. It is better to skip a story than to lie about it.

### 2. **Process-Based Timeouts (Windows Compatibility)**
* **Challenge:** The financial data fetcher (`yfinance`) could hang indefinitely on network issues. Standard Python threads cannot be forcibly killed.
* **Solution:** I used `multiprocessing` to wrap the API call. If it takes longer than 3 seconds, the OS kills the entire subprocess.
* **Benefit:** This guarantees the pipeline *never* freezes, even on a cheap server.

### 3. **Git as a Database (Flat-File CMS)**
* **Decision:** Instead of a Postgres database, I save news as Markdown files in the repo.
* **Tradeoff:** The repository size grows over time (slowly).
* **Why:** It simplifies the stack to **zero**. No database to pay for, no connection strings to manage, and perfect version history for every edit the AI makes.

### 4. **Astro vs. React/Next.js**
* **Decision:** I used Astro for the frontend.
* **Why:** Astro builds **Static HTML**. Since the news only updates once a day, using a dynamic framework like React would be overkill and slower for users. Astro gives us 100/100 Lighthouse performance scores out of the box.

---

## 🐛 Challenges Faced

Building an autonomous agent isn't just about stringing APIs together. Here are the real-world problems I encountered and solved:

1.  **The "Trailing Period" Hallucination:**
    * *Problem:* The AI would write perfect summaries but end them with `[Source](url).` (note the period). My strict regex validator rejected these as "hallucinated links" because the period wasn't part of the URL.
    * *Solution:* I rewrote the validator to "hunt" for the last Markdown link in the text, ignoring trailing punctuation, rather than relying on exact string matching.

2.  **Windows Multiprocessing Deadlocks:**
    * *Problem:* On Windows, `multiprocessing` spawns a fresh process that re-imports the entire environment. This was causing the financial data fetcher to time out immediately because it took 2 seconds just to load the library.
    * *Solution:* I implemented a dual-strategy: lightweight `ThreadPoolExecutor` for Windows/Local development (fast startup) and strict `multiprocessing` for Linux/Production environments (hard kill capability).

3.  **Dependency Drift:**
    * *Problem:* The AI ecosystem moves fast. The code initially broke because `langchain` updated its Google Gemini integration overnight.
    * *Solution:* I locked down the dependencies with strict version pinning (e.g., `langchain-google-genai>=4.2.0,<5.0.0`) to ensure the agent doesn't wake up broken one morning.

---

## 🔮 Future Work

This project is a Proof of Concept (PoC) that serves as a foundation. Here is what I would build next:

* **Human-in-the-Loop:** Add a step where the agent posts a draft to Slack/Discord for me to approve before publishing.
* **Multi-Agent Debate:** Have one agent write the story and a second agent (The "Critic") try to find flaws in it before publishing.
* **Vector Database:** Instead of searching the live web every time, build a knowledge base of past stories to link current events to historical context (e.g., "This is the 3rd antitrust lawsuit against Google this year").

---

## 📜 License

MIT License. Free to use, learn from, and modify.
