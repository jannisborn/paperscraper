import asyncio
import os
from typing import Any, List, Literal, Optional, Tuple

from semanticscholar import SemanticScholar

from ..orcid import orcid_to_author_name
from ..self_citations import CitationResult
from ..self_references import ReferenceResult, self_references_paper
from ..utils import author_name_to_ssaid, get_papers_for_author
from .core import Entity, EntityResult


class ResearcherResult(EntityResult):
    name: str
    ssid: int
    orcid: Optional[str] = None

    def _ordered_items(self) -> List[Tuple[str, Any]]:
        # enforce specific ordering
        return [
            ("name", self.name),
            ("self_reference_ratio", self.self_reference_ratio),
            ("self_citation_ratio", self.self_citation_ratio),
            ("num_references", self.num_references),
            ("num_citations", self.num_citations),
            ("self_references", self.self_references),
            ("self_citations", self.self_citations),
            ("ssid", self.ssid),
            ("orcid", self.orcid),
        ]

    def __repr__(self) -> str:
        inner = ", ".join(f"{k}={v!r}" for k, v in self._ordered_items())
        return f"{self.__class__.__name__}({inner})"

    def __str__(self) -> str:
        return " ".join(f"{k}={v!r}" for k, v in self._ordered_items())


ModeType = Literal[tuple(MODES := ("name", "orcid", "ssaid", "infer"))]

sch = SemanticScholar(api_key=os.getenv("SS_API_KEY"))


class Researcher(Entity):
    name: str
    ssid: int
    orcid: Optional[str] = None

    def __init__(self, input: str, mode: ModeType = "infer"):
        """
        Construct researcher object for self citation/reference analysis.

        Args:
            input: A researcher to search for, identified by name, ORCID iD, or Semantic Scholar Author ID.
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
                mode = "name"
        if mode == "ssaid":
            self.name = sch.get_author(input)._name
            self.ssid = input
        elif mode == "orcid":
            orcid_name = orcid_to_author_name(input)
            self.orcid = input
            self.ssid, self.name = author_name_to_ssaid(orcid_name)
        elif mode == "name":
            name = input
            self.ssid, self.name = author_name_to_ssaid(input)

    async def _self_references_async(
        self, verbose: bool = False
    ) -> List[ReferenceResult]:
        """Async version of self_references."""
        self.ssids = await get_papers_for_author(self.ssid)

        results: List[ReferenceResult] = await self_references_paper(
            self.ssids, verbose=verbose
        )
        # Remove papers with zero references or that are erratum/corrigendum
        results = [
            r
            for r in results
            if r.num_references > 0
            and "erratum" not in r.title.lower()
            and "corrigendum" not in r.title.lower()
        ]

        return results

    def self_references(self, verbose: bool = False) -> ResearcherResult:
        """
        Sifts through all papers of a researcher and extracts the self references.

        Args:
            verbose: If True, logs detailed information for each paper.

        Returns:
            A ResearcherResult containing aggregated self-reference data.
        """
        reference_results = asyncio.run(self._self_references_async(verbose=verbose))

        individual_self_references = {
            getattr(result, "title"): getattr(result, "self_references").get(self.name, 0.0)
            for result in reference_results
        }
        reference_ratio = sum(individual_self_references.values()) / max(1, len(
            individual_self_references
        ))
        return ResearcherResult(
            name=self.name,
            ssid=int(self.ssid),
            orcid=self.orcid,
            num_references=sum(r.num_references for r in reference_results),
            num_citations=-1,
            self_references=dict(
                sorted(
                    individual_self_references.items(), key=lambda x: x[1], reverse=True
                )
            ),
            self_citations={},
            self_reference_ratio=round(reference_ratio, 3),
            self_citation_ratio=-1.0,
        )

    def self_citations(self) -> ResearcherResult:
        """
        Sifts through all papers of a researcher and finds how often they are self-cited.
        """
        ...

    def get_result(self) -> ResearcherResult:
        """
        Provides the result of the analysis.
        """
        ...
