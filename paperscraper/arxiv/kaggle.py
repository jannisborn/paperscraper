"""Kaggle-backed arXiv metadata dumping utilities."""

import glob
import json
import os
import shutil
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from tqdm import tqdm

from ..utils import get_server_dumps_dir

DEFAULT_KAGGLE_DATASET = "Cornell-University/arxiv"


def arxiv_kaggle(
    start_date: datetime,
    end_date: datetime,
    save_path: str,
    kaggle_filepath: Optional[str] = None,
) -> int:
    """Convert a Kaggle arXiv metadata snapshot to paperscraper JSONL format.

    Args:
        start_date: Earliest paper submission date to include.
        end_date: Latest paper submission date to include.
        save_path: Destination JSONL path for converted papers.
        kaggle_filepath: Existing Kaggle snapshot file. If provided, no Kaggle
            download is attempted.

    Returns:
        Number of papers written to `save_path`.
    """
    cleanup_dir = default_kaggle_dir() if kaggle_filepath is None else None
    if kaggle_filepath is None:
        kaggle_filepath = download_kaggle_snapshot()

    try:
        written = 0
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        total_size = os.path.getsize(kaggle_filepath)
        with (
            open(kaggle_filepath, "r", encoding="utf-8") as in_fp,
            open(save_path, "w", encoding="utf-8") as out_fp,
            tqdm(
                total=total_size,
                desc="Converting arXiv Kaggle snapshot",
                unit="B",
                unit_scale=True,
            ) as progress_bar,
        ):
            for line in in_fp:
                progress_bar.update(len(line.encode("utf-8")))
                if not line.strip():
                    continue

                record = json.loads(line)
                paper_date = get_kaggle_paper_date(record)
                if paper_date is None or not start_date <= paper_date <= end_date:
                    continue

                if written > 0:
                    out_fp.write(os.linesep)
                out_fp.write(json.dumps(normalize_kaggle_record(record, paper_date)))
                written += 1
        return written
    finally:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def download_kaggle_snapshot() -> str:
    """Download the Kaggle arXiv metadata snapshot if needed.

    Returns:
        Path to the local Kaggle snapshot JSON file.

    Raises:
        ImportError: If the `kaggle` package is not installed.
        RuntimeError: If Kaggle authentication is missing or invalid.
        FileNotFoundError: If the download succeeds but no snapshot JSON is found.
    """
    kaggle_dir = default_kaggle_dir()
    os.makedirs(kaggle_dir, exist_ok=True)

    if existing_snapshot := find_kaggle_snapshot(kaggle_dir):
        return existing_snapshot

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        raise ImportError(
            "The Kaggle backend requires the `kaggle` package. Install it with "
            "`pip install kaggle` or `uv add kaggle`."
        ) from exc
    except SystemExit as exc:
        raise RuntimeError(
            "Kaggle authentication is required for the arXiv Kaggle backend. "
            "Run `kaggle auth login` or configure Kaggle credentials."
        ) from exc

    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as exc:
        raise RuntimeError(
            "Kaggle authentication is required for the arXiv Kaggle backend. "
            "Run `kaggle auth login` or configure Kaggle credentials."
        ) from exc
    api.dataset_download_files(
        DEFAULT_KAGGLE_DATASET,
        path=kaggle_dir,
        unzip=True,
        quiet=False,
    )

    snapshot = find_kaggle_snapshot(kaggle_dir)
    if snapshot is None:
        raise FileNotFoundError(f"No arXiv Kaggle snapshot found in {kaggle_dir}")
    return snapshot


def default_kaggle_dir() -> str:
    """Return the default temporary directory for Kaggle arXiv downloads.

    Returns:
        Path to the default Kaggle download directory.
    """
    return os.path.join(get_server_dumps_dir(), "arxiv_kaggle")


def find_kaggle_snapshot(kaggle_dir: str) -> Optional[str]:
    """Find the arXiv metadata snapshot JSON in a Kaggle download directory.

    Args:
        kaggle_dir: Directory to search.

    Returns:
        Path to the largest candidate JSON file, or None if no candidate exists.
    """
    candidates = [
        *glob.glob(os.path.join(kaggle_dir, "arxiv-metadata*.json")),
        *glob.glob(os.path.join(kaggle_dir, "*.json")),
    ]
    candidates = [path for path in candidates if os.path.isfile(path)]
    if not candidates:
        return None
    return sorted(candidates, key=os.path.getsize, reverse=True)[0]


def get_kaggle_paper_date(record: dict) -> Optional[datetime]:
    """Extract the first submission date from a Kaggle arXiv record.

    Args:
        record: Raw Kaggle arXiv metadata record.

    Returns:
        Naive UTC-normalized submission date at midnight, or None if no usable
        date is available.
    """
    created = next(
        (version.get("created") for version in record.get("versions", []) if version),
        None,
    )
    if created:
        try:
            date = parsedate_to_datetime(created)
            if date.tzinfo is not None:
                date = date.astimezone(timezone.utc).replace(tzinfo=None)
            return date.replace(hour=0, minute=0, second=0, microsecond=0)
        except (TypeError, ValueError):
            pass

    update_date = record.get("update_date")
    if update_date:
        try:
            return datetime.strptime(update_date, "%Y-%m-%d")
        except ValueError:
            return None
    return None


def normalize_kaggle_record(record: dict, paper_date: datetime) -> dict:
    """Normalize a Kaggle arXiv record to paperscraper dump fields.

    Args:
        record: Raw Kaggle arXiv metadata record.
        paper_date: Submission date returned by `get_kaggle_paper_date`.

    Returns:
        Dictionary with paperscraper's standard `title`, `authors`, `date`,
        `abstract`, `journal`, and `doi` fields.
    """
    arxiv_id = str(record.get("id", "")).split("v")[0]
    return {
        "title": normalize_whitespace(record.get("title", "")),
        "authors": normalize_whitespace(record.get("authors", "")),
        "date": paper_date.strftime("%Y-%m-%d"),
        "abstract": normalize_whitespace(record.get("abstract", "")),
        "journal": normalize_whitespace(record.get("journal-ref", "")),
        "doi": record.get("doi") or f"10.48550/arXiv.{arxiv_id}",
    }


def normalize_whitespace(value: Optional[str]) -> str:
    return " ".join(str(value or "").split())
