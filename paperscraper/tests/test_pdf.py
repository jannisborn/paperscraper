
import logging

import pytest

from paperscraper.pdf import save_pdf

logging.disable(logging.INFO)


class TestPDF:
   
    def test_basic_search(self):
        paper_data = {'doi': "10.48550/arXiv.2207.03928"}
        save_pdf(paper_data, filepath='gt4sd_paper.pdf')
        assert os.path.exists('gt4sd_paper.pdf')

    def test_get_from_dump(self):

        save_pdf_from_dump('medrxiv_covid_ai_imaging.jsonl', pdf_path='.', key_to_save='doi')
        assert os.path.exists('gt4sd_paper.pdf')
