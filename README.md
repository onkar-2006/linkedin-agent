# LinkedIn Agent Post Scheduler 🚀

An AI-driven LinkedIn post generation and scheduling platform. Research trending topics, write engaging copywriting drafts, attach visual graphics, and schedule or publish posts to your real LinkedIn feed in one dashboard.

---

## 🛠 Tech Stack
* **Frontend**: React (Vite) + Tailwind CSS + Lucide Icons.
* **Backend**: FastAPI (Python) + LangGraph state-workflow + FastMCP LinkedIn server.
* **Agent Integration**: Tavily Search API + Gemini / OpenAI Chat Models.
* **Database**: SQLite.

---

## ⚡ Quick Start

### 1. Prerequisites
* Install [Docker & Docker Compose](https://docs.docker.com/get-docker/) (for containerized setup).
* Or run locally using Python 3.11+ and Node.js 18+.

### 2. Configure Environment Variables
Copy `.env.example` to `.env` in the root directory and configure:
```ini
# Tavily API Key for real-time web search
TAVILY_API_KEY=your_tavily_key

# Select either OpenAI or Gemini (Gemini is preferred if both are set)
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key

# Real LinkedIn posting credentials
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8000/api/auth/linkedin/callback
```

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
From the root directory, start the services in one command:
```bash
docker-compose up --build
```
* **Frontend**: `http://localhost:3000`
* **Backend API**: `http://localhost:8000`

### Option B: Run Locally (Development)

#### Start FastMCP and Backend API:
```bash
cd backend
# Create and activate virtual environment, install requirements:
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

## 🚀 Deployment Guide
You can deploy this containerized app to any cloud provider:

### Deploy to Render or Railway:
1. Link your GitHub repository containing this codebase.
2. Create two services:
   * **Web Service for Backend** pointing to `./backend/Dockerfile` (Expose port `8000`).
   * **Web Service for Frontend** pointing to `./frontend/Dockerfile` (Expose port `80`).
3. Set your Environment Variables in the backend settings (from your `.env`).
4. Set the `LINKEDIN_REDIRECT_URI` to `https://your-backend-domain.com/api/auth/linkedin/callback`.
