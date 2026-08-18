import os
import uuid
import logging
import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import RedirectResponse as HTMLRedirect

# Import Database, workflow tools, and Schemas
from database import DatabaseManager
db = DatabaseManager()

from agent.workflow.workflow import agent_graph
import fastmcp_linkedin

from agent.schemas.schemas import ChatRequest, ImageRequest, PublishRequest, ScheduleRequest

logger = logging.getLogger("main_api.endpoints")

router = APIRouter()

# --- Chat Agent Endpoint ---
@router.post("/api/chat")
async def chat_endpoint(req: ChatRequest, x_user_urn: Optional[str] = Header(None)):
    """
    Initiates or resumes chat with the stateful agent.
    Runs LangGraph workflow and saves state transitions.
    """
    conversation_id = req.conversation_id or str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": conversation_id},
        "metadata": {"conversation_id": conversation_id},
        "tags": [conversation_id]
    }
    
    # 1. Update the graph state if updates were sent (e.g. user approval buttons clicked)
    if req.state_update:
        if x_user_urn:
            req.state_update["user_urn"] = x_user_urn
        agent_graph.update_state(config, req.state_update)
        logger.info(f"Updated state for thread {conversation_id} with: {req.state_update}")
        
    # 2. Save user message to database if provided
    if req.message:
        db.add_message(conversation_id, "user", req.message, user_urn=x_user_urn)
        # Update conversation title
        title = req.message[:35] + "..." if len(req.message) > 35 else req.message
        db.create_conversation(conversation_id, title, user_urn=x_user_urn)
        
        # Merge message into graph memory
        state = agent_graph.get_state(config)
        messages = list(state.values.get("messages", []))
        messages.append({"role": "user", "content": req.message})
        agent_graph.update_state(config, {"messages": messages})

    try:
        # 3. Determine if we are starting new or resuming from interrupt
        state = agent_graph.get_state(config)
        if state.next:
            logger.info(f"Resuming thread {conversation_id} at node(s): {state.next}")
            result_state = agent_graph.invoke(None, config=config)
        else:
            logger.info(f"Starting new workflow run for thread {conversation_id}")
            initial_messages = [{"role": "user", "content": req.message}] if req.message else []
            result_state = agent_graph.invoke({"messages": initial_messages}, config=config)
            
        # Get latest state values
        draft = result_state.get("draft_content", "")
        thinking = "\n".join(result_state.get("thinking_log", []))
        image_url = result_state.get("image_url")
        
        # 4. Save agent response to database
        # Fetch updated state info first to determine status
        updated_state = agent_graph.get_state(config)
        
        if updated_state.values.get("intent") == "chitchat":
            status_msg = updated_state.values.get("chitchat_response") or "Hello! How can I help you today?"
        else:
            status_msg = "I have compiled a professional draft post. Please review the details in the workspace panel on the right."
            if updated_state.values.get("posting_result"):
                status_msg = f"Operation complete: {updated_state.values.get('posting_result')}"
            elif updated_state.values.get("post_mode") == "scheduled":
                status_msg = f"Post successfully scheduled for {updated_state.values.get('scheduled_time')}."
        
        db.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=status_msg,
            thinking=thinking,
            image_url=image_url,
            user_urn=x_user_urn
        )
        
        # 5. Fetch updated state info to return to frontend
        updated_state = agent_graph.get_state(config)
        
        return {
            "conversation_id": conversation_id,
            "draft": draft,
            "thinking": thinking,
            "image_url": image_url,
            "graph_state": {
                "draft_content": updated_state.values.get("draft_content"),
                "image_url": updated_state.values.get("image_url"),
                "approval_status": updated_state.values.get("approval_status", "pending"),
                "image_needed": updated_state.values.get("image_needed", "pending"),
                "image_approved": updated_state.values.get("image_approved", "pending"),
                "post_mode": updated_state.values.get("post_mode", "pending"),
                "post_confirmed": updated_state.values.get("post_confirmed", "pending"),
                "posting_result": updated_state.values.get("posting_result"),
                "next": updated_state.next
            }
        }
    except Exception as e:
        logger.error(f"Agent graph execution failed: {e}", exc_info=True)
        err_msg = f"Failed to generate draft. Error: {e}"
        db.add_message(conversation_id, "assistant", err_msg, thinking="Workflow crashed.")
        return {
            "conversation_id": conversation_id,
            "draft": err_msg,
            "thinking": "Workflow execution error."
        }

@router.post("/api/agent/generate-image")
async def generate_image_endpoint(req: ImageRequest):
    """
    Uses the agent graph image node to generate an image matching a draft post.
    """
    try:
        from agent.nodes.node import WorkflowNodes
        nodes = WorkflowNodes()
        
        # Invoke image generation node with temporary state
        res = nodes.generate_image({"draft_content": req.draft_text})
        
        image_url = res.get("image_url")
        image_prompt = res.get("image_prompt")
        
        # Update message in database
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_messages SET image_url = ?, thinking = thinking || ? WHERE id = ?",
                (image_url, f"\nGenerated visual image matching draft: {image_prompt}", req.message_id)
            )
            conn.commit()
            
        return {
            "image_url": image_url,
            "image_prompt": image_prompt
        }
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Post Management Endpoints ---
@router.get("/api/posts")
async def get_posts(x_user_urn: Optional[str] = Header(None)):
    return db.get_posts(user_urn=x_user_urn)
 
@router.delete("/api/posts/{post_id}")
async def delete_post_endpoint(post_id: int):
    result = fastmcp_linkedin.delete_post(post_id)
    if "not found" in result:
        raise HTTPException(status_code=404, detail=result)
    return {"status": "success", "message": result}
 
