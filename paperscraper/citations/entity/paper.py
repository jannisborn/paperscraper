from typing import List

from ..self_references import self_references_paper
from .core import Entity, EntityResult


class PaperResult(EntityResult):
    title: str
    doi: str
    authors: List[str]
    # TODO: the ratios will be averaged across all authors


class Paper(Entity):
    title: str
    doi: str
    authors: List[str]

    def __init__(self, input: str, mode):
        # Determine whether
        ...

    def self_references(self):
        """
        Extracts the self references of a paper, for each author.
        """
        ...

    def self_citations(self):
        """
        Extracts the self citations of a paper, for each author.
        """
        ...

    def get_result(self) -> PaperResult:
        """
        Provides the result of the analysis.
        """
        ...
