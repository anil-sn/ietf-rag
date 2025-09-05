# src/qa_system/rag_pipeline.py

import logging
import requests
import json
from ragflow.core.retrieval import Retrieval
from ragflow.core.generation import Generation
from ragflow.config import RAGFlowConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OllamaLLM:
    """A wrapper class for interacting with a local Ollama-served LLM."""
    def __init__(self, model: str = "llama3:8b", host: str = "http://localhost:11434"):
        """
        Initializes the Ollama client.
        
        Args:
            model (str): The name of the model to use (e.g., 'llama3:8b', 'mistral').
            host (str): The URL of the Ollama server.
        """
        self.model = model
        self.host = host
        self.api_url = f"{self.host}/api/generate"
        logging.info(f"OllamaLLM initialized for model '{self.model}' at {self.host}")

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generates a response from the LLM.
        
        Args:
            prompt (str): The input prompt for the model.
            
        Returns:
            str: The generated text.
        """
        try:
            payload = {"model": self.model, "prompt": prompt, "stream": False}
            response = requests.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.RequestException as e:
            logging.error(f"Failed to connect to Ollama at {self.host}. Is it running?")
            logging.error(f"Error: {e}")
            return "Error: Could not get a response from the language model."

class QASystem:
    """
    The main Question-Answering system that orchestrates retrieval and generation.
    """
    
    VECTOR_DB_PATH = "data/chroma_db"
    COLLECTION_NAME = "networking_standards"
    EMBEDDING_MODEL_NAME = "BAAI/bge-large-en-v1.5"

    def __init__(self, llm_model: str = "llama3:8b"):
        """
        Initializes the QA system.
        """
        # 1. Initialize RAGFlow configuration (must match indexing config)
        self.config = RAGFlowConfig(
            vector_db_type='chroma',
            chroma_db_path=self.VECTOR_DB_PATH,
            embedding_model=self.EMBEDDING_MODEL_NAME
        )
        
        # 2. Initialize the Retrieval component
        self.retriever = Retrieval(self.config)
        
        # 3. Initialize the LLM
        self.llm = OllamaLLM(model=llm_model)

        # 4. Initialize the Generation component
        # We pass the llm's generate method directly to RAGFlow
        self.generator = Generation(self.config, llm=self.llm.generate)
        
        logging.info("QA System is ready.")

    def ask(self, question: str):
        """
        Asks a question to the RAG system.
        
        Args:
            question (str): The user's question.
            
        Returns:
            dict: A dictionary containing the answer and sourced documents.
        """
        logging.info(f"Received question: {question}")
        
        # Step 1: Retrieve relevant documents from the knowledge base
        # Using hybrid search settings from the architecture document
        retrieved_chunks = self.retriever.retrieve(
            query=question,
            collection_name=self.COLLECTION_NAME,
            retrieve_top_k=50, # Retrieve more candidates initially
            # --- Hybrid Search Weights ---
            vector_similarity_weight=0.4,
            keywords_similarity_weight=0.6,
        )

        if not retrieved_chunks:
            logging.warning("No relevant documents found for the question.")
            return {"answer": "I could not find any relevant information in the knowledge base to answer this question.", "sources": []}
            
        logging.info(f"Retrieved {len(retrieved_chunks)} relevant chunks.")
        
        # Step 2: Generate a response using the LLM and retrieved context
        # RAGFlow's generator automatically builds the prompt from the chunks
        answer = self.generator.generate(
            query=question,
            context=retrieved_chunks,
            prompt_template=self.get_prompt_template(),
        )

        # Extract source metadata for citation
        sources = [
            {
                "source": chunk.metadata.get("source", "Unknown"),
                "content": chunk.content,
            }
            for chunk in retrieved_chunks[:3] # Show top 3 sources
        ]

        return {"answer": answer, "sources": sources}

    @staticmethod
    def get_prompt_template():
        """Defines the prompt template for the LLM."""
        return (
            "You are an expert assistant specializing in IETF networking standards. "
            "Use the following retrieved context from RFC documents to answer the question. "
            "Provide a detailed and technical answer. If the context does not contain the answer, "
            "state that the information is not available in the provided documents.\n\n"
            "CONTEXT:\n"
            "----------\n"
            "{context}\n"
            "----------\n"
            "QUESTION: {query}\n\n"
            "ANSWER:"
        )

def run_qa():
    """Main function to test the QA system."""
    qa_system = QASystem()
    
    # Example question
    # question = "What is the main purpose of the BGP OPEN message?"
    question = "How does OSPF establish neighbor adjacencies?"

    print(f"\nAsking question: {question}\n")
    
    result = qa_system.ask(question)
    
    print("="*50)
    print("Generated Answer:")
    print("="*50)
    print(result['answer'])
    print("\n" + "="*50)
    print("Top Sources Consulted:")
    print("="*50)
    for i, source in enumerate(result['sources']):
        print(f"\n--- Source {i+1} ---")
        print(f"File: {source['source']}")
        print(f"Excerpt: {source['content'][:300]}...") # Print a snippet
    print("\n" + "="*50)


if __name__ == '__main__':
    run_qa()