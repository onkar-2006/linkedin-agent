# LinkedIn Autopilot Agent Scheduler 🚀

An AI-driven LinkedIn copywriting, graphic generation, and post scheduling dashboard. Research trending topics, draft engaging copy, generate premium visual assets, and schedule or publish posts to your real LinkedIn feed—all in one unified platform.

---

## ✨ Features
* **AI Research & Copywriter**: Integrates Tavily Search with Groq model fallbacks (prioritizing `openai/gpt-oss-120b`, and falling back to `groq/compound` or `qwen/qwen3.6-27b`) to draft engaging, value-oriented LinkedIn posts.
* **Human-in-the-Loop (HITL) Controls**: Pauses graph execution using LangGraph thread checkpointers to wait for user reviews on copywriting drafts, image choice, image approval, posting mode, and safety confirmations.
* **Flux Visual Graphic Generator**: Connects to the premium 12B parameter **Flux model** via Pollinations AI. Automatically enhances prompts and applies dynamic random seeding to generate high-fidelity vectors, clay 3D illustrations, or modern glassmorphic card graphics for free.
* **Autopilot Post Scheduler**: Runs a background worker daemon thread that checks SQLite every 10 seconds, automatically publishing posts to LinkedIn when their target scheduled release time is reached.
* **Stateful Split-Pane UI**: Left pane manages scrollable chat feeds, prompts, and collapsible agent reasoning logs; right pane provides a dedicated workspace for draft copywriting, bound graphic rendering, and workflow button controls.
* **Groq Key Rotation & Token Capping**: Auto-rotates multiple Groq API keys to bypass rate limits (429) and optimizes token counts by capping generations (`max_tokens=1000`) and compressing Tavily search payloads.
* **Sandbox / Mock Authorization Mode**: Falls back to a local sandbox test account (John Doe demo profile) when LinkedIn client IDs are omitted in the configuration.

---

## 🏗️ System Architecture

The following diagram illustrates how the **React Frontend**, **FastAPI Backend**, **LangGraph Workflow**, **SQLite database**, and external API providers communicate:

```mermaid
graph TD
    subgraph Client ["React Frontend UI"]
        UI["Split-Pane Dashboard"]
        WS["Workspace Panel"]
    end

    subgraph Server ["FastAPI Backend"]
        API["FastAPI Router"]
        Scheduler["Daemon Scheduler Thread"]
        MCP["FastMCP LinkedIn Server"]
    end

    subgraph Database ["SQLite DB"]
        SQL[("database.db")]
    end

    subgraph Agent ["LangGraph Engine"]
        LG["StateGraph Graph"]
        Saver["SQLite MemorySaver checkpointer"]
    end

    subgraph External ["External APIs"]
        Groq["Groq LLM Fallback Chain"]
        Tavily["Tavily Search API"]
        Pollinations["Pollinations AI Flux Generator"]
        LinkedIn["LinkedIn API Gateway"]
    end

    %% Vertical Interactions & Short Labels
    UI <-->|"Prompt & Render"| API
    WS -->|"HITL Actions"| API
    
    API <-->|"State & Interrupts"| LG
    API -->|"Save Logs"| SQL
    API -->|"Direct Publish"| MCP
    
    Scheduler -->|"Poll Due Posts"| SQL
    Scheduler -->|"Auto Publish"| MCP
    MCP -->|"Update Status"| SQL
    MCP -->|"Upload & Share"| LinkedIn
    
    LG -->|"Thread Save"| Saver
    LG -->|"Search Web"| Tavily
    LG -->|"Flux Image"| Pollinations
    LG -->|"Groq LLM"| Groq
```

---

## 🧠 LangGraph Workflow Architecture (HITL)

The core backend agent is built as a state machine using **LangGraph**. It utilizes conditional edges and `interrupt_after` blocks on user reviews to enable a true **Human-in-the-Loop (HITL)** experience:

