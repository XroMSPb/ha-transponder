"""Standalone validator for the Transponder clients (ЗСД / Автодор).

Run this before installing the integration to confirm your credentials work and
balances parse correctly. It uses the exact same code as the integration
(custom_components/transponder/api/).

Usage:
    pip install aiohttp
    python tools/test_login.py --provider zsd     --username YOUR_LOGIN
    python tools/test_login.py --provider avtodor --username YOUR_EMAIL_OR_PHONE
    # (you'll be prompted for the password, or pass --password)

Nothing is stored; credentials are used only for this one request.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

COMPONENT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components",
    "transponder",
)
sys.path.insert(0, COMPONENT_DIR)

import aiohttp  # noqa: E402

import api  # noqa: E402  (custom_components/transponder/api)
from const import DEFAULT_HEADERS  # noqa: E402


async def main(provider: str, username: str, password: str) -> int:
    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        client = api.get_client(provider, session, username, password)
        try:
            accounts = await client.async_get_accounts()
        except api.TransponderAuthError as err:
            print(f"❌ Auth failed: {err}")
            return 2
        except api.TransponderConnectionError as err:
            print(f"❌ Connection/parse error: {err}")
            return 3

    print(f"✅ Login OK ({provider}). Accounts:\n")
    for a in accounts:
        print(f"  Договор / Contract : {a.contract}")
        print(f"  Лицевой счёт       : {a.extra.get('account') or a.account_id}")
        print(f"  Статус             : {a.status}")
        print(f"  Баланс             : {a.balance} {a.currency}")
        if a.bonus_points is not None:
            print(f"  Бонусные баллы     : {a.bonus_points}")
        if a.transponders_count is not None:
            print(f"  Транспондеров      : {a.transponders_count}")
        print(f"  Обновлено          : {a.updated_at}")
        print()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test transponder cabinet login")
    parser.add_argument("--provider", required=True, choices=["zsd", "avtodor"])
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()
    pw = args.password or getpass.getpass("Пароль: ")
    raise SystemExit(asyncio.run(main(args.provider, args.username, pw)))
