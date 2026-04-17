import asyncio
import os
import sys
from sqlmodel import Session, create_engine, select

# Ensure the script can find the 'app' module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.decision.agent import run_decision_agent
from app.decision.schemas import AgentDecisionRequest
from app.decision.tools import RetrieveNeedsTool, RetrieveMenuMarkdownsTool
from app.db.models import Team, TeamMembership, Restaurant

# --- Test Configuration ---
DATABASE_URL = "sqlite:///./data/umamimatch.db"

# Provided existing records (from user's data)
TEAM_ID = "40d39990-78a2-4a93-8593-cddd160f555d"
TEAM_USER_ID = "6c561142-6991-483a-a72a-222b78c0c670"  # user behind the provided profile
RESTAURANT_ID = "4f1ce708-3ea1-4244-bac2-ebdc3d4ce094"


def ensure_membership(session: Session, team_id: str, user_id: str) -> None:
    """Ensure there is an active TeamMembership, create it if missing."""
    existing = session.exec(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
            TeamMembership.is_active == True,
        )
    ).first()
    if not existing:
        session.add(TeamMembership(team_id=team_id, user_id=user_id, is_active=True))
        session.commit()


async def test_agent_with_tools_using_existing_data():
    print("--- Starting Agent Tools Test (Existing Data) ---")

    # 1. DB session
    engine = create_engine(DATABASE_URL)
    session = Session(engine)

    try:
        # 2. Validate existing records
        team = session.get(Team, TEAM_ID)
        restaurant = session.get(Restaurant, RESTAURANT_ID)
        if not team:
            raise RuntimeError(f"Team not found: {TEAM_ID}")
        if not restaurant:
            raise RuntimeError(f"Restaurant not found: {RESTAURANT_ID}")

        # 3. Ensure active membership for the provided user
        ensure_membership(session, TEAM_ID, TEAM_USER_ID)

        # 4. Run tools directly
        needs_tool = RetrieveNeedsTool(db_session=session)
        menus_tool = RetrieveMenuMarkdownsTool(db_session=session)

        needs = needs_tool._run(team_id=TEAM_ID)
        menus = menus_tool._run(restaurant_ids=[RESTAURANT_ID])

        print("\n--- RetrieveNeedsTool Output ---")
        print(needs)
        print("--- RetrieveMenuMarkdownsTool Output ---")
        print(menus)

        # Sanity checks
        assert needs.get("team_id") == TEAM_ID, "Needs tool did not return correct team_id"
        assert menus.get("menus") and menus["menus"][0]["restaurant_id"] == RESTAURANT_ID, "Menus tool did not return the expected restaurant"

        # 5. Run the agent with the existing team + restaurant
        request_payload = AgentDecisionRequest(
            team_id=TEAM_ID,
            restaurant_ids=[RESTAURANT_ID],
            user_question=(
                "Use your tools to retrieve team needs and the restaurant menu. "
                "Filter out incompatible options (allergies: peanuts; restrictions: vegetarian). "
                "Recommend one restaurant and one dish. End your message with the token TOOLS_OK."
            ),
        )

        print("\nSending request to agent...")
        print(f"Team: {TEAM_ID} | Restaurants: {[RESTAURANT_ID]}")

        result = await run_decision_agent(
            request=request_payload.model_dump(),
            db_session=session,
        )

        print("\n--- Agent Response ---")
        print(result.get("response"))
        print("----------------------")

        if result.get("response") and "TOOLS_OK" in result.get("response"):
            print("\nSUCCESS: Tools executed and agent returned a response including TOOLS_OK.")
        else:
            print("\nNOTE: Tools test finished; review the response above to ensure it used tools sensibly.")

    except Exception as e:
        print("\n--- ERROR ---")
        print(f"An error occurred during the tools test: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(test_agent_with_tools_using_existing_data())
