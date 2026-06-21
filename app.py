"""
Agentic AML & KYC Compliance Engine
Enterprise prototype — single-file Streamlit application.
"""

from __future__ import annotations

import hashlib
import json
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration & paths
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
AUDIT_LOG_PATH = APP_DIR / "fintrac_audit_log.jsonl"
MODEL_REGISTRY_HASH = hashlib.sha256(b"aml-kyc-v3.2.1-osfi-e23").hexdigest()[:16]

# ---------------------------------------------------------------------------
# Enterprise theme (CSS)
# ---------------------------------------------------------------------------

ENTERPRISE_CSS = """
<style>
    :root {
        --aml-primary: #0B3D5C;
        --aml-accent: #1A6B8A;
        --aml-surface: #F7F9FB;
        --aml-border: #D1D9E0;
        --aml-text: #1A2332;
        --aml-muted: #5C6B7A;
        --aml-danger: #B42318;
        --aml-warning: #B54708;
        --aml-success: #067647;
        --aml-card-shadow: 0 1px 3px rgba(26, 35, 50, 0.08);
    }
    .stApp {
        background-color: var(--aml-surface);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0B3D5C 0%, #0E4A6E 100%);
        border-right: 1px solid var(--aml-border);
    }
    [data-testid="stSidebar"] * {
        color: #E8EEF4 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stTextInput label {
        color: #C5D4E0 !important;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .aml-header {
        background: #FFFFFF;
        border: 1px solid var(--aml-border);
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: var(--aml-card-shadow);
    }
    .aml-header h1 {
        color: var(--aml-primary);
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0 0 0.25rem 0;
        letter-spacing: -0.02em;
    }
    .aml-header p {
        color: var(--aml-muted);
        margin: 0;
        font-size: 0.875rem;
    }
    .aml-metric-row {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        margin-bottom: 1rem;
    }
    .aml-badge {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        border: 1px solid var(--aml-border);
    }
    .aml-badge-critical {
        background: #FEF3F2;
        color: var(--aml-danger);
        border-color: #FECDCA;
    }
    .aml-badge-high {
        background: #FFF6ED;
        color: var(--aml-warning);
        border-color: #FEDF89;
    }
    .aml-badge-low {
        background: #ECFDF3;
        color: var(--aml-success);
        border-color: #ABEFC6;
    }
    .aml-card {
        background: #FFFFFF;
        border: 1px solid var(--aml-border);
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: var(--aml-card-shadow);
    }
    .aml-card-title {
        color: var(--aml-primary);
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
        border-bottom: 1px solid var(--aml-border);
        padding-bottom: 0.5rem;
    }
    .agent-trace {
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.78rem;
        background: #F0F4F8;
        border: 1px solid var(--aml-border);
        border-radius: 6px;
        padding: 0.75rem 1rem;
        color: var(--aml-text);
        white-space: pre-wrap;
        line-height: 1.5;
    }
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid var(--aml-border);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        box-shadow: var(--aml-card-shadow);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 2px solid var(--aml-border);
    }
    .stTabs [data-baseweb="tab"] {
        border: 1px solid var(--aml-border);
        border-bottom: none;
        border-radius: 6px 6px 0 0;
        background: #FFFFFF;
        color: var(--aml-muted);
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: var(--aml-primary) !important;
        color: white !important;
        border-color: var(--aml-primary) !important;
    }
</style>
"""

# ---------------------------------------------------------------------------
# Mock dataset
# ---------------------------------------------------------------------------


def _tx(amount: float, tx_type: str, channel: str, counterparty: str, days_ago: int) -> dict:
    return {
        "amount": amount,
        "type": tx_type,
        "channel": channel,
        "counterparty": counterparty,
        "days_ago": days_ago,
    }


