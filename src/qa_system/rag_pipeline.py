import os
import pickle
import logging
import warnings
import torch

# Suppress annoying 3rd party warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")
try:
    from requests.exceptions import RequestsDependencyWarning
    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except ImportError:
    pass

os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"

from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_classic.retrievers.parent_document_retriever import ParentDocumentRetriever
from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.stores import InMemoryStore
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import ValidationError

from qa_system.protocol_compiler import ExtractionOutput, CoverageProofEngine, ProtocolCompiler, CoverageError

# Silence verbose logging for 3rd party libs but keep our pipeline logs
logging.basicConfig(level=logging.INFO, format='%(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

class LocalCrossEncoderReranker:
    def __init__(self, model_name="models/bge-reranker-v2-m3"):
        from sentence_transformers import CrossEncoder
        logging.info(f"Loading CrossEncoder Reranker Model: {model_name} on {DEVICE.upper()}...")
        self.encoder = CrossEncoder(model_name, device=DEVICE, local_files_only=True)
        
    def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
        if not documents: return []
        pairs = [[query, doc.page_content] for doc in documents]
        # Set show_progress_bar=False to keep CLI clean
        scores = self.encoder.predict(pairs, show_progress_bar=False)
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, score in scored_docs[:top_k]]

class GraphState(TypedDict):
    question: str
    documents: List[Document]
    extraction_output: ExtractionOutput
    generation: str
    verification_errors: List[str]
    verification_attempts: int
    sources: List[dict]

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