```mermaid
graph TD
    Start["User Prompt"] --> classify_intent{"Classify Intent Node"}
    
    %% Intent Branching
    classify_intent -->|chitchat| respond_chitchat["Respond Chitchat Node"]
    classify_intent -->|post request| research_and_draft["Research & Copy Draft Node"]
    
    respond_chitchat --> End["END"]
    
    %% Research & Draft
    research_and_draft -->|Web search + LLM Copywrite| wait_draft_approval("WAIT: Draft Review Interrupt")
    
    %% HITL Draft review
    wait_draft_approval -->|Revision requested| research_and_draft
    wait_draft_approval -->|Approved| ask_image_option["Ask Graphic Option Node"]
    
    ask_image_option --> wait_image_choice("WAIT: Image Choice Interrupt")
    
    %% HITL Image Choice
    wait_image_choice -->|No / Text Only| posting_agent["Posting Agent Node"]
    wait_image_choice -->|Yes / Generate Image| generate_image["Generate Visual Graphic Node"]
    
    %% Image generation
    generate_image -->|Flux model prompt| wait_image_approval("WAIT: Image Review Interrupt")
    
    %% HITL Image Approval
    wait_image_approval -->|Regenerate Image| generate_image
    wait_image_approval -->|Approve & Proceed| posting_agent
    
    %% Posting Agent mode selection
    posting_agent -->|Final review & hashtags| wait_post_mode("WAIT: Post Mode Interrupt")
    
    %% HITL Post Mode
    wait_post_mode -->|Scheduled| schedule_action["Schedule Post Node"]
    wait_post_mode -->|Immediate| confirm_posting_prompt["Safety Confirm Node"]
    
    confirm_posting_prompt --> wait_post_confirmation("WAIT: Post Confirm Interrupt")
    
    %% HITL Publish confirm
    wait_post_confirmation -->|Cancel| END_POST["END"]
    wait_post_confirmation -->|Yes, Publish Now| publish_action["Publish Action Node"]
    
    publish_action --> End
    schedule_action --> End
```

### LangGraph Workflow Features:
1. **Thread Checkpointer (`MemorySaver`)**: Session history and node configurations are preserved between api calls. Resuming is as simple as calling `agent_graph.invoke(None, config=config)` after updating state.
2. **Dynamic Key Rotation**: If a Groq API key is rate-limited (`429 Too Many Requests`), the agent automatically rotates to fallback keys configured in `.env` to prevent crashes.
3. **Token Capping**:
   * Outbound generations are restricted using `max_tokens=1000`.
   * Input tokens are reduced by compressing Tavily search results to 3 items and truncating snippets to 400 characters max.

---

## 🛠️ Tech Stack
* **Frontend**: React (Vite) styled with Tailwind CSS v4 and Lucide icons.
* **Backend**: FastAPI (Python 3.10+) running async endpoints.
* **Orchestration**: LangGraph state machine.
* **AI Tool Integration**: Tavily Search (Web search) + Pollinations AI (Flux image generator) + Groq (LLM).
* **Database**: SQLite3.

---

## ⚡ Quick Start