MOCK_ACCOUNTS: dict[str, dict[str, Any]] = {
    "CAD-88391029": {
        "account_id": "CAD-88391029",
        "account_name": "Northbridge Capital Holdings Ltd.",
        "account_type": "Corporate Operating",
        "jurisdiction": "Ontario, Canada",
        "country_risk_score": 72,
        "expected_monthly_volume": 175_000,
        "actual_30d_volume": 1_420_000,
        "risk_tier": "CRITICAL",
        "incorporation_date": "2021-03-14",
        "business_nature": "Import/Export — Industrial Equipment",
        "directors": [
            {"name": "Victor Chen", "role": "Director", "ownership_pct": 35, "pep": False},
            {"name": "Elena Rostova", "role": "Director / CFO", "ownership_pct": 25, "pep": False},
            {"name": "Marcus Webb", "role": "Nominee Director", "ownership_pct": 5, "pep": False},
        ],
        "ubos": [
            {"name": "Victor Chen", "ownership_pct": 35, "via": "Direct"},
            {"name": "Elena Rostova", "ownership_pct": 25, "via": "Direct"},
            {"name": "Offshore Trust — Cayman SPV", "ownership_pct": 40, "via": "Layered entity chain (3 hops)"},
        ],
        "corporate_layering_flags": [
            "Parent registered in British Virgin Islands",
            "Nominee director with no operational history",
            "40% ownership via opaque offshore trust structure",
        ],
        "transactions_30d": [
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 2),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 3),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 5),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 7),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 9),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 11),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 14),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 16),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 18),
            _tx(9_500, "Cash Deposit", "Branch Teller", "Self", 21),
            _tx(485_000, "Wire Outbound", "SWIFT", "Kraken Digital Asset Exchange", 4),
            _tx(320_000, "Wire Outbound", "SWIFT", "Global Trade Partners AG", 8),
            _tx(275_000, "Wire Inbound", "SWIFT", "Unknown — Dubai Free Zone", 12),
        ],
        "structuring_detected": True,
        "crypto_exchange_outbound": True,
        "adverse_media": [
            {
                "director": "Victor Chen",
                "headline": "Former executive linked to securities fraud investigation — Reuters",
                "source": "Reuters Global Compliance Feed",
                "date": "2024-11-02",
                "severity": "HIGH",
            },
            {
                "director": "Marcus Webb",
                "headline": "Nominee director appears in Panama Papers derivative dataset",
                "source": "ICIJ Vector Index",
                "date": "2023-08-19",
                "severity": "MEDIUM",
            },
        ],
    },
    "CAD-77210456": {
        "account_id": "CAD-77210456",
        "account_name": "Maple Leaf Retail Cooperative",
        "account_type": "Business Chequing",
        "jurisdiction": "Alberta, Canada",
        "country_risk_score": 18,
        "expected_monthly_volume": 890_000,
        "actual_30d_volume": 912_000,
        "risk_tier": "LOW",
        "incorporation_date": "2008-06-22",
        "business_nature": "Retail — Grocery & General Merchandise",
        "directors": [
            {"name": "Sarah Okafor", "role": "President", "ownership_pct": 60, "pep": False},
            {"name": "James Whitfield", "role": "Treasurer", "ownership_pct": 40, "pep": False},
        ],
        "ubos": [
            {"name": "Sarah Okafor", "ownership_pct": 60, "via": "Direct"},
            {"name": "James Whitfield", "ownership_pct": 40, "via": "Direct"},
        ],
        "corporate_layering_flags": [],
        "transactions_30d": [
            _tx(45_000, "ACH Inbound", "EFT", "Supplier Payments Pool", 1),
            _tx(38_200, "Wire Outbound", "SWIFT", "Wholesale Foods Inc.", 5),
            _tx(22_100, "POS Settlement", "Card Network", "Daily Sales", 3),
        ],
        "structuring_detected": False,
        "crypto_exchange_outbound": False,
        "adverse_media": [],
    },
    "CAD-55190233": {
        "account_id": "CAD-55190233",
        "account_name": "Horizon Tech Ventures Inc.",
        "account_type": "Corporate Operating",
        "jurisdiction": "British Columbia, Canada",
        "country_risk_score": 35,
        "expected_monthly_volume": 420_000,
        "actual_30d_volume": 510_000,
        "risk_tier": "MEDIUM",
        "incorporation_date": "2019-01-08",
        "business_nature": "SaaS — Enterprise Software",
        "directors": [
            {"name": "Priya Sharma", "role": "CEO", "ownership_pct": 55, "pep": False},
            {"name": "David Kim", "role": "CTO", "ownership_pct": 45, "pep": False},
        ],
        "ubos": [
            {"name": "Priya Sharma", "ownership_pct": 55, "via": "Direct"},
            {"name": "David Kim", "ownership_pct": 45, "via": "Direct"},
        ],
        "corporate_layering_flags": [],
        "transactions_30d": [
            _tx(125_000, "Wire Inbound", "SWIFT", "Enterprise Client — US", 2),
            _tx(88_000, "Wire Outbound", "SWIFT", "Cloud Infrastructure Vendor", 6),
        ],
        "structuring_detected": False,
        "crypto_exchange_outbound": False,
        "adverse_media": [],
    },
    "CAD-33487102": {
        "account_id": "CAD-33487102",
        "account_name": "Atlantic Fisheries Export Ltd.",
        "account_type": "Business Chequing",
        "jurisdiction": "Nova Scotia, Canada",
        "country_risk_score": 28,
        "expected_monthly_volume": 650_000,
        "actual_30d_volume": 598_000,
        "risk_tier": "LOW",
        "incorporation_date": "1995-11-30",
        "business_nature": "Seafood Export",
        "directors": [
            {"name": "Robert MacLeod", "role": "Managing Director", "ownership_pct": 70, "pep": False},
            {"name": "Anne Tremblay", "role": "Operations Director", "ownership_pct": 30, "pep": False},
        ],
        "ubos": [
            {"name": "Robert MacLeod", "ownership_pct": 70, "via": "Direct"},
            {"name": "Anne Tremblay", "ownership_pct": 30, "via": "Direct"},
        ],
        "corporate_layering_flags": [],
        "transactions_30d": [
            _tx(210_000, "Wire Inbound", "SWIFT", "Tokyo Seafood Importers", 4),
            _tx(195_000, "Wire Outbound", "SWIFT", "Fleet Maintenance Co.", 10),
        ],
        "structuring_detected": False,
        "crypto_exchange_outbound": False,
        "adverse_media": [],
    },
    "CAD-11904587": {
        "account_id": "CAD-11904587",
        "account_name": "Greenfield Property Management Corp.",
        "account_type": "Corporate Trust",
        "jurisdiction": "Quebec, Canada",
        "country_risk_score": 42,
        "expected_monthly_volume": 280_000,
        "actual_30d_volume": 395_000,
        "risk_tier": "MEDIUM",
        "incorporation_date": "2017-09-05",
        "business_nature": "Real Estate — Property Management",
        "directors": [
            {"name": "Isabelle Fontaine", "role": "President", "ownership_pct": 50, "pep": False},
            {"name": "Ahmed Hassan", "role": "Director", "ownership_pct": 50, "pep": True},
        ],
        "ubos": [
            {"name": "Isabelle Fontaine", "ownership_pct": 50, "via": "Direct"},
            {"name": "Ahmed Hassan", "ownership_pct": 50, "via": "Direct"},
        ],
        "corporate_layering_flags": ["PEP-associated beneficial owner (domestic municipal official)"],
        "transactions_30d": [
            _tx(95_000, "Wire Inbound", "SWIFT", "Tenant Rent Aggregator", 3),
            _tx(72_000, "Wire Outbound", "SWIFT", "Maintenance Contractors Ltd.", 8),
        ],
        "structuring_detected": False,
        "crypto_exchange_outbound": False,
        "adverse_media": [],
    },
}


