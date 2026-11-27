#!/usr/bin/env python3
"""BPM B2 loan origination + B3 repayment."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    FineractClient,
    cfg_int,
    clients_with_loans,
    clients_with_savings,
    load_clients,
    load_env,
    load_state,
    loan_originate,
    loan_repay,
    new_correlation_id,
    new_trace_id,
    save_clients,
    setup_warnings,
)


def main() -> int:
    load_env()
    setup_warnings()
    api = FineractClient()
    state = load_state()
    product_id = state.get("loan_product_id")
    payment_type_id = int(state.get("payment_type_id") or 1)
    if not product_id:
        print("[bpm-loan] missing loan_product_id — chạy job_seed trước")
        return 1

    clients = load_clients()
    principal = float(cfg_int("LOAN_PRINCIPAL", 1_000_000))
    originate_n = cfg_int("BPM_LOAN_ORIGINATE_COUNT", 2)
    repay_n = cfg_int("BPM_LOAN_REPAY_COUNT", 5)
    rmin = cfg_int("LOAN_REPAY_MIN", 50_000)
    rmax = cfg_int("LOAN_REPAY_MAX", 200_000)

    ok_o = fail_o = ok_r = fail_r = 0

    # B2 — chỉ client có savings, chưa có loan
    candidates = [c for c in clients_with_savings(clients) if not c.get("loan_id")]
    random.shuffle(candidates)
    for c in candidates[:originate_n]:
        corr = new_correlation_id()
        tid = new_trace_id()
        print(f"[bpm-loan] originate client={c['client_id']} corr={corr} trace={tid}")
        r = loan_originate(
            api, c["client_id"], int(product_id), principal, correlation_id=corr, trace_id=tid
        )
        if not r.get("ok"):
            fail_o += 1
            print(f"[bpm-loan] originate FAIL corr={corr} trace={tid} {r.get('detail')}")
            continue
        c["loan_id"] = r["loan_id"]
        c["loan_correlation_id"] = corr
        c["loan_trace_id"] = tid
        ok_o += 1
        print(f"[bpm-loan] originate ok loan={r['loan_id']} corr={corr} trace={tid}")

    save_clients(clients)

    # B3 — repayment
    loans = clients_with_loans(clients)
    if not loans:
        print("[bpm-loan] no loans for repay — seed/originate trước")
    for _ in range(min(repay_n, max(len(loans), 0))):
        if not loans:
            break
        c = random.choice(loans)
        corr = new_correlation_id()
        tid = new_trace_id()
        amount = random.randint(rmin, rmax)
        r = loan_repay(
            api, c["loan_id"], amount, payment_type_id, correlation_id=corr, trace_id=tid
        )
        if r.get("ok"):
            ok_r += 1
            print(
                f"[bpm-loan] repay ok loan={c['loan_id']} amount={amount} corr={corr} trace={tid}"
            )
        else:
            fail_r += 1
            print(
                f"[bpm-loan] repay FAIL loan={c['loan_id']} corr={corr} trace={tid} {r.get('detail')}"
            )

    print(f"[bpm-loan] summary originate ok={ok_o} fail={fail_o} | repay ok={ok_r} fail={fail_r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
