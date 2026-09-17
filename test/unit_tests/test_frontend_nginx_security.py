"""Security contract tests for the Atlas Nginx configuration."""

from pathlib import Path


NGINX_CONFIG = Path(__file__).parents[2] / "frontend/config/nginx/nginx.conf"


def test_frontend_nginx_does_not_forward_browser_credentials() -> None:
    """Strip Basic authorization before proxying requests to backend APIs."""
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    for location in ("database", "dictionary", "translator"):
        block = config.split(f"location /api/{location}/ {{", maxsplit=1)[1].split("}", maxsplit=1)[0]
        assert 'proxy_set_header Authorization "";' in block


def test_frontend_nginx_streams_api_responses_without_global_temp_storage() -> None:
    """Unprivileged Atlas workers must not write API responses under /var/lib/nginx."""
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    for location in ("database", "dictionary", "translator", "services", "operations", "maintenance", "gemma"):
        block = config.split(f"location /api/{location}/ {{", maxsplit=1)[1].split("}", maxsplit=1)[0]
        assert "proxy_buffering off;" in block


def test_frontend_nginx_bounds_translator_proxy_waits() -> None:
    """Fail connections quickly while allowing tracked translator requests to complete."""
    config = NGINX_CONFIG.read_text(encoding="utf-8")
    block = config.split("location /api/translator/ {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]

    assert "proxy_connect_timeout 5s;" in block
    assert "proxy_read_timeout 60s;" in block


def test_frontend_nginx_proxies_gemma_through_authenticated_gateway() -> None:
    """Keep Gemma credentials server-side while allowing long model responses."""
    config = NGINX_CONFIG.read_text(encoding="utf-8")
    block = config.split("location /api/gemma/ {", maxsplit=1)[1].split("}", maxsplit=1)[0]

    assert "proxy_pass http://atlas_supervisor_control/gemma/;" in block
    assert "proxy_read_timeout 130s;" in block
    assert "proxy_set_header X-Atlas-Authenticated $remote_user;" in block
    assert 'proxy_set_header Authorization "";' in block
    assert "supervisor-control-proxy.conf" in block


def test_frontend_nginx_proxies_dashboard_statistics_to_postgrest() -> None:
    """Proxy the dashboard statistics materialized view without serving a stale local file."""
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    assert "location = /api/database/rpc/atlas_dashboard_statistics {" not in config
    block = config.split("location /api/database/ {", maxsplit=1)[1].split("}", maxsplit=1)[0]
    assert "proxy_pass http://atlas_postgrest/;" in block
    assert 'proxy_set_header Authorization "";' in block


def test_frontend_nginx_blocks_operational_files_and_framing() -> None:
    """Keep deployment files private and prevent UI redressing attacks."""
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    assert 'Content-Security-Policy "frame-ancestors \'none\'"' in config
    assert 'X-Frame-Options "DENY"' in config
    locations = (
        "location ^~ /config/",
        "location ^~ /logs/",
        "location = /configure-atlas.sh",
        "location = /setup-tls.sh",
    )
    for location in locations:
        block = config.split(f"{location} {{", maxsplit=1)[1].split("}", maxsplit=1)[0]
        assert "deny all;" in block


def test_frontend_nginx_loads_persistent_supervisor_rpc_configuration() -> None:
    """Reinstalling replaceable frontend files must not remove remote RPC access."""
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    assert "include /etc/botjagwar/supervisor-rpc-location.conf;" in config
    assert "include supervisor-rpc-location.conf;" not in config
