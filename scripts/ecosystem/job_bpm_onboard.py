#!/usr/bin/env python3
"""BPM B1 — client onboard: create → open/approve/activate savings → deposit."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    FineractClient,
    cfg_int,
    create_client_active,
    load_clients,
    load_env,
    load_state,
    new_correlation_id,
    open_savings,
    save_clients,
    setup_warnings,
)


def main() -> int:
    load_env()
    setup_warnings()
    api = FineractClient()
    state = load_state()
    product_id = state.get("savings_product_id")
    payment_type_id = int(state.get("payment_type_id") or 1)
    if not product_id:
        print("[bpm-onboard] missing savings_product_id — chạy job_seed trước")
        return 1

    count = cfg_int("BPM_ONBOARD_COUNT", 3)
    deposit = float(cfg_int("INITIAL_DEPOSIT", 5_000_000))
    clients = load_clients()
    start_idx = max([c.get("external_index", 0) for c in clients] + [0]) + 1
    ok = fail = 0

    for n in range(count):
        idx = start_idx + n
        corr = new_correlation_id()
        print(f"[bpm-onboard] start corr={corr} idx={idx}")
        r = create_client_active(api, idx, correlation_id=corr)
        if not r.get("ok"):
            fail += 1
            print(f"[bpm-onboard] create FAIL corr={corr} {r.get('detail')}")
            continue
        s = open_savings(
            api,
            r["client_id"],
            int(product_id),
            correlation_id=corr,
            deposit=deposit,
            payment_type_id=payment_type_id,
        )
        if not s.get("ok"):
            fail += 1
            print(f"[bpm-onboard] savings FAIL corr={corr} {s.get('detail')}")
            # vẫn lưu client để seed/volume dùng sau
            clients.append(
                {
                    "external_index": idx,
                    "client_id": r["client_id"],
                    "firstname": r.get("firstname"),
                    "lastname": r.get("lastname"),
                    "correlation_id": corr,
                }
            )
            continue
        clients.append(
            {
                "external_index": idx,
                "client_id": r["client_id"],
                "savings_id": s["savings_id"],
                "firstname": r.get("firstname"),
                "lastname": r.get("lastname"),
                "correlation_id": corr,
            }
        )
        ok += 1
        print(f"[bpm-onboard] ok client={r['client_id']} savings={s['savings_id']} corr={corr}")
        time.sleep(0.5)

    save_clients(clients)
    print(f"[bpm-onboard] summary ok={ok} fail={fail}")
    return 0 if ok or fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
