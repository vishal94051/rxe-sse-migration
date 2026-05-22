import os
import json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from pymongo import MongoClient
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict

load_dotenv()

# ── State ──────────────────────────────────────────────────────────────────
class ValidationState(TypedDict):
    source_data      : List[dict]   # data from Postgres
    target_data      : List[dict]   # data from MongoDB
    business_rules   : List[dict]   # rules to validate against
    discrepancies    : List[dict]   # mismatches found
    report           : Dict         # final reconciliation report
    status           : str
    errors           : List[str]

# ── Connections ─────────────────────────────────────────────────────────────
engine = create_engine(os.getenv("POSTGRES_URL"))
mongo_client = MongoClient(os.getenv("MONGO_URL"))
collection = mongo_client["sse_target"]["migrations"]

# ── LLM ─────────────────────────────────────────────────────────────────────
llm = ChatAnthropic(
    model="claude-sonnet-4-5",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=4096
)

# ── Node 1: Fetch source from Postgres ──────────────────────────────────────
def fetch_source_data(state: ValidationState) -> ValidationState:
    print("\n[Node 1] Fetching source data from Postgres...")
    try:
        with engine.connect() as conn:
            extracts = conn.execute(
                text("SELECT * FROM extract_metadata WHERE status = 'ACTIVE'")
            ).mappings().all()

            rules = conn.execute(
                text("SELECT * FROM business_rules WHERE is_active = TRUE")
            ).mappings().all()

        state["source_data"]    = [dict(r) for r in extracts]
        state["business_rules"] = [dict(r) for r in rules]
        state["status"]         = "source_fetched"
        print(f"   ✅ Fetched {len(state['source_data'])} source records")

    except Exception as e:
        state["errors"].append(f"Source fetch error: {str(e)}")
        state["status"] = "failed"
        print(f"   ❌ Error: {e}")

    return state

# ── Node 2: Fetch target from MongoDB ───────────────────────────────────────
def fetch_target_data(state: ValidationState) -> ValidationState:
    print("\n[Node 2] Fetching target data from MongoDB...")
    try:
        documents = list(collection.find({}, {"_id": 0}))
        state["target_data"] = documents
        state["status"]      = "target_fetched"
        print(f"   ✅ Fetched {len(state['target_data'])} target documents")

    except Exception as e:
        state["errors"].append(f"Target fetch error: {str(e)}")
        state["status"] = "failed"
        print(f"   ❌ Error: {e}")

    return state

# ── Node 3: Compare with LLM ─────────────────────────────────────────────
def compare_with_llm(state: ValidationState) -> ValidationState:
    print("\n[Node 3] Comparing source vs target using Claude...")

    if state["status"] == "failed":
        return state

    try:
        prompt = f"""
You are a data validation expert. Compare the source and target data from a 
healthcare data migration and identify any discrepancies.

SOURCE DATA (RxE Postgres):
{json.dumps(state['source_data'], indent=2, default=str)}

TARGET DATA (SSE MongoDB):
{json.dumps(state['target_data'], indent=2, default=str)}

BUSINESS RULES TO VALIDATE:
{json.dumps(state['business_rules'], indent=2, default=str)}

Perform these checks:
1. Record count match — does target have same number of records as source?
2. Field mapping validation — are all fields correctly renamed per mappings?
3. Business rule validation — does data satisfy all business rules?
4. Data integrity — are required fields present and non-null?
5. Transformation accuracy — were UPPERCASE and date formats applied correctly?

For each discrepancy found, classify it as:
- "ACCEPTABLE" — minor variance that is business approved
- "MISMATCH" — true data issue that needs fixing

Return ONLY a valid JSON object in this exact format, no explanation:
{{
    "total_source_records": <number>,
    "total_target_records": <number>,
    "records_matched": <number>,
    "discrepancies": [
        {{
            "extract_id": "<id>",
            "field": "<field name>",
            "issue": "<description>",
            "classification": "ACCEPTABLE or MISMATCH",
            "source_value": "<value>",
            "target_value": "<value>"
        }}
    ],
    "business_rules_passed": [<list of rule names that passed>],
    "business_rules_failed": [<list of rule names that failed>],
    "overall_status": "PASS or FAIL"
}}
"""
        response = llm.invoke(prompt)
        raw = response.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)
        state["discrepancies"] = result.get("discrepancies", [])
        state["report"]        = result
        state["status"]        = "compared"
        print(f"   ✅ Comparison complete")
        print(f"   Found {len(state['discrepancies'])} discrepancies")

    except Exception as e:
        state["errors"].append(f"Comparison error: {str(e)}")
        state["status"] = "failed"
        print(f"   ❌ Error: {e}")

    return state

