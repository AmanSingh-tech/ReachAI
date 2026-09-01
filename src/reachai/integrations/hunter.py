from __future__ import annotations


class HunterClient:
    def find_email(self, name: str, domain: str):
        return f"{name.lower().replace(' ', '.')}@{domain}"

    def verify_email(self, email: str):
        return True
