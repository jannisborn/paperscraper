"""API for bioRxiv and medRxiv."""

import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from tempfile import mkdtemp
from time import sleep
from typing import Dict, Generator, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, HTTPError, JSONDecodeError, Timeout
from tqdm import tqdm

launch_dates = {"biorxiv": "2013-01-01", "medrxiv": "2019-06-01"}
logger = logging.getLogger(__name__)


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class XRXivApi:
    """API class."""

    def __init__(
        self,
        server: str,
        launch_date: str,
        api_base_url: str = "https://api.biorxiv.org",
        max_retries: int = 10,
        request_timeout: Tuple[float, float] = (5.0, 30.0),
        retry_backoff_seconds: float = 1.0,
        window_days: int = 365,
    ):
        """
        Initialize API class.

        Args:
            server: Name of the preprint server to access.
            launch_date: Launch date expressed as YYYY-MM-DD.
            api_base_url: Base url for the API.
            max_retries: Number of retries for transient failures per request.
            request_timeout: (connect timeout, read timeout), in seconds.
            retry_backoff_seconds: Initial backoff delay between retries.
            window_days: Date-window size for full-history scraping. Windows keep
                cursor offsets small and reduce deep-pagination slowdowns.
        """
        self.server = server
        self.api_base_url = api_base_url
        self.launch_date = launch_date
        self.launch_datetime = datetime.fromisoformat(self.launch_date)
        self.get_papers_url = (
            "{}/details/{}".format(self.api_base_url, self.server)
            + "/{start_date}/{end_date}/{cursor}"
        )
        self.max_retries = max(1, int(max_retries))
        self.request_timeout = request_timeout
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.window_days = max(1, int(window_days))

        # Reuse TCP connections across requests to lower latency and avoid
        # repeated TLS setup in long-running dumps.
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _iter_date_windows(self, start_datetime: datetime, end_datetime: datetime):
        """Iterate over date windows using the instance window size.

        Args:
            start_datetime: Start of the overall date range.
            end_datetime: End of the overall date range.

        Yields:
            Tuple[datetime, datetime]: Inclusive window bounds.
        """
        current_start = start_datetime
        max_span = timedelta(days=self.window_days - 1)

        while current_start <= end_datetime:
            current_end = min(current_start + max_span, end_datetime)
            yield current_start, current_end
            current_start = current_end + timedelta(days=1)

    def _normalize_date_range(
        self, start_date: Optional[str], end_date: Optional[str]
    ) -> Tuple[datetime, datetime]:
        """Validate and normalize start/end date inputs.

        Args:
            start_date: Optional start date in YYYY-MM-DD format.
            end_date: Optional end date in YYYY-MM-DD format.

        Returns:
            Tuple[datetime, datetime]: Normalized start and end datetimes.

        Raises:
            ValueError: If the normalized start date is after the end date.
        """
        now_datetime = datetime.now()
        if start_date:
            start_datetime = datetime.fromisoformat(start_date)
            if start_datetime < self.launch_datetime:
                start_datetime = self.launch_datetime
        else:
            start_datetime = self.launch_datetime

        if end_date:
            end_datetime = datetime.fromisoformat(end_date)
            if end_datetime > now_datetime:
                end_datetime = now_datetime
        else:
            end_datetime = now_datetime

        if start_datetime > end_datetime:
            raise ValueError(
                f"start_date {start_datetime.strftime('%Y-%m-%d')} cannot be later than "
                f"end_date {end_datetime.strftime('%Y-%m-%d')}"
            )
        return start_datetime, end_datetime

    def _iter_date_windows_custom(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        window_days: int,
    ):
        """Iterate over date windows for an explicit window size.

        Args:
            start_datetime: Start of the overall date range.
            end_datetime: End of the overall date range.
            window_days: Number of days per yielded window.

        Yields:
            Tuple[datetime, datetime]: Inclusive window bounds.

        Raises:
            ValueError: If `window_days` is smaller than 1.
        """
        if window_days < 1:
            raise ValueError(f"window_days must be >= 1, got {window_days}")
        current_start = start_datetime
        max_span = timedelta(days=window_days - 1)

        while current_start <= end_datetime:
            current_end = min(current_start + max_span, end_datetime)
            yield current_start, current_end
            current_start = current_end + timedelta(days=1)

    def _worker_api(self, worker_window_days: int, worker_retries: int) -> "XRXivApi":
        """Create a dedicated API client for a parallel worker.

        Args:
            worker_window_days: Window size used by the worker client.
            worker_retries: Retry limit used by the worker client.

        Returns:
            XRXivApi: A new client configured like the parent instance.
        """
        # Use a dedicated client per worker to avoid shared-session contention
        # across threads and keep retry/backoff state isolated.
        return XRXivApi(
            server=self.server,
            launch_date=self.launch_date,
            api_base_url=self.api_base_url,
            max_retries=worker_retries,
            request_timeout=self.request_timeout,
            retry_backoff_seconds=self.retry_backoff_seconds,
            window_days=worker_window_days,
        )

    def _fetch_window_to_file(
        self,
        idx: int,
        start_date: str,
        end_date: str,
        output_dir: str,
        fields: List[str],
        max_retries: int,
    ) -> Tuple[int, str, int]:
        """Fetch one date window and persist it as a temporary JSONL chunk.

        Args:
            idx: Window index used for stable chunk ordering.
            start_date: Window start date in YYYY-MM-DD format.
            end_date: Window end date in YYYY-MM-DD format.
            output_dir: Directory where the temporary chunk is written.
            fields: Metadata fields to keep for each record.
            max_retries: Per-request retry limit for this fetch.

        Returns:
            Tuple[int, str, int]: Window index, chunk path, and written row count.
        """
        worker_window_days = (
            datetime.fromisoformat(end_date) - datetime.fromisoformat(start_date)
        ).days + 1
        api = self._worker_api(
            worker_window_days=worker_window_days,
            worker_retries=max_retries,
        )

        part_path = os.path.join(output_dir, f"window_{idx:04d}.jsonl")
        count = 0
        with open(part_path, "w", encoding="utf-8") as fp:
            for paper in api.get_papers(
                start_date=start_date,
                end_date=end_date,
                fields=fields,
                max_retries=max_retries,
            ):
                if count > 0:
                    fp.write(os.linesep)
                fp.write(json.dumps(paper))
                count += 1
        return idx, part_path, count

    @staticmethod
    def _merge_window_files(
        save_path: str,
        ordered_window_paths: List[str],
        deduplicate_dois: bool,
    ) -> int:
        """Merge temporary JSONL chunks into a single output file.

        Args:
            save_path: Final JSONL output path.
            ordered_window_paths: Chunk files sorted by window order.
            deduplicate_dois: Whether to drop duplicate DOI entries.

        Returns:
            int: Number of rows written to `save_path`.
        """
        seen_dois = set()
        written = 0

        with open(save_path, "w", encoding="utf-8") as out_fp:
            for window_path in ordered_window_paths:
                with open(window_path, "r", encoding="utf-8") as in_fp:
                    for line in in_fp:
                        line = line.strip()
                        if not line:
                            continue

                        if deduplicate_dois:
                            paper = json.loads(line)
                            doi = str(paper.get("doi", "")).strip().lower()
                            if doi and doi in seen_dois:
                                continue
                            if doi:
                                seen_dois.add(doi)

                        if written > 0:
                            out_fp.write(os.linesep)
                        out_fp.write(line)
                        written += 1

        return written

    def dump_papers(
        self,
        save_path: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        max_retries: Optional[int] = None,
        max_workers: int = 1,
        window_days: Optional[int] = None,
        deduplicate_dois: bool = False,
        show_progress: bool = True,
    ) -> int:
        """Dump papers to JSONL, optionally in parallel using date windows.

        Args:
            save_path: Output JSONL path.
            start_date: Begin date, YYYY-MM-DD.
            end_date: End date, YYYY-MM-DD.
            fields: Fields to include per paper.
            max_retries: Optional per-request retry override.
            max_workers: Number of parallel window workers.
            window_days: Window size used for partitioning date ranges.
            deduplicate_dois: If True, drop repeated DOIs while merging windows.
            show_progress: If True, render tqdm progress bars.

        Returns:
            Number of records written to `save_path`.
        """
        if fields is None:
            fields = ["title", "doi", "authors", "abstract", "date", "journal"]
        if max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {max_workers}")
        worker_retries = max_retries if max_retries is not None else self.max_retries
        worker_retries = max(1, int(worker_retries))
        span_days = max(
            1, int(window_days if window_days is not None else self.window_days)
        )

        start_datetime, end_datetime = self._normalize_date_range(start_date, end_date)
        start_text = start_datetime.strftime("%Y-%m-%d")
        end_text = end_datetime.strftime("%Y-%m-%d")

        output_dir = os.path.dirname(os.path.abspath(save_path)) or "."
        os.makedirs(output_dir, exist_ok=True)

        if max_workers == 1:
            iterator = self.get_papers(
                start_date=start_text,
                end_date=end_text,
                fields=fields,
                max_retries=worker_retries,
            )
            if show_progress:
                iterator = tqdm(iterator, desc=f"{self.server} dump")

            written = 0
            seen_dois = set()
            with open(save_path, "w", encoding="utf-8") as fp:
                for paper in iterator:
                    if deduplicate_dois:
                        # For sequential mode, track DOIs inline.
                        doi = str(paper.get("doi", "")).strip().lower()
                        if doi and doi in seen_dois:
                            continue
                        if doi:
                            seen_dois.add(doi)

                    if written > 0:
                        fp.write(os.linesep)
                    fp.write(json.dumps(paper))
                    written += 1

            return written

        windows = list(
            self._iter_date_windows_custom(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                window_days=span_days,
            )
        )
        if not windows:
            with open(save_path, "w", encoding="utf-8"):
                pass
            return 0

        # Keep worker chunks outside server_dumps so interrupted runs
        # cannot be mistaken for dump files during module import.
        tmp_dir = mkdtemp(prefix=f"{self.server}_windows_")
        try:
            part_files: Dict[int, str] = {}
            futures = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for idx, (win_start, win_end) in enumerate(windows):
                    fut = executor.submit(
                        self._fetch_window_to_file,
                        idx,
                        win_start.strftime("%Y-%m-%d"),
                        win_end.strftime("%Y-%m-%d"),
                        tmp_dir,
                        fields,
                        worker_retries,
                    )
                    futures.append(fut)

                completion_iter = as_completed(futures)
                if show_progress:
                    completion_iter = tqdm(
                        completion_iter,
                        total=len(futures),
                        desc=f"{self.server} windows",
                    )

                for fut in completion_iter:
                    idx, part_path, _ = fut.result()
                    part_files[idx] = part_path

            ordered_window_paths = [part_files[idx] for idx in sorted(part_files)]
            return self._merge_window_files(
                save_path=save_path,
                ordered_window_paths=ordered_window_paths,
                deduplicate_dois=deduplicate_dois,
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def call_api(
        self,
        start_date: str,
        end_date: str,
        cursor: int,
        max_retries: Optional[int] = None,
    ) -> dict:
        """Call the x-rxiv details endpoint with retry and backoff.

        Args:
            start_date: Query start date in YYYY-MM-DD format.
            end_date: Query end date in YYYY-MM-DD format.
            cursor: Cursor offset for paginated retrieval.
            max_retries: Optional retry override for this call.

        Returns:
            dict: Parsed JSON response payload from the endpoint.

        Raises:
            requests.HTTPError: If a non-retryable HTTP error occurs.
            requests.Timeout: If retries are exhausted after timeout failures.
            requests.ConnectionError: If retries are exhausted after connection failures.
            RuntimeError: If the request loop exits unexpectedly without a result.
        """
        max_attempts = max_retries if max_retries is not None else self.max_retries
        max_attempts = max(1, int(max_attempts))
        backoff = self.retry_backoff_seconds
        transient_status = {408, 429, 500, 502, 503, 504}
        url = self.get_papers_url.format(
            start_date=start_date,
            end_date=end_date,
            cursor=cursor,
        )
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.get(url, timeout=self.request_timeout)
                if response.status_code in transient_status:
                    logger.info(
                        f"{self.server} transient HTTP {response.status_code} at cursor {cursor} "
                        f"for {start_date}..{end_date} (attempt {attempt}/{max_attempts}); retrying"
                    )
                    if attempt == max_attempts:
                        response.raise_for_status()
                    if backoff:
                        sleep(backoff)
                        backoff = min(60.0, max(backoff * 2, backoff + 0.1))
                    continue

                response.raise_for_status()
                return response.json()
            except (Timeout, ConnectionError) as exc:
                last_error = exc
                logger.info(
                    f"{self.server} request failed ({exc.__class__.__name__}) at cursor {cursor} "
                    f"for {start_date}..{end_date} (attempt {attempt}/{max_attempts}); retrying"
                )
                if attempt == max_attempts:
                    raise
                if backoff:
                    sleep(backoff)
                    backoff = min(60.0, max(backoff * 2, backoff + 0.1))
            except (JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.info(
                    f"{self.server} JSON decode failed at cursor {cursor} for {start_date}..{end_date} "
                    f"(attempt {attempt}/{max_attempts}); retrying"
                )
                if attempt == max_attempts:
                    raise
                if backoff:
                    sleep(backoff)
                    backoff = min(60.0, max(backoff * 2, backoff + 0.1))
            except HTTPError as exc:
                last_error = exc
                # Non-transient errors should fail fast.
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("Failed to query x-rxiv API for unknown reasons")

    def get_papers(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: Optional[List[str]] = None,
        max_retries: Optional[int] = None,
    ) -> Generator:
        """
        Get paper metadata.

        Args:
            start_date: Begin date. Defaults to launch date.
            end_date: End date. Defaults to today.
            fields: Fields to return per paper.
            max_retries: Optional per-request retry override.

        Yields:
            A generator of paper metadata dicts.
        """
        if fields is None:
            fields = ["title", "doi", "authors", "abstract", "date", "journal"]

        start_datetime, end_datetime = self._normalize_date_range(start_date, end_date)

        for window_start, window_end in self._iter_date_windows(
            start_datetime, end_datetime
        ):
            start_date_text = window_start.strftime("%Y-%m-%d")
            end_date_text = window_end.strftime("%Y-%m-%d")
            cursor = 0

            while True:
                json_response = self.call_api(
                    start_date=start_date_text,
                    end_date=end_date_text,
                    cursor=cursor,
                    max_retries=max_retries,
                )

                messages = json_response.get("messages", [])
                message = messages[0] if messages else {}
                if message.get("status") != "ok":
                    break

                collection = json_response.get("collection", [])
                if not collection:
                    break

                for paper in collection:
                    yield {field: paper.get(field, "") for field in fields}

                returned_count = len(collection)
                cursor += returned_count

                # The x-rxiv API page size is controlled server-side and has
                # changed over time. Keep paginating until the reported total is
                # reached, or until the API returns an empty collection.
                total = _to_int(message.get("total"), default=0)
                if total and cursor >= total:
                    break


class BioRxivApi(XRXivApi):
    """bioRxiv API."""

    def __init__(
        self,
        max_retries: int = 10,
        request_timeout: Tuple[float, float] = (5.0, 30.0),
        retry_backoff_seconds: float = 1.0,
        window_days: int = 30,
    ):
        super().__init__(
            server="biorxiv",
            launch_date=launch_dates["biorxiv"],
            max_retries=max_retries,
            request_timeout=request_timeout,
            retry_backoff_seconds=retry_backoff_seconds,
            window_days=window_days,
        )


class MedRxivApi(XRXivApi):
    """medRxiv API."""

    def __init__(
        self,
        max_retries: int = 10,
        request_timeout: Tuple[float, float] = (5.0, 30.0),
        retry_backoff_seconds: float = 1.0,
        window_days: int = 30,
    ):
        super().__init__(
            server="medrxiv",
            launch_date=launch_dates["medrxiv"],
            max_retries=max_retries,
            request_timeout=request_timeout,
            retry_backoff_seconds=retry_backoff_seconds,
            window_days=window_days,
        )