# ── Node 4: Generate reconciliation report ───────────────────────────────
def generate_report(state: ValidationState) -> ValidationState:
    print("\n[Node 4] Generating reconciliation report...")

    if state["status"] == "failed":
        return state

    try:
        report = state["report"]
        mismatches  = [d for d in state["discrepancies"] if d["classification"] == "MISMATCH"]
        acceptables = [d for d in state["discrepancies"] if d["classification"] == "ACCEPTABLE"]

        # Save report to MongoDB
        report_doc = {
            "report_type"           : "RECONCILIATION",
            "generated_at"          : datetime.now().isoformat(),
            "total_source_records"  : report.get("total_source_records"),
            "total_target_records"  : report.get("total_target_records"),
            "records_matched"       : report.get("records_matched"),
            "total_discrepancies"   : len(state["discrepancies"]),
            "mismatches"            : len(mismatches),
            "acceptable_variances"  : len(acceptables),
            "business_rules_passed" : report.get("business_rules_passed", []),
            "business_rules_failed" : report.get("business_rules_failed", []),
            "overall_status"        : report.get("overall_status"),
            "discrepancy_details"   : state["discrepancies"]
        }

        mongo_client["sse_target"]["reports"].insert_one(report_doc)
        state["status"] = "completed"

        # Print summary
        print(f"\n   {'='*40}")
        print(f"   RECONCILIATION REPORT SUMMARY")
        print(f"   {'='*40}")
        print(f"   Source records  : {report.get('total_source_records')}")
        print(f"   Target records  : {report.get('total_target_records')}")
        print(f"   Records matched : {report.get('records_matched')}")
        print(f"   Mismatches      : {len(mismatches)}")
        print(f"   Acceptable      : {len(acceptables)}")
        print(f"   Overall status  : {report.get('overall_status')}")
        print(f"   {'='*40}")
        print(f"   ✅ Report saved to MongoDB")

    except Exception as e:
        state["errors"].append(f"Report error: {str(e)}")
        state["status"] = "failed"
        print(f"   ❌ Error: {e}")

    return state

# ── Build the graph ──────────────────────────────────────────────────────
def build_agent():
    graph = StateGraph(ValidationState)

    graph.add_node("fetch_source", fetch_source_data)
    graph.add_node("fetch_target", fetch_target_data)
    graph.add_node("compare",      compare_with_llm)
    graph.add_node("report",       generate_report)

    graph.set_entry_point("fetch_source")
    graph.add_edge("fetch_source", "fetch_target")
    graph.add_edge("fetch_target", "compare")
    graph.add_edge("compare",      "report")
    graph.add_edge("report",       END)

    return graph.compile()

# ── Run ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("   VALIDATION AGENT — Reconciliation")
    print("=" * 50)

    agent = build_agent()

    initial_state = ValidationState(
        source_data=[],
        target_data=[],
        business_rules=[],
        discrepancies=[],
        report={},
        status="starting",
        errors=[]
    )

    final_state = agent.invoke(initial_state)

    print("\n" + "=" * 50)
    print("   FINAL STATUS:", final_state["status"].upper())
    if final_state["errors"]:
        print("   ERRORS:", final_state["errors"])
    print("=" * 50)