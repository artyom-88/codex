from __future__ import annotations

import unittest
from pathlib import Path


USERS_XML_PATH = Path(__file__).resolve().parents[1] / "common" / "clickhouse" / "users.xml"


class ClickHouseUsersConfigTests(unittest.TestCase):
    def test_codex_readonly_user_declares_an_authentication_method(self) -> None:
        xml_text = USERS_XML_PATH.read_text(encoding="utf-8")
        user_start = xml_text.find("<codex_readonly>")
        user_end = xml_text.find("</codex_readonly>")

        self.assertGreaterEqual(user_start, 0, "codex_readonly user must exist")
        self.assertGreater(user_end, user_start, "codex_readonly user must have a closing tag")
        user_xml = xml_text[user_start:user_end]
        self.assertTrue(
            any(
                f"<{tag}>" in user_xml or f"<{tag}/>" in user_xml
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
