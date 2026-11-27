#!/usr/bin/env python3
"""Volume V1 transfer / V2 deposit / V3 withdraw — nhịp gần theo giây trong 1 lần cron."""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    FineractClient,
    account_transfer,
    cfg_float,
    cfg_int,
    clients_with_savings,
    load_env,
    load_state,
    new_correlation_id,
    savings_deposit,
    savings_withdraw,
    setup_warnings,
)


def main() -> int:
    load_env()
    setup_warnings()
    api = FineractClient()
    state = load_state()
    payment_type_id = int(state.get("payment_type_id") or 1)
    pool = clients_with_savings()
    if len(pool) < 2:
        print("[volume] need >=2 clients with savings — chạy job_seed trước")
        return 1

    rounds = cfg_int("VOLUME_ROUNDS", 40)
    sleep_sec = cfg_float("VOLUME_SLEEP_SEC", 1.0)
    tmin, tmax = cfg_int("TRANSFER_MIN", 10_000), cfg_int("TRANSFER_MAX", 200_000)
    dmin, dmax = cfg_int("DEPOSIT_MIN", 5_000), cfg_int("DEPOSIT_MAX", 100_000)
    wmin, wmax = cfg_int("WITHDRAW_MIN", 5_000), cfg_int("WITHDRAW_MAX", 80_000)

    ok = {"txn.transfer": 0, "txn.deposit": 0, "txn.withdraw": 0}
    fail = 0

    for i in range(rounds):
        corr = new_correlation_id()
        kind = random.choices(
            ["txn.transfer", "txn.deposit", "txn.withdraw"],
            weights=[50, 30, 20],
            k=1,
        )[0]
        if kind == "txn.transfer":
            a, b = random.sample(pool, 2)
            amount = random.randint(tmin, tmax)
            r = account_transfer(api, a, b, amount, correlation_id=corr)
        elif kind == "txn.deposit":
            c = random.choice(pool)
            amount = random.randint(dmin, dmax)
            r = savings_deposit(api, c["savings_id"], amount, payment_type_id, correlation_id=corr)
        else:
            c = random.choice(pool)
            amount = random.randint(wmin, wmax)
            r = savings_withdraw(api, c["savings_id"], amount, payment_type_id, correlation_id=corr)

        if r.get("ok"):
            ok[kind] += 1
            print(f"[volume] ok {kind} amount={amount} corr={corr}")
        else:
            fail += 1
            print(f"[volume] FAIL {kind} corr={corr} {r.get('detail')}")

        if sleep_sec > 0 and i + 1 < rounds:
            time.sleep(sleep_sec)

    print(f"[volume] summary ok={ok} fail={fail}")
    return 0 if fail < rounds else 1


if __name__ == "__main__":
    raise SystemExit(main())
