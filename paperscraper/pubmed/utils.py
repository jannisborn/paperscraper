from pymed.article import PubMedArticle
import warnings
from typing import List, Union

finalize_disjunction = lambda x: "(" + x[:-4] + ") AND "
finalize_conjunction = lambda x: x[:-5]
date_root = '("{0}"[Date - Create] : "{1}"[Date - Create])'


def get_query_from_keywords(keywords: List[Union[str, List]]) -> str:
    """Receives a list of keywords and returns the query for the pubmed API.

    Args:
        keywords (List[str, List[str]]): Items will be AND separated. If items
            are lists themselves, they will be OR separated.

    Returns:
        str: query to enter to pubmed API.
    """

    query = ""
    for i, key in enumerate(keywords):
        if isinstance(key, str):
            query += f"({key}) AND "
        elif isinstance(key, list):
            inter = "".join([f"({syn}) OR " for syn in key])
            query += finalize_disjunction(inter)

    query = finalize_conjunction(query)
    return query


def get_query_from_keywords_and_date(
    keywords: List[Union[str, List]], start_date: str = "None", end_date: str = "None"
) -> str:
    """Receives a list of keywords and returns the query for the pubmed API.

    Args:
        keywords (List[str, List[str]]): Items will be AND separated. If items
            are lists themselves, they will be OR separated.
        start_date (str): Start date for the search. Needs to be in format:
            YYYY/MM/DD, e.g. '2020/07/20'. Defaults to 'None', i.e. no specific
            dates are used.
        end_date (str): End date for the search. Same notation as start_date.

    Note: If start_date and end_date are left as default, the function is
        identical to get_query_from_keywords.

    Returns:
        str: query to enter to pubmed API.
    """

    query = get_query_from_keywords(keywords)

    if start_date != "None" and end_date != "None":
        date = date_root.format(start_date, end_date)
    elif start_date != "None" and end_date == "None":
        date = date_root.format(start_date, "3000")
    elif start_date == "None" and end_date != "None":
        date = date_root.format("1000", end_date)
    else:
        return query

    return query + " AND " + date


def get_emails(paper: PubMedArticle) -> List:
    """
    Extracts author email addresses from PubMedArticle.

    Args:
        paper (PubMedArticle): An object of type PubMedArticle. Requires to have
            an 'author' field.

    Returns:
        List: A possibly empty list of emails associated to authors of the paper.
    """

    emails = []
    for author in paper.authors:
        for v in author.values():
            if v is not None and "@" in v:
                parts = v.split("@")
                if len(parts) == 2:
                    # Found one email address
                    prefix = parts[0].split(" ")[-1]
                    postfix = parts[1]
                    mail = prefix + "@" + postfix
                    if not (postfix.endswith(".") or postfix.endswith(" ")):
                        emails.append(mail)
                    else:
                        emails.append(mail[:-1])
                else:
                    # Found multiple addresses
                    for idx, part in enumerate(parts):
                        try:
                            if idx == 0:
                                prefix = part.split(" ")[-1]
                            else:
                                postfix = part.split("\n")[0]

                                if postfix.endswith("."):
                                    postfix = postfix[:-1]
                                    mail = prefix + "@" + postfix
                                else:
                                    current_postfix = postfix.split(" ")[0]
                                    mail = prefix + "@" + current_postfix
                                    prefix = postfix.split(" ")[1]
                                emails.append(mail)
                        except IndexError:
                            warnings.warn(f"Mail could not be inferred from {part}.")

    return list(set(emails))
