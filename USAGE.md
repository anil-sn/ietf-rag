# User Guide: IETF RAG System

Welcome to the **IETF Networking Standards RAG System**. This tool transforms your computer into an expert "Senior Network Architect," capable of traversing over 9,700 technical RFCs to provide exact, sourced, and hallucination-free answers about networking protocols.

This document explains how to use the Command Line Interface (CLI) to its full potential.

---

## The Command Line Interface (CLI)

The system is managed entirely through a single entry point: `src/main.py`.

You can run this using `uv`, which ensures all dependencies are correctly loaded in the virtual environment.

**General syntax:**
```bash
uv run python src/main.py [ACTION] [OPTIONS]
```

---

## 1. Setup & Ingestion Commands

These commands are used to prepare the system and download necessary data. You typically only need to run these once, or occasionally when you want to update your RFC library.

### `download-models`
Downloads the required open-source AI models (`BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3`) directly to your local machine. This command is specifically designed with an aggressive SSL bypass to work behind corporate MITM proxies (like Zscaler).
```bash
uv run python src/main.py download-models
```

### `ingest`
Connects to the official IETF mirrors and downloads all RFC documents. It automatically chooses the cleanest format available (preferring XML over TXT) and consolidates them into Markdown-compatible files.
```bash
uv run python src/main.py ingest
```
*   **Optional Flag: `--rsync`**
    If you are on an unrestricted network (port 873 open), you can use rsync for much faster, delta-based updates.
    ```bash
    uv run python src/main.py ingest --rsync
    ```

---

## 2. Indexing Commands

These commands process the raw text of the RFCs and build the databases the AI needs to answer questions.

### `index`
This is the core processing engine. It reads all 9,700+ RFCs, splits them into semantic chunks using our "Parent-Child" architecture, generates vector embeddings using your M4 Pro GPU, and builds a BM25 keyword index.
```bash
uv run python src/main.py index --force
```
*   *Note: This process is extremely computationally heavy. Expect it to take 1 to 2 hours to complete a full run.*
*   *The `--force` flag ensures any old or corrupted database files are completely overwritten.*

### `build-graph`
Parses the RFCs to extract their relationships (e.g., "RFC 4271 Updates RFC 1771" or "RFC 4271 References RFC 793"). It builds a NetworkX Knowledge Graph (GraphRAG) saved to disk.
```bash
uv run python src/main.py build-graph
```

---

## 3. Querying the System

This is how you interact with the LangGraph Agent to ask questions. 

*   **Prerequisite:** Ensure your local LLM server (e.g., `llama.cpp` hosting Qwen3.5-27B) is running on `http://localhost:8081` (or your configured IP).

### `ask` (Interactive Mode)
Starts a continuous, interactive Q&A loop. This is the best way to have a conversation with the system. Type `exit` or `quit` to leave.
```bash
uv run python src/main.py ask
```

**Example Session:**
```text
Welcome to the IETF RAG Q&A System. Type 'exit' to quit.

Please ask your question: How does OSPF establish neighbor adjacencies?

2026-03-18 12:45:01 - INFO - Received question: How does OSPF establish neighbor adjacencies?
2026-03-18 12:45:01 - INFO - Step 1: Multi-Query Hybrid Search...
2026-03-18 12:45:10 - INFO - Step 2: Reranking candidate chunks...
2026-03-18 12:45:12 - INFO - Agent: Grading document relevance...
2026-03-18 12:45:15 - INFO - Agent: Synthesizing final expert answer...

======================================================================
SOTA GENERATED ANSWER:
======================================================================
According to RFC 2328, OSPF establishes neighbor adjacencies through the Hello Protocol and the Database Exchange process...
```

### `ask -q` (Single Shot Mode)
If you just want to ask one question and immediately exit (useful for scripting or quick lookups), use the `-q` flag.
```bash
uv run python src/main.py ask -q "What is the structure of the BGP OPEN message?"
```

---

## Under the Hood: How Your Question is Processed

When you ask a question, you are triggering a sophisticated **Agentic Corrective-RAG (CRAG)** workflow:

1.  **Query Expansion:** The local Qwen LLM intercepts your question and brainstorms 3-5 technical variations to ensure it catches all relevant terminology (e.g., expanding "adjacency" to include "state machine", "hello packets").
2.  **Hybrid Retrieval:** It searches the Vector Database (for semantic meaning) AND the BM25 Index (for exact acronyms) simultaneously.
3.  **Cross-Encoder Re-ranking:** It takes the top 20 messy results and runs them through the `bge-reranker-v2-m3` model to perfectly sort them by relevance, keeping only the top 5.
4.  **Self-Reflection (Grading):** The Qwen LLM silently reads the 5 chunks and grades them. If the chunks *don't* actually contain the answer, the Agent triggers a "Fallback" (refusing to answer) to absolutely guarantee zero hallucinations.
5.  **Synthesis:** The LLM reads the verified technical context and drafts an exhaustive response citing specific RFC sections.

---

## Troubleshooting

-   **"Error: LLM is not initialized."** 
    Your `llama.cpp` server is not running, or it is running on the wrong IP/Port. Ensure Qwen is actively being served on the URL defined in `rag_pipeline.py`.
-   **"Document store not found. Did you run indexing?"**
    You tried to ask a question before running the `index` command. You must build the database first.
-   **SSL Errors during download**
    Ensure you are using the `download-models` command built into the tool, which has specialized logic to bypass corporate Zscaler/MITM proxies.
