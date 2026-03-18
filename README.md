# IETF Networking Standards SOTA RAG System

A State-of-the-Art (SOTA) Agentic Retrieval-Augmented Generation (RAG) system designed to ingest, index, and query the complete library of IETF RFCs (9,700+ documents). This system is optimized for **Senior Network Architects** and protocol developers, providing technical, sourced, and architecturally sound answers.

## 🚀 SOTA Architecture (2026 Edition)

This system implements the bleeding edge of RAG techniques:

### 1. Advanced Indexing & Retrieval
- **Embedding Model:** `BAAI/bge-m3` - Multi-lingual, multi-function model with an **8,192 token context window**, essential for long technical RFCs.
- **Parent-Child Architecture:** Documents are indexed using small, high-density **Child Chunks (800 chars)** for precise vector matching, while retrieving massive **Parent Chunks (3,000 chars)** to provide the LLM with full structural context.
- **Hybrid Ensemble Search:** Combines **Vector Similarity** (Semantic understanding) with **BM25 Keyword Search** (Lexical precision for acronyms like BGP, OSPF, LSA).
- **GraphRAG:** A **NetworkX-based Knowledge Graph** that maps relationships between RFCs (Updates, Obsoletes, References) to enable multi-hop reasoning.

### 2. Agentic Reasoning (Corrective-RAG)
- **LangGraph Orchestration:** The pipeline is a state-machine agent that doesn't just "retrieve and generate."
- **Multi-Query Expansion:** The system uses the LLM to brainstorm multiple technical variations of the user's question to bridge the lexical gap.
- **Cross-Encoder Reranking:** Candidate results are re-scored using `BAAI/bge-reranker-v2-m3` to filter out noise.
- **Self-Reflection Grading:** The agent evaluates the relevance of retrieved documents before answering. If documents are irrelevant, it triggers a **Corrective Fallback** instead of hallucinating.

### 3. Local-First Technical Stack
- **Inference:** OpenAI-compatible local server (e.g., `llama.cpp`) hosting **Qwen3.5-27B**.
- **Hardware Acceleration:** Full support for **Apple Silicon (MPS)**, leveraging the GPU/Neural Engine of M4 Pro/Max chips for embeddings and reranking.
- **Corporate Ready:** Custom SSL-bypass utilities for environments behind MITM proxies (Zscaler, etc.).

---

## 🛠️ Installation & Setup

### Prerequisites
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Local LLM Server (e.g., `llama.cpp` or `Ollama`) hosting `Qwen3.5-27B`.

### 1. Sync Environment
```bash
uv sync
```

### 2. Download SOTA Models
We have built a utility to bypass corporate SSL issues and download the BAAI models locally:
```bash
uv run python src/main.py download-models
```

### 3. Ingest IETF RFCs
Download and consolidate all 9,700+ RFCs (prefers XML, falls back to TXT):
```bash
uv run python src/main.py ingest
```

### 4. Build the Knowledge Base
Build the vector database, BM25 index, and relationship graph.
*Note: The vector indexing uses your M4 Pro's GPU (MPS) and takes a very long time for the full library.*

**Speed up Indexing with an API Endpoint:**
You can massively improve indexing speed by offloading embeddings to an OpenAI-compatible API (e.g., vLLM or Ollama on a server) instead of running them locally:
```bash
export USE_OPENAI_EMBEDDINGS="true"
export OPENAI_API_BASE="http://10.83.6.175:8081/v1"
export EMBEDDING_MODEL="nomic-embed-text" # Adjust as needed
export OPENAI_API_KEY="sk-not-needed"

uv run python src/main.py index --force
```

Or just run it locally (slower):
```bash
# Build Vector & BM25 Index
uv run python src/main.py index --force
```

```bash
# Build Relationship Graph
uv run python src/main.py build-graph
```

---

## 💬 Usage

### Interactive Mode
Start an expert session with the Senior Network Architect agent:
```bash
uv run python src/main.py ask
```

### Single Question
```bash
uv run python src/main.py ask -q "How does the BGP OPEN message handle capabilities negotiation?"
```

---

## 📁 Project Structure
- `src/main.py`: Unified CLI entry point.
- `src/data_ingestion/`: Ingests RFCs from official IETF mirrors.
- `src/knowledge_base/`:
    - `vector_store.py`: Parent-Child indexing logic + ChromaDB.
    - `graph_store.py`: Relationship graph builder.
- `src/qa_system/rag_pipeline.py`: LangGraph CRAG Agent logic.
- `src/utils/model_downloader.py`: SSL-bypassing model utility.
- `models/`: Local storage for BGE-M3 and Reranker.
- `data/`: Local storage for RFC text, Vector DB, and Graphs.

---

## ⚖️ Technical Persona
The system is prompted to act as a **Senior Network Architect**. It provides:
1. Deeply technical explanations of protocol state machines and packet formats.
2. Direct citations to RFC numbers and sections.
3. Strict factual grounding (refuses to answer if the information is not in the indexed RFCs).
