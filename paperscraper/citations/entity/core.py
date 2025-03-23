from abc import abstractmethod
from typing import Dict

from pydantic import BaseModel


class EntityResult(BaseModel):
    num_citations: int = -1
    num_references: int = -1
    # keys are authors or papers and values are absolute self links
    self_citations: Dict[str, int] = {}
    self_references: Dict[str, int] = {}
    # aggregated results
    self_citation_ratio: float = 0
    self_reference_ratio: float = 0


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