### 1. Prerequisites
* Install [Docker & Docker Compose](https://docs.docker.com/get-docker/) (Recommended)
* Or run locally using Python 3.10+ and Node.js 18+.

### 2. Configure Environment Variables
Copy `.env.example` to `.env` in the root directory and configure:
```ini
# Tavily API Key for real-time web search
TAVILY_API_KEY=your_tavily_key

# Groq API Key and Fallbacks for model rotation
GROQ_API_KEY=your_primary_groq_key
GROQ_API_KEY_FALLBACK_1=your_fallback_groq_key_1
GROQ_API_KEY_FALLBACK_2=your_fallback_groq_key_2

# Real LinkedIn posting credentials
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8000/api/auth/linkedin/callback
```
*Note: If `LINKEDIN_CLIENT_ID` is left empty, the application automatically defaults to a sandbox mock login environment (John Doe profile) for local testing.*

### 3. Setting Up Real LinkedIn API Credentials
To enable real LinkedIn publishing:
1. Go to the [LinkedIn Developer Portal](https://www.linkedin.com/developers/) and sign in.
2. Click **Create App** and fill in your details.
3. In the app portal, go to the **Products** tab and request activation for:
   * **Share on LinkedIn**
   * **Sign In with LinkedIn (using OpenID Connect)**
4. In the **Auth** tab, retrieve your **Client ID** and **Client Secret**, and set the **Authorized Redirect URLs** to:
   * `http://localhost:8000/api/auth/linkedin/callback`
5. Place these values inside the `.env` file.

---

## 🐳 Running the Application

### Option A: Run with Docker (Recommended)
From the root directory, start both frontend and backend in one command:
```bash
docker-compose up --build
```
* **Frontend Dashboard**: `http://localhost:3000`
* **Backend Swagger API docs**: `http://localhost:8000/docs`

### Option B: Run Locally (Development)

#### Start FastAPI Backend & MCP Server:
```bash
cd backend
# Create and activate a virtual environment:
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install requirements:
pip install -r requirements.txt

# Run the FastAPI server:
python main.py
```

#### Start Vite Frontend:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🚀 Key Implementation Features
* **Upgraded Visual Assets**: Utilizes the premium 12B **Flux** model via Pollinations AI. Prompts are automatically enhanced to generate modern clay 3D renders, sleek dark mode vectors, or premium glassmorphic UI card designs.
* **Auto-Scheduler Worker**: The background daemon worker thread checks the SQLite database every 10 seconds. When a post's `scheduled_time` is reached, it publishes the post automatically to LinkedIn.
* **Binary Image Upload**: Supports uploading local/base64-encoded visual assets to LinkedIn via the binary image stream.

---

## 🌐 Deploy to Render (Blueprint Guide)

Render supports automated, multi-service deployment via the [`render.yaml`](file:///c:/Users/DELL/Desktop/assignment-linkedine/render.yaml) blueprint. 

### Step-by-Step Deployment:
1. **Push your code** to your GitHub repository.
2. Go to the [Render Dashboard](https://dashboard.render.com/) and click **New -> Blueprint**.
3. Select your repository and click **Connect**.
4. Render will read [`render.yaml`](file:///c:/Users/DELL/Desktop/assignment-linkedine/render.yaml), identify the services, and ask you for Environment Variables (like `TAVILY_API_KEY`, `GROQ_API_KEY`, etc.). Fill them in.
5. Click **Apply** to spin up the services.
6. Once the backend Web Service is live, copy its URL (e.g. `https://linkedin-autopilot-backend.onrender.com`).
7. Update the `VITE_API_BASE` environment variable in your **frontend Static Site settings** on Render to point to `${YOUR_BACKEND_URL}/api`, and trigger a manual redeploy.
8. Your full-stack platform is now live!

---

### ⚠️ Render Free Plan Limitations & Workarounds

If you deploy this application under Render's **Free Plan**, you must configure the following to ensure the application behaves correctly:

#### 1. Ephemeral Database Resets
* **Problem**: Render's Free tier does not support persistent disks. This means your SQLite database (`database.db`) is stored inside the container's temporary memory. Whenever the container restarts or redeploys, **all chat history, scheduled posts, and user credentials will be cleared.**
* **Solution**: For a 100% free setup with persistence, you can deploy the backend container to **Railway** (which supports free persistent volumes), or modify the backend to connect to a free external database like neon.tech or Supabase. Alternatively, upgrade the Render backend to a **Starter Web Service** ($5/month) and uncomment the `disk:` block in [`render.yaml`](file:///c:/Users/DELL/Desktop/assignment-linkedine/render.yaml#L27-L32) to mount a persistent disk volume.

#### 2. Keeping the Post Scheduler Active (Avoiding Server Sleep)
* **Problem**: Render puts Free web services to sleep after 15 minutes of inactivity. When the container sleeps, the background scheduler thread (`run_post_scheduler`) stops running, and **scheduled posts will not publish on time**.
* **Solution**: Create a free account on [UptimeRobot](https://uptimerobot.com/) or [Cron-Job.org](https://cron-job.org/) and set up an HTTP monitor that pings your backend status endpoint (`https://your-backend.onrender.com/api/auth/linkedin/status`) every **10 to 12 minutes**. This keep-alive ping keeps your backend active 24/7 for free, allowing the background scheduler to publish scheduled posts on time!