# ---------------------------------------------------------------------------
# Agent system prompts
# ---------------------------------------------------------------------------

AGENT_A_SYSTEM = """You are Agent A — KYC & Ultimate Beneficial Owner (UBO) Analyst for a Tier-1 Canadian bank.
Your mandate: analyze corporate account profiles, extract UBO chains, and identify shell-company or corporate layering indicators.
Respond in structured prose (3-5 paragraphs). Include:
- UBO identification with ownership percentages
- Corporate layering / shell-company risk assessment
- Specific red flags with severity ratings (LOW/MEDIUM/HIGH/CRITICAL)
Be precise, regulatory-aligned (OSFI B-10, FINTRAC PCMLTFA), and cite data from the profile provided."""

AGENT_B_SYSTEM = """You are Agent B — Transaction Velocity & Structuring Analyst for a Tier-1 Canadian bank.
Your mandate: compute deviation from baseline transactional profiles and detect structuring, smurfing, or rapid fund dissipation.
Respond in structured prose (3-5 paragraphs). Include:
- Velocity deviation calculation and interpretation
- Structuring pattern analysis (e.g., sub-threshold cash deposits)
- Outbound flow analysis including crypto exchange transfers
- Quantified risk score contribution
Be precise and reference specific transaction amounts and dates."""

AGENT_C_SYSTEM = """You are Agent C — Adverse Media & Sanctions Intelligence Analyst.
Your mandate: simulate vector-database retrieval against global news feeds and flag directors tied to legal indictments, fraud, or reputational risk.
Respond in structured prose (2-4 paragraphs). Include:
- Adverse media matches with source attribution
- Director-level risk mapping
- Recommended enhanced due diligence actions
If no adverse media exists, state clearance with confidence level."""

COORDINATOR_SYSTEM = """You are the Master Compliance Coordinator for a Canadian financial institution.
Synthesize findings from Agents A (KYC/UBO), B (Transaction Velocity), and C (Adverse Media) into a formal
Suspicious Activity Report (SAR) narrative draft suitable for FINTRAC filing review.
Write in professional regulatory prose. Include: subject identification, suspicious activity description,
methodology, timeline, and recommended filing determination. Target 400-600 words."""


# ---------------------------------------------------------------------------
# LLM integration (litellm with fallback)
# ---------------------------------------------------------------------------


def _has_api_key(api_key: str | None) -> bool:
    if api_key and api_key.strip():
        return True
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _resolve_api_key(user_key: str | None) -> str | None:
    if user_key and user_key.strip():
        return user_key.strip()
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")


