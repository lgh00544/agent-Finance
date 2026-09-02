"""Batch 18: System Map fact-source import path consistency."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"


def _run_json(code: str, cwd: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_integrity_imports_from_project_root_with_backend_on_path():
    payload = _run_json(
        """
import json
import sys
sys.path.insert(0, 'backend')
from app.system_map import integrity
result = integrity.check_system_map_integrity()
print(json.dumps({
    'status': result['status'],
    'has_source_read_error': any(
        item['kind'] == 'source_read_error' for item in result['issues']
    ),
}))
""",
        PROJECT_ROOT,
    )

    assert payload["status"] in {"healthy", "attention", "error", "unknown"}
    assert payload["has_source_read_error"] is False


def test_integrity_imports_from_backend_directory_without_sys_path_patch():
    payload = _run_json(
        """
import json
from app.system_map import integrity
result = integrity.check_system_map_integrity()
print(json.dumps({
    'status': result['status'],
    'has_source_read_error': any(
        item['kind'] == 'source_read_error' for item in result['issues']
    ),
}))
""",
        BACKEND_DIR,
    )

    assert payload["status"] in {"healthy", "attention", "error", "unknown"}
    assert payload["has_source_read_error"] is False


def test_health_api_from_backend_directory_stays_read_only_and_path_safe():
    payload = _run_json(
        """
import json
from fastapi.testclient import TestClient
from app.main import app
response = TestClient(app).get('/api/system-map/health')
data = response.json()
registration = data['modules']['registration_integrity']
print(json.dumps({
    'status': data['status'],
    'registration_status': registration['status'],
    'has_source_read_error': any(
        item['kind'] == 'source_read_error' for item in registration.get('issues', [])
    ),
}))
""",
        BACKEND_DIR,
    )

    assert payload["status"] in {"healthy", "attention", "error", "unknown"}
    assert payload["has_source_read_error"] is False


def test_agent_modules_can_resolve_agent_prompts_from_backend_directory():
    payload = _run_json(
        """
import json
from app.agents import market_intel, portfolio_sentinel
print(json.dumps({
    'market_intel_prompt': hasattr(market_intel, 'market_intel_prompt'),
    'portfolio_sentinel_prompt': hasattr(portfolio_sentinel, 'portfolio_sentinel_prompt'),
}))
""",
        BACKEND_DIR,
    )

    assert payload["market_intel_prompt"] is True
    assert payload["portfolio_sentinel_prompt"] is True
