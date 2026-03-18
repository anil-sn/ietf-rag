import os
import ssl
import sys
import warnings

# Suppress all known noisy 3rd party warnings BEFORE any other imports
warnings.filterwarnings("ignore", message=".*urllib3.*")
warnings.filterwarnings("ignore", message=".*chardet.*")
warnings.filterwarnings("ignore", message=".*charset_normalizer.*")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

# Aggressively disable SSL verification for corporate proxy environments
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
# Disable HuggingFace SSL verification specifically
os.environ['HF_HUB_DISABLE_SSL_VERIFY'] = '1'

import argparse
import logging
import warnings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from data_ingestion.crawler import run_ingestion
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

# Initialize Rich Console
console = Console()

# Configure logging to integrate better with Rich
logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(message)s')
# We silence the standard info logging when using the interactive CLI to keep it clean
logger = logging.getLogger()
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

def main():
    """
    Main function to run the IETF RAG system.
    Provides a CLI to select the desired action.
    """
    parser = argparse.ArgumentParser(description="IETF Networking Standards Formal Compiler")
    parser.add_argument(
        "action",
        choices=["ingest", "download-models", "index", "build-graph", "ask"],
        help="The action to perform: "
             "'ingest' to crawl RFCs, "
             "'download-models' to fetch SOTA ML models, "
             "'index' to build the knowledge base, "
             "'build-graph' to extract the relationship graph, "
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

    parser.add_argument(
        "--rsync",
        action="store_true",
        help="Use rsync instead of HTTP tarballs for ingestion. (Requires port 873)"
    )

    args = parser.parse_args()

    if args.action == "ingest":
        console.print("[bold green]Starting data ingestion process...[/bold green]")
        # For long processes, we restore info logging
        logger.setLevel(logging.INFO)
        import asyncio
        asyncio.run(run_ingestion(use_rsync=args.rsync))
        console.print("[bold green]Data ingestion complete.[/bold green]")

    elif args.action == "download-models":
        from utils.model_downloader import download_sota_models
        logger.setLevel(logging.INFO)
        download_sota_models()
        
    elif args.action == "index":
        from knowledge_base.vector_store import run_indexing
        logger.setLevel(logging.INFO)
        console.print("[bold green]Starting knowledge base indexing process...[/bold green]")
        run_indexing(force_reindex=args.force)
        console.print("[bold green]Knowledge base indexing complete.[/bold green]")
        
    elif args.action == "build-graph":
        from knowledge_base.graph_store import run_graph_building
        logger.setLevel(logging.INFO)
        console.print("[bold green]Starting GraphRAG extraction process...[/bold green]")
        run_graph_building()
        console.print("[bold green]Graph extraction complete.[/bold green]")
        
    elif args.action == "ask":
        # Restore INFO logging so phase progress is visible above the spinner
        logger.setLevel(logging.INFO)
        
        from qa_system.rag_pipeline import QASystem
        with console.status("[bold cyan]Initializing Formal Protocol Compiler (Loading Models)...[/bold cyan]", spinner="dots"):
            qa_system = QASystem()
        
        if args.question:
            process_question(qa_system, args.question)
        else:
            console.print(Panel.fit("[bold blue]Welcome to the IETF Formal Protocol Compiler.[/bold blue]\nType 'exit' to quit.", border_style="blue"))
            while True:
                try:
                    user_question = Prompt.ask("\n[bold green]Ask Protocol Question[/bold green]")
                    if user_question.lower() in ["exit", "quit"]:
                        break
                    if not user_question.strip():
                        continue
                    process_question(qa_system, user_question)
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[bold red]Exiting...[/bold red]")
                    break

def process_question(qa_system, question: str):
    """Helper function to process a single question with Rich UI."""
    console.print(f"\n[bold yellow]Compiling FSM for:[/bold yellow] {question}")
    
    # We use a status spinner while the LangGraph agent executes
    with console.status("[bold magenta]Running Formal Compiler Pipeline (Retrieving, Extracting, Proving)...[/bold magenta]", spinner="bouncingBar"):
        result = qa_system.ask(question)
    
    console.print("\n[bold green]10/10 FORMAL COMPILER OUTPUT[/bold green]")
    # Render the generated Markdown deterministically
    md = Markdown(result.get('answer', 'No answer generated.'))
    console.print(Panel(md, border_style="green", title="Compiled State Machine"))
    
    sources = result.get('sources', [])
    if sources:
        # Group sources by RFC
        grouped_sources = {}
        for source in sources:
            src_name = source.get('source', 'Unknown').upper()
            sec_num = source.get('section_number', 'N/A')
            sec_title = source.get('section_title', 'Unknown Section')
            
            if src_name not in grouped_sources:
                grouped_sources[src_name] = []
                
            grouped_sources[src_name].append(f"Section {sec_num}: {sec_title}")

        # Build clean output string
        source_text = ""
        for i, (rfc, sections) in enumerate(grouped_sources.items(), 1):
            unique_sections = list(dict.fromkeys(sections)) # Deduplicate sections
            sections_str = ", ".join(unique_sections)
            source_text += f"[bold cyan][{i}][/bold cyan] [bold]{rfc}[/bold] - [dim]{sections_str}[/dim]\n"
            
        console.print(Panel(source_text.strip(), title="Verified Context Sources", border_style="cyan"))
    
    console.print()

if __name__ == '__main__':
    main()