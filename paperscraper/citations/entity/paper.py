import logging
import re
import sys
from typing import List, Literal

from ..self_references import ReferenceResult, self_references_paper
from ..utils import (
    DOI_PATTERN,
    get_doi_from_paper_id,
    get_doi_from_title,
    get_title_and_id_from_doi,
)
from .core import Entity

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


# TODO: Should also inherit from CitationResult
class PaperResult(ReferenceResult):
    title: str
    paper_id: str


ModeType = Literal[tuple(MODES := ("doi", "title", "ss_id", "infer"))]

BASE_URL: str = "https://api.semanticscholar.org/graph/v1/paper/search"


class Paper(Entity):
    title: str
    doi: str
    authors: List[str]

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
        if mode == "infer":
            if (
                len(input) > 15
                and " " not in input
                and (input.isalnum() and input.islower())
            ):
                # This is a paper ID
                mode = "paper_id"
            elif len(re.findall(DOI_PATTERN, input, re.IGNORECASE)) == 1:
                mode = "doi"
            else:
                logger.info(
                    f"Assuming `{input}` is a paper title, since it seems neither a DOI nor a paper ID"
                )
                mode = "title"

        if mode == "doi":
            self.doi = input
        elif mode == "title":
            self.doi = get_doi_from_title(input)
        elif mode == "paper_id":
            self.doi = get_doi_from_paper_id(input)
        out = get_title_and_id_from_doi(self.doi)
        if out is not None:
            self.title = out["title"]
            self.paper_id = out["paper_id"]

    def self_references(self):
        """
        Extracts the self references of a paper, for each author.
        """
        self.ref_result: ReferenceResult = self_references_paper(self.doi)

    def self_citations(self):
        """
        Extracts the self citations of a paper, for each author.
        """
        ...

    def get_result(self) -> PaperResult:
        """
        Provides the result of the analysis.
        """
        return PaperResult(title=self.title, paper_id=self.paper_id, **self.ref_result)
