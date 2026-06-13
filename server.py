#!/usr/bin/env python3
"""
MEOK UAS Commercial Drone Compliance MCP
=========================================

By MEOK AI Labs · https://haulage.app · MIT
<!-- mcp-name: io.github.CSOAI-ORG/meok-uas-commercial-drone-mcp -->

WHAT THIS DOES
--------------
Commercial drone logistics is governed by a stack of overlapping regs:
  - UK CAA CAP 722 + Air Navigation Order 2016 (Operational Authorisation)
  - EU Regulation 2019/947 + 2019/945 (Open / Specific / Certified Categories)
  - US FAA Part 107 (sUAS commercial) + Part 137 (Agricultural)
  - ICAO Annex 13 incident reporting

This MCP extends MEOK from road / air-cargo → unmanned. Royal Mail, NHS sample
transport drones, Wing, Amazon Prime Air, Aerialscape all need this stack to
launch routes:
  - Open A1/A2/A3 (sub-25kg, no op auth)
  - Specific (Operational Authorisation + risk assessment / SORA)
  - Certified (manned-aircraft rules — passenger / long-range BVLOS)
  - A2 CofC + GVC + OA endorsements for pilot competence
  - CAA SUA inspection prep (Ops Manual, pilot record, RA, insurance)

A single Specific category flight without a valid Operational Authorisation =
£5,000 CAA fine + grounding. This MCP gives the callable compliance toolkit.

TOOLS (8)
---------
- check_caa_operator_authorisation(operator)         → UK OSC / GA vs SA
- check_uas_open_category(uas_spec)                  → A1/A2/A3 sub-25kg
- check_uas_specific_category(operation_spec)        → SORA + OA
- check_uas_certified_category(uas_spec)             → manned-aircraft rules
- check_remote_pilot_competence(pilot_id, ...)       → A2 CofC + GVC + OA
- check_far_part_107_us(operator_data)               → US FAA Part 107
- check_easa_uas_reg_2019_947(operator_data)         → EU 2019/947 + 945
- prepare_caa_inspection_pack(operator_data)         → CAA SUA inspection

WHY YOU PAY
-----------
A single avoided Specific category misconfiguration = £5,000 CAA fine + lost
flying season. NHS sample transport routes that fail OSC review at CAA get
pulled the day before launch. Aerialscape / Royal Mail / Wing use this for
fleet-wide compliance attestation.

PRICING
-------
Free MIT self-host · £99/mo Starter · £299/mo Pro · £1,499/mo Fleet.

REGULATORY BASIS
----------------
UK CAA CAP 722 — UAS regulations
UK Air Navigation Order 2016 (as amended for UAS)
EU Regulation 2019/947 + 2019/945
US FAA 14 CFR Part 107 (sUAS) + Part 137 (Agricultural)
ICAO Annex 13 — Aircraft Accident and Incident Investigation
"""

from __future__ import annotations
import urllib.request as _meter_urlreq
import urllib.error as _meter_urlerr
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Optional
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("meok-uas-commercial-drone")
_HMAC_SECRET = os.environ.get("MEOK_HMAC_SECRET", "")


# ──────────────────────────────────────────────────────────────────────
# Regulatory tables
# ──────────────────────────────────────────────────────────────────────

# UK CAA CAP 722 operating authorisation pathways
CAA_AUTHORISATION_TYPES = {
    "GA": {
        "name": "General Authorisation",
        "scope": "Standard scenarios — UK PDRA-01 / PDRA-02 etc.",
        "duration_months": 12,
        "fee_gbp": 253,
        "renewal_required": True,
    },
    "SA": {
        "name": "Specific Authorisation",
        "scope": "Bespoke ops outside any PDRA — full OSC required",
        "duration_months": 12,
        "fee_gbp": 2900,
        "renewal_required": True,
    },
    "OSC": {
        "name": "Operational Safety Case",
        "scope": "Mandatory document set for Specific authorisations",
        "components": [
            "Operations Manual",
            "Pilot Competence Record",
            "Risk Assessment (SORA recommended)",
            "Insurance certificate (EC 785/2004)",
            "Maintenance Plan",
            "Emergency Response Plan",
        ],
    },
}

