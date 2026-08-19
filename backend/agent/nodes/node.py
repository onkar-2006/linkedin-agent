import os
import logging
from typing import Dict, Any, List, Optional
from langsmith import traceable
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from agent.tools.tools import web_search, generate_image
from agent.prompts.prompt import SYSTEM_DRAFT_PROMPT, SYSTEM_POST_PROMPT, IMAGE_PROMPT_GENERATOR_PROMPT, SYSTEM_CLASSIFIER_PROMPT, SYSTEM_CHITCHAT_PROMPT, SYSTEM_REVISION_PROMPT
import fastmcp_linkedin

logger = logging.getLogger("workflow_nodes")

def get_groq_llm():
    """Initializes the Groq LLM. Strictly requires GROQ_API_KEY."""
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key or groq_api_key.strip() == "":
        raise ValueError("GROQ_API_KEY is missing. Please set it in your backend .env file.")
        
    logger.info("Initializing Groq Chat LLM (groq/compound)...")
    return ChatGroq(
        model_name="groq/compound",
        groq_api_key=groq_api_key,
        temperature=0.7
    )

class WorkflowNodes:
    """
    OOP class containing LangGraph workflow nodes.
    Maintains LLM references and helper tools.
    """
    @traceable
    def classify_intent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifies user's intent into chitchat or post drafting.
        """
        logger.info("Executing Classify Intent Node...")
        if not isinstance(state, dict):
            state = state.dict()
        messages = state.get("messages", [])
        if not messages:
            return {"intent": "chitchat", "thinking_log": ["No messages found. Routing to chitchat."]}
            
        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if not last_user_message.strip():
            return {"intent": "chitchat", "thinking_log": ["Empty message. Routing to chitchat."]}
            
        raw_response = self._call_llm(SYSTEM_CLASSIFIER_PROMPT, f"User message: {last_user_message}").strip().lower()
        logger.info(f"Raw Classifier LLM Response: {raw_response}")
        
        # Strip thinking tags if reasoning model is used
        response = raw_response
        if "</think>" in raw_response:
            response = raw_response.split("</think>")[-1].strip()
        logger.info(f"Parsed Classifier LLM Response: {response}")
        
        intent = "post" if "post" in response else "chitchat"
        thinking = f"Classified user intent as: {intent.upper()}"
        return {
            "intent": intent,
            "thinking_log": state.get("thinking_log", []) + [thinking]
        }

    @traceable
    def respond_chitchat(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a friendly response for chitchat/greetings.
        """
        logger.info("Executing Respond Chitchat Node...")
        if not isinstance(state, dict):
            state = state.dict()
            
        messages = state.get("messages", [])
        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        
        response = self._call_llm(SYSTEM_CHITCHAT_PROMPT, f"User greeting: {last_user_message}")
        thinking = "Generated friendly chitchat response explaining capabilities."
        
        return {
            "chitchat_response": response,
            "thinking_log": state.get("thinking_log", []) + [thinking]
        }

    @traceable
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Invokes the Groq LLM to generate text with a robust key and model fallback chain."""
        primary_key = os.getenv("GROQ_API_KEY")
        fallback_1 = os.getenv("GROQ_API_KEY_FALLBACK_1")
        fallback_2 = os.getenv("GROQ_API_KEY_FALLBACK_2")

        # Gather keys dynamically from environment variables, avoiding duplicates
        keys = []
        if primary_key and primary_key.strip():
            keys.append(primary_key.strip())
        if fallback_1 and fallback_1.strip() and fallback_1.strip() not in keys:
            keys.append(fallback_1.strip())
        if fallback_2 and fallback_2.strip() and fallback_2.strip() not in keys:
            keys.append(fallback_2.strip())

        if not keys:
            raise ValueError("No Groq API keys available. Please configure GROQ_API_KEY in your backend .env file.")

        models = [
            "openai/gpt-oss-120b",
            "groq/compound",
            "groq/compound-mini",
            "qwen/qwen3.6-27b"
        ]

        messages = [
            HumanMessage(content=f"{system_prompt}\n\n{user_prompt}")
        ]

        last_error = None
        for model in models:
            for api_key in keys:
                try:
                    logger.info(f"Invoking Groq LLM using model: {model} with key starting with {api_key[:10]}...")
                    llm = ChatGroq(
                        model_name=model,
                        groq_api_key=api_key,
                        temperature=0.7,
                        max_tokens=1000
                    )
                    response = llm.invoke(messages)
                    return response.content
                except Exception as e:
                    logger.warning(f"Invocation failed for model {model} using key {api_key[:10]}: {e}. Trying next key/model fallback...")
                    last_error = e
                    continue

        if last_error is None:
            raise RuntimeError("All Groq models and keys failed to invoke, but no exception was captured.")
        raise last_error

    @traceable
    def research_and_draft(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Research & Draft Node: Takes the user's initial prompt (or revision request),
        performs web search (if initial) or revises draft, and resets routing variables.
        """
        logger.info("Executing Research & Draft Node...")
        if not isinstance(state, dict):
            state = state.dict()
        messages = state.get("messages", [])
        if not messages:
            return {"thinking_log": ["No messages found. Skipping research."]}
            
        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        current_draft = state.get("draft_content")
        
        if current_draft and current_draft.strip():
            # Revision Flow: Use existing draft and apply user changes
            thinking = f"Revising existing copy draft based on user feedback: '{last_user_message}'..."
            logger.info(thinking)
            search_result = "Skipped web search (Revision Flow)"
            
            user_prompt = f"Existing Draft:\n{current_draft}\n\nUser Revision Request:\n{last_user_message}"
            draft_thinking = "Applying user's changes to the existing draft."
            draft_raw = self._call_llm(SYSTEM_REVISION_PROMPT, user_prompt)
        else:
            # Initial Flow: Run web search and draft from scratch
            thinking = f"Analyzing prompt: '{last_user_message}' and initiating research search query..."
            logger.info(thinking)
            search_result = web_search.invoke(last_user_message)
            
            user_prompt = f"User request: {last_user_message}\n\nResearch Data:\n{search_result}"
            draft_thinking = "Writing the draft post. Structuring content with hook, body bullets, and CTA."
            draft_raw = self._call_llm(SYSTEM_DRAFT_PROMPT, user_prompt)
        
        import re
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", draft_raw, re.DOTALL | re.IGNORECASE)
        draft_match = re.search(r"<draft>(.*?)</draft>", draft_raw, re.DOTALL | re.IGNORECASE)
        
        thinking_text = thinking_match.group(1).strip() if thinking_match else draft_thinking
        
        if draft_match:
            draft_content = draft_match.group(1).strip()
        else:
            # Fallback if tags are missing
            draft_content = draft_raw
            cleaned_raw = draft_raw.replace("<thinking>", "").replace("</thinking>", "").replace("<draft>", "").replace("</draft>", "")
            if "thinking log:" in cleaned_raw.lower() or "thinking:" in cleaned_raw.lower():
                parts = cleaned_raw.split("\n\n", 1)
                if len(parts) > 1:
                    thinking_text = parts[0].replace("THINKING LOG:", "").replace("THINKING:", "").strip()
                    draft_content = parts[1].strip()
        
        return {
            "research_results": state.get("research_results", []) if current_draft else [search_result],
            "draft_content": draft_content,
            "thinking_log": state.get("thinking_log", []) + [thinking, thinking_text],
            # Reset workflow statuses for the new draft (and clear previous image visual references)
            "image_url": None,
            "image_prompt": None,
            "approval_status": "pending",
            "image_needed": "pending",
            "image_approved": "pending",
            "post_mode": "pending",
            "post_confirmed": "pending"
        }

    @traceable
    def ask_image_option(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ask Image Option Node: Prepares prompt asking user if they need an image.
        """
        logger.info("Executing Ask Image Option Node...")
        if not isinstance(state, dict):
            state = state.dict()
        thinking = "Prompting user for image choice (Yes/No)."
        return {
            "thinking_log": state.get("thinking_log", []) + [thinking],
            "image_needed": "pending"
        }

    @traceable
    def generate_image(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Image Generation Node: Creates a visual prompt based on the draft post,
        calls the image generator, and sets status to pending review.
        """
        logger.info("Executing Image Node...")
        if not isinstance(state, dict):
            state = state.dict()
        draft = state.get("draft_content", "")
        if not draft:
            raise ValueError("No draft content found. Image prompt generation aborted.")
            
        thinking = "Generating visual design prompt for the post..."
        image_prompt = self._call_llm(IMAGE_PROMPT_GENERATOR_PROMPT, f"Post draft:\n{draft}")
        
        thinking_2 = f"Invoking image generator with prompt: {image_prompt}"
        image_url = generate_image.invoke(image_prompt)
        
        return {
            "image_prompt": image_prompt,
            "image_url": image_url,
            "thinking_log": state.get("thinking_log", []) + [thinking, thinking_2],
            "image_approved": "pending"
        }

    @traceable
    def posting_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Posting Agent Node: Finalizes formatting, adds hashtags,
        and asks the user if they want to post immediately or schedule.
        """
        logger.info("Executing Posting Agent Node...")
        if not isinstance(state, dict):
            state = state.dict()
        draft = state.get("draft_content", "")
        
        # Apply final copywriting review and format using LLM
        finalized_post = self._call_llm(SYSTEM_POST_PROMPT, f"Raw Draft Post:\n{draft}")
        
        thinking = "Finalized drafting and optimized styling. Asking user for scheduling preferences."
        
        return {
            "draft_content": finalized_post,
            "thinking_log": state.get("thinking_log", []) + [thinking],
            "post_mode": "pending"
        }

    @traceable
    def confirm_posting_prompt(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Confirm Posting Node: Prompts user to confirm the immediate publish action.
        """
        logger.info("Executing Confirm Posting Prompt Node...")
        if not isinstance(state, dict):
            state = state.dict()
        thinking = "Immediate post selected. Asking user for final confirmation."
        return {
            "thinking_log": state.get("thinking_log", []) + [thinking],
            "post_confirmed": "pending"
        }

    @traceable
    def publish_action(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish Action Node: Directly publishes draft to LinkedIn using FastMCP tools.
        """
        logger.info("Executing Publish Action Node...")
        if not isinstance(state, dict):
            state = state.dict()
        content = state.get("draft_content")
        image_url = state.get("image_url")
        
        result = fastmcp_linkedin.publish_post(text=content, image_url=image_url)
        return {
            "posting_result": result,
            "thinking_log": state.get("thinking_log", []) + [f"Publish action triggered: {result}"]
        }

    @traceable
    def schedule_action(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule Action Node: Schedules post for later via FastMCP tools.
        """
        logger.info("Executing Schedule Action Node...")
        if not isinstance(state, dict):
            state = state.dict()
        content = state.get("draft_content")
        image_url = state.get("image_url")
        scheduled_time = state.get("scheduled_time")
        
        result = fastmcp_linkedin.schedule_post(text=content, publish_time=scheduled_time, image_url=image_url)
        return {
            "posting_result": result,
            "thinking_log": state.get("thinking_log", []) + [f"Schedule action triggered: {result}"]
        }

    @traceable
    def wait_draft_approval(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Wait state node for draft approval."""
        logger.info("Executing Wait Draft Approval Node...")
        return {}

    @traceable
    def wait_image_choice(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Wait state node for image choice."""
        logger.info("Executing Wait Image Choice Node...")
        return {}

    @traceable
    def wait_image_approval(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Wait state node for image approval."""
        logger.info("Executing Wait Image Approval Node...")
        return {}

    @traceable
    def wait_post_mode(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Wait state node for posting mode choice."""
        logger.info("Executing Wait Post Mode Node...")
        return {}

    @traceable
    def wait_post_confirmation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Wait state node for safety post confirmation."""
        logger.info("Executing Wait Post Confirmation Node...")
        return {}
