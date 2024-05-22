import logging
import threading

import pytest

from paperscraper.get_dumps import biorxiv, medrxiv

logging.disable(logging.INFO)


class TestDumper:
    @pytest.fixture
    def setup_medrxiv(self):
        return medrxiv

    @pytest.fixture
    def setup_biorxiv(self):
        return lambda: biorxiv(max_retries=2)

    def run_function_with_timeout(self, func, timeout):
        # Define the target function for the thread
        def target():
            func()

        # Create a daemon thread that runs the target function
        thread = threading.Thread(target=target)
        thread.daemon = True  # This makes the thread exit when the main thread exits
        thread.start()
        thread.join(
            timeout=timeout
        )  # Wait for the specified time or until the function finishes
        if thread.is_alive():
            return True  # Function is still running, which is our success condition
        return False  # Function has completed or failed within the timeout, which we don't expect

    @pytest.mark.timeout(30)
    def test_medrxiv(self, setup_medrxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(
            setup_medrxiv, 15
        ), "medrxiv should still be running after 15 seconds"

    @pytest.mark.timeout(30)
    def test_biorxiv(self, setup_biorxiv):
        # Check that the function runs for at least 15 seconds
        assert self.run_function_with_timeout(
            setup_biorxiv, 15
        ), "biorxiv should still be running after 15 seconds"
