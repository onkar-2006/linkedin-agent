import os
import logging
import urllib.parse
from typing import Dict, Any, List
from langchain_core.tools import tool

logger = logging.getLogger("agent_tools")

@tool
def web_search(query: str) -> str:
    """
    Search the web for up-to-date information on a specific topic or query.
    Requires a valid TAVILY_API_KEY in the environment.
    """
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key or tavily_key.strip() == "":
        raise ValueError("Tavily Search API key (TAVILY_API_KEY) is missing. Please set it in your backend .env file.")

    try:
        import requests
        logger.info(f"Calling Tavily API for query: {query}")
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 5
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            results_text = f"Tavily Search Results for '{query}':\n\n"
            for i, result in enumerate(data.get("results", []), 1):
                results_text += f"[{i}] {result.get('title')}: {result.get('content')}\nURL: {result.get('url')}\n\n"
            if data.get("answer"):
                results_text = f"Summary: {data.get('answer')}\n\n" + results_text
            return results_text
        else:
            return f"Error: Tavily Search failed with status code {response.status_code}. Response: {response.text}"
    except Exception as e:
        logger.error(f"Tavily Search exception: {e}")
        return f"Error: Tavily Search failed due to exception: {e}"

@tool
def generate_image(prompt: str) -> str:
    """
    Generate a high-quality professional image using Pollinations AI based on the provided prompt.
    Returns the URL of the generated image.
    """
    logger.info(f"Generating image via Pollinations AI for prompt: {prompt}")
    
    # URL encode the prompt to ensure it is safe to pass in the URL path
    encoded_prompt = urllib.parse.quote(prompt.strip())
    
    # We add parameters for dimensions (800x600) and no logos
    pollinations_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=600&nologo=true"
    
    logger.info(f"Generated Pollinations AI Image URL: {pollinations_url}")
    return pollinations_url
