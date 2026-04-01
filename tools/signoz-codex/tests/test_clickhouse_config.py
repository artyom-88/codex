from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


USERS_XML_PATH = Path(__file__).resolve().parents[1] / "common" / "clickhouse" / "users.xml"


class ClickHouseUsersConfigTests(unittest.TestCase):
    def test_codex_readonly_user_declares_an_authentication_method(self) -> None:
        root = ET.parse(USERS_XML_PATH).getroot()
        user = root.find("./users/codex_readonly")

        self.assertIsNotNone(user, "codex_readonly user must exist")
        self.assertTrue(
            any(
                user.find(f"./{tag}") is not None
                for tag in (
                    "password",
                    "password_sha256_hex",
                    "password_double_sha1_hex",
                    "no_password",
                    "ldap",
                    "kerberos",
                    "ssl_certificates",
                    "ssh_keys",
                    "http_authentication",
                )
            ),
            "codex_readonly must declare an explicit authentication method",
        )


if __name__ == "__main__":
    unittest.main()
