# IETF Formal Protocol Compiler

A mathematically verifiable, Agentic Retrieval-Augmented Generation (RAG) system designed to ingest, index, and compile the complete library of IETF RFCs (9,700+ documents) into deterministic Finite State Machines (FSMs).

This system is optimized for **Protocol Developers and Network Architects** who require mathematically sound, hallucination-free protocol specifications with exact, provable traceability back to the normative text of the original RFCs.

---

## ✨ Core Features & Architecture

This system transcends traditional "chat-with-your-PDF" systems. It is engineered as a deterministic pipeline designed for maximum factual fidelity.

### 1. Structured Semantic Ingestion & Metadata Tagging
*   **XML Semantic Parsing:** Instead of blindly chunking plain text, the system downloads raw XML RFCs and traverses the Document Object Model (DOM).
*   **Heuristic Typing:** Automatically classifies sections based on titles (e.g., `STATE_MACHINE`, `TIMER_LOGIC`).

### 2. Parent-Child Chunking Architecture
*   **Child Chunks (800 chars):** Used for precision vector indexing and similarity search.
*   **Parent Chunks (3000 chars):** Retrieves the complete logical section for the LLM, eliminating "lost-in-the-middle" context issues.

### 3. SOTA Embeddings & Re-ranking
*   **BAAI/bge-m3:** Multi-functional embeddings with an 8k context window.
*   **BAAI/bge-reranker-v2-m3:** A second-pass Cross-Encoder that scores relevance for the top 20 messy results, keeping only the top 7 ultra-relevant chunks.

### 4. Hybrid Ensemble Retrieval
*   **Ensemble Search:** Blends Vector Search (semantic) with BM25 Keyword Search (lexical) using a weighted score (60/40).

### 5. Agentic Proof Loops (LangGraph)
*   **Deterministic Coverage Proofs:** A Python engine identifies every "Normative Sentence" (`MUST`, `SHOULD`, etc.) and proves the LLM accounted for it.
*   **Self-Correction:** If proofs fail, LangGraph feeds the stack trace back to the LLM for up to 3 retry attempts.

---

## 🛠️ Installation & Setup

### Prerequisites
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Local LLM Server (e.g., `llama.cpp`, `vLLM`, or `Ollama`) hosting a capable LLM (e.g., Qwen 3.5).

### 1. Sync Environment
```bash
uv sync
```

### 2. Download Models
Download the BAAI models locally (includes SSL bypass for corporate networks):
```bash
uv run python src/main.py download-models
```

### 3. Ingest IETF RFCs
Download and parse all 9,700+ RFCs:
```bash
uv run python src/main.py ingest
```

### 4. Build Knowledge Base
Build the vector database and BM25 index:
```bash
# Recommended: Use an API endpoint for faster indexing
export USE_OPENAI_EMBEDDINGS="true"
export OPENAI_API_BASE="http://localhost:8081/v1"
uv run python src/main.py index --force

# Build the relationship graph
uv run python src/main.py build-graph
```

---

## 🚀 Quick Start & Usage

### Interactive Mode
Start an interactive CLI session with rich terminal rendering:
```bash
uv run python src/main.py ask
```

### Single Question
Compile a specific protocol feature and exit:
```bash
uv run python src/main.py ask -q "How does the BGP FSM handle the Hold Timer expiring?"
```

> [!TIP]
> For a comprehensive guide on all commands and advanced indexing, see [USAGE.md](./USAGE.md).

---

## 📁 Project Structure
- `src/main.py`: Unified Rich CLI entry point.
- `src/data_ingestion/`: Ingests and semantically parses RFCs.
- `src/knowledge_base/`: Vector store (Parent-Child) and Relationship Graph.
- `src/qa_system/`: LangGraph RAG pipeline and Formal Protocol Compiler.
- `src/utils/`: Support utilities including model downloaders.

---

## ⚖️ Verification Methodology
The system does not "answer" questions; it **compiles** state machines. If required protocol logic is missing or if the LLM cannot satisfy the mathematical coverage proofs, the compilation fails gracefully rather than risk generating a hallucinated protocol implementation.
