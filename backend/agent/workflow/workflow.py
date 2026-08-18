from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state.state import AgentState
from agent.nodes.node import WorkflowNodes

def create_agent_graph():
    nodes_instance = WorkflowNodes()
    workflow = StateGraph(AgentState)
    
    # Add nodes to graph
    workflow.add_node("classify_intent", nodes_instance.classify_intent)
    workflow.add_node("respond_chitchat", nodes_instance.respond_chitchat)
    workflow.add_node("research_and_draft", nodes_instance.research_and_draft)
    workflow.add_node("wait_draft_approval", nodes_instance.wait_draft_approval)
    workflow.add_node("ask_image_option", nodes_instance.ask_image_option)
    workflow.add_node("wait_image_choice", nodes_instance.wait_image_choice)
    workflow.add_node("generate_image", nodes_instance.generate_image)
    workflow.add_node("wait_image_approval", nodes_instance.wait_image_approval)
    workflow.add_node("posting_agent", nodes_instance.posting_agent)
    workflow.add_node("wait_post_mode", nodes_instance.wait_post_mode)
    workflow.add_node("confirm_posting_prompt", nodes_instance.confirm_posting_prompt)
    workflow.add_node("wait_post_confirmation", nodes_instance.wait_post_confirmation)
    workflow.add_node("publish_action", nodes_instance.publish_action)
    workflow.add_node("schedule_action", nodes_instance.schedule_action)
    
    # Set entry point
    workflow.set_entry_point("classify_intent")
    
    # 1. Routing from classify_intent
    workflow.add_conditional_edges(
        "classify_intent",
        lambda state: "respond_chitchat" if state.intent == "chitchat" else "research_and_draft"
    )
    
    # 2. Linear transitions to wait nodes
    workflow.add_edge("research_and_draft", "wait_draft_approval")
    workflow.add_edge("ask_image_option", "wait_image_choice")
    workflow.add_edge("generate_image", "wait_image_approval")
    workflow.add_edge("posting_agent", "wait_post_mode")
    workflow.add_edge("confirm_posting_prompt", "wait_post_confirmation")
    
    # 3. Conditional routing from wait nodes based on human input
    workflow.add_conditional_edges(
        "wait_draft_approval",
        lambda state: "research_and_draft" if state.approval_status == "revision_requested" else (
            "ask_image_option" if state.approval_status == "approved" else "wait_draft_approval"
        )
    )
    
    workflow.add_conditional_edges(
        "wait_image_choice",
        lambda state: "generate_image" if state.image_needed == "yes" else (
            "posting_agent" if state.image_needed == "no" else "wait_image_choice"
        )
    )
    
    workflow.add_conditional_edges(
        "wait_image_approval",
        lambda state: "generate_image" if state.image_approved == "no" else (
            "posting_agent" if state.image_approved == "yes" else "wait_image_approval"
        )
    )
    
    workflow.add_conditional_edges(
        "wait_post_mode",
        lambda state: "confirm_posting_prompt" if state.post_mode == "immediate" else (
            "schedule_action" if state.post_mode == "scheduled" else "wait_post_mode"
        )
    )
    
    workflow.add_conditional_edges(
        "wait_post_confirmation",
        lambda state: "publish_action" if state.post_confirmed == "yes" else (
            END if state.post_confirmed == "no" else "wait_post_confirmation"
        )
    )
    
    # Terminating edges
    workflow.add_edge("respond_chitchat", END)
    workflow.add_edge("publish_action", END)
    workflow.add_edge("schedule_action", END)
    
    # Compile with state memory checkpointer and interrupts
    memory = MemorySaver()
    app = workflow.compile(
        checkpointer=memory,
        interrupt_after=[
            "wait_draft_approval",
            "wait_image_choice",
            "wait_image_approval",
            "wait_post_mode",
            "wait_post_confirmation"
        ]
    )
    return app

# Compiled LangGraph application
agent_graph = create_agent_graph()
