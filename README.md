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


## Usage:
```
uv run python src/main.py ask -q "How OSPF & BGP work togather in L3VPN Solution"
Compiling FSM for: How OSPF & BGP work togather in L3VPN Solution
Phase 1: Multi-Query Hybrid Search...
[    ] Running Formal Compiler Pipeline (Retrieving, Extracting, Proving)...
- Generated queries: ['<analysis>', 'The original question is "How OSPF & BGP work togather in L3VPN Solution" (note the typo "togather"). I need to generate 3 alternative versions that would help retrieve relevant technical documents from a vector database. The goal is to create variations that capture different ways users might phrase this query while maintaining semantic similarity for effective retrieval.', 'Key concepts to preserve:', '- OSPF (Open Shortest Path First) - interior gateway protocol', '- BGP (Border Gateway Protocol) - exterior gateway protocol  ', '- L3VPN (Layer 3 Virtual Private Network)', '- How they interact/work together', "I'll create variations that:", '1. Use different phrasing while keeping technical accuracy', '2. Include related terminology that might appear in documents', '3. Vary the sentence structure and focus slightly', '4. Correct the typo "togather" to "together" or use alternative words like "interact", "integrate", etc.', 'Version 1: Focus on interaction/integration aspect', '"How do OSPF and BGP interact within an L3VPN architecture?"', 'Version 2: More detailed, mentioning routing specifically  ', '"What is the relationship between OSPF and BGP in Layer 3 VPN solutions for routing?"', 'Version 3: Broader scope, using "integration" terminology', '"Explain the integration of OSPF and BGP protocols in MPLS L3VPN environments"', 'These variations maintain semantic similarity while offering different phrasings that would match documents discussing this topic.', '</analysis>', 'How do OSPF and BGP interact within an L3VPN architecture?', 'What is the relationship between OSPF and BGP in Layer 3 VPN solutions for routing?', 'Explain the integration of OSPF and BGP protocols in MPLS L3VPN environments']
Architectural / Procedural Explanation

 The provided context describes the interaction between OSPF and BGP in Layer 3 Virtual Private Network (L3VPN) solutions through several key mechanisms:

 1. Basic Architecture (RFC 4577)

  • Customer Edge (CE) routers connect to Provider Edge (PE) routers
  • PE routers use BGP to distribute VPN routes among themselves across the provider backbone
  • CE routers peer with their attached PE router using OSPF as the routing protocol
  • CE routers at different sites do NOT peer directly with each other

 2. Route Distribution Problem and Solution Without modification, standard BGP/OSPF interaction would deliver inter-site routes as Type 5 LSAs (AS-external routes). This is undesirable because:

  • Routes from one VPN site to another should be treated as intra-network routes
  • They need to be distinguishable from "real" AS-external routes circulating in the VPN

 The solution: PE routers implement a modified BGP/OSPF interaction that delivers inter-site routes as Type 3 LSAs (inter-area routes), making them appear as OSPF intra-network routes.

 3. Key Requirements for L3VPN OSPF/BGP Interaction

  • No assumptions about OSPF topology (customer sites may not be stub/NSSA, may have multiple areas)
  • Routes between VPN sites in the same OSPF domain must be presented as intra-network routes
  • Supports "OSPF backdoor links" - direct OSPF connections between sites used when VPN backbone is unavailable

 4. BGP Identifier and OSPF Router ID Synchronization (RFC 1364) The BGP identifier MUST equal the OSPF router ID at all times when the router is up. This is required because:

  • ASBRs need to determine which router (RT1 or RT2) they're using to forward packets to an external network
  • The correct AS_PATH must be built based on matching BGP Identifier with OSPF routerID
  • Network administrators can correlate BGP and OSPF routes by identifier

 5. OSPF External Route Tag for BGP Attribute Setting (RFC 1364) The OSPF external route tag field is used to intelligently set BGP ORIGIN and AS_PATH attributes:


  +--+--+--+-+---------------------+--------------------+
  |a |c |p l|   ArbitraryTag       |  AutonomousSystem  |
  +--+--+--+-+---------------------+--------------------+


 Where:

  • a (Automatic bit): When set to 1, indicates Completeness and PathLength bits were auto-generated
  • c (Completeness bit): Indicates route completeness information
  • pl (PathLength - 2 bits): Contains path length information
  • ArbitraryTag: User-defined tag value
  • AutonomousSystem: AS number information

 This mechanism allows ASBRs to advertise routes to external ASes without waiting for IBGP updates.

 6. OSPFv3 Extension (RFC 6565) For IPv6 VPNs, OSPFv3 routes are translated to BGP VPN-IPv6 routes using Extended Communities:


  Attribute               Type Value(s)              Size
  ───────────────────────────────────────────────────────────────────────
  OSPF Domain Identifier  0x0005, 0x0105, or 0x0205  6 bytes (default: 0)
  OSPF Router ID          0x0107                     4 bytes


 Each OSPFv3 route added to the VRF routing table MUST have corresponding BGP Extended Communities Attributes preserving the original OSPFv3 information.

 7. Graceful Link Shutdown (RFC 8379) When a PE router is taken out of service:

  • All links on the PE can be set to graceful-link-shutdown state
  • This guarantees traffic diversion for dual-homed CEs
  • Sham links can also use this mechanism without touching remote-end configurations

 Summary Flow:


  CE (Site A) --OSPF--> PE(A) --BGP VPN routes-- Backbone -- BGP VPN routes --> PE(B) --OSPF--> CE (Site B)


 The key innovation is that inter-site routes appear as Type 3 LSAs (inter-area) rather than Type 5 LSAs (AS-external), preserving the illusion of a single OSPF domain across the VPN.

Verified Context Sources
 [1] RFC8379 - Section 7.3: L3VPN Services and Sham Links
 [2] RFC4577 - Section 3: Requirements, Section 1: Introduction
 [3] RFC1364 - Section 3: BGP Identifier and OSPF router ID, Section 4: Setting OSPF tags, BGP ORIGIN and AS_PATH attributes
 [4] RFC5252 - Section 1: Introduction
 [5] RFC6565 - Section 4.4: BGP Extended Communities Attributes
```
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
