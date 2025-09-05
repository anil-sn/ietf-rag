# src/main.py

import argparse
import logging
from data_ingestion.crawler import run_ingestion
from knowledge_base.vector_store import run_indexing
from qa_system.rag_pipeline import QASystem

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Main function to run the IETF RAG system.
    Provides a CLI to select the desired action.
    """
    parser = argparse.ArgumentParser(description="IETF Networking Standards RAG System")
    parser.add_argument(
        "action",
        choices=["ingest", "index", "ask"],
        help="The action to perform: "
             "'ingest' to crawl RFCs, "
             "'index' to build the knowledge base, "
             "'ask' to start the interactive QA session."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-indexing of the knowledge base. Used with 'index' action."
    )
    parser.add_argument(
        "-q", "--question",
        type=str,
        help="Ask a single question and exit. Used with 'ask' action."
    )

    args = parser.parse_args()

    if args.action == "ingest":
        logging.info("Starting data ingestion process...")
        run_ingestion()
        logging.info("Data ingestion complete.")
        
    elif args.action == "index":
        logging.info("Starting knowledge base indexing process...")
        run_indexing(force_reindex=args.force)
        logging.info("Knowledge base indexing complete.")
        
    elif args.action == "ask":
        logging.info("Initializing Question-Answering System...")
        qa_system = QASystem()
        
        if args.question:
            # Handle a single question from the command line
            process_question(qa_system, args.question)
        else:
            # Start interactive mode
            print("\nWelcome to the IETF RAG Q&A System. Type 'exit' to quit.")
            while True:
                try:
                    user_question = input("\nPlease ask your question: ")
                    if user_question.lower() in ["exit", "quit"]:
                        break
                    if not user_question.strip():
                        continue
                    process_question(qa_system, user_question)
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting...")
                    break

def process_question(qa_system: QASystem, question: str):
    """Helper function to process a single question and print the results."""
    print(f"\nAsking: {question}\n")
    
    result = qa_system.ask(question)
    
    # --- Print Formatted Output ---
    print("=" * 70)
    print("ANSWER")
    print("-" * 70)
    print(result.get('answer', 'No answer generated.'))
    print("=" * 70)
    
    print("\n" + "=" * 70)
    print("SOURCES")
    print("-" * 70)
    sources = result.get('sources', [])
    if not sources:
        print("No sources were consulted.")
    else:
        for i, source in enumerate(sources, 1):
            source_file = source.get('source', 'Unknown')
            content_snippet = source.get('content', '')[:350].replace('\n', ' ')
            print(f"[{i}] {source_file}\n    Excerpt: \"{content_snippet}...\"\n")
    print("=" * 70)

if __name__ == "__main__":
    main()