# UK / EU Open category subcategories (EU 2019/947 Article 4 + UK ANO retained)
OPEN_CATEGORY = {
    "A1": {
        "name": "Open A1 — over / close to people",
        "max_mtom_kg": 0.25,
        "max_altitude_ft_agl": 400,
        "vlos_required": True,
        "minimum_pilot_competence": "self-study + online test (C0/C1)",
        "uas_class_id_required": ["C0", "C1"],
        "over_uninvolved_people": "C0 yes; C1 transient only",
        "over_assemblies_of_people": False,
    },
    "A2": {
        "name": "Open A2 — close to people",
        "max_mtom_kg": 4.0,
        "max_altitude_ft_agl": 400,
        "vlos_required": True,
        "minimum_pilot_competence": "A2 Certificate of Competency (A2 CofC)",
        "uas_class_id_required": ["C2"],
        "min_horizontal_distance_m_from_uninvolved": 30,
        "low_speed_mode_distance_m": 5,
        "over_assemblies_of_people": False,
    },
    "A3": {
        "name": "Open A3 — far from people",
        "max_mtom_kg": 25.0,
        "max_altitude_ft_agl": 400,
        "vlos_required": True,
        "minimum_pilot_competence": "self-study + online test or A2 CofC",
        "uas_class_id_required": ["C2", "C3", "C4"],
        "min_horizontal_distance_m_from_uninvolved": 150,
        "no_overflight_of_residential_commercial_industrial_recreational": True,
        "over_assemblies_of_people": False,
    },
}

# Specific category — needs Operational Authorisation
SPECIFIC_CATEGORY = {
    "trigger_conditions": [
        "MTOM > 25 kg",
        "altitude > 400 ft AGL",
        "BVLOS (Beyond Visual Line of Sight)",
        "over assemblies of people",
        "outside Open category limits in any way",
    ],
    "required_authorisation": "Operational Authorisation (UK CAA Form SRG1320)",
    "required_documents": [
        "Operations Manual",
        "Risk Assessment (SORA methodology)",
        "Pilot Competence record (GVC minimum)",
        "Insurance per EC 785/2004",
        "Operator ID + Flyer ID",
    ],
    "pdra": {
        "PDRA-01": "VLOS or EVLOS sub-25kg, ≤400ft AGL, ≥50m from people",
        "PDRA-02": "BVLOS in atypical airspace (segregated)",
        "PDRA-G01": "Recreational / community ops",
        "PDRA-G02": "Photographic flights over operator's premises",
    },
}

# Certified category — manned-aircraft-like rules
CERTIFIED_CATEGORY = {
    "trigger_conditions": [
        "Carriage of people (passenger drone / eVTOL)",
        "Carriage of dangerous goods with high-consequence risk",
        "Flight over assemblies of people with MTOM >= significant",
        "BVLOS over urban / congested areas at high MTOM",
    ],
    "required": [
        "UAS type certificate (CS-UAS / EASA Special Condition Light-UAS)",
        "UAS Operator Certificate (UASOC / equivalent AOC)",
        "Licensed remote pilot (Part-FCL or equivalent)",
        "Continuing airworthiness organisation (CAMO equivalent)",
        "ICAO Annex 13 incident reporting framework",
    ],
    "applicable_specs": [
        "EASA Special Condition for Light-UAS (SC Light-UAS)",
        "CS-LUAS (Certification Spec for Light-UAS)",
        "ICAO Annex 6 Part IV (RPAS)",
    ],
}

# UK pilot competence ladder
UK_PILOT_COMPETENCE = {
    "flyer_id_test": "Free online test — required for all RC > 250g (annual)",
    "operator_id": "£11.59/yr — required for operator",
    "a2_cofc": {
        "name": "A2 Certificate of Competency",
        "covers": "Open A2 subcategory — fly C2 close to people",
        "delivery": "RAE-delivered theory + self-practical",
        "validity_years": 5,
    },
    "gvc": {
        "name": "General VLOS Certificate",
        "covers": "Specific category Operational Authorisation pilot",
        "delivery": "RAE theory + flight test + ops manual",
        "validity_years": 5,
    },
    "oa_endorsement": {
        "name": "Operational Authorisation endorsement",
        "covers": "Specific to the OA scope — BVLOS, swarms, EVLOS etc.",
        "issued_by": "CAA on operator's OSC",
        "validity": "linked to OA expiry (12 months)",
    },
}

# US FAA Part 107 thresholds (14 CFR Part 107)
PART_107_RULES = {
    "applies_to": "sUAS (small UAS) weighing < 55 lbs / 25 kg",
    "remote_pilot_certificate": "Required — TRUST + Part 107 knowledge test",
    "max_altitude_ft_agl": 400,
    "max_speed_knots": 87,
    "vlos_required": True,
    "daylight_or_civil_twilight": True,
    "operations_over_people": "Categories 1-4 with specific UAS requirements",
    "operations_over_moving_vehicles": "Permitted with operations-over-people compliance",
    "waiver_pathway": "Part 107.200 waiver — required for BVLOS / night / OOP not in cat 1-4",
    "remote_id_required": True,  # since 16 Sep 2023
    "registration_required": True,  # all UAS regardless of weight if commercial
    "agricultural_pathway": "Part 137 — agricultural aircraft operations (separate certificate)",
}

