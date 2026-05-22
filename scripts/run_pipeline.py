import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from agents.metadata_agent import build_agent as build_metadata
from agents.validation_agent import build_agent as build_validation

def print_banner(text):
    print("\n" + "=" * 55)
    print(f"   {text}")
    print("=" * 55)

def run_metadata_agent():
    print_banner("STEP 1: METADATA AGENT — Migration")
    start = time.time()

    agent = build_metadata()
    initial_state = {
        "extracts": [], "field_mappings": [],
        "business_rules": [], "transformed": [],
        "status": "starting", "errors": []
    }

    final_state = agent.invoke(initial_state)
    elapsed = round(time.time() - start, 2)

    if final_state["status"] == "completed":
        print(f"\n   ✅ Migration completed in {elapsed}s")
        print(f"   📦 Extracts migrated: {len(final_state['transformed'])}")
        return True
    else:
        print(f"\n   ❌ Migration failed: {final_state['errors']}")
        return False

def run_validation_agent():
    print_banner("STEP 2: VALIDATION AGENT — Reconciliation")
    start = time.time()

    agent = build_validation()
    initial_state = {
        "source_data": [], "target_data": [],
        "business_rules": [], "discrepancies": [],
        "report": {}, "status": "starting", "errors": []
    }

    final_state = agent.invoke(initial_state)
    elapsed = round(time.time() - start, 2)

    if final_state["status"] == "completed":
        report = final_state["report"]
        print(f"\n   ✅ Validation completed in {elapsed}s")
        print(f"   📊 Overall status  : {report.get('overall_status')}")
        print(f"   🔍 Discrepancies   : {len(final_state['discrepancies'])}")
        print(f"   ❌ Mismatches      : {len([d for d in final_state['discrepancies'] if d['classification'] == 'MISMATCH'])}")
        print(f"   ✅ Acceptable      : {len([d for d in final_state['discrepancies'] if d['classification'] == 'ACCEPTABLE'])}")
        return True
    else:
        print(f"\n   ❌ Validation failed: {final_state['errors']}")
        return False

if __name__ == "__main__":
    print_banner(f"RxE → SSE MIGRATION PIPELINE")
    print(f"   Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 1 — Migration
    migration_success = run_metadata_agent()

    if not migration_success:
        print("\n❌ Pipeline stopped — migration failed.")
        sys.exit(1)

    # Small pause between agents
    print("\n   ⏳ Waiting 2 seconds before validation...")
    time.sleep(2)

    # Step 2 — Validation
    validation_success = run_validation_agent()

    # Final summary
    print_banner("PIPELINE COMPLETE")
    print(f"   Migration  : {'✅ SUCCESS' if migration_success  else '❌ FAILED'}")
    print(f"   Validation : {'✅ SUCCESS' if validation_success else '❌ FAILED'}")
    print(f"   Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)