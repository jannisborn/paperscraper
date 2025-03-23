"""API for bioRxiv and medRXiv."""

import logging
import time
from datetime import datetime
from functools import wraps
from time import sleep
from typing import Generator, List, Optional
from urllib.error import HTTPError

import requests
from requests.exceptions import ConnectionError, Timeout

launch_dates = {"biorxiv": "2013-01-01", "medrxiv": "2019-06-01"}
logger = logging.getLogger(__name__)


def retry_multi():
    """Retry a function several times"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            num_retries = 0
            max_retries = getattr(self, "max_retries", 10)
            while num_retries <= max_retries:
                try:
                    ret = func(self, *args, **kwargs)
                    if ret is None:
                        time.sleep(5)
                        continue
                    break
                except HTTPError:
                    if num_retries == max_retries:
                        raise
                    num_retries += 1
                    time.sleep(5)
            return ret

        return wrapper

    return decorator


class XRXivApi:
    """API class."""

    def __init__(
        self,
        server: str,
        launch_date: str,
        api_base_url: str = "https://api.biorxiv.org",
        max_retries: int = 10,
    ):
        """
        Initialize API class.

        Args:
            server (str): name of the preprint server to access.
            launch_date (str): launch date expressed as YYYY-MM-DD.
            api_base_url (str, optional): Base url for the API. Defaults to 'api.biorxiv.org'.
            max_retries (int, optional): Maximal number of retries for a request before an
                error is raised. Defaults to 10.
        """
        self.server = server
        self.api_base_url = api_base_url
        self.launch_date = launch_date
        self.launch_datetime = datetime.fromisoformat(self.launch_date)
        self.get_papers_url = (
            "{}/details/{}".format(self.api_base_url, self.server)
            + "/{start_date}/{end_date}/{cursor}"
        )
        self.max_retries = max_retries

    @retry_multi()
    def call_api(self, start_date, end_date, cursor):
        try:
            json_response = requests.get(
                self.get_papers_url.format(
                    start_date=start_date, end_date=end_date, cursor=cursor
                ),
                timeout=10,
            ).json()
        except requests.exceptions.Timeout:
            logger.info("Timed out, will retry")
            return None

        return json_response

    def get_papers(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: List[str] = ["title", "doi", "authors", "abstract", "date", "journal"],
        max_retries: int = 10,
    ) -> Generator:
        """
        Get paper metadata.

        Args:
            start_date (Optional[str]): begin date. Defaults to None, a.k.a. launch date.
            end_date (Optional[str]): end date. Defaults to None, a.k.a. today.
            fields (List[str], optional): fields to return per paper.
                Defaults to ['title', 'doi', 'authors', 'abstract', 'date', 'journal'].
            max_retries (int): Number of retries on connection failure. Defaults to 10.

        Yields:
            Generator: a generator of paper metadata (dict) with the desired fields.
        """
        try:
            now_datetime = datetime.now()
            if start_date:
                start_datetime = datetime.fromisoformat(start_date)
                if start_datetime < self.launch_datetime:
                    start_date = self.launch_date
            else:
                start_date = self.launch_date
            if end_date:
                end_datetime = datetime.fromisoformat(end_date)
                if end_datetime > now_datetime:
                    end_date = now_datetime.strftime("%Y-%m-%d")
            else:
                end_date = now_datetime.strftime("%Y-%m-%d")
            do_loop = True
            cursor = 0
            while do_loop:
                papers = []
                for attempt in range(max_retries):
                    try:
                        json_response = self.call_api(start_date, end_date, cursor)
                        do_loop = json_response["messages"][0]["status"] == "ok"
                        if do_loop:
                            cursor += json_response["messages"][0]["count"]
                            for paper in json_response["collection"]:
                                processed_paper = {
                                    field: paper.get(field, "") for field in fields
                                }
                                papers.append(processed_paper)

                        if do_loop:
                            yield from papers
                            break
                    except (ConnectionError, Timeout) as e:
                        logger.error(
                            f"Connection error: {e}. Retrying ({attempt + 1}/{max_retries})"
                        )
                        sleep(5)
                        continue
                    except Exception as exc:
                        logger.exception(f"Failed getting papers: {exc}")
        except Exception as exc:
            logger.exception(f"Failed getting papers: {exc}")


class BioRxivApi(XRXivApi):
    """bioRxiv API."""

    def __init__(self, max_retries: int = 10):
        super().__init__(
            server="biorxiv",
            launch_date=launch_dates["biorxiv"],
            max_retries=max_retries,
        )


class MedRxivApi(XRXivApi):
    """medRxiv API."""

    def __init__(self, max_retries: int = 10):
        super().__init__(
            server="medrxiv",
            launch_date=launch_dates["medrxiv"],
            max_retries=max_retries,
        )
