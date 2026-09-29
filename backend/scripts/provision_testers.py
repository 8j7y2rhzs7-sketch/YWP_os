"""Provision external tester accounts with active subscription (no Whop charge).

Usage on a host with DATABASE_URL (Render Shell if scripts are present):
  python -m scripts.provision_testers --email a@x.com --password '...'
"""

from __future__ import annotations

import argparse
import secrets
import string

from app.core.database import SessionLocal
from app.services.tester_access import upsert_tester


def _password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision YWP OS tester accounts")
    parser.add_argument("--email", action="append", dest="emails")
    parser.add_argument("--password", action="append", dest="passwords", default=[])
    parser.add_argument("--name", action="append", dest="names", default=[])
    args = parser.parse_args()
    emails = args.emails or ["tester1@ywp-os.test", "tester2@ywp-os.test"]
    passwords = list(args.passwords)
    names = list(args.names)
    while len(passwords) < len(emails):
        passwords.append(_password())
    while len(names) < len(emails):
        names.append(emails[len(names)].split("@")[0].replace(".", " ").title())

    with SessionLocal() as db:
        for email, password, name in zip(emails, passwords, names, strict=True):
            user, created = upsert_tester(
                db, email=email, password=password, name=name
            )
            db.commit()
            verb = "Created" if created else "Updated"
            print(f"{verb}: {user.email} / {password} (subscription=active)")


if __name__ == "__main__":
    main()
