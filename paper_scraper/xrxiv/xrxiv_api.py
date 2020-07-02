"""API for bioRxiv and medRXiv."""
import requests
from datetime import datetime
from typing import Optional, List, Generator


launch_dates = {
    'biorxiv': '2013-01-01',
    'medrxiv': '2019-06-01'
}


class XRXivApi:
    """API class."""

    def __init__(
        self,
        server: str,
        launch_date: str,
        api_base_url: str = 'https://api.biorxiv.org'
    ):
        """
        Initialize API class.

        Args:
            server (str): name of the preprint server to access.
            launch_date (str): launch date expressed as YYYY-MM-DD.
            api_base_url (str, optional): Base url for the API. Defaults to 'api.biorxiv.org'.
        """
        self.server = server
        self.api_base_url = api_base_url
        self.launch_date = launch_date
        self.launch_datetime = datetime.fromisoformat(self.launch_date)
        self.get_papers_url = '{}/details/{}'.format(
            self.api_base_url, self.server
        ) + '/{begin_date}/{end_date}/{cursor}'

    def get_papers(
        self,
        begin_date: Optional[str] = None,
        end_date: Optional[str] = None,
        fields: List[str] = ['title', 'doi', 'authors', 'abstract', 'date', 'journal']
    ) -> Generator:
        """
        Get paper metadata.

        Args:
            begin_date (Optional[str], optional): begin date. Defaults to None, a.k.a. launch date.
            end_date (Optional[str], optional): end date. Defaults to None, a.k.a. today.
            fields (List[str], optional): fields to return per paper.
                Defaults to ['title', 'doi', 'authors', 'abstract', 'date', 'journal'].

        Yields:
            Generator: a generator of paper metadata (dict) with the desired fields.
        """
        try:
            now_datetime = datetime.now()
            if begin_date:
                begin_datetime = datetime.fromisoformat(begin_date)
                if begin_datetime < self.launch_datetime:
                    begin_date = self.launch_date
            else:
                begin_date = self.launch_date
            if end_date:
                end_datetime = datetime.fromisoformat(end_date)
                if end_datetime > now_datetime:
                    end_date = now_datetime.strftime('%Y-%m-%d')
            else:
                end_date = now_datetime.strftime('%Y-%m-%d')
            do_loop = True
            cursor = 0
            while do_loop:
                json_response = requests.get(
                    self.get_papers_url.format(
                        begin_date=begin_date,
                        end_date=end_date,
                        cursor=cursor
                    )
                ).json()
                do_loop = json_response['messages'][0]['status'] == 'ok'
                if do_loop:
                    cursor += json_response['messages'][0]['count']
                    for paper in json_response['collection']:
                        processed_paper = {
                            field: paper.get(field, '')
                            for field in fields
                        }
                        yield processed_paper
        except Exception as exc:
            raise RuntimeError('Failed getting papers: {} - {}'.format(
                exc.__class__.__name__, exc
            ))


class BioRxivApi(XRXivApi):
    """bioRxiv API."""

    def __init__(self):
        super().__init__(server='biorxiv', launch_date=launch_dates['biorxiv'])


class MedRxivApi(XRXivApi):
    """medRxiv API."""

    def __init__(self):
        super().__init__(server='medrxiv', launch_date=launch_dates['medrxiv'])
