from unittest.mock import call, patch

from paperscraper.utils import retry_with_exponential_backoff


def test_retry_with_exponential_backoff_retries_results_and_exceptions():
    results = iter([None, ValueError(), "done"])

    @retry_with_exponential_backoff(
        retry_if=lambda result: result is None,
        exceptions=(ValueError,),
    )
    def fetch():
        result = next(results)
        if isinstance(result, BaseException):
            raise result
        return result

    with patch("paperscraper.utils.time.sleep") as sleep:
        assert fetch() == "done"

    assert sleep.call_args_list == [call(1), call(2)]