# EU 2019/947 + 2019/945 quick reference
EASA_UAS_REGS = {
    "2019/947": {
        "name": "Implementing Regulation — Categories of UAS operation",
        "categories": ["Open", "Specific", "Certified"],
        "registration": "All UAS operators (Article 14) except toys < 250g without camera",
        "remote_pilot_competency": "Article 8 — different per category",
    },
    "2019/945": {
        "name": "Delegated Regulation — UAS Class identification + Manufacturer reqs",
        "classes": ["C0", "C1", "C2", "C3", "C4", "C5", "C6"],
        "ce_marking": "Required",
        "class_marking_deadline": "From 1 Jan 2024 (after transition period)",
    },
}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _sign(payload: dict) -> str:
    """HMAC-sign the response for tamper-evident audit."""
    if not _HMAC_SECRET:
        return "unsigned-no-key-configured"
    return hmac.new(
        _HMAC_SECRET.encode(),
        json.dumps(payload, sort_keys=True, default=str).encode(),
        hashlib.sha256,
    ).hexdigest()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attestation(payload: dict) -> dict:
    return {
        **payload,
        "ts": _ts(),
        "sig": _sign(payload),
        "issuer": "meok-uas-commercial-drone-mcp",
        "version": "1.0.0",
    }


# ──────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────


