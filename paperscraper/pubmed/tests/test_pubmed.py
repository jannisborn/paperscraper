from paperscraper.pubmed import get_and_dump_pubmed_papers
import os


class TestPubMed:

    def test_get_and_dump_pubmed(self):
        query = [['machine learning', 'deep learning'], ['zoology']]
        get_and_dump_pubmed_papers(query, output_filepath='tmp.jsonl')

        assert os.path.exists('tmp.jsonl')
