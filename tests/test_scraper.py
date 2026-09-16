import pytest
import requests

from price_tracker.parsing import BlockedError
from price_tracker.scraper import FetchError, fetch_html


class FakeResponse:
    def __init__(self, status_code: int, text: str = "<html></html>") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_retries_then_succeeds():
    session = FakeSession(
        [requests.ConnectionError("boom"), FakeResponse(503), FakeResponse(200, "ok")]
    )
    waits: list[float] = []
    assert fetch_html("https://x", session=session, sleep=waits.append) == "ok"
    assert session.calls == 3
    assert len(waits) == 2 and waits[1] > waits[0]  # exponential backoff


def test_gives_up_after_retries():
    session = FakeSession([FakeResponse(503)] * 3)
    with pytest.raises(FetchError, match="3 attempts"):
        fetch_html("https://x", session=session, sleep=lambda _: None)


def test_captcha_is_not_retried(load_fixture):
    session = FakeSession([FakeResponse(503, load_fixture("captcha.html"))])
    with pytest.raises(BlockedError):
        fetch_html("https://x", session=session, sleep=lambda _: None)
    assert session.calls == 1
