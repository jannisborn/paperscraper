
import logging
import os
import pytest

from paperscraper.pdf import save_pdf

logging.disable(logging.INFO)


class TestPDF:
   
    def test_basic_search(self):
        paper_data = {'doi': "10.48550/arXiv.2207.03928"}
        save_pdf(paper_data, filepath='gt4sd_paper.pdf')
        assert os.path.exists('gt4sd_paper.pdf')

