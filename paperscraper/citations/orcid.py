import logging
import sys

import requests

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://pub.orcid.org/v3.0/"


def orcid_to_author_name(orcid_id: str) -> str:
    """
    Given an ORCID ID (as a string, e.g. '0000-0002-1825-0097'),
    returns the full name of the author from the ORCID public API.
    """

    headers = {"Accept": "application/json"}
    response = requests.get(f"{BASE_URL}{orcid_id}/person", headers=headers)
    if response.status_code == 200:
        data = response.json()
        given = data.get("name", {}).get("given-names", {}).get("value", "")
        family = data.get("name", {}).get("family-name", {}).get("value", "")
        full_name = f"{given} {family}".strip()
        return full_name
    logger.error(
        f"Error fetching ORCID data ({orcid_id}): {response.status_code} {response.text}"
    )
