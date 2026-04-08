from __future__ import annotations

import unittest
from pathlib import Path


COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.yaml"


class DockerComposeConfigTests(unittest.TestCase):
    def test_published_ports_bind_to_loopback_by_default(self) -> None:
        compose = COMPOSE_PATH.read_text(encoding="utf-8")

        self.assertIn('"${SIGNOZ_CODEX_BIND_ADDR:-127.0.0.1}:8105:8080"', compose)
        self.assertIn('"${SIGNOZ_CODEX_BIND_ADDR:-127.0.0.1}:5317:4317"', compose)
        self.assertIn('"${SIGNOZ_CODEX_BIND_ADDR:-127.0.0.1}:5318:4318"', compose)

    def test_histogram_helper_download_is_checksum_verified(self) -> None:
        compose = COMPOSE_PATH.read_text(encoding="utf-8")

        self.assertIn("set -euo pipefail", compose)
        self.assertIn("SIGNOZ_CODEX_CLICKHOUSE_HISTOGRAM_SHA256", compose)
        self.assertIn("sha256sum -c -", compose)


if __name__ == "__main__":
    unittest.main()
