# IETF Formal Protocol Compiler

A mathematically verifiable, Agentic Retrieval-Augmented Generation (RAG) system designed to ingest, index, and compile the complete library of IETF RFCs (9,700+ documents) into deterministic Finite State Machines (FSMs). 

This system is optimized for **Protocol Developers and Network Architects** who require mathematically sound, hallucination-free protocol specifications with exact, provable traceability back to the normative text of the original RFCs.

## 🚀 SOTA Architecture (2026 Edition)

This system abandons the traditional "chatbot" RAG approach in favor of a **Formal Compilation Pipeline**:

### 1. Structured Semantic Ingestion
- **Semantic XML Parsing:** The ingest pipeline (`rfc_xml_parser.py`) processes raw RFCs, preserving strict hierarchical trees and heuristically classifying sections (e.g., `STATE_MACHINE`, `TIMER_LOGIC`, `ERROR_HANDLING`).
- **Parent-Child Architecture:** Documents are indexed using small, high-density **Child Chunks (800 chars)** for precise vector matching, while retrieving massive **Parent Chunks (3,000 chars)** to provide full structural context.
- **Hybrid Ensemble Search:** Combines **Vector Similarity** (Semantic understanding) with **BM25 Keyword Search** (Lexical precision for acronyms like BGP, OSPF).

### 2. Formal Compilation Pipeline
- **Strict Fact Extraction:** Instead of generating text, the LLM is forced to act as an extraction engine, generating structured JSON representations of states, events, conditions, and actions using *exact, verbatim text spans*.
- **Mathematical Coverage Proofs:** A deterministic Python engine (`CoverageProofEngine`) mathematically verifies that *every single normative sentence* (containing MUST, SHOULD, MAY, MUST NOT) in the retrieved context has been successfully mapped to an atomic protocol fact.
- **FSM Intermediate Representation (IR):** Extracted facts are parsed into a strongly-typed Intermediate Representation (`protocol_ir.py`), validating topological integrity (e.g., ensuring no dangling states or unhandled events).
- **Self-Correcting Feedback Loop:** If the coverage proofs or structural proofs fail, the LangGraph agent intercepts the exact Python stack trace/errors, formulates a critique, and forces the LLM to re-extract the facts until mathematical completeness is achieved.

### 3. Local-First Technical Stack
- **Inference:** OpenAI-compatible local server hosting models like **Qwen3.5-27B** set to `Temperature=0.0` for maximum determinism.
- **Embeddings & Reranking:** Leverages `BAAI/bge-m3` and `bge-reranker-v2-m3`. Includes full support for **Apple Silicon (MPS)**, or offloading to external OpenAI-compatible endpoints (vLLM/Ollama) for extreme speed.
- **Corporate Ready:** Custom SSL-bypass utilities for environments behind MITM proxies (Zscaler, etc.).

---

## 🛠️ Installation & Setup

### Prerequisites
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Local LLM Server (e.g., `llama.cpp`, `vLLM`, or `Ollama`) hosting a capable LLM.

### 1. Sync Environment
```bash
uv sync
```

### 2. Download SOTA Models
Built-in utility to bypass corporate SSL issues and download the BAAI models locally:
```bash
uv run python src/main.py download-models
```

### 3. Ingest IETF RFCs
Download and parse all 9,700+ RFCs into structured JSON:
```bash
uv run python src/main.py ingest
```

### 4. Build the Knowledge Base
Build the vector database, BM25 index, and relationship graph.

**Speed up Indexing with an API Endpoint (Recommended):**
You can massively improve indexing speed by offloading embeddings to an OpenAI-compatible API (e.g., vLLM or Ollama on a server) instead of running them locally on your GPU/CPU:
```bash
export USE_OPENAI_EMBEDDINGS="true"
export OPENAI_API_BASE="http://10.83.6.175:8081/v1"
export EMBEDDING_MODEL="nomic-embed-text" # Adjust as needed
export OPENAI_API_KEY="sk-not-needed"

uv run python src/main.py index --force
```

Or run it entirely locally (slower):
```bash
uv run python src/main.py index --force
```

Build the knowledge graph:
```bash
uv run python src/main.py build-graph
```

---

## 💬 Usage

### Interactive Mode
Start an interactive CLI session featuring rich terminal rendering and progress tracking:
```bash
uv run python src/main.py ask
```

### Single Question
```bash
uv run python src/main.py ask -q "How does the BGP FSM handle the Hold Timer expiring?"
```

---

## 📁 Project Structure
- `src/main.py`: Unified Rich CLI entry point.
- `src/data_ingestion/`: Ingests and semantically parses RFCs (`rfc_xml_parser.py`).
- `src/knowledge_base/`:
    - `vector_store.py`: Parent-Child indexing logic + ChromaDB.
    - `graph_store.py`: Relationship graph builder.
- `src/qa_system/`:
    - `rag_pipeline.py`: LangGraph State Machine agent managing the proof loops.
    - `protocol_compiler.py` & `protocol_ir.py`: The formal Python engines enforcing structural/normative proofs.
- `src/utils/model_downloader.py`: SSL-bypassing model utility.

---

## ⚖️ Verification Methodology
The system does not "answer" questions. It **compiles** state machines. 
If the required protocol logic is not found in the documents, or if the LLM cannot extract the facts without violating the mathematical coverage proofs, the compilation will fail gracefully rather than risk generating a hallucinated protocol implementation.
