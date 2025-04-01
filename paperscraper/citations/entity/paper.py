import logging
import re
import sys
from typing import List, Literal, Optional

from ..self_citations import CitationResult, self_citations_paper
from ..self_references import ReferenceResult, self_references_paper
from ..utils import (
    DOI_PATTERN,
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
            if (
                len(input) > 15
                and " " not in input
                and (input.isalnum() and input.islower())
            ):
                # This is a paper ID
                mode = "ssid"
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
            self.ref_result: ReferenceResult = self_references_paper(self.doi)

    def self_citations(self):
        """
        Extracts the self citations of a paper, for each author.
        """
        if isinstance(self.doi, str):
            self.citation_result: CitationResult = self_citations_paper(self.doi)

    def get_result(self) -> Optional[PaperResult]:
        """
        Provides the result of the analysis.
        """
        if not hasattr(self, "ref_result"):
            logger.warning(
                f"Can't get result since no referencing result for {self.input} exists."
            )
            return
        elif not hasattr(self, "citation_result"):
            logger.warning(
                f"Can't get result since no citation result for {self.input} exists."
            )
            return
        ref_result = self.ref_result.model_dump()
        ref_result.pop("ssid", None)
        return PaperResult(
            title=self.title, **ref_result, **self.citation_result.model_dump()
        )
