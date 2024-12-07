from typing import Literal, Optional

from semanticscholar import SemanticScholar

from .core import Entity, EntityResult


class ResearcherResult(EntityResult):
    name: str
    ssid: int
    orcid: Optional[str] = None
    # TODO: the ratios will be averaged across all papers for that author


ModeType = Literal[tuple(MODES := ("doi", "name", "orcid", "ssid"))]

sch = SemanticScholar()


class Researcher(Entity):
    name: str
    ssid: int
    orcid: Optional[str] = None

    def __init__(self, input: str, mode: ModeType):
        if mode not in MODES:
            raise ValueError(f"Unknown mode {mode} chose from {MODES}.")

        if mode == "ssid":
            author = sch.get_author(input)

    def self_references(self):
        """
        Sifts through all papers of a researcher and extracts the self references.
        """
        ...

    def self_citations(self):
        """
        Sifts through all papers of a researcher and finds how often they are self-cited.
        """
        ...

    def get_result(self) -> ResearcherResult:
        """
        Provides the result of the analysis.
        """
        ...