def _server_meter_check(api_key: str = "") -> dict:
    """Calls the live /verify endpoint for server-side metering. Fail-open."""
    try:
        data = json.dumps({"api_key": api_key, "tool": ""}).encode()
        req = _meter_urlreq.Request(_METER_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with _meter_urlreq.urlopen(req, timeout=2.5) as r:
            d = json.loads(r.read())
            if isinstance(d, dict) and "allowed" in d:
                return d
    except Exception:
        pass
    return {"allowed": True, "tier": "anonymous", "remaining": 200, "upgrade_url": "https://meok.ai/pricing"}


_METER_URL = "https://proofof.ai/verify"


@mcp.tool()
def check_caa_operator_authorisation(
    operator_name: str,
    operation_type: str = "VLOS_sub25kg",
    has_operator_id: bool = False,
    has_flyer_id: bool = False,
    holds_operational_authorisation: bool = False,
    holds_general_authorisation: bool = False,
    osc_documents_complete: bool = False,
    insurance_ec_785_2004: bool = False,
    mtom_kg: float = 0.0,
    altitude_ft_agl: float = 0.0,
    is_bvlos: bool = False,
    over_assemblies_of_people: bool = False,
) -> dict:
    """Determine UK CAA authorisation pathway: GA vs SA vs OSC required.

    Args:
      operator_name: legal name of operator
      operation_type: shorthand label e.g. 'VLOS_sub25kg' / 'BVLOS_route'
      has_operator_id: holds CAA Operator ID
      has_flyer_id: holds CAA Flyer ID
      holds_operational_authorisation: holds current OA (Specific category)
      holds_general_authorisation: holds GA (e.g. PDRA-01)
      osc_documents_complete: complete OSC documentation
      insurance_ec_785_2004: holds EC 785/2004 insurance
      mtom_kg: max take-off mass (kg)
      altitude_ft_agl: planned altitude (ft AGL)
      is_bvlos: is the operation BVLOS?
      over_assemblies_of_people: overflight of assemblies of people?
    """
    findings = []
    required_pathway = "Open"

    if not has_operator_id:
        findings.append("CAA Operator ID MISSING — register at register-drones.caa.co.uk (£11.59/yr)")
    if not has_flyer_id:
        findings.append("CAA Flyer ID MISSING — pass free online test (annual)")
    if not insurance_ec_785_2004:
        findings.append("EC 785/2004 insurance MISSING — minimum SDR cover required for commercial")

    # Trigger Specific category?
    needs_specific = (
        mtom_kg > 25.0
        or altitude_ft_agl > 400.0
        or is_bvlos
        or over_assemblies_of_people
    )

    if needs_specific:
        required_pathway = "Specific"
        if not (holds_operational_authorisation or holds_general_authorisation):
            findings.append(
                "Specific category triggers — Operational Authorisation (SA) "
                "OR General Authorisation (e.g. PDRA-01) REQUIRED"
            )
        if not osc_documents_complete and holds_operational_authorisation:
            findings.append(
                "OSC documentation incomplete — Ops Manual / Pilot Record / "
                "Risk Assessment / Insurance must all be filed."
            )

    if mtom_kg > 600.0:
        required_pathway = "Certified"
        findings.append(
            "MTOM > 600 kg or carriage of people → Certified category required "
            "(type certificate, UASOC, licensed pilot)."
        )

    decision = "AUTHORISED" if not findings else "BLOCK"

    payload = {
        "tool": "check_caa_operator_authorisation",
        "operator_name": operator_name,
        "operation_type": operation_type,
        "required_pathway": required_pathway,
        "authorisation_types_reference": CAA_AUTHORISATION_TYPES,
        "mtom_kg": mtom_kg,
        "altitude_ft_agl": altitude_ft_agl,
        "is_bvlos": is_bvlos,
        "over_assemblies_of_people": over_assemblies_of_people,
        "findings": findings,
        "decision": decision,
        "advisory": (
            "OK — fly under the stated pathway." if decision == "AUTHORISED" else
            "BLOCK — clear findings before flight. Single occurrence = £5,000 fine + grounding."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def check_uas_open_category(
    mtom_kg: float,
    uas_class_id: str = "",
    altitude_ft_agl: float = 0.0,
    is_vlos: bool = True,
    distance_from_uninvolved_m: float = 0.0,
    over_assemblies_of_people: bool = False,
    pilot_has_online_test: bool = False,
    pilot_has_a2_cofc: bool = False,
) -> dict:
    """Determine if an operation fits Open A1 / A2 / A3 (sub-25kg, no operating auth).

    Args:
      mtom_kg: max take-off mass (kg)
      uas_class_id: 'C0' / 'C1' / 'C2' / 'C3' / 'C4' / '' (legacy / no class)
      altitude_ft_agl: planned altitude (ft AGL)
      is_vlos: VLOS maintained?
      distance_from_uninvolved_m: horizontal distance from uninvolved people (m)
      over_assemblies_of_people: assemblies of people overflown?
      pilot_has_online_test: pilot passed CAA online test (Flyer ID)
      pilot_has_a2_cofc: pilot holds A2 Certificate of Competency
    """
    findings = []
    subcategory: Optional[str] = None

    if mtom_kg > 25.0:
        return _attestation({
            "tool": "check_uas_open_category",
            "fits_open_category": False,
            "reason": f"MTOM {mtom_kg} kg exceeds 25 kg ceiling — Specific category required.",
            "subcategory": None,
        })
    if altitude_ft_agl > 400.0:
        findings.append(f"Altitude {altitude_ft_agl} ft AGL > 400 ft — Specific category required.")
    if not is_vlos:
        findings.append("VLOS not maintained — Open category requires VLOS. Specific required.")
    if over_assemblies_of_people:
        findings.append("Over assemblies of people — Open category never permits this. Specific required.")

    # Subcategory selection
    if mtom_kg <= 0.25 and uas_class_id in ("C0", ""):
        subcategory = "A1"
    elif mtom_kg <= 4.0 and uas_class_id == "C1":
        subcategory = "A1"
    elif mtom_kg <= 4.0 and uas_class_id == "C2" and pilot_has_a2_cofc and distance_from_uninvolved_m >= 30:
        subcategory = "A2"
    elif mtom_kg <= 25.0 and distance_from_uninvolved_m >= 150:
        subcategory = "A3"

    if not subcategory and not findings:
        findings.append(
            f"Cannot fit MTOM {mtom_kg} kg + uas_class_id '{uas_class_id}' "
            f"+ distance {distance_from_uninvolved_m} m into A1/A2/A3."
        )

    if subcategory == "A2" and not pilot_has_a2_cofc:
        findings.append("A2 subcategory requires A2 CofC — pilot does not hold one.")

    if not pilot_has_online_test:
        findings.append("Pilot has not passed CAA online test (Flyer ID) — mandatory all Open ops.")

    payload = {
        "tool": "check_uas_open_category",
        "mtom_kg": mtom_kg,
        "uas_class_id": uas_class_id,
        "altitude_ft_agl": altitude_ft_agl,
        "subcategory": subcategory,
        "subcategory_rules": OPEN_CATEGORY.get(subcategory, {}),
        "fits_open_category": subcategory is not None and not findings,
        "findings": findings,
        "advisory": (
            f"OK — fly under Open {subcategory}." if subcategory and not findings else
            "BLOCK or escalate to Specific category."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def check_uas_specific_category(
    operation_description: str,
    mtom_kg: float,
    altitude_ft_agl: float = 0.0,
    is_bvlos: bool = False,
    over_assemblies_of_people: bool = False,
    over_residential: bool = False,
    has_operational_authorisation: bool = False,
    has_risk_assessment_sora: bool = False,
    pdra_used: str = "",
    operations_manual_in_place: bool = False,
    pilot_has_gvc: bool = False,
    insurance_ec_785_2004: bool = False,
) -> dict:
    """Determine if a Specific category operation has the full OA + OSC.

    Args:
      operation_description: free-text e.g. 'BVLOS NHS sample shuttle, A→B, 12km'
      mtom_kg: max take-off mass (kg)
      altitude_ft_agl: planned altitude (ft AGL)
      is_bvlos: BVLOS operation
      over_assemblies_of_people: overflight of assemblies of people
      over_residential: overflight of residential / commercial / industrial areas
      has_operational_authorisation: holds current OA (SRG1320)
      has_risk_assessment_sora: has completed SORA risk assessment
      pdra_used: which PDRA (e.g. 'PDRA-01' / '' if bespoke)
      operations_manual_in_place: Operations Manual exists
      pilot_has_gvc: pilot holds General VLOS Certificate
      insurance_ec_785_2004: insurance per EC 785/2004
    """
    findings = []

    # Confirm Specific is even the right category
    triggers = []
    if mtom_kg > 25.0:
        triggers.append("MTOM > 25 kg")
    if altitude_ft_agl > 400.0:
        triggers.append("Altitude > 400 ft AGL")
    if is_bvlos:
        triggers.append("BVLOS")
    if over_assemblies_of_people:
        triggers.append("Overflight of assemblies of people")

    if not triggers:
        return _attestation({
            "tool": "check_uas_specific_category",
            "specific_required": False,
            "advisory": (
                "No Specific category triggers — consider Open category instead "
                "(see check_uas_open_category)."
            ),
        })

    if not has_operational_authorisation:
        findings.append(
            "Operational Authorisation (CAA SRG1320) MISSING — "
            "no flight permitted. Single occurrence = £5,000 fine."
        )

    if not has_risk_assessment_sora and pdra_used == "":
        findings.append(
            "Bespoke Specific op without SORA risk assessment — required when no PDRA fits."
        )

    if not operations_manual_in_place:
        findings.append("Operations Manual MISSING — mandatory for any Specific op.")

    if not pilot_has_gvc:
        findings.append("Pilot does not hold GVC — minimum competence for Specific category.")

    if not insurance_ec_785_2004:
        findings.append("EC 785/2004 insurance MISSING — commercial Specific op requires it.")

    if over_assemblies_of_people and pdra_used in ("PDRA-01", "PDRA-G01"):
        findings.append(
            f"Overflight of assemblies of people NOT compatible with {pdra_used} — "
            "needs bespoke OA with SORA."
        )

    if mtom_kg > 600.0:
        findings.append(
            "MTOM > 600 kg crosses into Certified category — Specific path insufficient."
        )

    decision = "AUTHORISED" if not findings else "BLOCK"
    payload = {
        "tool": "check_uas_specific_category",
        "operation_description": operation_description,
        "specific_required": True,
        "triggers": triggers,
        "pdra_used": pdra_used or None,
        "pdra_reference": SPECIFIC_CATEGORY["pdra"],
        "required_authorisation": SPECIFIC_CATEGORY["required_authorisation"],
        "required_documents": SPECIFIC_CATEGORY["required_documents"],
        "findings": findings,
        "decision": decision,
        "advisory": (
            "OK — fly under the Operational Authorisation." if decision == "AUTHORISED" else
            "BLOCK — clear all findings before flight."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def check_uas_certified_category(
    operation_description: str,
    mtom_kg: float,
    carries_people: bool = False,
    carries_dangerous_goods_high_consequence: bool = False,
    over_assemblies_of_people: bool = False,
    bvlos_urban: bool = False,
    has_uas_type_certificate: bool = False,
    has_uas_operator_certificate: bool = False,
    has_licensed_remote_pilot: bool = False,
    has_camo_equivalent: bool = False,
    has_annex_13_reporting: bool = False,
) -> dict:
    """Determine if a Certified category UAS has the manned-aircraft-equivalent setup.

    Args:
      operation_description: free-text
      mtom_kg: max take-off mass (kg)
      carries_people: passenger drone / eVTOL
      carries_dangerous_goods_high_consequence: high-consequence DG (Class 1, 7 etc.)
      over_assemblies_of_people: overflight of assemblies of people, high MTOM
      bvlos_urban: BVLOS over urban / congested areas at high MTOM
      has_uas_type_certificate: UAS type certificate (CS-UAS / SC Light-UAS)
      has_uas_operator_certificate: UASOC / equivalent AOC
      has_licensed_remote_pilot: licensed remote pilot (Part-FCL equivalent)
      has_camo_equivalent: continuing-airworthiness organisation
      has_annex_13_reporting: ICAO Annex 13 reporting framework in place
    """
    findings = []

    triggers = []
    if carries_people:
        triggers.append("Carriage of people")
    if carries_dangerous_goods_high_consequence:
        triggers.append("High-consequence dangerous goods")
    if over_assemblies_of_people and mtom_kg >= 25.0:
        triggers.append("Overflight of assemblies of people at significant MTOM")
    if bvlos_urban and mtom_kg >= 25.0:
        triggers.append("BVLOS over urban at high MTOM")

    if not triggers:
        return _attestation({
            "tool": "check_uas_certified_category",
            "certified_required": False,
            "advisory": (
                "No Certified category triggers — try check_uas_specific_category instead."
            ),
        })

    if not has_uas_type_certificate:
        findings.append("UAS type certificate (CS-UAS / SC Light-UAS) MISSING")
    if not has_uas_operator_certificate:
        findings.append("UAS Operator Certificate (UASOC / equivalent AOC) MISSING")
    if not has_licensed_remote_pilot:
        findings.append("Licensed remote pilot (Part-FCL equivalent) MISSING")
    if not has_camo_equivalent:
        findings.append("Continuing-airworthiness org (CAMO equivalent) MISSING")
    if not has_annex_13_reporting:
        findings.append("ICAO Annex 13 incident reporting framework MISSING")

    decision = "AUTHORISED" if not findings else "BLOCK"
    payload = {
        "tool": "check_uas_certified_category",
        "operation_description": operation_description,
        "certified_required": True,
        "triggers": triggers,
        "required": CERTIFIED_CATEGORY["required"],
        "applicable_specs": CERTIFIED_CATEGORY["applicable_specs"],
        "findings": findings,
        "decision": decision,
        "advisory": (
            "OK — UAS + operator + crew are Certified-grade."
            if decision == "AUTHORISED" else
            "BLOCK — Certified category requires manned-aircraft-equivalent setup."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def check_remote_pilot_competence(
    pilot_id: str,
    has_a2_cofc: bool = False,
    has_gvc: bool = False,
    has_oa_endorsement: bool = False,
    has_flyer_id: bool = False,
    intended_category: str = "Open_A3",
) -> dict:
    """Verify a UK remote pilot has the right competence for the intended category.

    Args:
      pilot_id: pilot identifier (CAA reference or internal)
      has_a2_cofc: holds A2 Certificate of Competency
      has_gvc: holds General VLOS Certificate
      has_oa_endorsement: holds Operational Authorisation endorsement
      has_flyer_id: holds current CAA Flyer ID
      intended_category: 'Open_A1' / 'Open_A2' / 'Open_A3' / 'Specific' / 'Certified'
    """
    findings = []
    cat = intended_category.strip()

    if not has_flyer_id:
        findings.append("CAA Flyer ID MISSING — minimum for any flight in Open category.")

    if cat in ("Open_A1", "Open_A3"):
        # Self-study + online test is enough
        pass
    elif cat == "Open_A2":
        if not has_a2_cofc:
            findings.append("Open A2 requires A2 Certificate of Competency (A2 CofC) — pilot missing it.")
    elif cat == "Specific":
        if not has_gvc:
            findings.append("Specific category minimum is GVC — pilot missing it.")
        if not has_oa_endorsement:
            findings.append(
                "Operational Authorisation endorsement MISSING — required to fly under operator's OA."
            )
    elif cat == "Certified":
        findings.append(
            "Certified category requires Part-FCL-equivalent license — A2 CofC / GVC NOT sufficient."
        )
    else:
        findings.append(f"Unknown intended_category '{cat}'.")

    decision = "COMPETENT" if not findings else "BLOCK"

    payload = {
        "tool": "check_remote_pilot_competence",
        "pilot_id": pilot_id,
        "intended_category": cat,
        "has_a2_cofc": has_a2_cofc,
        "has_gvc": has_gvc,
        "has_oa_endorsement": has_oa_endorsement,
        "has_flyer_id": has_flyer_id,
        "competence_reference": UK_PILOT_COMPETENCE,
        "findings": findings,
        "decision": decision,
        "advisory": (
            f"OK — pilot competent for {cat}." if decision == "COMPETENT" else
            f"BLOCK — pilot not competent for {cat}. Single occurrence = grounding."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def check_far_part_107_us(
    operator_name: str,
    pilot_holds_remote_pilot_certificate: bool = False,
    pilot_passed_trust: bool = False,
    uas_registered_with_faa: bool = False,
    uas_remote_id_compliant: bool = False,
    uas_weight_lbs: float = 0.0,
    altitude_ft_agl: float = 0.0,
    is_bvlos: bool = False,
    is_night: bool = False,
    over_people_category: int = 0,
    is_agricultural: bool = False,
) -> dict:
    """Verify a US FAA Part 107 sUAS commercial operation.

    Args:
      operator_name: operator legal name
      pilot_holds_remote_pilot_certificate: holds FAA Remote Pilot Certificate
      pilot_passed_trust: passed TRUST (only for recreational, kept for completeness)
      uas_registered_with_faa: registered (mandatory for commercial regardless of weight)
      uas_remote_id_compliant: Remote ID compliant (since Sep 2023)
      uas_weight_lbs: weight in pounds
      altitude_ft_agl: planned altitude (ft AGL)
      is_bvlos: BVLOS operation
      is_night: night operation
      over_people_category: 0/1/2/3/4 — Categories under 107.39+
      is_agricultural: agricultural aircraft op (Part 137 instead)
    """
    findings = []

    if is_agricultural:
        return _attestation({
            "tool": "check_far_part_107_us",
            "operator_name": operator_name,
            "pathway": "Part 137 — agricultural aircraft operations",
            "advisory": (
                "Agricultural sUAS ops are governed by 14 CFR Part 137, NOT Part 107. "
                "Operator needs a Part 137 certificate from FAA."
            ),
        })

    if uas_weight_lbs >= 55.0:
        findings.append(
            f"UAS weight {uas_weight_lbs} lb ≥ 55 lb — outside Part 107. "
            "Requires exemption under Section 44807 or Part 135."
        )

    if not pilot_holds_remote_pilot_certificate:
        findings.append(
            "Pilot does NOT hold FAA Remote Pilot Certificate — required for commercial sUAS."
        )

    if not uas_registered_with_faa:
        findings.append(
            "UAS NOT registered with FAA — commercial ops require registration regardless of weight."
        )

    if not uas_remote_id_compliant:
        findings.append(
            "Remote ID NOT compliant — mandatory for all sUAS in airspace since 16 Sep 2023."
        )

    if altitude_ft_agl > 400.0:
        findings.append(
            f"Altitude {altitude_ft_agl} ft > 400 ft AGL — requires Part 107.51(b) waiver "
            "(or within 400 ft of structure)."
        )

    if is_bvlos:
        findings.append("BVLOS requires Part 107.31 waiver (or Part 108 BVLOS rule when finalised).")

    if is_night:
        # Since 2021, night ops permitted under 107.29(a)(2) with anti-collision lighting
        pass

    if over_people_category not in (0, 1, 2, 3, 4):
        findings.append(f"Invalid over_people_category {over_people_category} — must be 0-4.")

    decision = "AUTHORISED" if not findings else "BLOCK"

    payload = {
        "tool": "check_far_part_107_us",
        "operator_name": operator_name,
        "pathway": "Part 107 sUAS commercial",
        "uas_weight_lbs": uas_weight_lbs,
        "altitude_ft_agl": altitude_ft_agl,
        "is_bvlos": is_bvlos,
        "is_night": is_night,
        "over_people_category": over_people_category,
        "part_107_reference": PART_107_RULES,
        "findings": findings,
        "decision": decision,
        "advisory": (
            "OK — fly under Part 107." if decision == "AUTHORISED" else
            "BLOCK — clear findings or file Part 107.200 waiver."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def check_easa_uas_reg_2019_947(
    operator_name: str,
    member_state: str,
    operator_registered: bool = False,
    uas_class_id: str = "",
    uas_ce_marked: bool = False,
    category: str = "Open",
    pilot_competency_filed: bool = False,
    cross_border_notification_filed: bool = False,
) -> dict:
    """Verify an EU operation complies with Regulation 2019/947 + 2019/945.

    Args:
      operator_name: legal name
      member_state: ISO-2 e.g. 'DE' / 'FR'
      operator_registered: registered in EASA member state per Article 14
      uas_class_id: 'C0' / 'C1' / 'C2' / 'C3' / 'C4' / 'C5' / 'C6'
      uas_ce_marked: UAS bears CE marking
      category: 'Open' / 'Specific' / 'Certified'
      pilot_competency_filed: Article 8 competency record on file
      cross_border_notification_filed: cross-border notification (Specific cat) filed
    """
    findings = []

    if not operator_registered:
        findings.append(
            "Operator NOT registered per 2019/947 Article 14 — required for all UAS "
            "except toys < 250 g without camera."
        )

    cat = category.strip().capitalize()
    if cat not in ("Open", "Specific", "Certified"):
        findings.append(f"Invalid category '{cat}' — must be Open / Specific / Certified.")

    if uas_class_id and uas_class_id not in EASA_UAS_REGS["2019/945"]["classes"]:
        findings.append(
            f"UAS class id '{uas_class_id}' not in 2019/945 classes "
            f"({EASA_UAS_REGS['2019/945']['classes']})."
        )

    if not uas_ce_marked and uas_class_id:
        findings.append("UAS class-marked but NOT CE-marked — 2019/945 requires both.")

    if not pilot_competency_filed:
        findings.append("Pilot competency record (2019/947 Article 8) NOT filed.")

    if cat == "Specific" and not cross_border_notification_filed:
        findings.append(
            "Cross-border Specific cat ops require notification per Article 13 — not filed."
        )

    decision = "AUTHORISED" if not findings else "BLOCK"
    payload = {
        "tool": "check_easa_uas_reg_2019_947",
        "operator_name": operator_name,
        "member_state": member_state,
        "category": cat,
        "uas_class_id": uas_class_id,
        "easa_regs_reference": EASA_UAS_REGS,
        "findings": findings,
        "decision": decision,
        "advisory": (
            f"OK — operation compliant with 2019/947 + 2019/945 in {member_state}."
            if decision == "AUTHORISED" else
            "BLOCK — clear findings before flight. Member-state CAA can ground operator."
        ),
    }
    return _attestation(payload)


@mcp.tool()
def prepare_caa_inspection_pack(
    operator_name: str,
    operator_id_caa: str,
    has_operations_manual: bool = False,
    operations_manual_revision: str = "",
    has_pilot_competence_record: bool = False,
    has_risk_assessment: bool = False,
    risk_assessment_method: str = "SORA",
    has_insurance_certificate: bool = False,
    insurance_expiry: str = "",
    has_maintenance_log: bool = False,
    has_emergency_response_plan: bool = False,
    has_incident_register: bool = False,
) -> dict:
    """Prepare a CAA SUA inspection pack — what to hand over when CAA arrives.

    Args:
      operator_name: legal name
      operator_id_caa: CAA Operator ID
      has_operations_manual: Operations Manual filed
      operations_manual_revision: rev id e.g. 'Rev 3 (2026-02-01)'
      has_pilot_competence_record: pilot logs + A2 CofC / GVC / OA endorsement records
      has_risk_assessment: risk assessment present
      risk_assessment_method: 'SORA' / 'PDRA-01' / 'bespoke'
      has_insurance_certificate: EC 785/2004 cert present
      insurance_expiry: ISO date of expiry
      has_maintenance_log: per-UAS maintenance log
      has_emergency_response_plan: ERP filed
      has_incident_register: ICAO Annex 13 / Mandatory Occurrence Report register
    """
    pack = {
        "operator_name": operator_name,
        "operator_id_caa": operator_id_caa,
        "documents": {
            "Operations Manual": {
                "present": has_operations_manual,
                "revision": operations_manual_revision or None,
            },
            "Pilot Competence Record": {"present": has_pilot_competence_record},
            "Risk Assessment": {
                "present": has_risk_assessment,
                "method": risk_assessment_method,
            },
            "Insurance Certificate (EC 785/2004)": {
                "present": has_insurance_certificate,
                "expiry": insurance_expiry or None,
            },
            "Maintenance Log": {"present": has_maintenance_log},
            "Emergency Response Plan": {"present": has_emergency_response_plan},
            "Incident Register (Annex 13 / MOR)": {"present": has_incident_register},
        },
    }

    missing = [k for k, v in pack["documents"].items() if not v["present"]]
    insurance_expired = False
    if insurance_expiry:
        try:
            exp = datetime.fromisoformat(insurance_expiry)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            insurance_expired = exp < datetime.now(timezone.utc)
        except ValueError:
            missing.append("Insurance expiry malformed — supply ISO date")

    findings = []
    for m in missing:
        findings.append(f"MISSING: {m}")
    if insurance_expired:
        findings.append(f"Insurance EXPIRED on {insurance_expiry} — RENEW immediately.")

    decision = "INSPECTION_READY" if not findings else "BLOCK"

    payload = {
        "tool": "prepare_caa_inspection_pack",
        "pack": pack,
        "missing_documents": missing,
        "insurance_expired": insurance_expired,
        "findings": findings,
        "decision": decision,
        "advisory": (
            "OK — pack ready to hand over to CAA inspector."
            if decision == "INSPECTION_READY" else
            "BLOCK — close gaps before any unannounced CAA inspection (CAP 722 §7)."
        ),
    }
    return _attestation(payload)


# ──────────────────────────────────────────────────────────────────────
# Server entry
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/5kQ6oJ0xS3ce8sl7ew8k91j"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}
