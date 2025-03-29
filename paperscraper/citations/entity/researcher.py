from typing import List, Literal, Optional

from semanticscholar import SemanticScholar

from ..orcid import orcid_to_author_name
from ..self_references import ReferenceResult, self_references_paper
from ..utils import author_name_to_ssid, get_papers_for_author
from .core import Entity, EntityResult


class ResearcherResult(EntityResult):
    name: str
    ssid: int
    orcid: Optional[str] = None
    # TODO: the ratios will be averaged across all papers for that author


ModeType = Literal[tuple(MODES := ("name", "orcid", "ssid", "infer"))]

sch = SemanticScholar()


class Researcher(Entity):
    name: str
    ssid: int
    orcid: Optional[str] = None

    def __init__(self, input: str, mode: ModeType = "infer"):
        if mode not in MODES:
            raise ValueError(f"Unknown mode {mode} chose from {MODES}.")

        input = input.strip()
        if mode == "infer":
            if input.isdigit():
                mode = "ssid"
            elif (
                input.count("-") == 3
                and len(input) == 19
                and all([x.isdigit() for x in input.split("-")])
            ):
                mode = "orcid"
            else:
                mode = "author"

        if mode == "ssid":
            self.author = sch.get_author(input)
            self.ssid = input
        elif mode == "orcid":
            self.author = orcid_to_author_name(input)
            self.orcid = input
            self.ssid = author_name_to_ssid(input)
        elif mode == "author":
            self.author = input
            self.ssid = author_name_to_ssid(input)

        self.ssids = get_papers_for_author(self.ssid)

    def self_references(self):
        """
        Sifts through all papers of a researcher and extracts the self references.
        """
        results: List[ReferenceResult] = []
        for ssid in self.ssids:
            results.append(self_references_paper(ssid))

        # TODO: Aggregate results

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
