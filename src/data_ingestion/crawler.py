# src/data_ingestion/crawler.py

import requests
import logging
import os
from tqdm import tqdm
import asyncio
import re

# Correct import based on the library's structure
from crawl4ai.async_webcrawler import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class IETFCrawler:
    """
    A class to crawl RFC documents from the IETF Datatracker.
    
    This class performs two main functions:
    1. Queries the IETF Datatracker API to find URLs of relevant RFCs.
    2. Uses Crawl4AI's AsyncWebCrawler to scrape the content and save it
       as clean markdown files.
    """
    API_BASE_URL = "https://datatracker.ietf.org/api/v1/doc/document/"
    DOC_BASE_URL = "https://datatracker.ietf.org/doc/html/"
    
    def __init__(self, output_dir: str = "data/markdown_docs"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logging.info(f"Created output directory: {self.output_dir}")

    def fetch_rfc_urls(self, keywords: list[str], limit_per_keyword: int = 20) -> list[str]:
        """Fetches RFC URLs from the IETF Datatracker API."""
        unique_urls = set()
        logging.info(f"Fetching RFC URLs for keywords: {keywords}")
        
        for keyword in tqdm(keywords, desc="Fetching URLs"):
            params = {"name__icontains": keyword, "type_id": "rfc", "limit": limit_per_keyword}
            try:
                response = requests.get(self.API_BASE_URL, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                for doc in data.get("objects", []):
                    rfc_name = doc.get("name")
                    if rfc_name:
                        unique_urls.add(f"{self.DOC_BASE_URL}{rfc_name}")
            except requests.RequestException as e:
                logging.error(f"API request failed for keyword '{keyword}': {e}")
                
        logging.info(f"Found {len(unique_urls)} unique RFC URLs.")
        return list(unique_urls)

    def _url_to_filename(self, url: str) -> str:
        """Converts a URL to a safe, descriptive filename."""
        # Extracts the document name like 'rfc4271' from the URL
        match = re.search(r'/doc/html/([^/?]+)', url)
        if match:
            doc_name = match.group(1)
            return f"{doc_name}.md"
        # Fallback for unexpected URL formats
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', url)
        return f"{safe_name[-50:]}.md"

    async def crawl_and_save(self, urls: list[str]):
        """
        Asynchronously crawls URLs and saves their content as markdown files.
        """
        if not urls:
            logging.warning("No URLs provided to crawl. Aborting.")
            return
            
        logging.info(f"Starting crawl for {len(urls)} URLs...")
        
        # This config object holds all crawling options.
        # We can use the defaults for a simple scrape.
        run_config = CrawlerRunConfig()
        
        # AsyncWebCrawler should be used with an 'async with' block
        async with AsyncWebCrawler() as crawler:
            # arun_many crawls all URLs concurrently and returns a list of results
            results = await crawler.arun_many(urls=urls, config=run_config)
            
            logging.info("Crawling complete. Saving markdown files...")
            
            for result in tqdm(results, desc="Saving files"):
                if result.success and result.markdown:
                    filename = self._url_to_filename(result.url)
                    filepath = os.path.join(self.output_dir, filename)
                    try:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(result.markdown)
                    except Exception as e:
                        logging.error(f"Failed to write file {filepath}: {e}")
                else:
                    logging.warning(f"Failed to crawl {result.url}: {result.error_message}")
        
        logging.info(f"File saving complete. Markdown files are in {self.output_dir}")

async def run_ingestion():
    """Main async function to run the full data ingestion process."""
    protocols = ["IDR", "BGP", "OSPF", "ISIS"]
    crawler = IETFCrawler(output_dir="data/rfc_markdown")
    
    rfc_urls = crawler.fetch_rfc_urls(keywords=protocols, limit_per_keyword=25)
    
    poc_urls = rfc_urls[:10]
    logging.info(f"Processing a sample of {len(poc_urls)} URLs for this POC run.")

    # The crawl_and_save method is now a coroutine and must be awaited
    await crawler.crawl_and_save(urls=poc_urls)


if __name__ == '__main__':
    # Use asyncio.run() to execute the top-level async function
    asyncio.run(run_ingestion())