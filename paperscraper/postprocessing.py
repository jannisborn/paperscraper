import logging
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def aggregate_paper(
    data: List[Dict[str, str]],
    start_year: int = 2016,
    bins_per_year: int = 4,
    filtering: bool = False,
    filter_keys: List = list(),
    unwanted_keys: List = list(),
    return_filtered: bool = False,
    filter_abstract: bool = True,
    last_year: int = 2021,
):
    """Consumes a list of unstructured keyword results from a .jsonl and
    aggregates papers into several bins per year.

    Args:
        data (List[Dict[str,str]]): Content of a .jsonl file, i.e., a list of
            dictionaries, one per paper.
        start_year (int, optional): First year of interest. Defaults to 2016.
        bins_per_year (int, optional): Defaults to 4 (quarterly aggregation).
        filtering (bool, optional): Whether or not all papers in .jsonl are
            perceived as matches or whether an additional sanity checking for
            the keywords is performed in abstract/title. Defaults to False.
        filter_keys (list, optional): List of str used for filtering. Only
            applies if filtering is True. Defaults to empty list.
        unwanted_keys (list, optional): List of str that must not occur in either
            title or abstract. Only applies if filtering is True.
        return_filtered (bool, optional): Whether the filtered matches are also
            returned. Only applies if filtering is True. Defaults to False.
        filer_abstract (bool, optional): Whether the keyword is searched in the abstract
            or not. Defaults to True.
        last_year (int, optional): Most recent year for the aggregation. Defaults
            to current year. All newer entries are discarded.

    Returns:
        bins (np.array): Vector of length number of years (2020 - start_year) x
            bins_per_year.
    """

    if not isinstance(data, list):
        raise ValueError(f"Expected list, received {type(data)}")
    if not isinstance(bins_per_year, int):
        raise ValueError(f"Expected int, received {type(bins_per_year)}")
    if 12 % bins_per_year != 0:
        raise ValueError(f"Can't split year into {bins_per_year} bins")

    num_years = last_year - start_year + 1
    bins = np.zeros((num_years * bins_per_year))

    if len(data) == 0:
        return bins if not return_filtered else (bins, [])

    # Remove duplicate entries (keep only the first one)
    df = pd.DataFrame(data).sort_values(by="date", ascending=True)
    data = df.drop_duplicates(subset="title", keep="first").to_dict("records")

    dates = [dd["date"] for dd in data]

    filtered = []
    for paper, date in zip(data, dates):
        year = int(date.split("-")[0])
        if year < start_year or year > last_year:
            continue

        # At least one synonym per keyword needs to be in either title or
        # abstract.
        if filtering and filter_keys != list():

            # Filter out papers which undesired terms
            unwanted = False
            for unwanted_key in unwanted_keys:
                if unwanted_key.lower() in paper["title"].lower():
                    unwanted = True
                if (
                    filter_abstract
                    and paper["abstract"] is not None
                    and unwanted_key.lower() in paper["abstract"].lower()
                ):
                    unwanted = True
            if unwanted:
                continue

            got_keys = []
            for key_term in filter_keys:
                got_key = False
                if not isinstance(key_term, list):
                    key_term = [key_term]
                for key in key_term:
                    if key.lower() in paper["title"].lower():
                        got_key = True
                    if (
                        filter_abstract
                        and paper["abstract"] is not None
                        and key.lower() in paper["abstract"].lower()
                    ):
                        got_key = True
                got_keys.append(got_key)

            if len(got_keys) != sum(got_keys):
                continue

        filtered.append(paper)

        if len(date.split("-")) < 2:
            logger.warning(
                f"Paper without month {date}, randomly assigned month."
                f"{paper['title']}"
            )
            month = np.random.choice(12)
        else:
            month = int(date.split("-")[1])

        year_bin = year - start_year
        month_bin = int(np.floor((month - 1) / (12 / bins_per_year)))
        bins[year_bin * bins_per_year + month_bin] += 1

    if return_filtered:
        return bins, filtered
    else:
        return bins
