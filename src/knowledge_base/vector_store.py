import os
# Disable SSL Verification globally for requests/httpx/huggingface due to corporate proxy
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

import shutil
import logging
import pickle
import warnings
import torch
import json
from langchain_core.documents import Document

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# Intelligently detect Apple Silicon (MPS) or default to CPU
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.retrievers import ParentDocumentRetriever
from langchain_core.stores import InMemoryStore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NetworkingKB:
    """
    SOTA Knowledge Base using Parent-Child chunking architecture.
    """
    
    VECTOR_DB_PATH = "data/chroma_db"
    STORE_PATH = "data/doc_store"
    COLLECTION_NAME = "networking_standards"
    
    # SOTA: Upgrading to BGE-M3 (Multi-lingual, Multi-function, 8k context)
    EMBEDDING_MODEL_NAME = "models/bge-m3"
    
    def __init__(self, data_dir: str = "data/rfc_json"):
        self.data_dir = data_dir
        
        self.use_openai_embeddings = os.environ.get("USE_OPENAI_EMBEDDINGS", "false").lower() == "true"
        
        if self.use_openai_embeddings:
            base_url = os.environ.get("OPENAI_API_BASE", "http://10.83.6.175:8081/v1")
            api_key = os.environ.get("OPENAI_API_KEY", "sk-not-needed")
            # For BGE-M3 or Nomic if served via vLLM/Ollama
            model_name = os.environ.get("EMBEDDING_MODEL", "bge-m3") 
            
            logging.info(f"Loading OpenAI-compatible embedding model ({model_name}) from {base_url}...")
            self.embeddings = OpenAIEmbeddings(
                model=model_name,
                openai_api_base=base_url,
                openai_api_key=api_key,
                check_embedding_ctx_length=False
            )
        else:
            logging.info(f"Loading local embedding model from {self.EMBEDDING_MODEL_NAME} on {DEVICE.upper()}...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.EMBEDDING_MODEL_NAME,
                model_kwargs={'device': DEVICE, 'local_files_only': True},
                encode_kwargs={'normalize_embeddings': True}
            )
        
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""]
        )
        
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=300,
            separators=["\n\n", "\n", " ", ""]
        )

    def prepare_database(self, force_reindex: bool = False):
        if force_reindex:
            try:
                import chromadb.api.client
                if hasattr(chromadb.api.client.SharedSystemClient, 'clear_system_cache'):
                    chromadb.api.client.SharedSystemClient.clear_system_cache()
            except Exception as e:
                logging.warning(f"Failed to clear Chroma system cache: {e}")

            if os.path.exists(self.VECTOR_DB_PATH):
                logging.warning(f"Removing existing database at {self.VECTOR_DB_PATH}")
                shutil.rmtree(self.VECTOR_DB_PATH)
            if os.path.exists(self.STORE_PATH):
                logging.warning(f"Removing existing document store at {self.STORE_PATH}")
                shutil.rmtree(self.STORE_PATH)
                
        os.makedirs(self.VECTOR_DB_PATH, exist_ok=True)
        os.makedirs(self.STORE_PATH, exist_ok=True)
        logging.info("Database directories prepared.")

    def _flatten_sections(self, rfc_number: str, title: str, sections: list, parent_context: str = "", chunk_counter: list = None) -> list:
        """Recursively flattens the JSON section tree into LangChain Documents with strict metadata."""
        if chunk_counter is None:
            chunk_counter = [1]
            
        docs = []
        for sec in sections:
            sec_num = sec.get("section_number", "")
            sec_title = sec.get("title", "")
            sec_type = sec.get("section_type", "GENERAL")
            hierarchy = sec.get("hierarchy", {})
            content = sec.get("content", "").strip()
            
            # Context string helps the child chunks retain global meaning
            context_header = f"RFC {rfc_number}: {title}\nSection {sec_num}: {sec_title} ({sec_type})\n\n"
            
            if content:
                doc = Document(
                    page_content=context_header + content,
                    metadata={
                        "source_file": f"rfc{rfc_number}",
                        "section_number": sec_num,
                        "section_title": sec_title,
                        "section_type": sec_type,
                        "root_section": hierarchy.get("root_section", ""),
                        "chunk_id": str(chunk_counter[0])
                    }
                )
                docs.append(doc)
                chunk_counter[0] += 1
            
            # Recurse into subsections
            if sec.get("subsections"):
                docs.extend(self._flatten_sections(rfc_number, title, sec["subsections"], context_header, chunk_counter))
                
        return docs

    def index_documents(self, sample_size: int = None):
        if not os.path.exists(self.data_dir) or not os.listdir(self.data_dir):
            logging.error(f"Source JSON directory is empty or missing: {self.data_dir}. Did you run the XML parser?")
            return

        logging.info("Starting SOTA structured document indexing (Parent-Child Architecture)...")
        
        file_paths = [
            os.path.join(self.data_dir, f) 
            for f in os.listdir(self.data_dir) 
            if f.endswith('.json')
        ]
        
        if sample_size and len(file_paths) > sample_size:
            logging.info(f"Limiting indexing to {sample_size} JSON documents for initial testing.")
            file_paths = file_paths[:sample_size]
            
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
        
        documents = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        ) as progress:
            load_task = progress.add_task("[cyan]Loading JSON documents...", total=len(file_paths))
            
            for path in file_paths:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        rfc_data = json.load(f)
                    
                    rfc_number = rfc_data.get("rfc_number", "unknown")
                    rfc_title = rfc_data.get("title", "Unknown Title")
                    sections = rfc_data.get("sections", [])
                    
                    section_docs = self._flatten_sections(rfc_number, rfc_title, sections)
                    documents.extend(section_docs)
                    
                except Exception as e:
                    logging.warning(f"Failed to load JSON {path}: {e}")
                
                progress.update(load_task, advance=1)
                
            logging.info(f"Loaded {len(documents)} structured section documents. Initializing vector store...")
            
            vector_store = Chroma(
                collection_name=self.COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=self.VECTOR_DB_PATH
            )
            
            doc_store_path = os.path.join(self.STORE_PATH, "store.pkl")
            store_dict = {}
            if os.path.exists(doc_store_path):
                with open(doc_store_path, "rb") as f:
                    store_dict = pickle.load(f)
                    
            store = InMemoryStore()
            store.mset(list(store_dict.items()))
            
            retriever = ParentDocumentRetriever(
                vectorstore=vector_store,
                docstore=store,
                child_splitter=self.child_splitter,
                parent_splitter=self.parent_splitter,
            )
            
            logging.info("Generating parent and child embeddings (this may take a while)...")
            
            batch_size = 100
            embed_task = progress.add_task("[magenta]Embedding and indexing documents...", total=len(documents))
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                retriever.add_documents(batch, ids=None)
                progress.update(embed_task, advance=len(batch))
            
            with open(doc_store_path, "wb") as f:
                pickle.dump(store.store, f)
                
            bm25_docs_path = os.path.join(self.STORE_PATH, "bm25_docs.pkl")
            parent_docs = self.parent_splitter.split_documents(documents)
            with open(bm25_docs_path, "wb") as f:
                pickle.dump(parent_docs, f)
                
            logging.info(f"Indexing complete. Generated {len(store.store)} parent chunks.")

def run_indexing(force_reindex: bool = False):
    kb_manager = NetworkingKB()
    kb_manager.prepare_database(force_reindex=force_reindex)
    kb_manager.index_documents(sample_size=None)

if __name__ == '__main__':
    run_indexing(force_reindex=True)