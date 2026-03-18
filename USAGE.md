# User Guide: IETF Formal Protocol Compiler

Welcome to the **IETF Formal Protocol Compiler**. This tool transcends traditional RAG chat bots, transforming your computer into a strict, mathematically verifiable protocol extraction engine capable of traversing over 9,700 technical RFCs to compile deterministic Finite State Machines (FSMs).

This document explains how to use the Command Line Interface (CLI) to its full potential.

---

## The Command Line Interface (CLI)

The system is managed entirely through a single entry point: `src/main.py`.

You run this using `uv`, which ensures all dependencies are correctly loaded in the virtual environment.

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
Connects to the official IETF mirrors and downloads all RFC documents. It automatically prefers the semantically rich XML format, falling back to TXT for legacy documents, and strictly parses them into structured JSON trees.
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

These commands process the semantically parsed RFC JSONs and build the databases the AI needs to compile answers.

### `index`
This is the core processing engine. It reads all 9,700+ RFCs, splits them into semantic chunks using our "Parent-Child" architecture, generates vector embeddings, and builds a BM25 keyword index. 

You will see rich terminal progress bars as it works.

**To speed up indexing using an external OpenAI-compatible API (Recommended):**
```bash
export USE_OPENAI_EMBEDDINGS="true"
export OPENAI_API_BASE="http://10.83.6.175:8081/v1"
export EMBEDDING_MODEL="bge-m3" # Or your available embedding model
export OPENAI_API_KEY="sk-not-needed"

uv run python src/main.py index --force
```

**To run completely locally on your hardware (slower):**
```bash
uv run python src/main.py index --force
```
*   *Note: Local vector indexing uses your M4 Pro's GPU (MPS) and can take a very long time to complete a full run.*
*   *The `--force` flag ensures any old or corrupted database files are completely overwritten.*

### `build-graph`
Parses the RFCs to extract their relationships (e.g., "RFC 4271 Updates RFC 1771" or "RFC 4271 References RFC 793"). It builds a NetworkX Knowledge Graph (GraphRAG) saved to disk.
```bash
uv run python src/main.py build-graph
```

---

## 3. Compiling Protocols

This is how you interact with the LangGraph State Machine Agent to query and compile protocol features. 

*   **Prerequisite:** Ensure your local LLM server (e.g., `llama.cpp` hosting Qwen3.5-27B) is running on `http://localhost:8081` (or your configured IP). **Ensure temperature is set to 0 for deterministic results.**

### `ask` (Interactive Mode)
Starts a continuous, interactive compilation loop featuring Rich terminal rendering and dynamic status spinners. Type `exit` or `quit` to leave.
```bash
uv run python src/main.py ask
```

**Example Session:**
```text
╭──────────────────────────────────────────────────────────╮
│ Welcome to the IETF Formal Protocol Compiler.            │
│ Type 'exit' to quit.                                     │
╰──────────────────────────────────────────────────────────╯

Ask Protocol Question: How does the BGP FSM handle the Hold Timer expiring?

Compiling FSM for: How does the BGP FSM handle the Hold Timer expiring?
⠴ Running Formal Compiler Pipeline (Retrieving, Extracting, Proving)...

10/10 FORMAL COMPILER OUTPUT
╭──────────────────────── Compiled State Machine ────────────────────────╮
│ # Finite State Machine: BGP Hold Timer                             │
│                                                                        │
│ ...                                                                    │
╰────────────────────────────────────────────────────────────────────────╯

VERIFIED SOURCES
[1] rfc4271
    RFC 4271: A Border Gateway Protocol 4 (BGP-4)
    Section 8.2.2: State Machine ...
```

### `ask -q` (Single Shot Mode)
If you just want to compile one FSM and immediately exit (useful for scripting or quick lookups), use the `-q` flag.
```bash
uv run python src/main.py ask -q "What is the structure of the BGP OPEN message?"
```

---

## Under the Hood: The Compilation Pipeline

When you ask a question, you are triggering a rigorous, mathematically verifiable **LangGraph Pipeline**:

1.  **Multi-Query Hybrid Search:** The system searches the Vector Database (for semantic meaning) AND the BM25 Index (for exact acronyms) simultaneously.
2.  **Cross-Encoder Re-ranking:** It takes the candidate results and runs them through a Cross-Encoder to perfectly sort them by true relevance, keeping only the top chunks.
3.  **Strict LLM Fact Extraction:** Instead of chatting, the LLM is forced to output structured JSON representing the protocol's facts (States, Events, Conditions). It is strictly instructed to use **exact, verbatim text spans** from the RFC. No summarization or paraphrasing is allowed.
4.  **Mathematical Coverage Proofs:** Our deterministic Python `CoverageProofEngine` analyzes the retrieved RFC chunks. It identifies every "normative sentence" (containing MUST, SHOULD, MAY, MUST NOT). It then mathematically proves that the LLM's JSON output has accounted for every single normative requirement.
5.  **FSM Intermediate Representation (IR):** The extracted JSON is compiled into a strict Python object model. This step verifies structural integrity (e.g., catching paradoxes or missing transitions).
6.  **Self-Correcting Retry Loop:** If the Coverage Proofs or Structural Proofs fail, the LLM does not hallucinate an answer. Instead, the exact Python stack trace and missing coverage rules are fed back to the LLM, forcing it to retry the extraction. If it cannot solve the proofs after 3 tries, it outputs the compiler errors.

---

## Troubleshooting

-   **"Connection refused" or LLM Errors** 
    Your `llama.cpp` server is not running, or it is running on the wrong IP/Port. Ensure Qwen is actively being served on the URL defined in `rag_pipeline.py`.
-   **"Document store not found. Did you run indexing?"**
    You tried to ask a question before running the `index` command. You must build the database first.
-   **"JSON Schema Validation Failed"**
    The LLM failed to produce valid JSON during the extraction phase. This usually happens if the local LLM is too small or if the temperature is not set to `0.0`.
-   **SSL Errors during download**
    Ensure you are using the `download-models` command built into the tool, which has specialized logic to bypass corporate Zscaler/MITM proxies.
