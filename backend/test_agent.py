import os
import sys
import asyncio
from dotenv import load_dotenv

# Load real environment variables from .env
load_dotenv()

# Add current folder to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Ensure console printing supports UTF-8 characters (emojis) on Windows
import io
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from agent.workflow.workflow import agent_graph
from agent.nodes.node import WorkflowNodes

async def run_tests():
    print("==================================================")
    print("  STARTING LANGGRAPH AGENT INTEGRATION TESTING  ")
    print("==================================================")
    
    # Check keys
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        print("FAIL: GROQ_API_KEY not found in environment!")
        return
    else:
        print(f"SUCCESS: GROQ_API_KEY is configured: {groq_key[:10]}...")

    nodes = WorkflowNodes()
    
    # 0. Test Classification Nodes
    print("\n--- 0. Testing 'classify_intent' & 'respond_chitchat' Nodes ---")
    greeting_state = {
        "messages": [{"role": "user", "content": "hello there!"}],
        "thinking_log": []
    }
    draft_req_state = {
        "messages": [{"role": "user", "content": "create a post about fastmcp"}],
        "thinking_log": []
    }
    
    try:
        res_g = nodes.classify_intent(greeting_state)
        print(f"SUCCESS: Greeting classified as: {res_g.get('intent')}")
        
        res_d = nodes.classify_intent(draft_req_state)
        print(f"SUCCESS: Post request classified as: {res_d.get('intent')}")
        
        res_c = nodes.respond_chitchat({**greeting_state, **res_g})
        print(f"SUCCESS: Chitchat response generated: {res_c.get('chitchat_response')}")
    except Exception as e:
        print(f"FAIL: Classification or chitchat node crashed: {e}")
        return

    # 1. Test Research and Draft Node
    print("\n--- 1. Testing 'research_and_draft' Node ---")
    initial_state = {
        "messages": [{"role": "user", "content": "Explain what Vite 6.0 is in a short LinkedIn post."}],
        "draft_content": "",
        "thinking_log": []
    }
    
    try:
        res = nodes.research_and_draft(initial_state)
        print("SUCCESS: 'research_and_draft' node executed successfully!")
        print(f"Draft Generated Preview (first 150 chars):\n{res.get('draft_content', '')[:150]}...")
        print(f"Thinking Log Length: {len(res.get('thinking_log', []))}")
        
        # Save output state for next nodes
        state = {**initial_state, **res}
    except Exception as e:
        print(f"FAIL: 'research_and_draft' execution crashed: {e}")
        return

    # 2. Test Ask Image Option Node
    print("\n--- 2. Testing 'ask_image_option' Node ---")
    try:
        res_image_opt = nodes.ask_image_option(state)
        print("SUCCESS: 'ask_image_option' node executed!")
        print(f"State Returned: {res_image_opt}")
        state = {**state, **res_image_opt}
    except Exception as e:
        print(f"FAIL: 'ask_image_option' node crashed: {e}")
        return

    # 3. Test Generate Image Node
    print("\n--- 3. Testing 'generate_image' Node ---")
    try:
        res_image = nodes.generate_image(state)
        print("SUCCESS: 'generate_image' node executed!")
        print(f"Image URN/URL: {res_image.get('image_url')}")
        print(f"Image Prompt: {res_image.get('image_prompt')}")
        state = {**state, **res_image}
    except Exception as e:
        print(f"FAIL: 'generate_image' node crashed: {e}")
        return

    # 4. Test Posting Agent Mode Select Node
    print("\n--- 4. Testing 'posting_agent' Node ---")
    try:
        res_posting = nodes.posting_agent(state)
        print("SUCCESS: 'posting_agent' node executed!")
        print(f"State Returned: {res_posting}")
        state = {**state, **res_posting}
    except Exception as e:
        print(f"FAIL: 'posting_agent' node crashed: {e}")
        return

    print("\n==================================================")
    print("  ALL CORE LANGGRAPH AGENT NODES TESTED SUCCESSFULLY!  ")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
