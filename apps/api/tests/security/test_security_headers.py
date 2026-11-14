# 文件说明：后端自动化测试：test_security_headers。
import httpx


async def test_api_responses_include_security_headers(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/api/v1/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