class QASystem:
    VECTOR_DB_PATH = "data/chroma_db"
    STORE_PATH = "data/doc_store"
    COLLECTION_NAME = "networking_standards"
    EMBEDDING_MODEL_NAME = "models/bge-m3"

    def __init__(self, model_name: str = "Qwen3.5-27B.Q4_K_M.gguf", base_url: str = "http://10.83.6.175:8081/v1"):
        logging.info(f"Initializing 10/10 Formal Protocol Compiler with LLM {model_name}...")

        # Check LLM Server Connectivity
        import requests
        try:
            requests.get(f"{base_url}/models", timeout=5)
        except Exception as e:
            logging.error(f"CRITICAL: Cannot reach LLM Server at {base_url}. Is it running? Error: {e}")

        self.use_openai_embeddings = os.environ.get("USE_OPENAI_EMBEDDINGS", "false").lower() == "true"

        if self.use_openai_embeddings:
            emb_base_url = os.environ.get("OPENAI_API_BASE", "http://10.83.6.175:8081/v1")
            emb_api_key = os.environ.get("OPENAI_API_KEY", "sk-not-needed")
            emb_model = os.environ.get("EMBEDDING_MODEL", "bge-m3") 

            logging.info(f"Loading OpenAI-compatible embedding model ({emb_model}) from {emb_base_url}...")
            self.embeddings = OpenAIEmbeddings(
                model=emb_model,
                openai_api_base=emb_base_url,
                openai_api_key=emb_api_key,
                check_embedding_ctx_length=False
            )
        else:
            logging.info(f"Loading local embedding model from {self.EMBEDDING_MODEL_NAME} on {DEVICE.upper()}...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.EMBEDDING_MODEL_NAME,
                model_kwargs={'device': DEVICE, 'local_files_only': True},
                encode_kwargs={'normalize_embeddings': True},
                show_progress=False # Keep CLI clean
            )

        self.vector_store = Chroma(
            collection_name=self.COLLECTION_NAME,
            embedding_function=self.embeddings,
            persist_directory=self.VECTOR_DB_PATH
        )
        
        self.llm = ChatOpenAI(
            base_url=base_url,
            api_key="sk-not-needed", 
            model=model_name,
            temperature=0.0, # Zero temp for strict parsing
            max_tokens=4096,
            timeout=120 # 2 minute timeout for complex extractions
        )
        
        doc_store_path = os.path.join(self.STORE_PATH, "store.pkl")
        store = InMemoryStore()
        if os.path.exists(doc_store_path):
            with open(doc_store_path, "rb") as f:
                store.mset(list(pickle.load(f).items()))
                
        parent_retriever = ParentDocumentRetriever(
            vectorstore=self.vector_store,
            docstore=store,
            child_splitter=RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100),
            parent_splitter=RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=300),
            search_kwargs={"k": 20}
        )

        bm25_docs_path = os.path.join(self.STORE_PATH, "bm25_docs.pkl")
        if os.path.exists(bm25_docs_path):
            with open(bm25_docs_path, "rb") as f:
                keyword_retriever = BM25Retriever.from_documents(pickle.load(f))
                keyword_retriever.k = 15
            ensemble_retriever = EnsembleRetriever(retrievers=[parent_retriever, keyword_retriever], weights=[0.6, 0.4])
        else:
            ensemble_retriever = parent_retriever

        multi_query_prompt = PromptTemplate(
            input_variables=["question"],
            template="""You are an AI assistant. Generate 3 different versions of the given user question to retrieve relevant technical documents from a vector database.
CRITICAL: Output ONLY the 3 alternative questions, separated by newlines. Do NOT output any conversational text, introductory remarks, markdown formatting, or reasoning. Just 3 lines of text.
Original question: {question}"""
        )

        self.retriever = MultiQueryRetriever.from_llm(retriever=ensemble_retriever, llm=self.llm, prompt=multi_query_prompt)
        
        try:
            self.reranker = LocalCrossEncoderReranker()
        except Exception as e:
            logging.warning(f"Could not load local reranker. Skipping. {e}")
            self.reranker = None

        self.app = self._build_agent_graph()
        logging.info("SOTA 10/10 Formal Protocol Compiler is ready.")

    def _build_agent_graph(self):
        workflow = StateGraph(GraphState)
        
        workflow.add_node("retrieve_and_rerank", self.node_retrieve_and_rerank)
        workflow.add_node("extract_atomic_facts", self.node_extract_atomic_facts)
        workflow.add_node("compile_and_prove", self.node_compile_and_prove)
        
        workflow.set_entry_point("retrieve_and_rerank")
        
        workflow.add_conditional_edges(
            "retrieve_and_rerank",
            self.edge_has_documents,
            {
                "proceed": "extract_atomic_facts",
                "stop": END
            }
        )
        
        workflow.add_edge("extract_atomic_facts", "compile_and_prove")
        
        workflow.add_conditional_edges(
            "compile_and_prove",
            self.edge_check_proofs,
            {
                "pass": END,
                "retry": "extract_atomic_facts"
            }
        )
        
        return workflow.compile()

    def edge_has_documents(self, state: GraphState):
        if not state["documents"]: return "stop"
        return "proceed"

    def node_retrieve_and_rerank(self, state: GraphState):
        question = state["question"]
        logging.info("Phase 1: Multi-Query Hybrid Search...")
        raw_docs = self.retriever.invoke(question)
        unique_docs = {doc.page_content: doc for doc in raw_docs}.values()
        
        # Group docs by root section
        grouped_docs = sorted(list(unique_docs), key=lambda d: d.metadata.get('root_section', '0'))
        
        if self.reranker:
            best_docs = self.reranker.rerank(question, grouped_docs, top_k=7)
        else:
            best_docs = grouped_docs[:7]
            
        if not best_docs:
            return {"documents": [], "question": question, "generation": "The provided context does not contain sufficient information to compile a state machine deterministically."}
            
        return {"documents": best_docs, "question": question}

    def format_docs_for_extraction(self, docs):
        formatted = []
        for doc in docs:
            src = doc.metadata.get('source_file', 'Unknown')
            sec_num = doc.metadata.get('section_number', 'N/A')
            chunk_id = doc.metadata.get('chunk_id', '0')
            formatted.append(f"[Source: {src}, Section: {sec_num}, Chunk: {chunk_id}]\n{doc.page_content}\n")
        return "\n---\n".join(formatted)

    def node_extract_atomic_facts(self, state: GraphState):
        logging.info(f"Phase 2: LLM Strict Extraction (Attempt {state.get('verification_attempts', 0) + 1})...")
        
        critique = ""
        if state.get("verification_errors"):
            critique = "\nYOUR PREVIOUS EXTRACTION FAILED FORMAL PROOFS:\n" + "\n".join(state["verification_errors"]) + "\nYOU MUST FIX THESE ERRORS BY MAPPING ALL NORMATIVE SENTENCES."

        prompt = PromptTemplate(
            template="""You are a Protocol Fact Extraction Engine.
Your task is to extract ONLY explicitly stated, VERBATIM protocol facts from the provided RFC context.

You are NOT allowed to:
- Summarize
- Infer missing logic
- Combine multiple sentences into one fact
- Modify or normalize text

--------------------------------------------------
MANDATORY RULES
--------------------------------------------------
1. TEXT SPAN (CRITICAL): MUST be copied EXACTLY from the context. NO paraphrasing.
2. SENTENCE COVERAGE: You MUST process EVERY normative sentence (containing MUST, SHOULD, MAY, MUST NOT). If a sentence contains a normative keyword, it MUST map to AT LEAST ONE fact in your `sentence_links` output.
3. ATOMICITY: Each fact MUST come from ONE sentence only. Do NOT merge multiple sentences.
4. NO GUESSING: If information is unclear → DO NOT create a fact.
5. RAW ENTITIES: Extract EXACT tokens from text (e.g., "Hold Timer", "Idle state").
6. FAILURE MODE & ARCHITECTURAL QUESTIONS: 
   - If the user's question is about general architecture or procedure (e.g., "How does X work with Y?") rather than a specific Finite State Machine, AND the context contains no FSM normative rules...
   - DO NOT fail. Instead, leave the `facts` and `sentence_links` empty, and provide a highly detailed, technical answer in the `general_protocol_explanation` field.

{critique}

--------------------------------------------------
CONTEXT:
{context}
--------------------------------------------------

QUESTION: {question}""",
            input_variables=["context", "question", "critique"],
        )
        
        extractor = prompt | self.llm.with_structured_output(ExtractionOutput)
        context_str = self.format_docs_for_extraction(state["documents"])
        
        try:
            output = extractor.invoke({
                "context": context_str, 
                "question": state["question"],
                "critique": critique
            })
            errors = []
        except ValidationError as e:
            logging.error(f"Pydantic Validation failed.")
            output = None
            errors = [f"JSON Schema Validation Failed: {str(e)}"]
        except Exception as e:
            logging.error(f"Extraction failed: {e}")
            output = None
            errors = [f"LLM Failed to return structured JSON: {str(e)}"]
            
        return {"extraction_output": output, "verification_errors": errors}

    def node_compile_and_prove(self, state: GraphState):
        logging.info("Phase 3: Python Coverage Proofs and FSM Compilation...")
        attempts = state.get("verification_attempts", 0) + 1
        errors = state.get("verification_errors", [])
        
        if not state.get("extraction_output"):
            return {"verification_attempts": attempts, "verification_errors": errors}
            
        output = state["extraction_output"]
        context_str = self.format_docs_for_extraction(state["documents"])
        
        # 1. Hard Coverage Proof
        try:
            CoverageProofEngine.validate_coverage(context_str, output)
        except CoverageError as e:
            errors.append(str(e))
            
        # 2. Compile FSM and run Structural Proofs
        compiler = ProtocolCompiler(output)
        generation = compiler.compile()
        if compiler.errors:
            errors.extend(compiler.errors)
            
        return {
            "verification_errors": errors, 
            "verification_attempts": attempts,
            "generation": generation
        }

    def edge_check_proofs(self, state: GraphState):
        errors = state.get("verification_errors", [])
        attempts = state.get("verification_attempts", 0)
        
        if len(errors) == 0:
            logging.info("Phase 4: Proofs PASS. State Machine is mathematically sound and coverage is complete.")
            return "pass"
        elif attempts >= 3:
            logging.warning("Phase 4: Proofs FAIL. Max retries reached. Outputting compiler errors.")
            return "pass"
        else:
            logging.warning(f"Phase 4: Proofs FAIL. Triggering Re-extraction. Errors: {errors}")
            return "retry"

    def ask(self, question: str):
        initial_state = {
            "question": question, 
            "documents": [], 
            "extraction_output": None, 
            "generation": "", 
            "verification_errors": [],
            "verification_attempts": 0,
            "sources": []
        }
        final_state = self.app.invoke(initial_state)
        
        # Process and clean sources
        raw_sources = []
        for doc in final_state["documents"]:
            src = doc.metadata.get("source_file", "Unknown")
            # Deduplicate prefix: 'rfcrfc4271' -> 'rfc4271'
            if src.startswith("rfcrfc"):
                src = src[3:]
            
            # Prioritize proper RFCs and exclude raw reference dumps like "[DesignReport]" if possible
            if not src.lower().startswith("rfc") and len(src) > 10:
                continue

            raw_sources.append({
                "source": src,
                "section_number": doc.metadata.get("section_number", "N/A"),
                "section_title": doc.metadata.get("section_title", "Unknown"),
                "content": doc.page_content
            })
            
        return {
            "answer": final_state["generation"],
            "sources": raw_sources
        }

def run_qa():
    qa_system = QASystem()
    question = "How does the BGP FSM handle the Hold Timer expiring?"
    print(f"\nAsking question: {question}\n")
    result = qa_system.ask(question)
    print("="*80)
    print("10/10 FORMAL COMPILER OUTPUT:")
    print("="*80)
    print(result['answer'])

if __name__ == '__main__':
    run_qa()