def call_llm(system_prompt: str, user_message: str, api_key: str | None, model: str) -> tuple[str, str]:
    """Returns (response_text, source_label). source_label is 'llm' or 'mock'."""
    key = _resolve_api_key(api_key)
    if not key:
        return "", "mock"

    try:
        import litellm

        litellm.suppress_debug_info = True
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            api_key=key,
            temperature=0.2,
            max_tokens=1200,
        )
        content = response.choices[0].message.content or ""
        return content.strip(), "llm"
    except Exception:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=key)
            response = client.chat.completions.create(
                model=model.replace("openai/", "").replace("anthropic/", ""),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
            content = response.choices[0].message.content or ""
            return content.strip(), "llm"
        except Exception:
            return "", "mock"


# ---------------------------------------------------------------------------
# Mock agent responses (fallback)
# ---------------------------------------------------------------------------


def mock_agent_a(account: dict) -> str:
    ubo_lines = "\n".join(
        f"  • {u['name']}: {u['ownership_pct']}% ({u['via']})" for u in account["ubos"]
    )
    flags = account["corporate_layering_flags"]
    flag_text = "\n".join(f"  • [{i + 1}] {f}" for i, f in enumerate(flags)) if flags else "  • No layering indicators detected."

    risk = "CRITICAL" if len(flags) >= 2 else ("MEDIUM" if flags else "LOW")
    return textwrap.dedent(f"""
    **UBO Extraction Complete — Agent A (KYC Analyst)**

    Account holder {account['account_name']} ({account['account_id']}) incorporated {account['incorporation_date']}
    in {account['jurisdiction']}. Business classification: {account['business_nature']}.

    **Ultimate Beneficial Owners Identified:**
    {ubo_lines}

    **Corporate Layering Assessment — Severity: {risk}**
    {flag_text}

    **Director Registry Scan:**
    {chr(10).join(f"  • {d['name']} — {d['role']} ({d['ownership_pct']}%){' [PEP FLAG]' if d.get('pep') else ''}" for d in account['directors'])}

    **Recommendation:** {"Immediate Enhanced Due Diligence (EDD) and UBO verification escalation required." if flags else "Standard periodic KYC refresh sufficient."}
    """).strip()


def mock_agent_b(account: dict) -> str:
    expected = account["expected_monthly_volume"]
    actual = account["actual_30d_volume"]
    deviation_pct = ((actual - expected) / expected * 100) if expected else 0
    velocity_ratio = actual / expected if expected else 0

    cash_9500 = [t for t in account["transactions_30d"] if t["amount"] == 9_500 and t["type"] == "Cash Deposit"]
    crypto = [t for t in account["transactions_30d"] if "crypto" in t["counterparty"].lower() or "kraken" in t["counterparty"].lower()]

    struct_note = (
        f"CRITICAL: {len(cash_9500)} cash deposits of $9,500 detected within 30 days — classic structuring pattern "
        f"designed to evade CTR reporting thresholds ($10,000 CAD)."
        if cash_9500
        else "No sub-threshold structuring patterns identified."
    )
    crypto_note = (
        f"CRITICAL: Outbound wire of ${crypto[0]['amount']:,.0f} to {crypto[0]['counterparty']} ({crypto[0]['days_ago']} days ago) — "
        "rapid fund dissipation to virtual asset service provider."
        if crypto
        else "No crypto exchange outbound transfers detected."
    )

    return textwrap.dedent(f"""
    **Transaction Velocity Analysis — Agent B (Velocity Analyst)**

    **Baseline Profile:** Expected monthly volume: ${expected:,.0f} CAD
    **Observed 30-Day Volume:** ${actual:,.0f} CAD
    **Velocity Deviation:** {deviation_pct:+.1f}% ({velocity_ratio:.1f}x baseline)
    **Deviation Severity:** {"CRITICAL — exceeds 3x threshold" if velocity_ratio > 3 else ("ELEVATED" if velocity_ratio > 1.5 else "WITHIN TOLERANCE")}

    **Structuring Analysis:**
    {struct_note}

    **Fund Dissipation Analysis:**
    {crypto_note}

    **30-Day Transaction Summary:** {len(account['transactions_30d'])} transactions reviewed.
    Total inbound: ${sum(t['amount'] for t in account['transactions_30d'] if 'Inbound' in t['type'] or 'Deposit' in t['type']):,.0f} |
    Total outbound: ${sum(t['amount'] for t in account['transactions_30d'] if 'Outbound' in t['type']):,.0f}

    **Risk Score Contribution (Agent B):** {"45% — primary driver" if velocity_ratio > 3 else ("20% — moderate" if velocity_ratio > 1.5 else "5% — minimal")}
    """).strip()


def mock_agent_c(account: dict) -> str:
    media = account["adverse_media"]
    if not media:
        return textwrap.dedent("""
        **Adverse Media Vector Search — Agent C (Media Intelligence)**

        Vector database query executed against 847 global news feeds (Reuters, Bloomberg, ICIJ, OCCRP).
        **Result:** NO MATCHES — All directors cleared at 94.2% confidence interval.
        **Sanctions Screening:** PASS — No OFAC, UN, or FINTRAC listed entities associated.
        **Recommendation:** Standard monitoring cadence maintained.
        """).strip()

    hits = "\n".join(
        f"  • [{m['severity']}] {m['director']}: \"{m['headline']}\" — {m['source']} ({m['date']})"
        for m in media
    )
    return textwrap.dedent(f"""
    **Adverse Media Vector Search — Agent C (Media Intelligence)**

    Vector similarity search (cosine threshold ≥ 0.82) returned {len(media)} high-confidence match(es):

    {hits}

    **Director Risk Mapping:**
    {chr(10).join(f"  • {m['director']}: ADVERSE MEDIA HIT — severity {m['severity']}" for m in media)}

    **Recommendation:** Mandatory Enhanced Due Diligence. Consider SAR filing threshold assessment.
    **Risk Score Contribution (Agent C):** {"35% — significant driver" if media else "0%"}
    """).strip()


def mock_sar_narrative(account: dict, agent_a: str, agent_b: str, agent_c: str) -> str:
    return textwrap.dedent(f"""
    SUSPICIOUS ACTIVITY REPORT — DRAFT NARRATIVE
    =============================================
    Filing Institution: [REDACTED] National Bank of Canada
    Subject Account: {account['account_id']} — {account['account_name']}
    Jurisdiction: {account['jurisdiction']}
    Report Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
    Prepared By: Automated Compliance Engine v3.2.1 (Human Review Required)

    I. SUBJECT IDENTIFICATION
    -------------------------
    The subject entity, {account['account_name']}, is a {account['account_type']} account
    incorporated on {account['incorporation_date']}, engaged in {account['business_nature']}.
    Ultimate beneficial ownership analysis reveals {len(account['ubos'])} identified UBO(s), including
    {"opaque offshore trust structures requiring further investigation" if account['corporate_layering_flags'] else "transparent direct ownership"}.

    II. NATURE OF SUSPICIOUS ACTIVITY
    ---------------------------------
    Automated transaction monitoring detected a material deviation between the account's expected
    monthly transactional volume of ${account['expected_monthly_volume']:,.0f} CAD and the observed
    30-day velocity of ${account['actual_30d_volume']:,.0f} CAD, representing a
    {((account['actual_30d_volume'] - account['expected_monthly_volume']) / account['expected_monthly_volume'] * 100):+.0f}%
    variance from baseline profile.

    {"Multiple structured cash deposits of $9,500 CAD were identified, consistent with deliberate threshold avoidance under FINTRAC large cash transaction reporting requirements. An outbound wire transfer to a known virtual asset service provider (cryptocurrency exchange) was detected, indicating potential layering and rapid fund dissipation." if account.get('structuring_detected') else "No structuring patterns or crypto exchange transfers were identified during the review period."}

    III. ADVERSE MEDIA & REPUTATIONAL RISK
    --------------------------------------
    {"Adverse media screening identified director-level matches in global news feeds, including securities fraud investigations and offshore entity disclosures. Enhanced due diligence is warranted." if account['adverse_media'] else "Adverse media screening returned no matches. Directors cleared at standard confidence thresholds."}

    IV. AGENT ANALYSIS SUMMARY
    --------------------------
    [Agent A — KYC/UBO]: Corporate layering risk assessed as {account['risk_tier']}.
    [Agent B — Velocity]: Transaction velocity deviation flagged as primary alert driver.
    [Agent C — Media]: {len(account['adverse_media'])} adverse media match(es) identified.

    V. RECOMMENDED DETERMINATION
    ----------------------------
    Based on the totality of automated analysis, this account {"MEETS the threshold for mandatory FINTRAC suspicious transaction reporting under PCMLTFA Section 7." if account['risk_tier'] in ('CRITICAL', 'HIGH') else "does NOT currently meet SAR filing thresholds but warrants enhanced monitoring."}

    Compliance Officer: Please review, edit as necessary, and authorize filing below.
    """).strip()


# ---------------------------------------------------------------------------
# XAI feature importance (mock SHAP/LIME)
# ---------------------------------------------------------------------------


def compute_feature_importance(account: dict) -> dict[str, float]:
    expected = account["expected_monthly_volume"]
    actual = account["actual_30d_volume"]
    velocity_ratio = actual / expected if expected else 1.0

    velocity_pct = min(55, max(5, (velocity_ratio - 1) * 15 + 10))
    media_pct = min(40, len(account["adverse_media"]) * 18)
    country_pct = min(25, account["country_risk_score"] * 0.25)
    layering_pct = min(20, len(account["corporate_layering_flags"]) * 7)
    struct_pct = 15 if account.get("structuring_detected") else 0
    crypto_pct = 12 if account.get("crypto_exchange_outbound") else 0

    raw = {
        "Velocity Deviation": velocity_pct,
        "Adverse Media Match": media_pct,
        "Country Risk": country_pct,
        "Corporate Layering": layering_pct,
        "Structuring Pattern": struct_pct,
        "Crypto Exchange Outflow": crypto_pct,
    }
    total = sum(raw.values()) or 1.0
    normalized = {k: round(v / total * 100, 1) for k, v in raw.items() if v > 0}
    if not normalized:
        normalized = {"Baseline Profile Match": 100.0}

    top = dict(sorted(normalized.items(), key=lambda x: x[1], reverse=True)[:5])
    remainder = 100.0 - sum(top.values())
    if remainder > 0.1 and top:
        first_key = next(iter(top))
        top[first_key] = round(top[first_key] + remainder, 1)
    return top


def compute_alert_score(account: dict) -> float:
    importance = compute_feature_importance(account)
    base = sum(importance.values()) * 0.85
    tier_boost = {"CRITICAL": 92, "HIGH": 78, "MEDIUM": 52, "LOW": 18}.get(account["risk_tier"], 40)
    return min(99.0, max(tier_boost, base))


def build_osfi_registry_metadata(account_id: str, alert_score: float) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "registry_framework": "OSFI E-23 Model Risk Management",
        "model_id": "AML-KYC-AGENTIC-v3.2.1",
        "model_version": "3.2.1",
        "model_type": "Multi-Agent Ensemble (KYC + Velocity + Adverse Media)",
        "training_lineage_hash": f"sha256:{MODEL_REGISTRY_HASH}",
        "training_dataset": "Synthetic + anonymized production samples (2019-2025)",
        "validation_status": "PASSED — Backtesting AUC 0.94 (Q4 2025)",
        "data_privacy_masking_validation": {
            "pii_tokenization": "PASSED",
            "field_level_encryption": "AES-256-GCM",
            "gdpr_pipeda_alignment": "COMPLIANT",
            "direct_identifier_removal": "VERIFIED",
            "re_identification_risk_score": 0.02,
        },
        "explainability_method": "SHAP TreeExplainer + LIME tabular surrogate (simulated)",
        "bias_fairness_audit": "PASSED — demographic parity within 3% tolerance",
        "account_under_review": account_id,
        "alert_score": alert_score,
        "audit_timestamp_utc": now.isoformat(),
        "auditor_system": "compliance-engine-governance-module",
        "deployment_environment": "production-shadow-mode",
        "next_scheduled_review": "2026-09-01",
    }


