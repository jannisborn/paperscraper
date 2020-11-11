from typing import List, Union

finalize_disjunction = lambda x: '(' + x[:-4] + ') AND '
finalize_conjunction = lambda x: x[:-5]


def get_query_from_keywords(keywords: List[Union[str, List[str]]]) -> str:
    """Receives a list of keywords and returns the query for the arxiv API.

    Args:
        keywords (List[str, List[str]]): Items will be AND separated. If items
            are lists themselves, they will be OR separated.

    Returns:
        str: query to enter to arxiv API.
    """

    query = ''
    for i, key in enumerate(keywords):
        if isinstance(key, str):
            query += f'all:{key} AND '
        elif isinstance(key, list):
            inter = ''.join([f'all:{syn} OR ' for syn in key])
            query += finalize_disjunction(inter)

    query = finalize_conjunction(query)
    return query
