import os
import json
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from pymongo import MongoClient
import pandas as pd
from datetime import datetime

load_dotenv()

# ── Connections ──────────────────────────────────────────────────────────────
engine = create_engine(os.getenv("POSTGRES_URL"))
mongo_client = MongoClient(os.getenv("MONGO_URL"))
sse_db = mongo_client["sse_target"]

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RxE to SSE Migration Dashboard",
    page_icon="🏥",
    layout="wide"
)

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🏥 RxE to SSE Migration Dashboard")
st.caption("Automate Migration. Intelligent Validation. Business Confidence.")
st.divider()

# ── Run agents button ─────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    run_migration = st.button(
        "🚀 Run Metadata Agent",
        use_container_width=True,
        type="primary"
    )

with col2:
    run_validation = st.button(
        "✅ Run Validation Agent",
        use_container_width=True
    )

# ── Run Metadata Agent ────────────────────────────────────────────────────────
if run_migration:
    with st.spinner("Running Metadata Agent..."):
        try:
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from agents.metadata_agent import build_agent as build_metadata
            from typing import TypedDict, List
            
            agent = build_metadata()
            initial_state = {
                "extracts": [], "field_mappings": [],
                "business_rules": [], "transformed": [],
                "status": "starting", "errors": []
            }
            final_state = agent.invoke(initial_state)

            if final_state["status"] == "completed":
                st.success(f"✅ Migration completed! {len(final_state['transformed'])} extracts migrated.")
            else:
                st.error(f"❌ Migration failed: {final_state['errors']}")
        except Exception as e:
            st.error(f"Error: {e}")

# ── Run Validation Agent ──────────────────────────────────────────────────────
if run_validation:
    with st.spinner("Running Validation Agent..."):
        try:
            from agents.validation_agent import build_agent as build_validation

            agent = build_validation()
            initial_state = {
                "source_data": [], "target_data": [],
                "business_rules": [], "discrepancies": [],
                "report": {}, "status": "starting", "errors": []
            }
            final_state = agent.invoke(initial_state)

            if final_state["status"] == "completed":
                st.success("✅ Validation completed! Report saved.")
            else:
                st.error(f"❌ Validation failed: {final_state['errors']}")
        except Exception as e:
            st.error(f"Error: {e}")

st.divider()

# ── Section 1: Source Database Stats ─────────────────────────────────────────
st.subheader("📊 Source Database (RxE Postgres)")

try:
    with engine.connect() as conn:
        extracts = pd.read_sql(
            "SELECT extract_id, extract_name, extract_type, status, record_count FROM extract_metadata",
            conn
        )
        total_records = extracts["record_count"].sum()
        active_count  = len(extracts[extracts["status"] == "ACTIVE"])
        pending_count = len(extracts[extracts["status"] == "PENDING"])

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Extracts",  len(extracts))
    m2.metric("Active Extracts", active_count)
    m3.metric("Pending",         pending_count)
    m4.metric("Total Records",   f"{total_records:,}")

    # Table
    st.dataframe(extracts, use_container_width=True)

except Exception as e:
    st.error(f"Could not load source data: {e}")

st.divider()

# ── Section 2: Target Database Stats ──────────────────────────────────────────
st.subheader("🎯 Target Database (SSE MongoDB)")

try:
    migrations = list(sse_db["migrations"].find({}, {"_id": 0}))

    if migrations:
        m1, m2 = st.columns(2)
        m1.metric("Migrated Documents", len(migrations))
        m2.metric("Migration Status", "✅ Complete")

        # Show migrated documents
        st.json(migrations[0])
        if len(migrations) > 1:
            st.caption(f"Showing 1 of {len(migrations)} documents")
    else:
        st.warning("No migrated data found. Run the Metadata Agent first.")

except Exception as e:
    st.error(f"Could not load target data: {e}")

st.divider()

# ── Section 3: Validation Report ──────────────────────────────────────────────
st.subheader("📋 Latest Validation Report")

try:
    # Get latest report
    reports = list(sse_db["reports"].find(
        {}, {"_id": 0}
    ).sort("generated_at", -1).limit(1))

    if reports:
        report = reports[0]

        # Status banner
        overall = report.get("overall_status", "UNKNOWN")
        if overall == "PASS":
            st.success(f"✅ Overall Status: {overall}")
        else:
            st.error(f"❌ Overall Status: {overall}")

        # Report metrics
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Source Records",  report.get("total_source_records", 0))
        m2.metric("Target Records",  report.get("total_target_records", 0))
        m3.metric("Matched",         report.get("records_matched", 0))
        m4.metric("Mismatches",      report.get("mismatches", 0))
        m5.metric("Acceptable",      report.get("acceptable_variances", 0))

        # Business rules
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**✅ Rules Passed:**")
            for rule in report.get("business_rules_passed", []):
                st.markdown(f"- {rule}")

        with col2:
            st.markdown("**❌ Rules Failed:**")
            failed = report.get("business_rules_failed", [])
            if failed:
                for rule in failed:
                    st.markdown(f"- {rule}")
            else:
                st.markdown("- None")

        # Discrepancies table
        discrepancies = report.get("discrepancy_details", [])
        if discrepancies:
            st.markdown("**🔍 Discrepancy Details:**")
            df = pd.DataFrame(discrepancies)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No discrepancies found.")

        # Report timestamp
        st.caption(f"Report generated at: {report.get('generated_at')}")

    else:
        st.warning("No validation report found. Run the Validation Agent first.")

except Exception as e:
    st.error(f"Could not load report: {e}")

st.divider()

# ── Section 4: Field Mappings ─────────────────────────────────────────────────
st.subheader("🔀 Field Mappings (RxE → SSE)")

try:
    with engine.connect() as conn:
        mappings = pd.read_sql(
            """
            SELECT 
                fm.extract_id,
                em.extract_name,
                fm.source_field,
                fm.target_field,
                fm.data_type,
                fm.transformation
            FROM field_mappings fm
            JOIN extract_metadata em ON fm.extract_id = em.extract_id
            ORDER BY fm.extract_id
            """,
            conn
        )
    st.dataframe(mappings, use_container_width=True)

except Exception as e:
    st.error(f"Could not load field mappings: {e}")