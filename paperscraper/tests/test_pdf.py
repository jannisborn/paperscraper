import logging
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from paperscraper.load_dumps import QUERY_FN_DICT
from paperscraper.pdf import save_pdf, save_pdf_from_dump

logging.disable(logging.INFO)


TEST_FILE_PATH = str(Path(__file__).parent / "test_dump.jsonl")
SAVE_PATH = "tmp_pdf_storage"


class TestPDF:

    @pytest.fixture
    def paper_data(self):
        return {"doi": "10.48550/arXiv.2207.03928"}

    def test_basic_search(self):
        paper_data = {"doi": "10.48550/arXiv.2207.03928"}
        save_pdf(paper_data, filepath="gt4sd_paper.pdf")
        assert os.path.exists("gt4sd_paper.pdf")
        os.remove("gt4sd_paper.pdf")

    def test_missing_doi(self):
        with pytest.raises(KeyError):
            paper_data = {"title": "Sample Paper"}
            save_pdf(paper_data, "sample_paper.pdf")

    def test_invalid_metadata_type(self):
        with pytest.raises(TypeError):
            save_pdf(paper_metadata="not_a_dict", filepath="output.pdf")

    def test_missing_doi_key(self):
        with pytest.raises(KeyError):
            save_pdf(paper_metadata={}, filepath="output.pdf")

    def test_invalid_filepath_type(self):
        with pytest.raises(TypeError):
            save_pdf(paper_metadata=self.paper_data, filepath=123)

    def test_incorrect_filepath_extension(self):
        with pytest.raises(TypeError):
            save_pdf(paper_metadata=self.paper_data, filepath="output.txt")

    def test_incorrect_filepath_type(self):
        with pytest.raises(TypeError):
            save_pdf(paper_metadata=list(self.paper_data), filepath="output.txt")

    def test_nonexistent_directory_in_filepath(self, paper_data):
        with pytest.raises(ValueError):
            save_pdf(paper_metadata=paper_data, filepath="/nonexistent/output.pdf")

    @patch("requests.get")
    def test_network_issues_on_doi_url_request(self, mock_get, paper_data):
        mock_get.side_effect = Exception("Network error")
        save_pdf(paper_metadata=paper_data, filepath="output.pdf")
        assert not os.path.exists("output.pdf")

    @patch("requests.get")
    def test_missing_pdf_url_in_meta_tags(self, mock_get, paper_data):
        response = MagicMock()
        response.text = "<html></html>"
        mock_get.return_value = response
        save_pdf(paper_metadata=paper_data, filepath="output.pdf")
        assert not os.path.exists("output.pdf")

    @patch("requests.get")
    def test_network_issues_on_pdf_url_request(self, mock_get, paper_data):
        response_doi = MagicMock()
        response_doi.text = (
            '<meta name="citation_pdf_url" content="http://valid.url/document.pdf">'
        )
        mock_get.side_effect = [response_doi, Exception("Network error")]
        save_pdf(paper_metadata=paper_data, filepath="output.pdf")
        assert not os.path.exists("output.pdf")

    @patch("requests.get")
    @patch("builtins.open", new_callable=mock_open)
    def test_successful_pdf_download_and_save(self, mock_file, mock_get, paper_data):
        response_doi = MagicMock()
        response_doi.text = (
            '<meta name="citation_pdf_url" content="http://valid.url/document.pdf">'
        )
        response_pdf = MagicMock()
        response_pdf.content = b"PDF content"
        mock_get.side_effect = [response_doi, response_pdf]
        save_pdf(paper_metadata=paper_data, filepath="output.pdf")
        mock_file.assert_called_once_with("output.pdf", "wb+")
        mock_file().write.assert_called_once_with(b"PDF content")

    def test_save_pdf_from_dump_without_path(self):
        with pytest.raises(ValueError):
            save_pdf_from_dump(TEST_FILE_PATH, pdf_path=SAVE_PATH, key_to_save="doi")

    def test_save_pdf_from_dump_wrong_type(self):
        with pytest.raises(TypeError):
            save_pdf_from_dump(-1, pdf_path=SAVE_PATH, key_to_save="doi")

    def test_save_pdf_from_dump_wrong_output_type(self):
        with pytest.raises(TypeError):
            save_pdf_from_dump(TEST_FILE_PATH, pdf_path=1, key_to_save="doi")

    def test_save_pdf_from_dump_wrong_suffix(self):
        with pytest.raises(ValueError):
            save_pdf_from_dump(
                TEST_FILE_PATH.replace("jsonl", "json"),
                pdf_path=SAVE_PATH,
                key_to_save="doi",
            )

    def test_save_pdf_from_dump_wrong_key(self):
        with pytest.raises(ValueError):
            save_pdf_from_dump(TEST_FILE_PATH, pdf_path=SAVE_PATH, key_to_save="doix")

    def test_save_pdf_from_dump_wrong_key_type(self):
        with pytest.raises(TypeError):
            save_pdf_from_dump(TEST_FILE_PATH, pdf_path=SAVE_PATH, key_to_save=["doix"])

    def test_save_pdf_from_dump(self):
        os.makedirs(SAVE_PATH, exist_ok=True)
        save_pdf_from_dump(TEST_FILE_PATH, pdf_path=SAVE_PATH, key_to_save="doi")
        shutil.rmtree(SAVE_PATH)
