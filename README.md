
# **Intelligent Analytics Assistant (LLM-Powered SQL Engine)**

### **Natural Language → SQL → Insight Pipeline for ContosoRetailDW**

This project implements a **production-grade intelligent analytics assistant** capable of understanding business questions (TR/EN), generating accurate SQL queries, validating them against the real ContosoRetailDW schema, executing them safely on SQL Server, and producing executive-level summaries or visualizations.

The system combines **LLMs, rule-based templates, LangChain SQL tools, schema validation, and a self-correcting SQL pipeline** to maximize correctness, reliability, and business usability.

---

# **Project Purpose**

The assistant automates the full analytical workflow:

1. **Understand natural-language questions** (English or Turkish)
2. **Classify intent** and detect required tables
3. **Generate high-quality SQL**
4. **Validate & normalize SQL before execution**
5. **Execute SQL** safely using MSSQL (pyodbc)
6. **Summarize results** as business insights (TR/EN)
7. **Visualize results via Streamlit**

Goal:
✔️ No manual SQL writing
✔️ No schema memorization
✔️ No JOIN debugging
✔️ Business-friendly analytics

---

# **Key Capabilities**

## **1. Natural Language → SQL Generation (Hybrid Engine)**

Supports both **English and Turkish** automatically using a layered architecture:

### **a) Template Engine (Deterministic)**

* Known analytics patterns → guaranteed-correct SQL
* Zero hallucination
* Best for common questions (top products, totals, trends)

### **b) Dynamic LLM SQL Generator**

* Flexible reasoning for unseen or complex questions
* Schema-aware prompts
* Correct MSSQL syntax
* Automatically falls back to templates when needed

### **c) SQL Normalizer + Correction Pipeline**

Handles:

* Fuzzy table name correction
* MSSQL keyword normalization
* LIMIT → TOP conversion
* Phantom column cleanup

Ensures **clean, executable SQL**.

---

## **2. Intent Classification**

Each question is analyzed for:

* Aggregation
* Ranking
* Trend analysis
* Comparison
* Category/channel performance
* Expected SQL shape
* Complexity level

---

## **3. LangChain SQL Integration **

LangChain is used as a **schema intelligence layer**, not an agent.

Provides:

* `list_tables()` → table discovery
* `get_schema(table)` → accurate column/types
* `check_sql(query)` → SQL structure validation

Prevents:

* Wrong table names
* Incorrect JOIN keys
* Missing GROUP BY
* Invalid MSSQL syntax

This increased SQL correctness dramatically.

---

## **4. SQL Validation Pipeline**

Each query passes through:

1. **SQLNormalizer**
2. **Table usage validator**
3. **LangChain SQL checker**
4. **Custom QueryValidator**
5. **Self-correction loop**
6. **Safe pyodbc execution wrapper**

Result: almost no invalid SQL reaches the database.

---

## **5. Executive-Level Business Summaries (TR/EN)**

Generates clear business insights:

* Performance drivers
* Trends
* MoM / YoY analysis
* Category breakdowns
* Forecast-style commentary

Output language auto-matches input.

---

## **6. Streamlit UI**

Includes:

* Chat-like interface
* SQL viewer
* Data table results
* Optional charts
* Query history

---

# **System Architecture**

```
User (TR/EN)
    ↓
Intent Classifier
    ↓
Template Engine (fast-path)
    ↓
LangChain Schema Loader
    ↓
LLM SQL Generator (Ollama → OpenAI fallback)
    ↓
SQL Normalizer + Validator + LC Checker
    ↓
Safe SQL Execution (MSSQL)
    ↓
Business Summary Generator (TR/EN)
    ↓
Streamlit UI
```

---

# **Project Directory Structure (2025)**

```
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
│   │   ├── langchain_db.py
│   ├── tools
│   │   ├── sql_tools.py
│   ├── memory
│   │   ├── query_logger.py
│   ├── utils
│       ├── logger.py
├── tests
│   ├── run_test_scenarios.py
│   ├── test_scenarios.json
├── sql_table_validator.py
├── poc_interactive.py
├── poc_streamlit.py
├── requirements.txt
└── README.md
```

---

# **Installation & Setup**

## **1. Install dependencies**

```
pip install -r requirements.txt
```

## **2. Pull Ollama models**

```
ollama pull llama3.1:8b
ollama pull llama3.2:latest
```

## **3. Configure database**

In `.env` or `config.py`:

```
DB_SERVER=localhost
DB_NAME=ContosoRetailDW
DB_DRIVER=ODBC Driver 18 for SQL Server
```

## **4. Run Streamlit UI**

```
streamlit run poc_streamlit.py
```

## **5. Run interactive terminal**

```
python poc_interactive.py
```

---

# **Automated Test Suite**

Run:

```
python tests/run_test_scenarios.py
```

Tests:

* Intent detection
* SQL correctness
* Table usage (via LangChain schema)
* JOIN structure
* Execution safety
* Summary quality

Example scenario:

```
{
  "id": 1,
  "name": "Simple Aggregation",
  "question": "2008 yılında toplam satış nedir?",
  "expected_tables": ["FactSales", "DimDate"]
}
```

---

# **Example Supported Questions**

* **“2008 yılında toplam satış nedir?”** → Aggregation
* **“What are the top 5 products?”** → Ranking
* **“2007 mağaza vs online satış karşılaştırması”** → Comparison
* **“Show monthly trend for 2009”** → Trend
* **“En az satan ürün hangisi?”** → Ranking
* **“Which category performs best online?”** → Category analysis

---

# **Future Enhancements**

| Feature                           | Status      |
| --------------------------------- | ----------- |
| Advanced analytics dashboards     | Planned     |
| GPT-4o Mini fallback routing      | In progress |
| Multi-step SQL planning agent     | Planned     |
| Contoso-specific fine-tuned model | Research    |
| Multi-language conversational UI  | Planned     |

---

# **License**

This project is intended for **research, education, and prototyping**.
Production deployment requires additional security, monitoring, and scalability enhancements.

