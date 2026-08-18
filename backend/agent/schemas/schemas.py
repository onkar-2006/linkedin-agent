from pydantic import BaseModel
from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    state_update: Optional[Dict[str, Any]] = None

class ImageRequest(BaseModel):
    message_id: int
    draft_text: str

class PublishRequest(BaseModel):
    text: str
    image_url: Optional[str] = None

class ScheduleRequest(BaseModel):
    text: str
    publish_time: str # ISO 8601 timestamp
    image_url: Optional[str] = None
