"""Shared helpers for Fineract ecosystem cron jobs (Instana V1–V3 / B1–B3)."""
from __future__ import annotations

import json
import os
import random
import uuid
import warnings
from datetime import date
from pathlib import Path
from typing import Any

import requests

HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Phan", "Vũ", "Đặng", "Bùi", "Đỗ"]
TEN_DEM = ["Văn", "Thị", "Minh", "Thu", "Hồng", "Thanh", "Quang", "Anh", "Tuấn", ""]
TEN = [
    "An", "Bình", "Chi", "Dũng", "Hà", "Hương", "Khoa", "Lan", "Long", "Mai",
    "Nam", "Nga", "Phương", "Sơn", "Thảo", "Trung", "Tú", "Vy", "Yến", "Đức",
]

DATE_FMT = "dd MMMM yyyy"
LOCALE = "en"
# Savings account type for accounttransfers
ACCT_TYPE_SAVINGS = 2


def load_env(path: str | None = None) -> None:
    env_path = Path(path or os.environ.get("FINERACT_ECO_ENV", "/home/sysadmin/npd-fineract-ecosystem/.env"))
    if not env_path.is_file():
        alt = Path(__file__).resolve().parent / ".env"
        if alt.is_file():
            env_path = alt
        else:
            return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def cfg_int(key: str, default: int) -> int:
    try:
        return int(cfg(key, str(default)))
    except ValueError:
        return default


def cfg_float(key: str, default: float) -> float:
    try:
        return float(cfg(key, str(default)))
    except ValueError:
        return default


def verify_tls() -> bool:
    return cfg("VERIFY_TLS", "0") not in ("0", "false", "False", "no")


def setup_warnings() -> None:
    if not verify_tls():
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def base_url() -> str:
    return cfg("FINERACT_URL", "https://npd-fineract.co/fineract-provider/api/v1").rstrip("/")


def data_dir() -> Path:
    p = Path(cfg("DATA_DIR", str(Path(__file__).resolve().parent / "data")))
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_path() -> Path:
    return data_dir() / "state.json"


def clients_path() -> Path:
    return data_dir() / "clients.json"


def today_str() -> str:
    # e.g. 27 November 2026
    return date.today().strftime("%d %B %Y")


def random_vn_name(index: int) -> tuple[str, str]:
    dem = random.choice(TEN_DEM)
    first = f"{dem} {random.choice(TEN)}".replace("  ", " ").strip() if dem else random.choice(TEN)
    last = random.choice(HO)
    return first, f"{last}{index}"


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def new_idempotency_key() -> str:
    return str(uuid.uuid4())


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_clients() -> list[dict]:
    return load_json(clients_path(), [])


def save_clients(clients: list[dict]) -> None:
    save_json(clients_path(), clients)


def load_state() -> dict:
    return load_json(state_path(), {})


def save_state(state: dict) -> None:
    save_json(state_path(), state)


class FineractClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.auth = (
            cfg("FINERACT_USER", "mifos"),
            cfg("FINERACT_PASSWORD", "password"),
        )
        self.session.headers.update(
            {
                "Fineract-Platform-TenantId": cfg("FINERACT_TENANT", "default"),
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self.session.verify = verify_tls()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        business_flow: str = "",
        business_step: str = "",
        correlation_id: str | None = None,
        idempotent: bool = False,
        timeout: int = 60,
    ) -> dict:
        corr = correlation_id or new_correlation_id()
        headers = {
            "X-Correlation-ID": corr,
            "X-Business-Flow": business_flow,
        }
        if business_step:
            headers["X-Business-Step"] = business_step
        if idempotent or method.upper() in ("POST", "PUT"):
            headers["Idempotency-Key"] = new_idempotency_key()

        url = f"{base_url()}/{path.lstrip('/')}"
        try:
            r = self.session.request(
                method,
                url,
                json=json_body,
                params=params,
                headers=headers,
                timeout=timeout,
            )
        except Exception as e:
            return {"ok": False, "correlation_id": corr, "detail": str(e), "status": 0}

        try:
            body = r.json() if r.content else {}
        except Exception:
            body = {"raw": r.text[:500]}

        if 200 <= r.status_code < 300:
            return {"ok": True, "correlation_id": corr, "status": r.status_code, "data": body}

        detail = body.get("defaultUserMessage") or body.get("message") or r.text[:300]
        if isinstance(body, dict) and body.get("errors"):
            detail = f"{detail} | {body['errors']}"
        return {
            "ok": False,
            "correlation_id": corr,
            "status": r.status_code,
            "detail": detail,
            "data": body,
        }

    def get(self, path: str, **kw: Any) -> dict:
        return self.request("GET", path, **kw)

    def post(self, path: str, json_body: dict | None = None, **kw: Any) -> dict:
        return self.request("POST", path, json_body=json_body, idempotent=True, **kw)


def ensure_currency(api: FineractClient) -> str:
    preferred = cfg("FINERACT_CURRENCY", "").strip()
    r = api.get("currencies", business_flow="setup.currency")
    if not r.get("ok"):
        raise RuntimeError(f"currencies: {r.get('detail')}")
    selected = (r["data"] or {}).get("selectedCurrencyOptions") or []
    codes = [c.get("code") for c in selected if c.get("code")]
    if preferred and preferred in codes:
        return preferred
    if codes:
        return codes[0]
    # try enable preferred
    if preferred:
        put = api.request(
            "PUT",
            "currencies",
            json_body={"currencies": [preferred]},
            business_flow="setup.currency",
            business_step="enable",
        )
        if put.get("ok"):
            return preferred
    raise RuntimeError("No currency enabled — set FINERACT_CURRENCY and enable in Fineract")


def ensure_payment_type(api: FineractClient) -> int:
    r = api.get("paymenttypes", business_flow="setup.paymenttype")
    if r.get("ok") and isinstance(r.get("data"), list) and r["data"]:
        return int(r["data"][0]["id"])
    created = api.post(
        "paymenttypes",
        {
            "name": "NPD-ECO-CASH",
            "description": "Ecosystem cash",
            "isCashPayment": True,
            "position": 1,
        },
        business_flow="setup.paymenttype",
        business_step="create",
    )
    if not created.get("ok"):
        raise RuntimeError(f"paymenttypes: {created.get('detail')}")
    return int(created["data"]["resourceId"])


def find_product_by_name(api: FineractClient, kind: str, name: str) -> int | None:
    # kind: savingsproducts | loanproducts
    r = api.get(kind, business_flow="setup.product")
    if not r.get("ok"):
        return None
    items = r["data"] if isinstance(r["data"], list) else []
    for p in items:
        if p.get("name") == name:
            return int(p["id"])
    return None


def ensure_savings_product(api: FineractClient, currency: str) -> int:
    name = cfg("SAVINGS_PRODUCT_NAME", "NPD-ECO-SAVINGS")
    existing = find_product_by_name(api, "savingsproducts", name)
    if existing:
        return existing
    body = {
        "name": name,
        "shortName": "NES",
        "description": "NPD ecosystem savings",
        "currencyCode": currency,
        "digitsAfterDecimal": 0,
        "inMultiplesOf": 1,
        "locale": LOCALE,
        "nominalAnnualInterestRate": 0,
        "interestCompoundingPeriodType": 1,  # daily
        "interestPostingPeriodType": 4,  # monthly
        "interestCalculationType": 1,  # daily balance
        "interestCalculationDaysInYearType": 365,
        "accountingRule": 1,  # NONE
        "withdrawalFeeForTransfers": False,
        "allowOverdraft": False,
        "enforceMinRequiredBalance": False,
        "minRequiredOpeningBalance": 0,
    }
    r = api.post("savingsproducts", body, business_flow="setup.product", business_step="savings")
    if not r.get("ok"):
        raise RuntimeError(f"savingsproducts: {r.get('detail')}")
    return int(r["data"]["resourceId"])


def ensure_loan_product(api: FineractClient, currency: str) -> int:
    name = cfg("LOAN_PRODUCT_NAME", "NPD-ECO-LOAN")
    existing = find_product_by_name(api, "loanproducts", name)
    if existing:
        return existing
    body = {
        "name": name,
        "shortName": "NEL",
        "description": "NPD ecosystem loan",
        "currencyCode": currency,
        "digitsAfterDecimal": 0,
        "inMultiplesOf": 1,
        "principal": cfg_int("LOAN_PRINCIPAL", 1_000_000),
        "minPrincipal": 100_000,
        "maxPrincipal": 50_000_000,
        "numberOfRepayments": 12,
        "repaymentEvery": 1,
        "repaymentFrequencyType": 2,  # months
        "interestRatePerPeriod": 0,
        "interestRateFrequencyType": 2,
        "amortizationType": 1,  # equal installments
        "interestType": 0,  # declining
        "interestCalculationPeriodType": 1,  # same as repayment
        "transactionProcessingStrategyCode": "mifos-standard-strategy",
        "accountingRule": 1,  # NONE
        "locale": LOCALE,
        "dateFormat": DATE_FMT,
        "isInterestRecalculationEnabled": False,
        "daysInYearType": 365,
        "daysInMonthType": 30,
    }
    r = api.post("loanproducts", body, business_flow="setup.product", business_step="loan")
    if not r.get("ok"):
        raise RuntimeError(f"loanproducts: {r.get('detail')}")
    return int(r["data"]["resourceId"])


def create_client_active(api: FineractClient, index: int, correlation_id: str | None = None) -> dict:
    first, last = random_vn_name(index)
    office_id = cfg_int("OFFICE_ID", 1)
    day = today_str()
    corr = correlation_id or new_correlation_id()
    body = {
        "officeId": office_id,
        "firstname": first,
        "lastname": last,
        "externalId": f"ECO-{index}-{uuid.uuid4().hex[:8]}",
        "active": True,
        "activationDate": day,
        "submittedOnDate": day,
        "dateFormat": DATE_FMT,
        "locale": LOCALE,
        "mobileNo": f"09{20000000 + (index % 70000000):08d}"[:12],
    }
    r = api.post(
        "clients",
        body,
        business_flow="bpm.client.onboard",
        business_step="create",
        correlation_id=corr,
    )
    if not r.get("ok"):
        return r
    client_id = int(r["data"].get("clientId") or r["data"]["resourceId"])
    return {"ok": True, "correlation_id": corr, "client_id": client_id, "firstname": first, "lastname": last}


def open_savings(
    api: FineractClient,
    client_id: int,
    product_id: int,
    *,
    correlation_id: str | None = None,
    deposit: float = 0,
    payment_type_id: int = 1,
) -> dict:
    day = today_str()
    corr = correlation_id or new_correlation_id()
    submit = api.post(
        "savingsaccounts",
        {
            "clientId": client_id,
            "productId": product_id,
            "locale": LOCALE,
            "dateFormat": DATE_FMT,
            "submittedOnDate": day,
        },
        business_flow="bpm.client.onboard",
        business_step="savings.submit",
        correlation_id=corr,
    )
    if not submit.get("ok"):
        return submit
    savings_id = int(submit["data"]["savingsId"] if "savingsId" in submit["data"] else submit["data"]["resourceId"])

    approve = api.post(
        f"savingsaccounts/{savings_id}",
        {"approvedOnDate": day, "dateFormat": DATE_FMT, "locale": LOCALE},
        params={"command": "approve"},
        business_flow="bpm.client.onboard",
        business_step="savings.approve",
        correlation_id=corr,
    )
    if not approve.get("ok"):
        return {**approve, "savings_id": savings_id}

    activate = api.post(
        f"savingsaccounts/{savings_id}",
        {"activatedOnDate": day, "dateFormat": DATE_FMT, "locale": LOCALE},
        params={"command": "activate"},
        business_flow="bpm.client.onboard",
        business_step="savings.activate",
        correlation_id=corr,
    )
    if not activate.get("ok"):
        return {**activate, "savings_id": savings_id}

    if deposit and deposit > 0:
        dep = api.post(
            f"savingsaccounts/{savings_id}/transactions",
            {
                "transactionDate": day,
                "transactionAmount": deposit,
                "paymentTypeId": payment_type_id,
                "dateFormat": DATE_FMT,
                "locale": LOCALE,
            },
            params={"command": "deposit"},
            business_flow="bpm.client.onboard",
            business_step="savings.deposit",
            correlation_id=corr,
        )
        if not dep.get("ok"):
            return {**dep, "savings_id": savings_id}

    return {"ok": True, "correlation_id": corr, "savings_id": savings_id}


def savings_deposit(
    api: FineractClient,
    savings_id: int,
    amount: float,
    payment_type_id: int,
    *,
    correlation_id: str | None = None,
    business_flow: str = "txn.deposit",
) -> dict:
    return api.post(
        f"savingsaccounts/{savings_id}/transactions",
        {
            "transactionDate": today_str(),
            "transactionAmount": amount,
            "paymentTypeId": payment_type_id,
            "dateFormat": DATE_FMT,
            "locale": LOCALE,
        },
        params={"command": "deposit"},
        business_flow=business_flow,
        business_step="deposit",
        correlation_id=correlation_id,
    )


def savings_withdraw(
    api: FineractClient,
    savings_id: int,
    amount: float,
    payment_type_id: int,
    *,
    correlation_id: str | None = None,
) -> dict:
    return api.post(
        f"savingsaccounts/{savings_id}/transactions",
        {
            "transactionDate": today_str(),
            "transactionAmount": amount,
            "paymentTypeId": payment_type_id,
            "dateFormat": DATE_FMT,
            "locale": LOCALE,
        },
        params={"command": "withdrawal"},
        business_flow="txn.withdraw",
        business_step="withdraw",
        correlation_id=correlation_id,
    )


def account_transfer(
    api: FineractClient,
    from_client: dict,
    to_client: dict,
    amount: float,
    *,
    correlation_id: str | None = None,
) -> dict:
    office_id = cfg_int("OFFICE_ID", 1)
    body = {
        "fromOfficeId": office_id,
        "fromClientId": from_client["client_id"],
        "fromAccountType": ACCT_TYPE_SAVINGS,
        "fromAccountId": from_client["savings_id"],
        "toOfficeId": office_id,
        "toClientId": to_client["client_id"],
        "toAccountType": ACCT_TYPE_SAVINGS,
        "toAccountId": to_client["savings_id"],
        "transferDate": today_str(),
        "transferAmount": amount,
        "transferDescription": f"ECO-V1-{uuid.uuid4().hex[:8]}",
        "dateFormat": DATE_FMT,
        "locale": LOCALE,
    }
    return api.post(
        "accounttransfers",
        body,
        business_flow="txn.transfer",
        business_step="transfer",
        correlation_id=correlation_id,
    )


def loan_originate(
    api: FineractClient,
    client_id: int,
    product_id: int,
    principal: float,
    *,
    correlation_id: str | None = None,
) -> dict:
    day = today_str()
    corr = correlation_id or new_correlation_id()
    apply = api.post(
        "loans",
        {
            "clientId": client_id,
            "productId": product_id,
            "loanType": "individual",
            "submittedOnDate": day,
            "expectedDisbursementDate": day,
            "principal": principal,
            "loanTermFrequency": 12,
            "loanTermFrequencyType": 2,
            "numberOfRepayments": 12,
            "repaymentEvery": 1,
            "repaymentFrequencyType": 2,
            "interestRatePerPeriod": 0,
            "amortizationType": 1,
            "interestType": 0,
            "interestCalculationPeriodType": 1,
            "transactionProcessingStrategyCode": "mifos-standard-strategy",
            "locale": LOCALE,
            "dateFormat": DATE_FMT,
        },
        business_flow="bpm.loan.origination",
        business_step="apply",
        correlation_id=corr,
    )
    if not apply.get("ok"):
        return apply
    loan_id = int(apply["data"]["loanId"] if "loanId" in apply["data"] else apply["data"]["resourceId"])

    approve = api.post(
        f"loans/{loan_id}",
        {
            "approvedOnDate": day,
            "approvedLoanAmount": principal,
            "expectedDisbursementDate": day,
            "locale": LOCALE,
            "dateFormat": DATE_FMT,
        },
        params={"command": "approve"},
        business_flow="bpm.loan.origination",
        business_step="approve",
        correlation_id=corr,
    )
    if not approve.get("ok"):
        return {**approve, "loan_id": loan_id}

    disburse = api.post(
        f"loans/{loan_id}",
        {
            "actualDisbursementDate": day,
            "transactionAmount": principal,
            "locale": LOCALE,
            "dateFormat": DATE_FMT,
        },
        params={"command": "disburse"},
        business_flow="bpm.loan.origination",
        business_step="disburse",
        correlation_id=corr,
    )
    if not disburse.get("ok"):
        return {**disburse, "loan_id": loan_id}

    return {"ok": True, "correlation_id": corr, "loan_id": loan_id}


def loan_repay(
    api: FineractClient,
    loan_id: int,
    amount: float,
    payment_type_id: int,
    *,
    correlation_id: str | None = None,
) -> dict:
    return api.post(
        f"loans/{loan_id}/transactions",
        {
            "transactionDate": today_str(),
            "transactionAmount": amount,
            "paymentTypeId": payment_type_id,
            "locale": LOCALE,
            "dateFormat": DATE_FMT,
        },
        params={"command": "repayment"},
        business_flow="bpm.loan.repay",
        business_step="repay",
        correlation_id=correlation_id,
    )


def clients_with_savings(clients: list[dict] | None = None) -> list[dict]:
    rows = clients if clients is not None else load_clients()
    return [c for c in rows if c.get("client_id") and c.get("savings_id")]


def clients_with_loans(clients: list[dict] | None = None) -> list[dict]:
    rows = clients if clients is not None else load_clients()
    return [c for c in rows if c.get("loan_id")]
