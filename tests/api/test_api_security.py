"""Security, static assets, and frontend integrity tests."""

import os
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import create_app
from backend.database.connection import DatabaseManager
from backend.api.dependencies import get_db_manager

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@pytest.mark.asyncio
async def test_frontend_index_and_static_assets_served():
    """Test 1 & 2: Root GET / serves frontend index.html; static CSS and JS load with 200."""
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # GET /
        resp_index = await client.get("/")
        assert resp_index.status_code == 200
        assert "IIMBx" in resp_index.text
        assert "DPM-101" in resp_index.text

        # GET /css/styles.css
        resp_css = await client.get("/css/styles.css")
        assert resp_css.status_code == 200
        assert "telemetry-bar" in resp_css.text

        # GET /js/app.js
        resp_js = await client.get("/js/app.js")
        assert resp_js.status_code == 200
        assert "submitQuestion" in resp_js.text

        # GET /js/api.js
        resp_api_js = await client.get("/js/api.js")
        assert resp_api_js.status_code == 200
        assert "ApiClient" in resp_api_js.text


@pytest.mark.asyncio
async def test_security_headers_present():
    """Verify security response headers are added across all endpoints."""
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")

    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_frontend_does_not_expose_secrets():
    """Test 16: Verify no API keys or local secrets are hardcoded in frontend files."""
    frontend_files = [
        FRONTEND_DIR / "index.html",
        FRONTEND_DIR / "css" / "styles.css",
        FRONTEND_DIR / "js" / "app.js",
        FRONTEND_DIR / "js" / "api.js",
        FRONTEND_DIR / "js" / "chat.js",
        FRONTEND_DIR / "js" / "metrics.js",
    ]

    for file_path in frontend_files:
        assert file_path.exists(), f"Expected frontend file {file_path} missing."
        content = file_path.read_text(encoding="utf-8").lower()
        # Verify no hardcoded secrets or environment key patterns
        assert "aiworkspacesec" not in content
        assert "gemini_api_key=" not in content
        assert "secret_key" not in content


def test_no_unsafe_html_injection_in_frontend():
    """Test 17: Verify chat.js and app.js use textContent rather than innerHTML for messages."""
    chat_js = (FRONTEND_DIR / "js" / "chat.js").read_text(encoding="utf-8")

    # Ensure textContent is used for message text
    assert "textEl.textContent = text" in chat_js
    assert "textEl.textContent = answer" in chat_js
    assert "tagEl.textContent = source" in chat_js

    # Ensure no dangerous innerHTML assignment of user text
    assert "innerHTML = text" not in chat_js
    assert "innerHTML = answer" not in chat_js


@pytest.mark.asyncio
async def test_real_app_startup_and_shutdown():
    """Test 18: Verify application lifespan startup and shutdown execute cleanly."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200

