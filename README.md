# RxE to SSE Migration — AI Agents Pipeline

Automate Migration. Intelligent Validation. Business Confidence.

## Overview

This project automates the migration of healthcare metadata from a legacy 
RxE SQL system to a modern SSE platform (Cosmos DB) using AI agents built 
with LangGraph and Claude (Anthropic).

Instead of manual migration and reconciliation, two autonomous AI agents 
handle the entire pipeline end to end.

## Architecture
RxE Source (Postgres)
↓
METADATA AGENT (LangGraph)
├── Node 1: Fetch metadata, field mappings, business rules
├── Node 2: Transform using Claude AI
└── Node 3: Push transformed JSON to SSE target
↓
SSE Target (MongoDB)
↓
VALIDATION AGENT (LangGraph)
├── Node 1: Fetch source data from Postgres
├── Node 2: Fetch migrated data from MongoDB
├── Node 3: Compare and reconcile using Claude AI
└── Node 4: Generate reconciliation report
↓
Reconciliation Report (MongoDB)
↓
Streamlit Dashboard (UI)

## Tech Stack

| Layer | Technology |
|---|---|
| AI Agents | LangGraph |
| LLM | Claude (Anthropic) |
| Source Database | PostgreSQL 15 (Docker) |
| Target Database | MongoDB 6 (Docker) |
| Dashboard | Streamlit |
| ORM | SQLAlchemy |
| Infrastructure | Docker Compose |
| Language | Python 3.11 |

## Project Structure

rxe-sse-migration/
├── agents/
│     ├── metadata_agent.py      # Migration agent
│     └── validation_agent.py    # Validation agent
├── scripts/
│     ├── seed_data.py           # Creates fake RxE source data
│     ├── db_connections.py      # Tests DB connectivity
│     ├── run_pipeline.py        # Runs full pipeline end to end
│     └── dashboard.py           # Streamlit UI
├── docker-compose.yml           # Postgres + MongoDB setup
├── .env.example                 # Environment variables template
└── README.md

## Getting Started

### Prerequisites
- Python 3.11
- Docker Desktop
- Anthropic API key

### Setup

1. Clone the repo
```bash
git clone https://github.com/yourusername/rxe-sse-migration.git
cd rxe-sse-migration
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Set up environment variables
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

4. Start databases
```bash
docker compose up -d
```

5. Seed source data
```bash
python scripts/seed_data.py
```

### Running the Pipeline

Run full pipeline (migration + validation):
```bash
python scripts/run_pipeline.py
```

Run individual agents:
```bash
python agents/metadata_agent.py
python agents/validation_agent.py
```

Launch dashboard:
```bash
streamlit run scripts/dashboard.py
```

## Agent Design

### Metadata Agent
Reads extract metadata, field mappings, and business rules from the RxE 
Postgres database. Uses Claude to intelligently apply transformation rules 
and convert data into SSE compatible JSON format. Pushes transformed 
documents to MongoDB.

### Validation Agent
Fetches both source (Postgres) and target (MongoDB) data after migration. 
Uses Claude to compare records, validate against business rules, and 
classify discrepancies as either ACCEPTABLE variances or true MISMATCHES. 
Generates a full reconciliation report saved to MongoDB.

## Key Features

- AI powered field mapping and transformation
- Intelligent reconciliation with business rule classification
- End to end pipeline with single command execution
- Real time dashboard with migration and validation status
- Fully containerised local development environment
- Modular agent design — each agent independently runnable

## Sample Output

=======================================================
RxE → SSE MIGRATION PIPELINE
Migration  : ✅ SUCCESS
Validation : ✅ SUCCESS
Extracts migrated  : 3598373
Overall status     : PASS
Discrepancies      : 2030 (0 mismatches, 2030 acceptable)