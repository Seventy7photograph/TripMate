# 文件说明：后端自动化测试：test_ssrf。
import pytest

from app.services.url_safety import UnsafeUrlError, validate_external_http_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/v1",
        "http://localhost:8000/v1",
        "http://[::1]/v1",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://user:pass@example.com/v1",
    ],
)
def test_rejects_private_or_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_external_http_url(url)


def test_allows_public_provider_url() -> None:
    normalized = validate_external_http_url("https://api.deepseek.com/v1/")
    assert normalized == "https://api.deepseek.com/v1"
