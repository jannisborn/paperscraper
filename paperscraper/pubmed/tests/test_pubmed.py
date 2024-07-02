from paperscraper.pubmed import get_and_dump_pubmed_papers, get_pubmed_papers
from paperscraper.pubmed.utils import get_query_from_keywords_and_date
import os
import pytest
from unittest.mock import patch
import tempfile

KEYWORDS = [['machine learning', 'deep learning'], ['zoology']]


class TestPubMed:

    def test_get_and_dump_pubmed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_filepath = os.path.join(temp_dir, 'tmp.jsonl')
            get_and_dump_pubmed_papers(KEYWORDS, output_filepath=output_filepath)
            assert os.path.exists(output_filepath), "File was not created"
    
    def test_email(self):
        query = get_query_from_keywords_and_date(KEYWORDS, start_date='2020/07/20')
        df = get_pubmed_papers(query, fields=['emails', 'title', 'authors'])
        assert 'emails' in df.columns

        query = get_query_from_keywords_and_date(KEYWORDS, end_date='2020/07/20')
        df = get_pubmed_papers(query, fields=['emails', 'title', 'authors'])
        assert 'emails' in df.columns

        query = get_query_from_keywords_and_date(KEYWORDS, start_date='2020/07/10', end_date='2020/07/20')
        df = get_pubmed_papers(query, fields=['emails', 'title', 'authors'])
        assert 'emails' in df.columns