@router.post("/api/posts/publish")
async def publish_now_endpoint(req: PublishRequest, x_user_urn: Optional[str] = Header(None)):
    result = fastmcp_linkedin.publish_post(text=req.text, image_url=req.image_url, user_urn=x_user_urn)
    return {"status": "success", "message": result}
 
@router.post("/api/posts/schedule")
async def schedule_endpoint(req: ScheduleRequest, x_user_urn: Optional[str] = Header(None)):
    result = fastmcp_linkedin.schedule_post(
        text=req.text,
        publish_time=req.publish_time,
        image_url=req.image_url,
        user_urn=x_user_urn
    )
    if "Error" in result:
        raise HTTPException(status_code=400, detail=result)
    return {"status": "success", "message": result}
 
# --- Conversations History Endpoints ---
@router.get("/api/conversations")
async def list_conversations(x_user_urn: Optional[str] = Header(None)):
    return db.get_conversations(user_urn=x_user_urn)

@router.get("/api/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    messages = db.get_messages(conversation_id)
    config = {"configurable": {"thread_id": conversation_id}}
    state = agent_graph.get_state(config)
    
    return {
        "messages": messages,
        "graph_state": {
            "draft_content": state.values.get("draft_content"),
            "image_url": state.values.get("image_url"),
            "approval_status": state.values.get("approval_status", "pending"),
            "image_needed": state.values.get("image_needed", "pending"),
            "image_approved": state.values.get("image_approved", "pending"),
            "post_mode": state.values.get("post_mode", "pending"),
            "post_confirmed": state.values.get("post_confirmed", "pending"),
            "posting_result": state.values.get("posting_result"),
            "next": state.next
        }
    }

@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str):
    success = db.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"status": "success"}

# --- LinkedIn OAuth Endpoints ---
@router.get("/api/auth/linkedin")
async def linkedin_auth_url():
    """Generates LinkedIn OAuth authorization link."""
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
    
    if not client_id or not redirect_uri:
        # Fallback to local sandbox mock auth URL!
        return {"url": "http://localhost:8000/api/auth/linkedin/mock"}
        
    state = str(uuid.uuid4())
    url = (
        f"https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
        f"&state={state}&scope=openid%20profile%20w_member_social%20email"
    )
    return {"url": url}

@router.get("/api/auth/linkedin/mock")
async def linkedin_mock_auth():
    """Mocks LinkedIn login and automatically saves mock credentials for local testing."""
    mock_urn = "urn:li:person:mock_user_john_doe"
    db.save_credentials(
        access_token="mock_access_token_12345",
        expires_at=int(datetime.utcnow().timestamp()) + 3600 * 24 * 30, # 30 days
        member_urn=mock_urn,
        first_name="John Doe",
        last_name="(Demo)",
        profile_picture="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=256"
    )
    frontend_url = os.getenv("FRONTEND_REDIRECT", "http://localhost:5173")
    import urllib.parse
    query = urllib.parse.urlencode({
        "auth": "success",
        "urn": mock_urn,
        "first_name": "John Doe",
        "last_name": "(Demo)",
        "picture": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=256"
    })
    return HTMLRedirect(f"{frontend_url}?{query}")


@router.get("/api/auth/linkedin/callback")
async def linkedin_callback(code: str, state: str):
    """Receives callback authorization code, requests access token, and saves it."""
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
    
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(status_code=400, detail="LinkedIn credentials missing.")
        
    try:
        # Exchange code for Access Token
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=data, timeout=15)
            if token_response.status_code != 200:
                logger.error(f"Token exchange error: {token_response.text}")
                raise HTTPException(status_code=400, detail=f"Failed token exchange: {token_response.text}")
                
            token_data = token_response.json()
            access_token = token_data["access_token"]
            expires_in = token_data["expires_in"]
            expires_at = int(datetime.utcnow().timestamp()) + expires_in
            
            userinfo_url = "https://api.linkedin.com/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = await client.get(userinfo_url, headers=headers, timeout=15)
            
            first_name = ""
            last_name = ""
            member_urn = "urn:li:person:unknown"
            profile_picture = None
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                member_urn = f"urn:li:person:{user_data.get('sub')}"
                first_name = user_data.get("given_name", "")
                last_name = user_data.get("family_name", "")
                profile_picture = user_data.get("picture", "")
            else:
                logger.warning(f"Could not retrieve user info: {user_response.text}.")
                
            db.save_credentials(
                access_token=access_token,
                expires_at=expires_at,
                member_urn=member_urn,
                first_name=first_name,
                last_name=last_name,
                profile_picture=profile_picture
            )
            
            frontend_url = os.getenv("FRONTEND_REDIRECT", "http://localhost:5173")
            import urllib.parse
            query = urllib.parse.urlencode({
                "auth": "success",
                "urn": member_urn,
                "first_name": first_name,
                "last_name": last_name,
                "picture": profile_picture or ""
            })
            return HTMLRedirect(f"{frontend_url}?{query}")
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
 
 
@router.get("/api/auth/linkedin/status")
async def linkedin_status(x_user_urn: Optional[str] = Header(None)):
    """Returns connected profile status info for a user."""
    creds = db.get_credentials(x_user_urn)
    if not creds:
        return {"connected": False}
        
    expired = creds['expires_at'] < int(datetime.utcnow().timestamp())
    if expired:
        db.clear_credentials(x_user_urn)
        return {"connected": False}
        
    return {
        "connected": True,
        "first_name": creds.get("first_name"),
        "last_name": creds.get("last_name"),
        "profile_picture": creds.get("profile_picture"),
        "member_urn": creds.get("member_urn")
    }
 
@router.post("/api/auth/linkedin/disconnect")
async def linkedin_disconnect(x_user_urn: Optional[str] = Header(None)):
    db.clear_credentials(x_user_urn)
    return {"status": "success"}
