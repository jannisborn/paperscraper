import logging
import sys
from typing import List, Literal, Optional

from ..self_citations import CitationResult, self_citations_paper
from ..self_references import ReferenceResult, self_references_paper
from ..utils import (
    determine_paper_input_type,
    get_doi_from_ssid,
    get_doi_from_title,
    get_title_and_id_from_doi,
)
from .core import Entity

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


class PaperResult(ReferenceResult, CitationResult):
    title: str


ModeType = Literal[tuple(MODES := ("doi", "title", "ss_id", "infer"))]

BASE_URL: str = "https://api.semanticscholar.org/graph/v1/paper/search"


class Paper(Entity):
    title: str = ""
    doi: str = ""
    authors: List[str] = []

    def __init__(self, input: str, mode: ModeType = "infer"):
        """
        Set up a Paper object for analysis.

        Args:
            input: Paper identifier. This can be the title, DOI or semantic scholar ID
                of the paper.
            mode: The format in which the ID was provided. Defaults to "infer".

        Raises:
            ValueError: If unknown mode is given.
        """
        if mode not in MODES:
            raise ValueError(f"Unknown mode {mode} chose from {MODES}.")

        input = input.strip()
        self.input = input
        if mode == "infer":
            mode = determine_paper_input_type(input)

        if mode == "doi":
            self.doi = input
        elif mode == "title":
            self.doi = get_doi_from_title(input)
        elif mode == "ssid":
            self.doi = get_doi_from_ssid(input)

        if self.doi is not None:
            out = get_title_and_id_from_doi(self.doi)
            if out is not None:
                self.title = out["title"]
                self.ssid = out["ssid"]

    def self_references(self):
        """
        Extracts the self references of a paper, for each author.
        """
        if isinstance(self.doi, str):
            self.self_ref: ReferenceResult = self_references_paper(self.doi)

    def self_citations(self):
        """
        Extracts the self citations of a paper, for each author.
        """
        if isinstance(self.doi, str):
            self.self_cite: CitationResult = self_citations_paper(self.doi)

    def get_result(self) -> Optional[PaperResult]:
        """
        Provides the result of the analysis.

        Returns: PaperResult if available.
        """
        if not hasattr(self, "self_ref"):
            self.self_references()
        if not hasattr(self, "self_cite"):
            self.self_citations()
        return PaperResult(
            title=self.title,
            **{
                k: v
                for k, v in self.self_ref.model_dump().items()
                if k not in ["ssid", "title"]
            },
            **{
                k: v
                for k, v in self.self_cite.model_dump().items()
                if k not in ["title"]
            },
        )
