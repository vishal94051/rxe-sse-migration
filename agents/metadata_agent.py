import os
import json
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from pymongo import MongoClient
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

load_dotenv()

# ── State ──────────────────────────────────────────────────────────────────
# This is the "memory" of the agent — everything it knows at each step
class AgentState(TypedDict):
    extracts        : List[dict]   # raw data from Postgres
    field_mappings  : List[dict]   # mapping rules from Postgres
    business_rules  : List[dict]   # business rules from Postgres
    transformed     : List[dict]   # transformed JSON for SSE
    status          : str          # current status message
    errors          : List[str]    # any errors encountered

# ── Database connections ────────────────────────────────────────────────────
engine = create_engine(os.getenv("POSTGRES_URL"))
mongo_client = MongoClient(os.getenv("MONGO_URL"))
db = mongo_client["sse_target"]
collection = db["migrations"]

# ── LLM ────────────────────────────────────────────────────────────────────
llm = ChatAnthropic(
    model="claude-sonnet-4-5",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=4096
)

# ── Node 1: Fetch data from Postgres ───────────────────────────────────────
def fetch_from_postgres(state: AgentState) -> AgentState:
    print("\n[Node 1] Fetching data from RxE Postgres...")
    try:
        with engine.connect() as conn:
            # Fetch extracts
            extracts = conn.execute(
                text("SELECT * FROM extract_metadata WHERE status = 'ACTIVE'")
            ).mappings().all()

            # Fetch field mappings
            mappings = conn.execute(
                text("SELECT * FROM field_mappings")
            ).mappings().all()

            # Fetch business rules
            rules = conn.execute(
                text("SELECT * FROM business_rules WHERE is_active = TRUE")
            ).mappings().all()

        state["extracts"]       = [dict(r) for r in extracts]
        state["field_mappings"] = [dict(r) for r in mappings]
        state["business_rules"] = [dict(r) for r in rules]
        state["status"]         = "fetched"

        print(f"   ✅ Fetched {len(state['extracts'])} extracts")
        print(f"   ✅ Fetched {len(state['field_mappings'])} field mappings")
        print(f"   ✅ Fetched {len(state['business_rules'])} business rules")

    except Exception as e:
        state["errors"].append(f"Postgres fetch error: {str(e)}")
        state["status"] = "failed"
        print(f"   ❌ Error: {e}")

    return state

# ── Node 2: Transform using LLM ────────────────────────────────────────────
def transform_with_llm(state: AgentState) -> AgentState:
    print("\n[Node 2] Transforming data using Claude...")

    if state["status"] == "failed":
        return state

    try:
        prompt = f"""
You are a data migration expert. Transform the following RxE extract metadata 
into SSE compatible JSON format using the field mappings provided.

EXTRACTS TO MIGRATE:
{json.dumps(state['extracts'], indent=2, default=str)}

FIELD MAPPINGS TO APPLY:
{json.dumps(state['field_mappings'], indent=2, default=str)}

BUSINESS RULES TO EMBED:
{json.dumps(state['business_rules'], indent=2, default=str)}

Transform each extract into SSE JSON format following these rules:
1. Rename fields according to field_mappings (source_field → target_field)
2. Apply transformations (UPPERCASE, date FORMAT, DIRECT)
3. Embed applicable business rules inside each extract
4. Add a migration_metadata block with timestamp and status

Return ONLY a valid JSON array, no explanation, no markdown backticks.
"""
        response = llm.invoke(prompt)
        raw = response.content.strip()

        # Clean response if needed
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        transformed = json.loads(raw)
        state["transformed"] = transformed
        state["status"] = "transformed"
        print(f"   ✅ Transformed {len(transformed)} extracts")

    except Exception as e:
        state["errors"].append(f"Transform error: {str(e)}")
        state["status"] = "failed"
        print(f"   ❌ Error: {e}")

    return state

# ── Node 3: Push to MongoDB ─────────────────────────────────────────────────
def push_to_mongodb(state: AgentState) -> AgentState:
    print("\n[Node 3] Pushing transformed data to SSE MongoDB...")

    if state["status"] == "failed":
        return state

    try:
        # Clear previous migration data
        collection.delete_many({})

        # Insert transformed documents
        result = collection.insert_many(state["transformed"])
        state["status"] = "completed"
        print(f"   ✅ Pushed {len(result.inserted_ids)} documents to MongoDB")

    except Exception as e:
        state["errors"].append(f"MongoDB push error: {str(e)}")
        state["status"] = "failed"
        print(f"   ❌ Error: {e}")

    return state

# ── Build the graph ─────────────────────────────────────────────────────────
def build_agent():
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("fetch",     fetch_from_postgres)
    graph.add_node("transform", transform_with_llm)
    graph.add_node("push",      push_to_mongodb)

    # Add edges (flow)
    graph.set_entry_point("fetch")
    graph.add_edge("fetch",     "transform")
    graph.add_edge("transform", "push")
    graph.add_edge("push",      END)

    return graph.compile()

# ── Run the agent ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("   METADATA AGENT — RxE to SSE Migration")
    print("=" * 50)

    agent = build_agent()

    initial_state = AgentState(
        extracts=[],
        field_mappings=[],
        business_rules=[],
        transformed=[],
        status="starting",
        errors=[]
    )

    final_state = agent.invoke(initial_state)

    print("\n" + "=" * 50)
    print("   FINAL STATUS:", final_state["status"].upper())
    if final_state["errors"]:
        print("   ERRORS:", final_state["errors"])
    print("=" * 50)