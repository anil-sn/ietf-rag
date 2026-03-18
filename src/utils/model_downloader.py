import os
import ssl
import warnings
import logging
from huggingface_hub import snapshot_download

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def download_sota_models(base_dir="models"):
    """
    Utility to download BGE-M3 and BGE-Reranker-v2-M3 models.
    Implements a deep SSL monkey-patch to bypass corporate proxy issues.
    """
    logging.info("Initializing SOTA Model Downloader...")
    
    # 1. Implementation of the SSL monkey-patch
    original_create_default_context = ssl.create_default_context
    def no_verify_context(*args, **kwargs):
        ctx = original_create_default_context(*args, **kwargs)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    
    ssl.create_default_context = no_verify_context
    
    # Suppress insecure warnings
    warnings.filterwarnings('ignore')
    os.environ['HF_HUB_DISABLE_SSL_VERIFY'] = '1'

    models_to_download = {
        "BAAI/bge-m3": os.path.join(base_dir, "bge-m3"),
        "BAAI/bge-reranker-v2-m3": os.path.join(base_dir, "bge-reranker-v2-m3")
    }

    for repo_id, local_path in models_to_download.items():
        logging.info(f"Downloading {repo_id} to {local_path}...")
        try:
            snapshot_download(
                repo_id=repo_id, 
                local_dir=local_path,
                local_dir_use_symlinks=False
            )
            logging.info(f"✓ {repo_id} download complete.")
        except Exception as e:
            logging.error(f"Failed to download {repo_id}: {e}")

if __name__ == "__main__":
    download_sota_models()