import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from impact_factor.core import Factor
from thefuzz import fuzz

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.disable(logging.INFO)


class Impactor:
    def __init__(self):
        """
        Initialize the Impactor class with an instance of the Factor class.
        This allows access to the database of journal impact factors.
        """
        self.fa = Factor()
        self.all_journals = self.fa.search("%")
        self.metadata = pd.DataFrame(self.all_journals, dtype=str)
        logger.info(f"Loaded metadata for {len(self.metadata)} journals")

    def search(
        self,
        query: str,
        threshold: int = 100,
        sort_by: Optional[str] = None,
        min_impact: float = 0.0,
        max_impact: float = float("inf"),
        return_all: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search for journals matching the given query with an optional fuzziness
            level and sorting.

        Args:
            query: The journal name or abbreviation to search for.
            threshold: The threshold for fuzzy matching. If set to 100, exact matching
                is performed. If set below 100, fuzzy matching is used. Defaults to 100.
            sort_by: Criterion for sorting results, one of 'impact', 'journal' and 'score'.
            min_impact: Minimum impact factor for journals to be considered, defaults to 0.
            max_impact: Maximum impact factor for journals to be considered, defaults to infinity.
            return_all: If True, returns all columns of the DataFrame for each match.

        Returns:
            List[dict]: A list of dictionaries containing the journal information.

        """
        # Validation of parameters
        if not isinstance(query, str) or not isinstance(threshold, int):
            raise TypeError(
                f"Query must be a str and threshold must be an int, not {type(query)} and {type(threshold)}"
            )
        if threshold < 0 or threshold > 100:
            raise ValueError(
                f"Fuzziness threshold must be between 0 and 100, not {threshold}"
            )

        if str.isdigit(query) and threshold >= 100:
            # When querying with NLM ID, exact matching does not work since impact_factor
            # strips off leading zeros, so we use fuzzy matching instead
            threshold = 99

        # Define a function to calculate fuzziness score
        def calculate_fuzziness_score(row):
            return max(fuzz.partial_ratio(query, str(value)) for value in row.values)

        # Search with or without fuzzy matching
        if threshold >= 100:
            matched_df = self.metadata[
                self.metadata.apply(
                    lambda x: query.lower() in x.astype(str).str.lower().values, axis=1
                )
            ].copy()
            # Exact matches get a default score of 100
            matched_df["score"] = 100
        else:
            matched_df = self.metadata[
                self.metadata.apply(
                    lambda x: calculate_fuzziness_score(x) >= threshold, axis=1
                )
            ].copy()
            matched_df["score"] = matched_df.apply(calculate_fuzziness_score, axis=1)

        # Sorting based on the specified criterion
        if sort_by == "score":
            matched_df = matched_df.sort_values(by="score", ascending=False)
        elif sort_by == "journal":
            matched_df = matched_df.sort_values(by="journal")
        elif sort_by == "impact":
            matched_df = matched_df.sort_values(by="factor", ascending=False)

        matched_df["factor"] = pd.to_numeric(matched_df["factor"])
        matched_df = matched_df[
            (matched_df["factor"] >= min_impact) & (matched_df["factor"] <= max_impact)
        ]

        # Prepare the final result
        results = [
            row.to_dict()
            if return_all
            else {
                "journal": row["journal"],
                "factor": row["factor"],
                "score": row["score"],
            }
            for _, row in matched_df.iterrows()
        ]

        return results
