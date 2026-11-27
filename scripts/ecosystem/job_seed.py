#!/usr/bin/env python3
"""Bootstrap: currency/payment/products + clients/savings/loans cho lab Instana."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    FineractClient,
    cfg,
    cfg_int,
    create_client_active,
    ensure_currency,
    ensure_loan_product,
    ensure_payment_type,
    ensure_savings_product,
    load_clients,
    load_env,
    loan_originate,
    open_savings,
    save_clients,
    save_state,
    setup_warnings,
)


def main() -> int:
    load_env()
    setup_warnings()
    api = FineractClient()

    print("[seed] ping offices…")
    ping = api.get("offices/1", business_flow="setup.ping")
    if not ping.get("ok"):
        print(f"[seed] FAIL API: {ping.get('detail')} (check FINERACT_URL / auth)")
        return 1

    currency = ensure_currency(api)
    payment_type_id = ensure_payment_type(api)
    savings_product_id = ensure_savings_product(api, currency)
    loan_product_id = ensure_loan_product(api, currency)
    print(
        f"[seed] currency={currency} paymentType={payment_type_id} "
        f"savingsProduct={savings_product_id} loanProduct={loan_product_id}"
    )

    target_clients = cfg_int("TARGET_CLIENTS", 1000)
    target_savings = cfg_int("TARGET_SAVINGS", 400)
    target_loans = cfg_int("TARGET_LOANS", 150)
    deposit = float(cfg_int("INITIAL_DEPOSIT", 5_000_000))
    principal = float(cfg_int("LOAN_PRINCIPAL", 1_000_000))

    clients = load_clients()
    by_ext = {c.get("external_index"): c for c in clients if c.get("external_index") is not None}
    ok_c = ok_s = ok_l = 0
    fail = 0

    for i in range(target_clients):
        if i in by_ext and by_ext[i].get("client_id"):
            continue
        r = create_client_active(api, i)
        if not r.get("ok"):
            fail += 1
            print(f"[seed] client#{i} fail corr={r.get('correlation_id')} {r.get('detail')}")
            continue
        row = {
            "external_index": i,
            "client_id": r["client_id"],
            "firstname": r.get("firstname"),
            "lastname": r.get("lastname"),
            "correlation_id": r.get("correlation_id"),
        }
        clients.append(row)
        by_ext[i] = row
        ok_c += 1
        if ok_c % 50 == 0:
            save_clients(clients)
            print(f"[seed] clients created={ok_c}")

    save_clients(clients)

    with_savings = sum(1 for c in clients if c.get("savings_id"))
    for c in clients:
        if with_savings >= target_savings:
            break
        if c.get("savings_id"):
            continue
        corr = c.get("correlation_id")
        r = open_savings(
            api,
            c["client_id"],
            savings_product_id,
            correlation_id=corr or "",
            deposit=deposit,
            payment_type_id=payment_type_id,
        )
        if not r.get("ok"):
            fail += 1
            print(f"[seed] savings client={c['client_id']} fail {r.get('detail')}")
            continue
        c["savings_id"] = r["savings_id"]
        with_savings += 1
        ok_s += 1
        if ok_s % 25 == 0:
            save_clients(clients)
            print(f"[seed] savings opened={ok_s} total={with_savings}")

    save_clients(clients)

    with_loans = sum(1 for c in clients if c.get("loan_id"))
    for c in clients:
        if with_loans >= target_loans:
            break
        if not c.get("savings_id") or c.get("loan_id"):
            continue
        r = loan_originate(api, c["client_id"], loan_product_id, principal)
        if not r.get("ok"):
            fail += 1
            print(f"[seed] loan client={c['client_id']} fail {r.get('detail')}")
            continue
        c["loan_id"] = r["loan_id"]
        c["loan_correlation_id"] = r.get("correlation_id")
        with_loans += 1
        ok_l += 1
        if ok_l % 10 == 0:
            save_clients(clients)
            print(f"[seed] loans={ok_l} total={with_loans}")

    save_clients(clients)
    state = {
        "currency": currency,
        "payment_type_id": payment_type_id,
        "savings_product_id": savings_product_id,
        "loan_product_id": loan_product_id,
        "clients": len(clients),
        "savings": sum(1 for c in clients if c.get("savings_id")),
        "loans": sum(1 for c in clients if c.get("loan_id")),
    }
    save_state(state)
    print(
        f"[seed] done new_clients={ok_c} new_savings={ok_s} new_loans={ok_l} "
        f"totals={state} fails={fail}"
    )
    return 0 if fail == 0 or (ok_c + ok_s + ok_l) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
