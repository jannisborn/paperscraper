import os
from typing import Dict, Optional
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def load_api_keys(filepath: Optional[str] = None) -> Dict[str, str]:
    """
    Reads API keys from a file and returns them as a dictionary.
    The file should have each API key on a separate line in the format:
        KEY_NAME=API_KEY_VALUE

    Example:
        WILEY_TDM_API_TOKEN=your_wiley_token_here
        ELSEVIER_TDM_API_KEY=your_elsevier_key_here

    Args:
        filepath: Optional path to the file containing API keys.

    Returns:
        Dict[str, str]: A dictionary where keys are API key names and values are their respective API keys.
    """
    if filepath:
        load_dotenv(dotenv_path=filepath)
    else:
        load_dotenv(find_dotenv())

    return {
        "WILEY_TDM_API_TOKEN": os.getenv("WILEY_TDM_API_TOKEN"),
        "ELSEVIER_TDM_API_KEY": os.getenv("ELSEVIER_TDM_API_KEY"),
        "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
    }


def download_pdf_to_path(pdf_url: str, out_path: Path, headers: dict) -> bool:
    # Stream to avoid loading the entire PDF in memory
    with requests.get(
        pdf_url, stream=True, timeout=60, headers=headers, allow_redirects=True
    ) as r:
        r.raise_for_status()
        # Read first chunk to validate it’s a PDF
        it = r.iter_content(chunk_size=64 * 1024)
        first = next(it, b"")
        if not first.startswith(b"%PDF"):
            return False
        with open(out_path.with_suffix(".pdf"), "wb") as f:
            f.write(first)
            for chunk in it:
                if chunk:
                    f.write(chunk)
    return True