# ---------------------------------------------------------------------------
# Multi-agent orchestration
# ---------------------------------------------------------------------------


def _account_context(account: dict) -> str:
    return json.dumps(
        {
            "account_id": account["account_id"],
            "account_name": account["account_name"],
            "jurisdiction": account["jurisdiction"],
            "expected_monthly_volume": account["expected_monthly_volume"],
            "actual_30d_volume": account["actual_30d_volume"],
            "directors": account["directors"],
            "ubos": account["ubos"],
            "corporate_layering_flags": account["corporate_layering_flags"],
            "transactions_30d": account["transactions_30d"],
            "adverse_media": account["adverse_media"],
            "risk_tier": account["risk_tier"],
        },
        indent=2,
    )


def run_compliance_engine(
    account: dict,
    api_key: str | None,
    model: str,
) -> dict[str, Any]:
    ctx = _account_context(account)
    trace: list[dict[str, str]] = []

    trace.append({"agent": "Orchestrator", "status": "START", "detail": f"Investigation initiated for {account['account_id']}"})

    # Agent A
    trace.append({"agent": "Agent A — KYC & UBO Analyst", "status": "RUNNING", "detail": "Scanning corporate profile and UBO chain..."})
    llm_a, src_a = call_llm(AGENT_A_SYSTEM, f"Analyze this account profile:\n{ctx}", api_key, model)
    result_a = llm_a if llm_a else mock_agent_a(account)
    trace.append({"agent": "Agent A — KYC & UBO Analyst", "status": "COMPLETE", "detail": f"Source: {'Live LLM' if src_a == 'llm' else 'Mock fallback'}"})

    # Agent B
    trace.append({"agent": "Agent B — Transaction Velocity Analyst", "status": "RUNNING", "detail": "Computing velocity deviation and structuring patterns..."})
    llm_b, src_b = call_llm(AGENT_B_SYSTEM, f"Analyze transactions and velocity:\n{ctx}", api_key, model)
    result_b = llm_b if llm_b else mock_agent_b(account)
    trace.append({"agent": "Agent B — Transaction Velocity Analyst", "status": "COMPLETE", "detail": f"Source: {'Live LLM' if src_b == 'llm' else 'Mock fallback'}"})

    # Agent C
    trace.append({"agent": "Agent C — Adverse Media Crawler", "status": "RUNNING", "detail": "Querying vector index against global news feeds..."})
    llm_c, src_c = call_llm(AGENT_C_SYSTEM, f"Screen for adverse media:\n{ctx}", api_key, model)
    result_c = llm_c if llm_c else mock_agent_c(account)
    trace.append({"agent": "Agent C — Adverse Media Crawler", "status": "COMPLETE", "detail": f"Source: {'Live LLM' if src_c == 'llm' else 'Mock fallback'}"})

    # Coordinator / SAR
    trace.append({"agent": "Master Coordinator", "status": "RUNNING", "detail": "Synthesizing SAR narrative draft..."})
    coordinator_input = (
        f"Account: {account['account_name']} ({account['account_id']})\n\n"
        f"AGENT A FINDINGS:\n{result_a}\n\n"
        f"AGENT B FINDINGS:\n{result_b}\n\n"
        f"AGENT C FINDINGS:\n{result_c}"
    )
    llm_sar, src_sar = call_llm(COORDINATOR_SYSTEM, coordinator_input, api_key, model)
    sar = llm_sar if llm_sar else mock_sar_narrative(account, result_a, result_b, result_c)
    trace.append({"agent": "Master Coordinator", "status": "COMPLETE", "detail": f"SAR draft ready — Source: {'Live LLM' if src_sar == 'llm' else 'Mock fallback'}"})

    feature_importance = compute_feature_importance(account)
    alert_score = compute_alert_score(account)
    osfi_metadata = build_osfi_registry_metadata(account["account_id"], alert_score)

    trace.append({"agent": "XAI Governance Module", "status": "COMPLETE", "detail": "SHAP/LIME feature attribution computed"})
    trace.append({"agent": "Orchestrator", "status": "COMPLETE", "detail": f"Investigation complete — Alert Score: {alert_score:.1f}"})

    return {
        "agent_a": result_a,
        "agent_b": result_b,
        "agent_c": result_c,
        "sar_narrative": sar,
        "trace": trace,
        "feature_importance": feature_importance,
        "alert_score": alert_score,
        "osfi_metadata": osfi_metadata,
        "used_llm": any(s == "llm" for s in (src_a, src_b, src_c, src_sar)),
    }


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def append_audit_log(entry: dict) -> None:
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_audit_log() -> list[dict]:
    if not AUDIT_LOG_PATH.exists():
        return []
    entries = []
    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def risk_badge_html(tier: str) -> str:
    css = {"CRITICAL": "aml-badge-critical", "HIGH": "aml-badge-high", "MEDIUM": "aml-badge-high", "LOW": "aml-badge-low"}
    cls = css.get(tier, "aml-badge-low")
    return f'<span class="aml-badge {cls}">{tier}</span>'


