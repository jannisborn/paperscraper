import json
import logging
import math
import sys
import time
from email.utils import parsedate_to_datetime
from functools import wraps
from importlib import resources
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Type, TypeVar

import pandas as pd

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar("T")
DOI_PATTERN = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"


def retry_after_seconds(value: Optional[str]) -> float:
    """Parse an HTTP Retry-After delay or date; invalid/past values mean no delay."""
    if value is None:
        return 0.0
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = parsedate_to_datetime(value).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            return 0.0
    return max(0.0, seconds) if math.isfinite(seconds) else 0.0


def _resolve_backend(
    backend: str,
    api_key: Optional[str],
    api_backends: Sequence[Tuple[str, Optional[str]]],
    default: str,
) -> str:
    """Resolve an automatic backend from configured API keys."""
    if backend != "auto":
        return backend
    if api_key is not None:
        raise ValueError("api_key cannot be used with backend='auto'")
    return next((name for name, key in api_backends if key), default)


def retry_with_exponential_backoff(
    *,
    max_attempts: int = 3,
    retry_if: Callable[[T], bool] = lambda result: False,
    exceptions: Tuple[Type[BaseException], ...] = (),
    base_delay: float = 1,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a function after failures, waiting ``base_delay * 2**attempt``."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                except exceptions:
                    if attempt == max_attempts - 1:
                        raise
                else:
                    if not retry_if(result) or attempt == max_attempts - 1:
                        return result
                if base_delay:
                    time.sleep(base_delay * 2**attempt)
            raise RuntimeError("unreachable")

        return wrapper

    return decorator


def get_server_dumps_dir() -> str:
    """Return the filesystem path to the bundled server_dumps directory."""
    return str(resources.files("paperscraper").joinpath("server_dumps"))


def dump_papers(papers: pd.DataFrame, filepath: str) -> None:
    """
    Receives a pd.DataFrame, one paper per row and dumps it into a .jsonl
    file with one paper per line.

    Args:
        papers (pd.DataFrame): A dataframe of paper metadata, one paper per row.
        filepath (str): Path to dump the papers, has to end with `.jsonl`.
    """
    if not isinstance(filepath, str):
        raise TypeError(f"filepath must be a string, not {type(filepath)}")
    if not filepath.endswith(".jsonl"):
        raise ValueError("Please provide a filepath with .jsonl extension")

    if isinstance(papers, List) and all([isinstance(p, Dict) for p in papers]):
        papers = pd.DataFrame(papers)
        logger.warning(
            "Preferably pass a pd.DataFrame, not a list of dictionaries. "
            "Passing a list is a legacy functionality that might become deprecated."
        )

    if not isinstance(papers, pd.DataFrame):
        raise TypeError(f"papers must be a pd.DataFrame, not {type(papers)}")

    paper_list = list(papers.T.to_dict().values())

    with open(filepath, "w") as f:
        for paper in paper_list:
            f.write(json.dumps(paper) + "\n")


def get_filename_from_query(query: List[str]) -> str:
    """Convert a keyword query into filenames to dump the paper.

    Args:
        query (list): List of string with keywords.

    Returns:
        str: Filename.
    """
    filename = "_".join([k if isinstance(k, str) else k[0] for k in query]) + ".jsonl"
    filename = filename.replace(" ", "").lower()
    return filename


def load_jsonl(filepath: str) -> List[Dict[str, str]]:
    """
    Load data from a `.jsonl` file, i.e., a file with one dictionary per line.

    Args:
        filepath (str): Path to `.jsonl` file.

    Returns:
        List[Dict[str, str]]: A list of dictionaries, one per paper.
    """

    with open(filepath, "r") as f:
        data = [json.loads(line) for line in f if line.strip()]
    return data
