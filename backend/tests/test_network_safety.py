"""Security and unit tests for SSRF prevention and URL validation."""

from app.services.trend.network_safety import sanitize_canonical_url, validate_source_url


def test_ssrf_blocked_localhost():
    """Verify localhost variations are blocked."""
    assert validate_source_url("http://localhost/rss.xml", check_dns=False)[0] is False
    assert validate_source_url("http://localhost:8080/feed", check_dns=False)[0] is False
    assert validate_source_url("http://127.0.0.1/rss", check_dns=False)[0] is False
    assert validate_source_url("http://127.0.0.2:8000/feed", check_dns=False)[0] is False


def test_ssrf_blocked_private_ipv4():
    """Verify private RFC 1918 IPv4 ranges are blocked."""
    assert validate_source_url("http://10.0.0.1/feed", check_dns=False)[0] is False
    assert validate_source_url("http://10.255.255.255/rss", check_dns=False)[0] is False
    assert validate_source_url("http://172.16.0.1/feed", check_dns=False)[0] is False
    assert validate_source_url("http://172.31.255.255/feed", check_dns=False)[0] is False
    assert validate_source_url("http://192.168.1.1/feed", check_dns=False)[0] is False
    assert validate_source_url("http://192.168.0.254/feed", check_dns=False)[0] is False


def test_ssrf_blocked_cloud_metadata():
    """Verify AWS/GCP/Azure link-local metadata endpoints are blocked."""
    url1 = "http://169.254.169.254/latest/meta-data/"
    assert validate_source_url(url1, check_dns=False)[0] is False
    url2 = "http://metadata.google.internal/computeMetadata/v1/"
    assert validate_source_url(url2, check_dns=False)[0] is False


def test_ssrf_blocked_ipv6_loopback_and_private():
    """Verify IPv6 loopback and private ranges are blocked."""
    assert validate_source_url("http://[::1]/feed", check_dns=False)[0] is False
    assert validate_source_url("http://[fe80::1]/feed", check_dns=False)[0] is False


def test_ssrf_blocked_prohibited_schemes():
    """Verify non-http/https schemes are blocked."""
    assert validate_source_url("file:///etc/passwd", check_dns=False)[0] is False
    assert validate_source_url("ftp://ftp.example.com/feed.xml", check_dns=False)[0] is False
    assert validate_source_url("gopher://gopher.example.com/", check_dns=False)[0] is False
    assert validate_source_url("data:text/plain;base64,SGVsbG8=", check_dns=False)[0] is False


def test_ssrf_blocked_internal_service_ports():
    """Verify sensitive service ports (PostgreSQL, Redis, MySQL, SSH) are blocked."""
    assert validate_source_url("http://public-news.com:22/rss", check_dns=False)[0] is False
    assert validate_source_url("http://public-news.com:5432/rss", check_dns=False)[0] is False
    assert validate_source_url("http://public-news.com:6379/rss", check_dns=False)[0] is False
    assert validate_source_url("http://public-news.com:3306/rss", check_dns=False)[0] is False


def test_ssrf_allowed_valid_public_urls():
    """Verify valid public HTTPS/HTTP URLs pass syntactic validation."""
    is_safe, error = validate_source_url("https://www.reuters.com/tools/rss", check_dns=False)
    assert is_safe is True
    assert error is None

    is_safe2, _ = validate_source_url("http://feeds.bbci.co.uk/news/rss.xml", check_dns=False)
    assert is_safe2 is True


def test_sanitize_canonical_url_tracking_removal():
    """Verify URL sanitization strips tracking parameters."""
    dirty = "https://news.example.com/story/123?utm_source=twitter&utm_medium=social&fbclid=xyz987"
    clean = sanitize_canonical_url(dirty)
    assert "utm_source" not in clean
    assert "fbclid" not in clean
    assert clean == "https://news.example.com/story/123"