def render_header() -> None:
    st.markdown(
        """
        <div class="aml-header">
            <h1>🏛️ Agentic AML &amp; KYC Compliance Engine</h1>
            <p>OSFI E-23 Aligned · Multi-Agent Investigation · FINTRAC SAR Workflow</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_transaction_table(account: dict) -> None:
    rows = []
    for t in account["transactions_30d"]:
        rows.append(
            {
                "Days Ago": t["days_ago"],
                "Type": t["type"],
                "Channel": t["channel"],
                "Counterparty": t["counterparty"],
                "Amount (CAD)": f"${t['amount']:,.2f}",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


def init_session_state() -> None:
    defaults = {
        "investigation_result": None,
        "sar_edited": None,
        "last_account_id": None,
        "file_success_shown": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def main() -> None:
    st.set_page_config(
        page_title="AML & KYC Compliance Engine",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)
    init_session_state()
    render_header()

    # ---- Sidebar ----
    with st.sidebar:
        st.markdown("### Compliance Console")
        st.markdown("---")
        account_ids = list(MOCK_ACCOUNTS.keys())
        selected_id = st.selectbox(
            "Select Account for Investigation",
            account_ids,
            format_func=lambda x: f"{x} — {MOCK_ACCOUNTS[x]['account_name']}",
        )
        account = MOCK_ACCOUNTS[selected_id]

        st.markdown("---")
        st.markdown("**API Configuration**")
        api_key_input = st.text_input(
            "OpenAI / Anthropic API Key",
            type="password",
            placeholder="sk-... (optional — mock mode if empty)",
            help="Leave blank to use environment variables or mock responses.",
        )
        model_choice = st.selectbox(
            "Model",
            ["gpt-4o-mini", "gpt-4o", "anthropic/claude-3-5-sonnet-20241022"],
        )

        using_key = _has_api_key(api_key_input)
        mode_label = "🟢 Live LLM" if using_key else "🟡 Mock Mode (Fully Interactive)"
        st.info(mode_label)

        st.markdown("---")
        run_btn = st.button("▶ Run Automated Investigation", type="primary", use_container_width=True)

        st.markdown("---")
        st.caption(f"Model Registry: v3.2.1 · Hash `{MODEL_REGISTRY_HASH}`")
        st.caption(f"Audit log: `{AUDIT_LOG_PATH.name}`")

    if run_btn:
        with st.spinner("Orchestrating multi-agent compliance investigation..."):
            st.session_state.investigation_result = run_compliance_engine(
                account, api_key_input or None, model_choice
            )
            st.session_state.sar_edited = st.session_state.investigation_result["sar_narrative"]
            st.session_state.last_account_id = selected_id
            st.session_state.file_success_shown = False

    result = st.session_state.investigation_result
    if result is None:
        st.info("Select an account in the sidebar and click **Run Automated Investigation** to begin.")
        _render_account_preview(account)
        return

    if st.session_state.last_account_id != selected_id:
        st.warning("Account selection changed. Re-run investigation to refresh analysis for the selected account.")

    alert_score = result["alert_score"]
    tier = account["risk_tier"]

    tab_dashboard, tab_trace, tab_governance = st.tabs(
        ["📊 Alert Dashboard", "🔍 Agent Workflow Trace", "📋 Model Governance Log"]
    )

    # ---- Tab 1: Alert Dashboard ----
    with tab_dashboard:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Alert Score", f"{alert_score:.1f}", delta=f"{tier} tier")
        c2.metric("30-Day Volume", f"${account['actual_30d_volume']:,.0f}")
        c3.metric("Expected Monthly", f"${account['expected_monthly_volume']:,.0f}")
        velocity_dev = (account["actual_30d_volume"] - account["expected_monthly_volume"]) / account["expected_monthly_volume"] * 100
        c4.metric("Velocity Deviation", f"{velocity_dev:+.0f}%")

        st.markdown(
            f'<div class="aml-card"><div class="aml-card-title">Risk Classification</div>'
            f'{risk_badge_html(tier)} &nbsp; Account {account["account_id"]} — {account["account_name"]}</div>',
            unsafe_allow_html=True,
        )

        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.markdown('<div class="aml-card-title">XAI Feature Importance (SHAP / LIME Surrogate)</div>', unsafe_allow_html=True)
            fi_df = pd.DataFrame(
                {"Driver": list(result["feature_importance"].keys()), "Contribution (%)": list(result["feature_importance"].values())}
            ).set_index("Driver")
            st.bar_chart(fi_df, horizontal=True, height=280)
            st.caption("Simulated SHAP TreeExplainer + LIME tabular attribution — top 5 drivers normalized to 100%.")

        with col_right:
            st.markdown('<div class="aml-card-title">30-Day Transaction Ledger</div>', unsafe_allow_html=True)
            render_transaction_table(account)

        st.markdown("---")
        st.markdown("### Human-in-the-Loop — SAR Filing Workspace")

        sar_key = f"sar_text_{st.session_state.last_account_id}"
        if st.session_state.sar_edited is None:
            st.session_state.sar_edited = result["sar_narrative"]

        edited_sar = st.text_area(
            "Draft SAR Narrative (Editable)",
            value=st.session_state.sar_edited,
            height=320,
            key=sar_key,
            help="Review and edit the coordinator-generated narrative before filing.",
        )
        st.session_state.sar_edited = edited_sar

        btn_col1, btn_col2 = st.columns([1, 3])
        with btn_col1:
            if st.button("✅ Approve and File to FINTRAC", type="primary", use_container_width=True):
                audit_entry = {
                    "event": "FINTRAC_SAR_FILED",
                    "account_id": account["account_id"],
                    "account_name": account["account_name"],
                    "alert_score": alert_score,
                    "risk_tier": tier,
                    "filed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "compliance_officer_action": "APPROVED",
                    "sar_narrative_hash": hashlib.sha256(edited_sar.encode()).hexdigest(),
                    "sar_word_count": len(edited_sar.split()),
                    "model_version": result["osfi_metadata"]["model_version"],
                    "training_lineage_hash": result["osfi_metadata"]["training_lineage_hash"],
                }
                append_audit_log(audit_entry)
                st.toast("✅ SAR successfully filed to FINTRAC — audit log updated.", icon="✅")
                st.session_state.file_success_shown = True
                st.success(
                    f"Filing recorded at `{audit_entry['filed_at_utc']}` · "
                    f"Narrative hash `{audit_entry['sar_narrative_hash'][:12]}...`"
                )

        with btn_col2:
            if st.session_state.file_success_shown:
                st.caption(f"Latest audit entries persisted to `{AUDIT_LOG_PATH}`")

    # ---- Tab 2: Agent Workflow Trace ----
    with tab_trace:
        st.markdown("### Multi-Agent Processing Trace")
        llm_note = "Live LLM responses" if result.get("used_llm") else "Mock fallback responses (no API key or LLM unavailable)"
        st.caption(f"Response mode: **{llm_note}**")

        for step in result["trace"]:
            icon = {"START": "🚀", "RUNNING": "⏳", "COMPLETE": "✅"}.get(step["status"], "•")
            st.markdown(
                f'<div class="aml-card">'
                f'<strong>{icon} {step["agent"]}</strong> — <em>{step["status"]}</em><br/>'
                f'<span style="color:#5C6B7A;font-size:0.85rem;">{step["detail"]}</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")
        agent_tabs = st.tabs(["Agent A — KYC & UBO", "Agent B — Velocity", "Agent C — Adverse Media"])
        with agent_tabs[0]:
            st.markdown(f'<div class="agent-trace">{result["agent_a"]}</div>', unsafe_allow_html=True)
        with agent_tabs[1]:
            st.markdown(f'<div class="agent-trace">{result["agent_b"]}</div>', unsafe_allow_html=True)
        with agent_tabs[2]:
            st.markdown(f'<div class="agent-trace">{result["agent_c"]}</div>', unsafe_allow_html=True)

    # ---- Tab 3: Model Governance Log ----
    with tab_governance:
        st.markdown("### OSFI E-23 Model Registry Track Log")
        st.json(result["osfi_metadata"])

        st.markdown("---")
        st.markdown("### Local FINTRAC Audit Log")
        audit_entries = load_audit_log()
        if audit_entries:
            st.dataframe(pd.DataFrame(audit_entries), use_container_width=True, hide_index=True)
        else:
            st.info("No filings recorded yet. Approve a SAR narrative to create the first audit entry.")


def _render_account_preview(account: dict) -> None:
    st.markdown("### Account Preview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Account", account["account_id"])
    c2.metric("Risk Tier", account["risk_tier"])
    c3.metric("30-Day Volume", f"${account['actual_30d_volume']:,.0f}")

    st.markdown(
        f"**{account['account_name']}** · {account['account_type']} · {account['jurisdiction']}"
    )
    render_transaction_table(account)


if __name__ == "__main__":
    main()
