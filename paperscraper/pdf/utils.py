import os
from typing import Dict, Optional

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
