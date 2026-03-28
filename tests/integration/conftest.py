from __future__ import annotations

import os
from typing import Dict

import pytest
import requests


def _should_run_integration() -> bool:
    return os.getenv("RUN_DESKTOP_INTEGRATION_TESTS", "0").strip() == "1"


@pytest.fixture(scope="session")
def integration_base_url() -> str:
    return os.getenv("DESKTOP_TEST_API_BASE", "http://127.0.0.1:8765").rstrip("/")


@pytest.fixture(scope="session")
def integration_headers() -> Dict[str, str]:
    return {
        "X-API-Key": os.getenv("DESKTOP_TEST_API_KEY", "desktop-control-key"),
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="session")
def integration_session() -> requests.Session:
    # 强制直连本地服务，避免受系统 HTTP(S)_PROXY 干扰返回 502。
    session = requests.Session()
    session.trust_env = False
    return session


@pytest.fixture(scope="session", autouse=True)
def integration_gate(integration_base_url: str, integration_session: requests.Session):
    if not _should_run_integration():
        pytest.skip("未开启真实集成测试。设置 RUN_DESKTOP_INTEGRATION_TESTS=1 后再执行。")

    try:
        resp = integration_session.get(f"{integration_base_url}/health", timeout=2)
        if resp.status_code != 200:
            pytest.skip(f"目标服务不可用：{integration_base_url} /health status={resp.status_code}")
    except Exception as exc:
        pytest.skip(f"目标服务不可达：{integration_base_url}，错误：{exc}")
