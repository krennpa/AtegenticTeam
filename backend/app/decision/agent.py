from datetime import datetime

from langchain.tools import Tool
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from sqlmodel import Session

from .tools import RetrieveMenuMarkdownsTool, RetrieveNeedsTool
from ..core.config import settings
from .prompts import REASONING_PROMPT
from .llm_factory import get_chat_model


# 1. Initialize LLM lazily to avoid startup failures without credentials
_llm = None

def get_llm():
    """Get or initialize the LLM instance."""
    global _llm
    if _llm is None:
        _llm = get_chat_model()
    return _llm


def _parse_agent_response(text: str) -> dict:
    """Parse the agent's final markdown text into structured fields.
    Expects lines with bold headings:
      **Recommendation**: <value>
      **Dish**: <value>
      **Reasoning**: <value>
    Returns a dict with recommendation_restaurant_name, recommendation_restaurant_url,
    recommended_dish, explanation_md, raw_text.
    """
    from urllib.parse import urlparse
    
    recommendation = ""
    dish = ""
    reasoning = ""

    for line in (text or "").splitlines():
        s = line.strip()
        lower = s.lower()
        if lower.startswith("**recommendation**"):
            try:
                value = s.split(":", 1)[1].strip()
            except Exception:
                value = s
            recommendation = value
        elif lower.startswith("**dish**"):
            try:
                value = s.split(":", 1)[1].strip()
            except Exception:
                value = s
            dish = value
        elif lower.startswith("**reasoning**"):
            try:
                value = s.split(":", 1)[1].strip()
            except Exception:
                value = s
            reasoning = value

    rec_name = recommendation
    rec_url = None
    if recommendation.startswith("http://") or recommendation.startswith("https://"):
        rec_url = recommendation
        # Extract clean domain name from URL (without www.)
        try:
            parsed = urlparse(recommendation)
            domain = parsed.netloc or parsed.path
            # Remove www. prefix if present
            if domain.startswith("www."):
                domain = domain[4:]
            # Remove port if present
            domain = domain.split(":")[0]
            rec_name = domain
        except Exception:
            rec_name = recommendation

    return {
        "recommendation_restaurant_name": rec_name or "",
        "recommendation_restaurant_url": rec_url,
        "recommended_dish": dish or "",
        "explanation_md": reasoning or (text or ""),
        "raw_text": text or "",
    }


def create_decision_agent_executor(db_session: Session):
    """Creates and returns the LangGraph agent executor."""

    # 3. Initialize Tools with the database session
    needs_tool = RetrieveNeedsTool(db_session=db_session)
    menu_tool = RetrieveMenuMarkdownsTool(db_session=db_session)

    # Wrap them in LangChain's Tool class
    tools = [
        Tool(
            name=needs_tool.name,
            func=needs_tool._run,
            description=needs_tool.description,
            args_schema=needs_tool.args_schema,
        ),
        Tool(
            name=menu_tool.name,
            func=menu_tool._run,
            description=menu_tool.description,
            args_schema=menu_tool.args_schema,
        ),
    ]

    # 4. Create the prompt for the ReAct Agent using only the 'messages' state
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", REASONING_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    # 5. Create the ReAct Agent
    agent_executor = create_react_agent(model=get_llm(), tools=tools, prompt=prompt)

    return agent_executor


async def run_decision_agent(request: dict, db_session: Session):
    """Runs the decision agent and returns the final result based on the latest documentation."""
    agent = create_decision_agent_executor(db_session=db_session)

    # Get current day information with full context
    now = datetime.now()
    current_day = now.strftime("%A")  # Full day name (e.g., "Monday")
    current_date = now.strftime("%Y-%m-%d")  # ISO date format
    current_time = now.strftime("%H:%M")  # Time in HH:MM format

    # Prepare the input for the agent using the 'messages' state key expected by create_react_agent
    input_message = f"""Current Date & Time: {current_day}, {current_date} at {current_time}
Team ID: {request['team_id']}
Restaurant IDs: {request['restaurant_ids']}

CONTEXT:
- Today is {current_day}. This is CRITICAL for menu selection.
- Some restaurants have daily menus (only today's items available)
- Some restaurants have weekly menus (different items each day)
- Some restaurants have static menus (same items always available)
- You MUST use the tools to retrieve team needs and restaurant menus with their metadata
- Pay attention to menu_type, detected_days, and freshness in the menu data
- Select dishes that are available TODAY ({current_day})

User Question: {request['user_question']}

Remember: Use retrieve_team_needs and retrieve_restaurant_menus tools to gather all necessary information before making your recommendation."""
    inputs = {"messages": [("human", input_message)]}

    # Invoke the agent and get the final state
    result_state = await agent.ainvoke(inputs)

    # Prefer the last AI message content if present
    final_response = ""
    messages = result_state.get("messages", [])
    if messages:
        try:
            final_response = messages[-1].content or ""
        except Exception:
            pass

    # Fallback: some executors return 'output'
    if not final_response and isinstance(result_state, dict) and "output" in result_state:
        final_response = result_state.get("output") or ""

    # Final fallback: directly ping the LLM to verify connectivity (only if explicitly enabled via settings)
    if not final_response and bool(getattr(settings, "agent_test_fallback", False)):
        try:
            ping = get_llm().invoke([("human", "Reply exactly: model connectivity is healthy")])
            final_response = getattr(ping, "content", "") or ""
        except Exception:
            pass

    # Build structured response
    structured = _parse_agent_response(final_response)
    if not structured["raw_text"]:
        structured = _parse_agent_response("Agent finished without a final response.")

    return structured
