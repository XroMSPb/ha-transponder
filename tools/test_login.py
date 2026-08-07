"""Standalone validator for the ЗСД cabinet client.

Run this before installing the integration to confirm your credentials work and
the balance parses correctly. It uses the exact same code as the Home Assistant
integration (custom_components/zsd_transponder/api.py).

Usage:
    pip install aiohttp
    python tools/test_login.py --username YOUR_LOGIN
    # (you'll be prompted for the password, or pass --password)

Nothing is stored; credentials are used only for this one request.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

# Make the standalone api.py / const.py importable without pulling in Home Assistant.
COMPONENT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "custom_components",
    "zsd_transponder",
)
sys.path.insert(0, COMPONENT_DIR)

import aiohttp  # noqa: E402

from api import ZsdApiClient, ZsdAuthError, ZsdConnectionError  # noqa: E402


async def main(username: str, password: str) -> int:
    async with aiohttp.ClientSession() as session:
        client = ZsdApiClient(session, username, password)
        try:
            contracts = await client.async_get_balances()
        except ZsdAuthError as err:
            print(f"❌ Auth failed: {err}")
            return 2
        except ZsdConnectionError as err:
            print(f"❌ Connection/parse error: {err}")
            return 3

    print("✅ Login OK. Contracts found:\n")
    for c in contracts:
        print(f"  Договор : {c.contract}")
        print(f"  Статус  : {c.status}")
        print(f"  Баланс  : {c.balance} ₽")
        print(f"  Обновлено: {c.updated_at}")
        print()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test ЗСД cabinet login")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()
    pw = args.password or getpass.getpass("Пароль ЗСД: ")
    raise SystemExit(asyncio.run(main(args.username, pw)))
