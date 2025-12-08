#LLM-Powered Intelligent Analytics Assistant 

Natural Language → SQL → Business Insight Engine for ContosoRetailDW

This project implements a production-grade analytics assistant that can understand business questions (in English or Turkish), generate accurate SQL queries, execute them on the Microsoft ContosoRetailDW data warehouse, and summarize results as business insights.
The system is optimized for correctness, reliability, and explainability—powered by LLMs, LangChain SQL tools, and a robust validation framework.

1. Project Purpose

The goal of this assistant is to automate the complete analytical workflow:

Understand natural-language questions

Classify intent & detect required tables

Generate high-quality SQL

Validate & correct SQL before execution

Execute the query on SQL Server

Summarize results in business language (TR/EN)

(Optional) Visualize insights in Streamlit

This dramatically reduces friction between business users and complex data warehouse data models.

 2. Key Capabilities
Natural Language → SQL Generation (Hybrid Engine)

Supports both Turkish and English automatically.

Uses a layered architecture:

Template Engine → deterministic SQL for common questions

Dynamic LLM Generator → flexible reasoning

LangChain SQL Tools → schema-aware generation

Validator & Normalizer → safe SQL execution

Self-Correction Module → fixes invalid SQL

Intent Classification

Each query is analyzed to determine:

Aggregation, ranking, comparison, trend, geography, financial…

Complexity level

Required tables

Expected shape of the SQL output

LangChain SQL Integration (2025)

New — Production-grade enhancement

LangChain is used only where it matters most:

Table discovery
tables = list_tables()

Schema extraction (columns, types, FK structure)
schema = get_schema("FactSales")

SQL validation & correction
checked = check_sql(sql)


This gives the LLM real schema awareness, preventing:

Wrong table names

Wrong column names

Bad JOINs

Missing GROUP BY

MSSQL syntax issues

This dramatically increases SQL correctness and stability.

SQL Validation Pipeline

Each generated SQL query goes through:

SQL Normalizer

Table usage checker

LangChain SQL checker

Custom QueryValidator

Self-correction cycle

Safe execution wrapper

This prevents almost all invalid SQL before reaching the database.

Executive-Level Summaries (TR/EN)

The assistant produces natural-language business insights:

Trends

Drivers of performance

Comparative analysis

Forecast-style interpretation

Language is automatically matched to user input:

Ask in English → Answer in English

Ask in Turkish → Answer in Turkish

 Modern Streamlit UI

Provides:

Chat-like interface

Generated SQL viewer

Data table results

Optional charts

Query history

3. System Architecture
User Question (TR/EN)
        ↓
Intent Classifier
        ↓
Template Engine (if applicable)
        ↓
LangChain schema loader (tables + columns)
        ↓
LLM SQL Generator (Ollama → OpenAI fallback)
        ↓
SQL Normalizer + Validator + LangChain SQL Checker
        ↓
Safe Execution (pyodbc)
        ↓
Business Summary Generator (TR/EN)
        ↓
Streamlit Web UI

4. LangChain Integration (NEW – 2025)

This project integrates LangChain minimally but effectively:

New Files Added
File	Purpose
app/database/langchain_db.py	Creates SQLDatabase object for MSSQL
app/tools/sql_tools.py	list_tables(), get_schema(), check_sql()
sql_generator.py (updated)	Uses schema in prompt + SQL correction
LangChain is NOT used for:

Agents
Tool-chains
ReAct loops
Multi-step planners

Instead, Harmony AI uses LangChain as a schema engine + SQL correctness engine, keeping the system fast and stable.

5. Final Project Directory Structure (2025)
├── app
│   ├── core
│   │   ├── config.py
│   │   ├── intent_classifier.py
│   │   ├── schema_builder.py
│   ├── llm
│   │   ├── sql_generator.py
│   │   ├── prompt_manager.py
│   │   ├── result_summarizer.py
│   │   ├── templates.py
│   ├── database
│   │   ├── db_client.py
│   │   ├── sql_normalizer.py
│   │   ├── query_validator.py
│   │   ├── langchain_db.py       ← NEW
│   ├── tools
│   │   ├── sql_tools.py          ← NEW
│   ├── memory
│   │   ├── query_logger.py
│   │   └── (PatternMiner removed)
│   ├── utils
│       ├── logger.py
│
├── tests
│   ├── run_test_scenarios.py
│   ├── test_scenarios.json
│   ├── sql_table_validator.py    ← NEW (2025)
│
├── poc_interactive.py
├── poc_streamlit.py
├── README.md
├── requirements.txt

6. Installation & Setup
 1- Install dependencies
pip install -r requirements.txt

 2️- Pull Ollama models
ollama pull llama3.1:8b
ollama pull llama3.2:latest

 3️- Configure Database

Edit app/core/config.py or .env:

DB_SERVER=localhost
DB_NAME=ContosoRetailDW
DB_DRIVER="ODBC Driver 18 for SQL Server"

 4️- Run the Streamlit UI
streamlit run poc_streamlit.py

 5️- Run Interactive Terminal Mode
python poc_interactive.py

7. Automated Test Suite

Run:

python tests/run_test_scenarios.py


Each scenario validates:

Correct intent

Correct SQL

Correct table usage (via LangChain schema)

No execution errors

Logical structure

Quality of summaries

Example test case:

{
  "id": 1,
  "name": "Simple Aggregation",
  "question": "2008 yılında toplam satış nedir?",
  "expected_tables": ["FactSales", "DimDate"]
}

8. Example Supported Questions (TR & EN)
Example Question	Category
“2008 yılında toplam satış nedir?”	Aggregation
“What are the top 5 products?”	Ranking
“2007 mağaza vs online satış karşılaştırması”	Comparison
“Show the monthly trend for 2009”	Trend
“En az satan ürün hangisi?”	Ranking
“Which category performs best online?”	Category Analysis
9. Future Enhancements
Feature	Status
Advanced analytics dashboards	Planned
GPT-4o Mini fallback routing	In progress
Multi-step SQL Planning Agent	Planned
Contoso-specific fine-tuned model	Research phase
Multi-language conversational UI	Planned
10. License

This project is intended for research, education, and prototyping.
Not recommended for production without further security, monitoring, and scalability enhancements.