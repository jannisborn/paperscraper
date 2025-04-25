from typing import List, Literal, Optional

from semanticscholar import SemanticScholar
from tqdm import tqdm

from ..orcid import orcid_to_author_name
from ..self_references import ReferenceResult
from ..utils import author_name_to_ssaid, get_papers_for_author
from .core import Entity, EntityResult


class ResearcherResult(EntityResult):
    name: str
    ssid: int
    orcid: Optional[str] = None
    # TODO: the ratios will be averaged across all papers for that author


ModeType = Literal[tuple(MODES := ("name", "orcid", "ssaid", "infer"))]

sch = SemanticScholar()


class Researcher(Entity):
    name: str
    ssid: int
    orcid: Optional[str] = None

    def __init__(self, input: str, mode: ModeType = "infer"):
        """
        Construct researcher object for self citation/reference analysis.

        Args:
            input: A researcher to search for.
            mode: This can be a `name` `orcid` (ORCID iD) or `ssaid` (Semantic Scholar Author ID).
                Defaults to "infer".

        Raises:
            ValueError: Unknown mode
        """
        if mode not in MODES:
            raise ValueError(f"Unknown mode {mode} chose from {MODES}.")

        input = input.strip()
        if mode == "infer":
            if input.isdigit():
                mode = "ssaid"
            elif (
                input.count("-") == 3
                and len(input) == 19
                and all([x.isdigit() for x in input.split("-")])
            ):
                mode = "orcid"
            else:
                mode = "author"

        if mode == "ssaid":
            self.author = sch.get_author(input)
            self.ssid = input
        elif mode == "orcid":
            self.author = orcid_to_author_name(input)
            self.orcid = input
            self.ssid = author_name_to_ssaid(input)
        elif mode == "author":
            self.author = input
            self.ssid = author_name_to_ssaid(input)

        # TODO: Skip over erratum / corrigendum
        self.ssids = get_papers_for_author(self.ssid)

    def self_references(self):
        """
        Sifts through all papers of a researcher and extracts the self references.
        """
        # TODO: Asynchronous call to self_references
        print("Going through SSIDs", self.ssids)

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
