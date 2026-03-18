import os
import subprocess
import urllib.request
import tarfile
import logging
import glob
import shutil
import asyncio
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

class IETFBulkDownloader:
    TARBALLS = {
        "xml_all": "https://www.rfc-editor.org/in-notes/tar/xmlsource-all.tar.gz",
        "xml_latest": "https://www.rfc-editor.org/in-notes/tar/xmlsource-rfc8650-latest.tar.gz",
        "txt_all": "https://www.rfc-editor.org/in-notes/tar/RFC-all.tar.gz",
        "txt_latest": "https://www.rfc-editor.org/in-notes/tar/RFCs8501-latest.tar.gz"
    }

    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        self.tar_dir = os.path.join(base_dir, "tarballs")
        self.raw_dir = os.path.join(base_dir, "raw_rfcs") # Shared with rsync
        self.output_dir = os.path.join(base_dir, "rfc_markdown") 

        for d in [self.tar_dir, self.raw_dir, self.output_dir]:
            os.makedirs(d, exist_ok=True)

    def download_tarballs(self):
        import ssl
        # Create an unverified SSL context to bypass corporate proxy/firewall certificate errors
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)

        for name, url in self.TARBALLS.items():
            filepath = os.path.join(self.tar_dir, url.split("/")[-1])
            if not os.path.exists(filepath):
                logging.info(f"Downloading {url} to {filepath}")
                with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=name) as t:
                    urllib.request.urlretrieve(url, filename=filepath, reporthook=t.update_to)
            else:
                logging.info(f"Tarball {filepath} already exists. Skipping download.")

    def extract_tarballs(self):
        for name, url in self.TARBALLS.items():
            filepath = os.path.join(self.tar_dir, url.split("/")[-1])
            extract_path = self.raw_dir
            
            logging.info(f"Extracting {filepath} to {extract_path}")
            try:
                with tarfile.open(filepath, "r:gz") as tar:
                    tar.extractall(path=extract_path)
            except Exception as e:
                logging.error(f"Failed to extract {filepath}: {e}")

class IETFRsyncDownloader:
    """
    Downloads RFCs using the official IETF rsync mirrors.
    """
    
    RSYNC_MODULE = "rsync.rfc-editor.org::rfcs"

    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        self.raw_dir = os.path.join(base_dir, "raw_rfcs")
        self.output_dir = os.path.join(base_dir, "rfc_markdown") 

        for d in [self.raw_dir, self.output_dir]:
            os.makedirs(d, exist_ok=True)

    def sync_rfcs(self):
        logging.info(f"Starting rsync from {self.RSYNC_MODULE} to {self.raw_dir}")
        cmd = [
            "rsync",
            "-avz",
            "--delete",
            "--include=*/",
            "--include=*.txt",
            "--include=*.xml",
            "--exclude=*",
            self.RSYNC_MODULE,
            self.raw_dir
        ]
        
        logging.info("Running command: " + " ".join(cmd))
        try:
            subprocess.run(cmd, check=True)
            logging.info("rsync synchronization completed successfully.")
        except subprocess.CalledProcessError as e:
            logging.error(f"rsync failed with exit code {e.returncode}.")
            logging.error("Note: rsync uses port 873. If you are behind a corporate firewall, this port might be blocked.")
            raise

def consolidate_documents(base_dir="data"):
    """Shared consolidation method for both downloaders."""
    raw_dir = os.path.join(base_dir, "raw_rfcs")
    output_dir = os.path.join(base_dir, "rfc_markdown")
    logging.info("Consolidating documents (Preferring XML, fallback to TXT)...")
    
    xml_files = glob.glob(os.path.join(raw_dir, "**", "*.xml"), recursive=True)
    txt_files = glob.glob(os.path.join(raw_dir, "**", "*.txt"), recursive=True)

    rfc_map = {}
    
    for file in txt_files:
        basename = os.path.basename(file).lower()
        if basename.startswith("rfc") and basename.endswith(".txt"):
            rfc_num = basename.replace(".txt", "")
            rfc_map[rfc_num] = {"txt": file, "xml": None}
            
    for file in xml_files:
        basename = os.path.basename(file).lower()
        if basename.startswith("rfc") and basename.endswith(".xml"):
            rfc_num = basename.replace(".xml", "")
            if rfc_num not in rfc_map:
                rfc_map[rfc_num] = {"txt": None, "xml": file}
            else:
                rfc_map[rfc_num]["xml"] = file

    logging.info(f"Found {len(rfc_map)} unique RFCs.")
    
    processed = 0
    for rfc_num, paths in tqdm(rfc_map.items(), desc="Consolidating to output dir"):
        out_path = os.path.join(output_dir, f"{rfc_num}.md")
        
        if os.path.exists(out_path):
            continue
        
        source_file = paths["xml"] if paths["xml"] else paths["txt"]
        if not source_file:
            continue
            
        shutil.copy2(source_file, out_path)
        processed += 1
        
    logging.info(f"Consolidated {processed} new documents into {output_dir}.")

async def run_ingestion(use_rsync=False):
    """Main async function to run the full data ingestion process."""
    if use_rsync:
        logging.info("Starting rsync ingestion of IETF RFCs...")
        downloader = IETFRsyncDownloader(base_dir="data")
        downloader.sync_rfcs()
    else:
        logging.info("Starting bulk HTTP tarball downloading of IETF RFCs...")
        downloader = IETFBulkDownloader(base_dir="data")
        downloader.download_tarballs()
        downloader.extract_tarballs()
        
    consolidate_documents(base_dir="data")
    logging.info("Data ingestion complete.")

if __name__ == '__main__':
    # Default to HTTP tarballs if run directly. The CLI will control this.
    asyncio.run(run_ingestion(use_rsync=False))