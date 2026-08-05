from abc import abstractmethod
from typing import Dict

from pydantic import BaseModel


class EntityResult(BaseModel):
    # aggregated results
    self_citation_ratio: float = 0
    self_reference_ratio: float = 0
    # total number of author citations/references
    num_citations: int
    num_references: int
    # keys are papers and values are percentage of self citations/references
    self_citations: Dict[str, float] = {}
    self_references: Dict[str, float] = {}


class Entity:
    """
    An abstract entity class with a set of utilities shared by the objects that perform
    self-linking analyses, such as Paper and Researcher.
    """

    @abstractmethod
    def self_references(self):
        """
        Has to be implemented by the child class. Performs a self-referencing analyses
        for the object.
        """
        ...

    @abstractmethod
    def self_citations(self):
        """
        Has to be implemented by the child class. Performs a self-citation analyses
        for the object.
        """
        ...

    @abstractmethod
    def get_result(self):
        """
        Has to be implemented by the child class. Provides the result of the analysis.
        """
        ...
