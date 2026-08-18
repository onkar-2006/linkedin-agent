import os
import uuid
import time
import httpx
import logging
import asyncio
import threading
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Setup Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main_api")

# Initialize FastAPI App
app = FastAPI(title="LinkedIn Agent Scheduler Backend")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import Database, workflow tools, and Schemas
from database import DatabaseManager
db = DatabaseManager()

from agent.workflow.workflow import agent_graph
import fastmcp_linkedin

from agent.schemas.schemas import ChatRequest, ImageRequest, PublishRequest, ScheduleRequest

# --- Background Scheduler for Scheduled Posts ---
def run_post_scheduler():
    """Background worker thread that runs every 10 seconds checking for scheduled posts to publish."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            posts = db.get_posts()
            now_str = datetime.utcnow().isoformat()
            
            for post in posts:
                if post['status'] == 'scheduled' and post['scheduled_time']:
                    # Compare times
                    scheduled = post['scheduled_time']
                    if scheduled.endswith('Z'):
                        scheduled = scheduled[:-1]
                    if scheduled <= now_str:
                        logger.info(f"Scheduled post ID {post['id']} is due! Publishing...")
                        db.update_post(post['id'], status='publishing')
                        
                        result = fastmcp_linkedin.publish_post(
                            text=post['content'],
                            image_url=post['image_url']
                        )
                        logger.info(f"Scheduler publish result: {result}")
                        
                        if "[Real LinkedIn] Post successfully published" in result:
                            urn = None
                            if "URN:" in result:
                                urn = result.split("URN:")[-1].strip()
                            db.update_post(post['id'], status='published', linkedin_urn=urn)
                        else:
                            db.update_post(post['id'], status='failed')
                            
        except Exception as e:
            logger.error(f"Error in scheduled post runner: {e}", exc_info=True)
        time.sleep(10)


# Start scheduler thread
scheduler_thread = threading.Thread(target=run_post_scheduler, daemon=True)
scheduler_thread.start()

logger.info("Background post scheduler thread started.")

# Register Modular API Routes
from endpoints.api import router as api_router
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
