import os
import re
import logging
import pickle
import networkx as nx
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RFCGraphBuilder:
    """
    Parses RFC documents to build a Knowledge Graph (GraphRAG).
    Extracts explicit relationships like "Obsoletes", "Updates", and "References".
    """
    
    GRAPH_STORE_PATH = "data/doc_store/rfc_graph.pkl"
    
    def __init__(self, data_dir: str = "data/rfc_markdown"):
        self.data_dir = data_dir
        self.graph = nx.DiGraph()

    def _extract_rfc_number(self, filename: str) -> str:
        """Extracts '4271' from 'rfc4271.md'"""
        match = re.search(r'rfc(\d+)', filename, re.IGNORECASE)
        return match.group(1) if match else filename.replace(".md", "")

    def _parse_headers(self, text: str, current_rfc: str):
        """Scans the top of the RFC for relationship headers."""
        # We usually only need to check the first 2000 characters for headers
        header_text = text[:2000]
        
        # Regex patterns for common RFC headers
        obsoletes_pattern = r'Obsoletes:\s*([0-9,\s]+)'
        updates_pattern = r'Updates:\s*([0-9,\s]+)'
        
        obsoletes_match = re.search(obsoletes_pattern, header_text, re.IGNORECASE)
        if obsoletes_match:
            for target in re.findall(r'\d+', obsoletes_match.group(1)):
                self.graph.add_edge(current_rfc, target, relationship="obsoletes")
                
        updates_match = re.search(updates_pattern, header_text, re.IGNORECASE)
        if updates_match:
            for target in re.findall(r'\d+', updates_match.group(1)):
                self.graph.add_edge(current_rfc, target, relationship="updates")

    def _parse_references(self, text: str, current_rfc: str):
        """Scans the bottom of the RFC for Normative/Informative references."""
        # Simple heuristic: Look for [RFCxxxx] blocks in the text
        references = re.findall(r'\[RFC(\d+)\]', text, re.IGNORECASE)
        # Deduplicate
        unique_refs = set(references)
        
        for ref in unique_refs:
            if ref != current_rfc:
                self.graph.add_edge(current_rfc, ref, relationship="references")

    def build_graph(self):
        """Iterates over all RFCs and builds the NetworkX Directed Graph."""
        if not os.path.exists(self.data_dir):
            logging.error(f"Source data directory is empty or missing: {self.data_dir}")
            return

        logging.info("Starting GraphRAG extraction. Building relationship graph...")
        
        file_paths = [
            os.path.join(self.data_dir, f) 
            for f in os.listdir(self.data_dir) 
            if f.endswith('.md') or f.endswith('.txt') or f.endswith('.xml')
        ]
        
        for path in tqdm(file_paths, desc="Parsing RFC Relationships"):
            filename = os.path.basename(path)
            current_rfc = self._extract_rfc_number(filename)
            
            # Add the base node
            self.graph.add_node(current_rfc, type="RFC", path=path)
            
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                    
                self._parse_headers(text, current_rfc)
                self._parse_references(text, current_rfc)
                
            except Exception as e:
                logging.warning(f"Failed to parse relationships for {path}: {e}")

        # Save the graph
        os.makedirs(os.path.dirname(self.GRAPH_STORE_PATH), exist_ok=True)
        with open(self.GRAPH_STORE_PATH, "wb") as f:
            pickle.dump(self.graph, f)
            
        logging.info(f"Graph generation complete! Found {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges.")
        logging.info(f"Graph saved to {self.GRAPH_STORE_PATH}")

def run_graph_building():
    builder = RFCGraphBuilder()
    builder.build_graph()

if __name__ == '__main__':
    run_graph_building()