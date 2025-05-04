import logging
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paperscraper.pdf import load_api_keys, save_pdf, save_pdf_from_dump
from paperscraper.pdf.fallbacks import FALLBACKS

logging.disable(logging.INFO)


TEST_FILE_PATH = str(Path(__file__).parent / "test_dump.jsonl")
SAVE_PATH = "tmp_pdf_storage"


class TestPDF:
    @pytest.fixture
    def paper_data(self):
        return {"doi": "10.48550/arXiv.2207.03928"}

    def test_basic_search(self):
        paper_data = {"doi": "10.48550/arXiv.2207.03928"}
        save_pdf(paper_data, filepath="gt4sd.pdf", save_metadata=True)
        assert os.path.exists("gt4sd.pdf")
        assert os.path.exists("gt4sd.json")
        os.remove("gt4sd.pdf")
        os.remove("gt4sd.json")

        # chemrxiv
        paper_data = {"doi": "10.26434/chemrxiv-2021-np7xj-v4"}
        save_pdf(paper_data, filepath="kinases.pdf", save_metadata=True)
        assert os.path.exists("kinases.pdf")
        assert os.path.exists("kinases.json")
        os.remove("kinases.pdf")
        os.remove("kinases.json")

        # biorxiv
        if os.path.exists("taskload.pdf"):
            os.remove("taskload.pdf")
        paper_data = {"doi": "10.1101/798496"}
        os.environ.pop("AWS_ACCESS_KEY_ID", None)
        os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
        save_pdf(paper_data, filepath="taskload.pdf", save_metadata=True)
        # NOTE: Locally this fails but surprisingly the CI does not need to fight with Cloudflare for the moment
        assert os.path.exists("taskload.pdf")
        assert os.path.exists("taskload.json")

        # Now try with S3 routine
        keys = load_api_keys("api_keys.txt")
        save_pdf(
            {"doi": "10.1101/786871"},
            filepath="taskload.pdf",
            save_metadata=False,
            api_keys=keys,
        )
        assert os.path.exists("taskload.pdf")
        os.remove("taskload.pdf")

        # Test S3 fallback explicitly
        FALLBACKS["s3"](doi="10.1101/786871", output_path="taskload.pdf", api_keys=keys)
        assert os.path.exists("taskload.pdf")
        os.remove("taskload.pdf")

        # medrxiv
        paper_data = {"doi": "10.1101/2020.09.02.20187096"}
        save_pdf(paper_data, filepath="covid_review.pdf", save_metadata=True)
        assert os.path.exists("covid_review.pdf")
        assert os.path.exists("covid_review.json")
        os.remove("covid_review.pdf")
        os.remove("covid_review.json")

        # journal with OA paper
        paper_data = {"doi": "10.1038/s42256-023-00639-z"}
        save_pdf(paper_data, filepath="regression_transformer", save_metadata=True)
        assert os.path.exists("regression_transformer.pdf")
        assert os.path.exists("regression_transformer.json")
        os.remove("regression_transformer.pdf")
        os.remove("regression_transformer.json")

        # book chapter with paywall
        paper_data = {"doi": "10.1007/978-981-97-4828-0_7"}
        save_pdf(paper_data, filepath="clm_chapter", save_metadata=True)
        assert not os.path.exists("clm_chapter.pdf")
        assert os.path.exists("clm_chapter.json")
        os.remove("clm_chapter.json")

        # journal without OA paper
        paper_data = {"doi": "10.1126/science.adk9587"}
        save_pdf(paper_data, filepath="color", save_metadata=True)
        assert not os.path.exists("color.pdf")
        assert not os.path.exists("color.json")

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

    def test_api_keys_none_pmc(self):
        """Test that save_pdf works properly even when no API keys are provided. Paper in PMC."""
        test_doi = {"doi": "10.1038/s41587-022-01613-7"}  # DOI known to be in PMC
        filename = SAVE_PATH + "_pmc"
        # Call function with no API keys
        save_pdf(test_doi, filepath=filename, api_keys=None)

        # Verify file was created - with .xml extension from PMC fallback
        assert os.path.exists(filename + ".xml"), (
            "XML file was not created via PMC fallback"
        )
        os.remove(filename + ".xml")

    def test_api_keys_none_oa(self):
        """Test that save_pdf works properly even when no API keys are provided. Paper available open-access."""
        test_doi = {"doi": "10.1038/s42256-023-00639-z"}  # DOI known to be OA
        filename = SAVE_PATH + "_oa"
        # Call function with no API keys
        save_pdf(test_doi, filepath=filename, api_keys=None)

        # Verify file was created - with .pdf extension for direct PDF download
        assert os.path.exists(filename + ".pdf"), (
            "PDF file was not created for OA content"
        )
        os.remove(filename + ".pdf")

    def test_api_key_file(self):
        test_doi = {"doi": "10.1002/smll.202309431"}  # Use a DOI from Wiley
        with open("tmp_keyfile.txt", "w") as f:
            f.write("WILEY_TDM_API_TOKEN=INVALID_TEST_KEY_123")
        save_pdf(test_doi, filepath=SAVE_PATH, api_keys="tmp_keyfile.txt")
        os.remove("tmp_keyfile.txt")

    def test_api_key_env(self):
        test_doi = {"doi": "10.1002/smll.202309431"}  # Use a DOI known to be in PMC
        with patch.dict(
            os.environ, {"WILEY_TDM_API_TOKEN": "ANOTHER_INVALID_TEST_KEY"}
        ):
            save_pdf(test_doi, filepath=SAVE_PATH, api_keys=None)

    @pytest.mark.skipif(
        os.getenv("INSTITUTIONAL_NETWORK") != "1",
        reason="Not in an institutional network",
    )
    def test_api_key_file_academic_network(self):
        test_doi = {"doi": "10.1002/smll.202309431"}  # Use a DOI from Wiley
        filename = SAVE_PATH + "_wiley"
        wiley_key_path = SAVE_PATH + "_wiley_key1"
        success = False
        try:
            with open(wiley_key_path, "w") as f:
                f.write("WILEY_TDM_API_TOKEN=INVALID_TEST_KEY_123")
            save_pdf(test_doi, filepath=filename, api_keys=wiley_key_path)
            # Verify file was created - with .pdf extension for Wiley content
            assert os.path.exists(filename + ".pdf"), (
                "PDF file was not created for Wiley content"
            )
            success = True
        finally:
            for file in [filename + ".pdf", wiley_key_path]:
                if os.path.exists(file):
                    os.remove(file)
            if not success:
                raise ValueError("PDF file was not created for Wiley content")

    @pytest.mark.skipif(
        os.getenv("INSTITUTIONAL_NETWORK") != "1",
        reason="Not in an institutional network",
    )
    def test_api_key_file_env_academic_network(self):
        test_doi = {"doi": "10.1002/smll.202309431"}  # Use a DOI from Wiley
        filename = SAVE_PATH + "_wiley"
        line = "WILEY_TDM_API_TOKEN=INVALID_TEST_KEY_123\n"
        # Append to .env file in the current directory
        with open(".env", "a") as f:
            f.write(line)

        try:
            save_pdf(test_doi, filepath=filename, api_keys=None)

            # Verify file was created - with .pdf extension for Wiley content
            assert os.path.exists(filename + ".pdf"), (
                "PDF file was not created for Wiley content"
            )
        finally:
            # Clean up
            if os.path.exists(filename + ".pdf"):
                os.remove(filename + ".pdf")
            with open(".env", "r") as f:
                lines = f.readlines()
            if lines and lines[-1] == line:
                with open(".env", "w") as f:
                    f.writelines(lines[:-1])

    def test_fallback_bioc_pmc_real_api(self):
        """Test the BioC-PMC fallback with a real API call."""
        test_doi = "10.1038/s41587-022-01613-7"  # Use a DOI known to be in PMC
        output_path = Path("test_bioc_pmc_output")
        try:
            result = FALLBACKS["bioc_pmc"](test_doi, output_path)
            assert result is True
            assert (output_path.with_suffix(".xml")).exists()
            with open(
                output_path.with_suffix(".xml"), "r"
            ) as f:  # Check if the file contains XML data
                content = f.read()
                assert "<" in content and ">" in content  # Basic XML check
                assert len(content) > 100  # Should have substantial content
        finally:
            if (output_path.with_suffix(".xml")).exists():
                os.remove(output_path.with_suffix(".xml"))

    def test_fallback_bioc_pmc_no_pmcid(self):
        """Test BioC-PMC fallback when no PMCID is available."""
        test_doi = "10.1002/smll.202309431"  # This DOI should not have a PMCID
        output_path = Path("test_bioc_pmc_no_pmcid")
        result = FALLBACKS["bioc_pmc"](test_doi, output_path)
        assert result is False
        assert not os.path.exists(output_path.with_suffix(".xml"))

    def test_fallback_elife_xml_real_api(self):
        """Test the eLife XML fallback with a real API call."""
        test_doi = "10.7554/eLife.100173"  # Use a DOI known to be in eLife
        output_path = Path("test_elife_xml_output")
        try:
            result = FALLBACKS["elife"](test_doi, output_path)
            assert result is True
            assert (output_path.with_suffix(".xml")).exists()
            with open(
                output_path.with_suffix(".xml"), "r"
            ) as f:  # Check if the file contains XML data
                content = f.read()
                assert "<" in content and ">" in content  # Basic XML check
                assert len(content) > 100  # Should have substantial content
        finally:
            if (output_path.with_suffix(".xml")).exists():
                os.remove(output_path.with_suffix(".xml"))

    def test_fallback_elife_nonexistent_article(self):
        """Test eLife XML fallback with a DOI that looks like eLife but doesn't exist."""
        test_doi = (
            "10.7554/eLife.00001"  # Article that doesn't exist in eLife repository
        )
        output_path = Path("test_elife_nonexistent")
        result = FALLBACKS["elife"](test_doi, output_path)
        # Assertions - should return False and not create a file
        assert result is False
        assert not os.path.exists(output_path.with_suffix(".xml"))

    @patch("requests.get")
    def test_fallback_wiley_api_mock(self, mock_get):
        """Test Wiley API fallback with mocked response."""
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.5 test content"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        paper_metadata = {"doi": "10.1002/smll.202309431"}
        output_path = Path("test_wiley_output")
        api_keys = {"WILEY_TDM_API_TOKEN": "test_token"}
        try:
            FALLBACKS["wiley"](paper_metadata, output_path, api_keys)
            assert mock_get.called
            mock_get.assert_called_with(
                "https://api.wiley.com/onlinelibrary/tdm/v1/articles/10.1002%2Fsmll.202309431",
                headers={"Wiley-TDM-Client-Token": "test_token"},
                allow_redirects=True,
                timeout=60,
            )
            pdf_path = output_path.with_suffix(".pdf")
            assert os.path.exists(pdf_path)
            with open(pdf_path, "rb") as f:
                content = f.read()
                assert content == b"%PDF-1.5 test content"
        finally:
            if os.path.exists(output_path.with_suffix(".pdf")):
                os.remove(output_path.with_suffix(".pdf"))

    def test_fallback_wiley_api_returns_boolean(self):
        """Test that fallback_wiley_api properly returns a boolean value."""
        paper_metadata = {"doi": "10.1002/smll.202309431"}
        output_path = Path("test_wiley_output")
        api_keys = {"WILEY_TDM_API_TOKEN": "INVALID_TEST_KEY_123"}
        result = FALLBACKS["wiley"](paper_metadata, output_path, api_keys)
        # Check the result is a boolean
        # will be True if on university network and False otherwise
        assert isinstance(result, bool)
        if result and output_path.with_suffix(".pdf").exists():
            os.remove(output_path.with_suffix(".pdf"))

    @patch("requests.get")
    def test_fallback_elsevier_api_mock(self, mock_get):
        """Test Elsevier API fallback with mocked response."""
        mock_response = MagicMock()
        mock_response.content = b"<xml>Test content</xml>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        paper_metadata = {"doi": "10.1016/j.xops.2024.100504"}
        output_path = Path("test_elsevier_output")
        api_keys = {"ELSEVIER_TDM_API_KEY": "test_key"}
        try:
            FALLBACKS["elsevier"](paper_metadata, output_path, api_keys)
            assert mock_get.called
            mock_get.assert_called_with(
                "https://api.elsevier.com/content/article/doi/10.1016/j.xops.2024.100504?apiKey=test_key&httpAccept=text%2Fxml",
                headers={"Accept": "application/xml"},
                timeout=60,
            )
            xml_path = output_path.with_suffix(".xml")
            assert os.path.exists(xml_path)
            with open(xml_path, "rb") as f:
                content = f.read()
                assert content == b"<xml>Test content</xml>"
        finally:
            if os.path.exists(output_path.with_suffix(".xml")):
                os.remove(output_path.with_suffix(".xml"))

    def test_fallback_elsevier_api_invalid_key(self, caplog):
        """Test real Elsevier API connectivity by verifying invalid key response pattern."""
        caplog.set_level(logging.ERROR)
        paper_metadata = {"doi": "10.1016/j.xops.2024.100504"}
        output_path = Path("test_elsevier_invalid")
        api_keys = {"ELSEVIER_TDM_API_KEY": "INVALID_TEST_KEY_123"}
        result = FALLBACKS["elsevier"](paper_metadata, output_path, api_keys)
        # Should return False for invalid key
        assert result is False
        assert not output_path.with_suffix(".xml").exists()
        # Check for the specific APIKEY_INVALID error in the logs
        assert "invalid" in caplog.text.lower()
