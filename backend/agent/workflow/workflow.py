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
    workflow.add_node("ask_image_option", nodes_instance.ask_image_option)
    workflow.add_node("generate_image", nodes_instance.generate_image)
    workflow.add_node("posting_agent", nodes_instance.posting_agent)
    workflow.add_node("confirm_posting_prompt", nodes_instance.confirm_posting_prompt)
    workflow.add_node("publish_action", nodes_instance.publish_action)
    workflow.add_node("schedule_action", nodes_instance.schedule_action)
    
    # Set entry point
    workflow.set_entry_point("classify_intent")
    
    # Connect conditional routing edges
    workflow.add_conditional_edges(
        "classify_intent",
        lambda state: "respond_chitchat" if state.intent == "chitchat" else "research_and_draft"
    )
    
    # Connect conditional routing edges
    workflow.add_conditional_edges(
        "research_and_draft",
        lambda state: "research_and_draft" if state.approval_status == "revision_requested" else "ask_image_option"
    )
    
    workflow.add_conditional_edges(
        "ask_image_option",
        lambda state: "generate_image" if state.image_needed == "yes" else "posting_agent"
    )
    
    workflow.add_conditional_edges(
        "generate_image",
        lambda state: "generate_image" if state.image_approved == "no" else "posting_agent"
    )
    
    workflow.add_conditional_edges(
        "posting_agent",
        lambda state: "confirm_posting_prompt" if state.post_mode == "immediate" else "schedule_action"
    )
    
    workflow.add_conditional_edges(
        "confirm_posting_prompt",
        lambda state: "publish_action" if state.post_confirmed == "yes" else END
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
            "research_and_draft",
            "ask_image_option",
            "generate_image",
            "posting_agent",
            "confirm_posting_prompt"
        ]
    )
    return app

# Compiled LangGraph application
agent_graph = create_agent_graph()
