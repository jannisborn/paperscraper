"""API for bioRxiv and medRXiv."""
import requests
from typing import Optional


class XRXivApi:
    """API class."""

    def __init__(
        server: str,
        self, api_base_url: str = 'api.biorxiv.org',
        launch_date: Optional[str] = None
    ):
        """
        Initialize API class.

        Args:
            server (str): name of the preprint server to access.
            api_base_url (str, optional): Base url for the API. Defaults to 'api.biorxiv.org'.
            launch_date (Optional[str], optional): Launch date expressed as YYYY-MM-DD.
                Defaults to None.
        """
        self.server = server
        self.api_base_url = api_base_url
        self.launch_date = launch_date
        self.details = 'details'
