import os
import re
import json
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RFCStructuredParser:
    """
    Parses IETF xml2rfc format documents into structured JSON.
    Preserves section hierarchy, normative language, and architectural diagrams.
    """
    
    def __init__(self, raw_dir: str = "data/raw_rfcs", output_dir: str = "data/rfc_json"):
        self.raw_dir = raw_dir
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def parse_file(self, filepath: str) -> Optional[Dict]:
        """Parses a single RFC XML file."""
        if not filepath.endswith('.xml'):
            return None
            
        rfc_num = os.path.basename(filepath).replace(".xml", "").lower()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'xml')
        except Exception as e:
            logging.error(f"Failed to read {filepath}: {e}")
            return None

        # Extract top-level metadata
        rfc_doc = {
            "rfc_number": rfc_num,
            "title": self._extract_title(soup),
            "abstract": self._extract_abstract(soup),
            "sections": []
        }

        # Recursively extract sections
        for section in soup.find_all('section', recursive=False):
            # xml2rfc usually puts sections under <middle> or <back>
            pass
            
        # Often the root sections are inside <middle>
        middle = soup.find('middle')
        if middle:
            for section in middle.find_all('section', recursive=False):
                rfc_doc["sections"].append(self._parse_section(section, parent_path=[]))
                
        # Also grab appendices from <back>
        back = soup.find('back')
        if back:
            for section in back.find_all('section', recursive=False):
                rfc_doc["sections"].append(self._parse_section(section, parent_path=["Appendix"]))

        return rfc_doc

    def _extract_title(self, soup: BeautifulSoup) -> str:
        title_tag = soup.find('title')
        return title_tag.text.strip() if title_tag else "Unknown Title"
        
    def _extract_abstract(self, soup: BeautifulSoup) -> str:
        abstract = soup.find('abstract')
        if not abstract:
            return ""
        return " ".join(p.text.strip() for p in abstract.find_all('t'))

    def _classify_section_type(self, title: str, content: str) -> str:
        """Heuristically classifies the semantic purpose of an RFC section."""
        title_lower = title.lower()
        content_lower = content.lower()[:500] # Check first 500 chars
        
        if any(kw in title_lower for kw in ["state machine", "fsm", "state transition"]):
            return "STATE_MACHINE"
        elif any(kw in title_lower for kw in ["message format", "packet format", "header format"]):
            return "MESSAGE_FORMAT"
        elif any(kw in title_lower for kw in ["procedure", "operation", "processing"]):
            return "PROCEDURE"
        elif any(kw in title_lower for kw in ["timer", "timeout", "retransmission"]):
            return "TIMER_LOGIC"
        elif "error handling" in title_lower or "error code" in title_lower:
            return "ERROR_HANDLING"
        elif "security consideration" in title_lower:
            return "SECURITY"
        else:
            return "GENERAL"

    def _parse_section(self, section_tag, parent_path: List[str] = None) -> Dict:
        """Recursively parses a <section> tag, maintaining strict hierarchy."""
        if parent_path is None:
            parent_path = []
            
        sec_id = section_tag.get('pn', section_tag.get('anchor', ''))
        
        # Clean up section number
        sec_num = sec_id.replace("section-", "")
        if sec_num.startswith("appendix-"):
            sec_num = sec_num.replace("appendix-", "Appendix ")
            
        name_tag = section_tag.find('name', recursive=False)
        sec_title = name_tag.text.strip() if name_tag else "Unnamed Section"
        
        content_blocks = []
        for child in section_tag.children:
            if child.name == 't':
                content_blocks.append(child.text.strip())
            elif child.name == 'ul' or child.name == 'ol':
                for li in child.find_all('li'):
                    content_blocks.append(f"- {li.text.strip()}")
            elif child.name == 'artwork' or child.name == 'sourcecode':
                content_blocks.append(f"\n```text\n{child.text}\n```\n")

        full_content = "\n".join(content_blocks)
        
        # 10/10 Fix: Maintain strict hierarchical paths
        current_path = parent_path + [sec_num] if sec_num else parent_path
        parent_section = parent_path[-1] if parent_path else None
        root_section = current_path[0] if current_path else None
        
        # 10/10 Fix: Semantic typing
        sec_type = self._classify_section_type(sec_title, full_content)

        parsed_section = {
            "section_number": sec_num,
            "title": sec_title,
            "section_type": sec_type,
            "hierarchy": {
                "parent_section": parent_section,
                "root_section": root_section,
                "path": current_path
            },
            "content": full_content,
            "subsections": []
        }
        
        for sub_section in section_tag.find_all('section', recursive=False):
            parsed_section["subsections"].append(self._parse_section(sub_section, current_path))
            
        return parsed_section

    def _parse_txt_file(self, filepath: str) -> Optional[Dict]:
        """Heuristically parses older plain-text RFCs into the structured JSON format."""
        rfc_num = os.path.basename(filepath).replace(".txt", "").lower()
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception as e:
            logging.error(f"Failed to read {filepath}: {e}")
            return None
            
        # Basic heuristic to find title and abstract (top 2000 chars)
        header_text = text[:2000]
        title_match = re.search(r'\n\n\s+(.+?)\n\n', header_text)
        title = title_match.group(1).strip() if title_match else "Unknown Title"
        
        rfc_doc = {
            "rfc_number": rfc_num,
            "title": title,
            "abstract": "Text-only RFC. Abstract not explicitly extracted.",
            "sections": []
        }
        
        # Regex to find standard RFC section headers (e.g., "1. Introduction" or "4.2. BGP Timers")
        # Looks for newline, optional spaces, numbers with dots, spaces, title, newline
        section_pattern = re.compile(r'\n\n\s*(\d+(?:\.\d+)*)\.?\s+([A-Z].+?)\n', re.MULTILINE)
        
        matches = list(section_pattern.finditer(text))
        
        if not matches:
            # If we can't parse sections, treat the whole doc as one general section
            rfc_doc["sections"].append({
                "section_number": "1",
                "title": "Full Document",
                "section_type": "GENERAL",
                "hierarchy": {"parent_section": None, "root_section": "1", "path": ["1"]},
                "content": text,
                "subsections": []
            })
            return rfc_doc

        sections_dict = {}
        root_sections = []

        for i, match in enumerate(matches):
            sec_num = match.group(1)
            sec_title = match.group(2).strip()
            
            # Extract content until the next section
            start_idx = match.end()
            end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
            content = text[start_idx:end_idx].strip()
            
            # Clean up pagination markers (e.g., "RFC 4271  [Page 12]") from content
            content = re.sub(r'\n\f?\n?.*\[Page \d+\]\n', '\n', content)
            
            path = sec_num.split('.')
            parent_num = ".".join(path[:-1]) if len(path) > 1 else None
            root_num = path[0]
            
            sec_type = self._classify_section_type(sec_title, content)
            
            parsed_sec = {
                "section_number": sec_num,
                "title": sec_title,
                "section_type": sec_type,
                "hierarchy": {
                    "parent_section": parent_num,
                    "root_section": root_num,
                    "path": path
                },
                "content": content,
                "subsections": []
            }
            
            sections_dict[sec_num] = parsed_sec
            
            # Build the tree
            if parent_num and parent_num in sections_dict:
                sections_dict[parent_num]["subsections"].append(parsed_sec)
            elif not parent_num:
                root_sections.append(parsed_sec)
                
        rfc_doc["sections"] = root_sections
        return rfc_doc

    def process_all(self):
        """Processes all XML and TXT files in the raw directory and saves them as JSON."""
        import glob
        from tqdm import tqdm
        
        xml_files = glob.glob(os.path.join(self.raw_dir, "**", "*.xml"), recursive=True)
        txt_files = glob.glob(os.path.join(self.raw_dir, "**", "*.txt"), recursive=True)
        
        # We only want to process the TXT file if an XML version doesn't exist
        xml_rfc_nums = {os.path.basename(f).replace(".xml", "").lower() for f in xml_files}
        txt_to_process = [f for f in txt_files if os.path.basename(f).replace(".txt", "").lower() not in xml_rfc_nums]
        
        all_files = xml_files + txt_to_process
        logging.info(f"Found {len(xml_files)} XML and {len(txt_to_process)} TXT fallback RFCs.")
        logging.info(f"Starting structured parsing for {len(all_files)} total files...")
        
        processed_count = 0
        for filepath in tqdm(all_files, desc="Parsing RFCs to JSON"):
            try:
                if filepath.endswith(".xml"):
                    rfc_doc = self.parse_file(filepath)
                else:
                    rfc_doc = self._parse_txt_file(filepath)
                    
                if rfc_doc and rfc_doc["sections"]:
                    out_path = os.path.join(self.output_dir, f"{rfc_doc['rfc_number']}.json")
                    with open(out_path, 'w', encoding='utf-8') as f:
                        json.dump(rfc_doc, f, indent=2)
                    processed_count += 1
            except Exception as e:
                logging.error(f"Error processing {filepath}: {e}")
                
        logging.info(f"Successfully converted {processed_count} files to structured JSON in {self.output_dir}.")

def run_parser():
    parser = RFCStructuredParser()
    parser.process_all()

if __name__ == '__main__':
    run_parser()