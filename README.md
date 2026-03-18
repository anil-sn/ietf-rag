# IETF Formal Protocol Compiler

A mathematically verifiable, Agentic Retrieval-Augmented Generation (RAG) system designed to ingest, index, and compile the complete library of IETF RFCs (9,700+ documents) into deterministic Finite State Machines (FSMs). 

This system is optimized for **Protocol Developers and Network Architects** who require mathematically sound, hallucination-free protocol specifications with exact, provable traceability back to the normative text of the original RFCs.

## 🚀 SOTA Architecture (2026 Edition)

This system transcends traditional "chat-with-your-PDF" systems. It is engineered as a deterministic pipeline designed for maximum factual fidelity. Here are the core techniques implemented:

### 1. Structured Semantic Ingestion & Metadata Tagging
*   **XML Semantic Parsing:** Instead of blindly chunking plain text, the system downloads raw XML RFCs and traverses the Document Object Model (DOM). It preserves the exact structural hierarchy (`root_section`, `section_number`).
*   **Heuristic Typing:** It automatically classifies sections based on titles (e.g., tagging a section as `STATE_MACHINE`, `TIMER_LOGIC`, or `SECURITY_CONSIDERATIONS`). This allows for highly targeted retrieval contexts later.

### 2. Parent-Child Chunking Architecture
*   **The Context vs. Precision Dilemma:** Traditional RAG uses one chunk size. If chunks are too large, vector search loses precision. If chunks are too small, the LLM loses the surrounding context (e.g., it sees "Timer expires" but not "Which timer in which state?").
*   **Child Chunks (800 chars):** Used *exclusively* for vector indexing and similarity search. Because they are small, they map tightly to specific concepts, ensuring high retrieval accuracy.
*   **Parent Chunks (3000 chars):** When a Child Chunk is matched during a search, the system *does not* return the child to the LLM. Instead, it traces back and retrieves the massive Parent Chunk. This ensures the LLM sees the complete logical section, eliminating "lost-in-the-middle" context issues.

### 3. SOTA Embeddings (`BAAI/bge-m3`)
*   **Multi-Lingual, Multi-Function:** We utilize the BGE-M3 model, one of the top open-source embedding models available. 
*   **8k Context Window:** It natively supports up to 8,192 tokens. This is crucial for networking standards where technical vocabulary stretches over long paragraphs.
*   **Dense Vectors:** Text is converted into high-dimensional mathematical representations, allowing the system to understand semantic similarity.

### 4. Multi-Query Expansion
*   **Lexical Gap Bridging:** Users rarely ask questions using the exact terminology found in an RFC.
*   **LLM Brainstorming:** Before searching the database, the local Qwen LLM intercepts the user's question and generates 3 distinct, highly technical variations. 
*   **Example:** "How OSPF & BGP work together" is expanded into "Explain OSPF BGP interaction in MPLS Layer 3 VPN architecture." All variations are searched simultaneously.

### 5. Hybrid Ensemble Retrieval
*   **Vector Search (Semantic):** Uses ChromaDB and BGE-M3 to find chunks based on *meaning*. Great for conceptual questions.
*   **BM25 Keyword Search (Lexical):** Uses a traditional, TF-IDF based keyword search. Crucial for finding exact acronyms (BGP, OSPF, LSA) which vector models sometimes blur.
*   **Ensemble Weighting:** The system retrieves results from both engines and blends them using a weighted score (60% Vector / 40% Keyword).

### 6. Cross-Encoder Re-ranking (`BAAI/bge-reranker-v2-m3`)
*   **The Filtering Phase:** Initial retrieval often returns "noisy" results (e.g., retrieving an RFC that just happens to mention "OSPF" in the glossary).
*   **Deep Scoring:** The system takes the top 20 messy results from the Hybrid Search and feeds them into a specialized Cross-Encoder neural network. The Cross-Encoder reads the original question *and* the document chunk simultaneously, assigning an absolute relevance score. Only the top 7 ultra-relevant chunks survive.

### 7. Formal LLM Fact Extraction (Zero Temperature)
*   **Strict JSON Contract:** The LLM (`Qwen3.5-27B.Q4_K_M`) is configured with `Temperature=0.0` (zero creativity). It is instructed *not* to converse.
*   **Verbatim Spans:** It must extract protocol facts (States, Events, Timers) into a strict JSON schema. Crucially, the text must be an *exact string match* copied from the RFC. No paraphrasing is allowed.

### 8. Deterministic Coverage Proofs (Python Engine)
*   **Anti-Hallucination Mechanism:** The `CoverageProofEngine` is a hardcoded Python script. It parses the retrieved RFC text and identifies every "Normative Sentence" (any sentence containing `MUST`, `SHOULD`, `MAY`, or `MUST NOT`).
*   **Mathematical Verification:** The Python engine checks the LLM's JSON output to prove that *every single normative sentence* was mapped to a fact. If the LLM misses a constraint, the proof fails.

### 9. Agentic Retry Loops (LangGraph)
*   **Self-Correction:** If the Python Coverage Proof fails, the system does not crash. LangGraph orchestrates a feedback loop.
*   **Critique Injection:** The exact Python stack trace (e.g., *"Normative sentence dropped: 'The Hold Time MUST be either zero...'"*) is fed *back* to the LLM. The LLM is forced to retry the extraction and fix its mistakes (up to 3 attempts).

### 10. Abstract Syntax Tree (AST) & FSM Compilation
*   **Structural Proofs:** Once extraction passes sentence coverage, the facts are compiled into a Python Object Graph (`ProtocolCompiler`). 
*   **Logical Validation:** The compiler checks for topological paradoxes (e.g., a transition pointing to a non-existent state, or two transitions triggering on the exact same event/condition). 
*   **Graceful Degradation:** If the question is purely architectural (and lacks FSM facts), the compiler gracefully falls back to displaying a high-fidelity technical explanation rather than throwing an error.

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
