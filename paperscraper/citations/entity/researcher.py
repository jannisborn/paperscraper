import os
from typing import Any, List, Literal, Optional, Tuple

from semanticscholar import SemanticScholar

from ...async_utils import run_sync
from ..orcid import orcid_to_author_name
from ..self_citations import CitationResult, self_citations_paper
from ..self_references import ReferenceResult, self_references_paper
from ..utils import author_name_to_ssaid, get_papers_for_author
from .core import Entity, EntityResult


class ResearcherResult(EntityResult):
    name: str
    ssaid: int
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
            ("ssaid", self.ssaid),
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
    ssaid: int
    orcid: Optional[str] = None
    ssids: List[int] = []

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
            self.ssaid = input
        elif mode == "orcid":
            orcid_name = orcid_to_author_name(input)
            self.orcid = input
            self.ssaid, self.name = author_name_to_ssaid(orcid_name)
        elif mode == "name":
            self.name = input
            self.ssaid, self.name = author_name_to_ssaid(input)

        self.result = ResearcherResult(
            name=self.name,
            ssaid=int(self.ssaid),
            orcid=self.orcid,
            num_citations=-1,
            num_references=-1,
        )

    async def _self_references_async(
        self, verbose: bool = False
    ) -> List[ReferenceResult]:
        """Async version of self_references."""
        if self.ssaid == "-1":
            return []
        if self.ssids == []:
            self.ssids = await get_papers_for_author(self.ssaid)

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
        reference_results = run_sync(self._self_references_async(verbose=verbose))

        individual_self_references = {
            getattr(result, "title"): getattr(result, "self_references").get(
                self.name, 0.0
            )
            for result in reference_results
        }
        reference_ratio = sum(individual_self_references.values()) / max(
            1, len(individual_self_references)
        )

        self.result = self.result.model_copy(
            update={
                "num_references": sum(r.num_references for r in reference_results),
                "self_references": dict(
                    sorted(
                        individual_self_references.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                ),
                "self_reference_ratio": round(reference_ratio, 3),
            }
        )

        return self.result

    async def _self_citations_async(
        self, verbose: bool = False
    ) -> List[CitationResult]:
        """Async version of self_citations."""
        if self.ssaid == "-1":
            return []
        if self.ssids == []:
            self.ssids = await get_papers_for_author(self.ssaid)

        results: List[CitationResult] = await self_citations_paper(
            self.ssids, verbose=verbose
        )
        # Remove papers with zero references or that are erratum/corrigendum
        results = [
            r
            for r in results
            if r.num_citations > 0
            and "erratum" not in r.title.lower()
            and "corrigendum" not in r.title.lower()
        ]

        return results

    def self_citations(self, verbose: bool = False) -> ResearcherResult:
        """
        Sifts through all papers of a researcher and finds how often they are self-cited.

        Args:
            verbose: If True, logs detailed information for each paper.
        """
        citation_results = run_sync(self._self_citations_async(verbose=verbose))
        individual_self_citations = {
            getattr(result, "title"): getattr(result, "self_citations").get(
                self.name, 0.0
            )
            for result in citation_results
        }
        citation_ratio = sum(individual_self_citations.values()) / max(
            1, len(individual_self_citations)
        )

        self.result = self.result.model_copy(
            update={
                "num_citations": sum(r.num_citations for r in citation_results),
                "self_citations": dict(
                    sorted(
                        individual_self_citations.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )
                ),
                "self_citation_ratio": round(citation_ratio, 3),
            }
        )

        return self.result

    def get_result(self) -> ResearcherResult:
        """
        Provides the result of the analysis.
        """
        if getattr(self.result, "num_references", -1) < 0:
            self.self_references()
        if getattr(self.result, "num_citations", -1) < 0:
            self.self_citations()
        return self.result
