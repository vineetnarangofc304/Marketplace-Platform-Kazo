"""Seed data for multi-marketplace portals.

Parsed from `All Portal_Commercial -AI.xlsx` (26 Feb 2026 revision).
Each portal defines:
  - code, name, status ('live' | 'coming_soon')
  - fee_heads: T-1..T-5 (label, applies_on_sale, applies_on_return, sign_on_return)
  - case_matrix: {Delivered, DTO, RTO, InternalCancel} → per fee head behaviour
  - notes: free text

Editable via Masters → Portals. Default seed is loaded on backend bootstrap
if the portals collection is empty.
"""
PORTALS_SEED = [
    {
        "code": "myntra",
        "name": "Myntra",
        "status": "live",
        "notes": "Primary connector. NSV-GT commission base. Zone-level return fees.",
        "fee_heads": [
            {"key": "T1", "label": "Commission %",  "sale": 0.085,  "return": -0.085, "unit": "pct"},
            {"key": "T2", "label": "GT Logistic",   "sale": "table", "return": "table", "unit": "table"},
            {"key": "T3", "label": "Fixed Fee",     "sale": "table", "return": "reversed", "unit": "table"},
            {"key": "T4", "label": "Return Fee",    "sale": 0.0,     "return": "table", "unit": "table"},
        ],
        "case_matrix": {
            "Delivered":       {"T1": "Charged",  "T2": "Charged",       "T3": "Charged", "T4": "-"},
            "DTO":             {"T1": "Reversal", "T2": "Again Charged", "T3": "Kept",    "T4": "Charged"},
            "RTO":             {"T1": "All null", "T2": "All null",      "T3": "All null","T4": "All null"},
            "InternalCancel":  {"T1": "All null", "T2": "All null",      "T3": "All null","T4": "All null"},
        },
    },
    {
        "code": "amazon",
        "name": "Amazon",
        "status": "coming_soon",
        "notes": "18.7% commission + 11.5% logistic. Effective Apr-2025 to Mar-2026.",
        "fee_heads": [
            {"key": "T1", "label": "Commission %",  "sale": 0.187,  "return": -0.187, "unit": "pct"},
            {"key": "T2", "label": "Logistic %",    "sale": 0.115,  "return": 0.115,  "unit": "pct"},
        ],
        "case_matrix": {
            "Delivered":       {"T1": "Charged",  "T2": "Charged"},
            "DTO":             {"T1": "Reversal", "T2": "Again Charged"},
            "RTO":             {"T1": "All null", "T2": "All null"},
            "InternalCancel":  {"T1": "All null", "T2": "All null"},
        },
    },
    {
        "code": "ajio",
        "name": "AJIO (Direct Ship)",
        "status": "coming_soon",
        "notes": "Flat 36% commission. No reversal on return-DTO fixed heads.",
        "fee_heads": [
            {"key": "T1", "label": "Commission %",  "sale": 0.36,   "return": -0.36,  "unit": "pct"},
        ],
        "case_matrix": {
            "Delivered":       {"T1": "Charged"},
            "DTO":             {"T1": "Reversal"},
            "RTO":             {"T1": "All null"},
            "InternalCancel":  {"T1": "All null"},
        },
    },
    {
        "code": "nykaa",
        "name": "Nykaa",
        "status": "coming_soon",
        "notes": "24% commission + Rs.50/order fixed + 0.80% gateway (Prepaid & COD). No reversal on fixed / gateway.",
        "fee_heads": [
            {"key": "T1", "label": "Commission %",       "sale": 0.24,   "return": -0.24,  "unit": "pct"},
            {"key": "T2", "label": "Fixed per Order",    "sale": 50.0,   "return": 0.0,    "unit": "flat_inr"},
            {"key": "T3", "label": "Gateway % (P+C)",    "sale": 0.008,  "return": 0.0,    "unit": "pct"},
        ],
        "case_matrix": {
            "Delivered":       {"T1": "Charged",  "T2": "Charged",  "T3": "Charged"},
            "DTO":             {"T1": "Reversal", "T2": "No reversal", "T3": "No reversal"},
            "RTO":             {"T1": "All null", "T2": "All null",    "T3": "All null"},
            "InternalCancel":  {"T1": "All null", "T2": "All null",    "T3": "All null"},
        },
    },
    {
        "code": "tatacliq",
        "name": "Tata Cliq",
        "status": "coming_soon",
        "notes": "16% commission + 31% (bags only) + 3% marketing + 6% logistic. Marketing reversed on DTO.",
        "fee_heads": [
            {"key": "T1", "label": "Commission %",     "sale": 0.16,   "return": -0.16, "unit": "pct"},
            {"key": "T2", "label": "Bag Commission %", "sale": 0.31,   "return": -0.31, "unit": "pct", "conditional": "bags_only"},
            {"key": "T3", "label": "Marketing Exp %",  "sale": 0.03,   "return": -0.03, "unit": "pct"},
            {"key": "T4", "label": "Logistic %",       "sale": 0.06,   "return": 0.06,  "unit": "pct"},
        ],
        "case_matrix": {
            "Delivered":       {"T1": "Charged",  "T2": "Charged",  "T3": "Charged",  "T4": "Charged"},
            "DTO":             {"T1": "Reversal", "T2": "Reversal", "T3": "Reversal", "T4": "Again Charged"},
            "RTO":             {"T1": "All null", "T2": "All null", "T3": "All null", "T4": "All null"},
            "InternalCancel":  {"T1": "All null", "T2": "All null", "T3": "All null", "T4": "All null"},
        },
    },
    {
        "code": "flipkart",
        "name": "Flipkart",
        "status": "coming_soon",
        "notes": "Category-level commission (external rate card required). Effective Apr-2025 to Mar-2026.",
        "fee_heads": [
            {"key": "T1", "label": "Commission %",  "sale": "category", "return": "category", "unit": "category_table"},
            {"key": "T2", "label": "Fixed Fee",     "sale": "table",    "return": "reversed", "unit": "table"},
            {"key": "T3", "label": "Logistic",      "sale": "table",    "return": "again_charged", "unit": "table"},
        ],
        "case_matrix": {
            "Delivered":       {"T1": "Charged",  "T2": "Charged",       "T3": "Charged"},
            "DTO":             {"T1": "Reversal", "T2": "Reversal",      "T3": "Again Charged"},
            "RTO":             {"T1": "All null", "T2": "All null",      "T3": "All null"},
            "InternalCancel":  {"T1": "All null", "T2": "All null",      "T3": "All null"},
        },
    },
]
