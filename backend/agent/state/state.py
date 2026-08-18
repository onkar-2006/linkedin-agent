from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class AgentState(BaseModel):
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    draft_content: Optional[str] = None
    image_url: Optional[str] = None
    image_prompt: Optional[str] = None
    research_results: List[str] = Field(default_factory=list)
    thinking_log: List[str] = Field(default_factory=list)
    approval_status: str = "pending" # pending, approved, revision_requested
    image_needed: str = "pending"    # pending, yes, no
    image_approved: str = "pending"  # pending, yes, no
    post_mode: str = "pending"       # pending, immediate, scheduled
    post_confirmed: str = "pending"  # pending, yes, no
    scheduled_time: Optional[str] = None
    posting_result: Optional[str] = None
    intent: str = "pending"
    chitchat_response: Optional[str] = None
