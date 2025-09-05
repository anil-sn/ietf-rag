# src/knowledge_base/vector_store.py

import os
import shutil
import logging
from ragflow.core.indexing import Indexing
from ragflow.config import DocumentType, RAGFlowConfig
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NetworkingKB:
    """
    Manages the knowledge base using RAGFlow for indexing and ChromaDB 
    for vector storage.
    """
    
    VECTOR_DB_PATH = "data/chroma_db"
    COLLECTION_NAME = "networking_standards"
    
    # We choose BGE (BGE-large-en-v1.5) as it is highly effective 
    # for technical and detailed domain content.
    EMBEDDING_MODEL_NAME = "BAAI/bge-large-en-v1.5"
    
    def __init__(self, data_dir: str = "data/rfc_markdown"):
        """
        Initializes the knowledge base manager.
        
        Args:
            data_dir (str): Directory containing the crawled markdown RFCs.
        """
        self.data_dir = data_dir
        
        # 1. Initialize RAGFlow configuration
        self.config = RAGFlowConfig(
            vector_db_type='chroma',
            chroma_db_path=self.VECTOR_DB_PATH,
            embedding_model=self.EMBEDDING_MODEL_NAME,
            chunk_config={
                # Optimized chunking for technical content (1536 tokens suggested in architecture)
                "chunk_token_num": 1536,
                "overlap_token_num": 150,
                "delimiter": "\n\n", # Preserve paragraph structure
                "layout_recognize": True, # Useful for complex RFC formatting
            }
        )
        
        # 2. Check and load the embedding model locally
        try:
            self.embedding_model = SentenceTransformer(self.EMBEDDING_MODEL_NAME)
            logging.info(f"Loaded embedding model: {self.EMBEDDING_MODEL_NAME}")
        except Exception as e:
            logging.error(f"Failed to load embedding model: {e}")
            raise

    def prepare_database(self, force_reindex: bool = False):
        """
        Prepares the vector database (ChromaDB), optionally clearing old data.
        """
        if force_reindex and os.path.exists(self.VECTOR_DB_PATH):
            logging.warning(f"Removing existing database at {self.VECTOR_DB_PATH}")
            shutil.rmtree(self.VECTOR_DB_PATH)
            os.makedirs(self.VECTOR_DB_PATH)
            logging.info("Clean database directory created.")
        elif not os.path.exists(self.VECTOR_DB_PATH):
            os.makedirs(self.VECTOR_DB_PATH)
            logging.info(f"Created new database directory at {self.VECTOR_DB_PATH}")

    def index_documents(self):
        """
        Indexes the markdown files in the data directory using RAGFlow.
        """
        if not os.path.exists(self.data_dir) or not os.listdir(self.data_dir):
            logging.error(f"Source data directory is empty or missing: {self.data_dir}")
            logging.error("Please run the crawler first.")
            return

        logging.info("Starting document indexing...")
        
        # Initialize RAGFlow's Indexing component
        indexer = Indexing(self.config)
        
        # Get list of all markdown files
        file_paths = [
            os.path.join(self.data_dir, f) 
            for f in os.listdir(self.data_dir) 
            if f.endswith('.md')
        ]
        
        # RAGFlow automatically handles parsing, chunking, and indexing
        try:
            indexer.index_documents(
                file_paths=file_paths,
                doc_type=DocumentType.markdown, # We crawled to markdown
                collection_name=self.COLLECTION_NAME,
            )
            logging.info("Indexing complete. Knowledge Base created successfully.")
            
        except Exception as e:
            logging.error(f"An error occurred during indexing: {e}")
            
# Helper function to run indexing directly
def run_indexing(force_reindex: bool = False):
    """Runs the full indexing process."""
    kb_manager = NetworkingKB()
    kb_manager.prepare_database(force_reindex=force_reindex)
    kb_manager.index_documents()

if __name__ == '__main__':
    # If run directly, force a re-index for testing
    run_indexing(force_reindex=True)