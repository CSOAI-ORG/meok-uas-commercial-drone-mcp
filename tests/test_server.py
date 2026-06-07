"""Smoke tests for meok-uas-commercial-drone-mcp."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import (
    check_caa_operator_authorisation,
    check_uas_open_category,
    check_uas_specific_category,
    check_uas_certified_category,
    check_remote_pilot_competence,
    check_far_part_107_us,
    check_easa_uas_reg_2019_947,
    prepare_caa_inspection_pack,
    CAA_AUTHORISATION_TYPES,
    OPEN_CATEGORY,
    SPECIFIC_CATEGORY,
    CERTIFIED_CATEGORY,
    UK_PILOT_COMPETENCE,
    PART_107_RULES,
    EASA_UAS_REGS,
)


def _call(tool, **kwargs):
    """FastMCP wraps tools as Tool objects — extract the callable."""
    fn = tool.fn if hasattr(tool, "fn") else tool
    return fn(**kwargs)


# ──────────────────────────────────────────────────────────────────────
# check_caa_operator_authorisation
# ──────────────────────────────────────────────────────────────────────

def test_caa_auth_clean_vlos_sub25kg():
    r = _call(check_caa_operator_authorisation,
              operator_name="Aerialscape Ltd",
              operation_type="VLOS_sub25kg",
              has_operator_id=True,
              has_flyer_id=True,
              insurance_ec_785_2004=True,
              mtom_kg=4.0,
              altitude_ft_agl=200.0)
    assert r["decision"] == "AUTHORISED"
    assert r["required_pathway"] == "Open"


def test_caa_auth_bvlos_triggers_specific_and_blocks_without_oa():
    r = _call(check_caa_operator_authorisation,
              operator_name="NHS Drone Logistics",
              operation_type="BVLOS_pathology",
              has_operator_id=True,
              has_flyer_id=True,
              insurance_ec_785_2004=True,
              mtom_kg=10.0,
              altitude_ft_agl=300.0,
              is_bvlos=True)
    assert r["required_pathway"] == "Specific"
    assert r["decision"] == "BLOCK"
    assert any("Operational Authorisation" in f for f in r["findings"])


def test_caa_auth_missing_operator_id_blocks():
    r = _call(check_caa_operator_authorisation,
              operator_name="Joe Bloggs Films",
              operation_type="VLOS_sub25kg",
              has_operator_id=False,
              has_flyer_id=True,
              insurance_ec_785_2004=True,
              mtom_kg=2.0)
    assert r["decision"] == "BLOCK"
    assert any("Operator ID" in f for f in r["findings"])


def test_caa_auth_certified_over_600kg():
    r = _call(check_caa_operator_authorisation,
              operator_name="Joby UK",
              operation_type="passenger_eVTOL",
              has_operator_id=True,
              has_flyer_id=True,
              insurance_ec_785_2004=True,
              mtom_kg=750.0)
    assert r["required_pathway"] == "Certified"


# ──────────────────────────────────────────────────────────────────────
# check_uas_open_category
# ──────────────────────────────────────────────────────────────────────

def test_open_a1_dji_mini_c0():
    r = _call(check_uas_open_category,
              mtom_kg=0.249,
              uas_class_id="C0",
              altitude_ft_agl=350.0,
              is_vlos=True,
              pilot_has_online_test=True)
    assert r["subcategory"] == "A1"
    assert r["fits_open_category"] is True


def test_open_a3_far_from_people():
    r = _call(check_uas_open_category,
              mtom_kg=20.0,
              uas_class_id="C3",
              altitude_ft_agl=300.0,
              is_vlos=True,
              distance_from_uninvolved_m=200.0,
              pilot_has_online_test=True)
    assert r["subcategory"] == "A3"


def test_open_over_25kg_kicks_to_specific():
    r = _call(check_uas_open_category,
              mtom_kg=30.0,
              altitude_ft_agl=200.0,
              is_vlos=True)
    assert r["fits_open_category"] is False
    assert "Specific" in r["reason"]


def test_open_a2_requires_a2_cofc():
    # Within A2 numbers but no A2 CofC → can't subcategorise A2
    r = _call(check_uas_open_category,
              mtom_kg=2.0,
              uas_class_id="C2",
              altitude_ft_agl=300.0,
              is_vlos=True,
              distance_from_uninvolved_m=40.0,
              pilot_has_online_test=True,
              pilot_has_a2_cofc=False)
    # Either no subcategory found, or a finding cites A2 CofC requirement
    assert (r["subcategory"] != "A2") or any("A2 CofC" in f for f in r["findings"])


# ──────────────────────────────────────────────────────────────────────
# check_uas_specific_category
# ──────────────────────────────────────────────────────────────────────

def test_specific_full_oa_clean():
    r = _call(check_uas_specific_category,
              operation_description="BVLOS NHS sample shuttle, A→B, 12km",
              mtom_kg=10.0,
              altitude_ft_agl=300.0,
              is_bvlos=True,
              has_operational_authorisation=True,
              has_risk_assessment_sora=True,
              operations_manual_in_place=True,
              pilot_has_gvc=True,
              insurance_ec_785_2004=True)
    assert r["specific_required"] is True
    assert r["decision"] == "AUTHORISED"


def test_specific_no_oa_blocks():
    r = _call(check_uas_specific_category,
              operation_description="BVLOS pathology",
              mtom_kg=10.0,
              is_bvlos=True,
              has_operational_authorisation=False,
              operations_manual_in_place=True,
              pilot_has_gvc=True,
              insurance_ec_785_2004=True)
    assert r["decision"] == "BLOCK"
    assert any("£5,000" in f or "SRG1320" in f for f in r["findings"])


def test_specific_not_triggered_low_risk():
    r = _call(check_uas_specific_category,
              operation_description="VLOS 200ft mapping flight, sub-25kg",
              mtom_kg=4.0,
              altitude_ft_agl=200.0)
    assert r["specific_required"] is False


# ──────────────────────────────────────────────────────────────────────
# check_uas_certified_category
# ──────────────────────────────────────────────────────────────────────

def test_certified_passenger_drone_clean():
    r = _call(check_uas_certified_category,
              operation_description="Passenger eVTOL urban shuttle",
              mtom_kg=2000.0,
              carries_people=True,
              has_uas_type_certificate=True,
              has_uas_operator_certificate=True,
              has_licensed_remote_pilot=True,
              has_camo_equivalent=True,
              has_annex_13_reporting=True)
    assert r["certified_required"] is True
    assert r["decision"] == "AUTHORISED"


def test_certified_missing_type_cert_blocks():
    r = _call(check_uas_certified_category,
              operation_description="Passenger eVTOL",
              mtom_kg=1500.0,
              carries_people=True,
              has_uas_type_certificate=False,
              has_uas_operator_certificate=True,
              has_licensed_remote_pilot=True,
              has_camo_equivalent=True,
              has_annex_13_reporting=True)
    assert r["decision"] == "BLOCK"
    assert any("type certificate" in f for f in r["findings"])


def test_certified_no_triggers():
    r = _call(check_uas_certified_category,
              operation_description="Sub-25kg VLOS",
              mtom_kg=10.0)
    assert r["certified_required"] is False


# ──────────────────────────────────────────────────────────────────────
# check_remote_pilot_competence
# ──────────────────────────────────────────────────────────────────────

def test_pilot_a3_only_needs_flyer_id():
    r = _call(check_remote_pilot_competence,
              pilot_id="PIL-001",
              has_flyer_id=True,
              intended_category="Open_A3")
    assert r["decision"] == "COMPETENT"


def test_pilot_specific_needs_gvc_and_oa():
    r = _call(check_remote_pilot_competence,
              pilot_id="PIL-002",
              has_flyer_id=True,
              has_gvc=False,
              has_oa_endorsement=False,
              intended_category="Specific")
    assert r["decision"] == "BLOCK"
    assert any("GVC" in f for f in r["findings"])


def test_pilot_a2_needs_a2_cofc():
    r = _call(check_remote_pilot_competence,
              pilot_id="PIL-003",
              has_flyer_id=True,
              has_a2_cofc=False,
              intended_category="Open_A2")
    assert r["decision"] == "BLOCK"
    assert any("A2 CofC" in f for f in r["findings"])


def test_pilot_certified_cant_use_gvc():
    r = _call(check_remote_pilot_competence,
              pilot_id="PIL-004",
              has_flyer_id=True,
              has_gvc=True,
              intended_category="Certified")
    assert r["decision"] == "BLOCK"
    assert any("Part-FCL" in f for f in r["findings"])


# ──────────────────────────────────────────────────────────────────────
# check_far_part_107_us
# ──────────────────────────────────────────────────────────────────────

def test_part_107_clean_commercial():
    r = _call(check_far_part_107_us,
              operator_name="Wing LLC",
              pilot_holds_remote_pilot_certificate=True,
              uas_registered_with_faa=True,
              uas_remote_id_compliant=True,
              uas_weight_lbs=10.0,
              altitude_ft_agl=300.0)
    assert r["decision"] == "AUTHORISED"


def test_part_107_missing_remote_pilot_cert_blocks():
    r = _call(check_far_part_107_us,
              operator_name="MyDroneCo",
              pilot_holds_remote_pilot_certificate=False,
              uas_registered_with_faa=True,
              uas_remote_id_compliant=True,
              uas_weight_lbs=4.0)
    assert r["decision"] == "BLOCK"
    assert any("Remote Pilot Certificate" in f for f in r["findings"])


def test_part_107_over_55lb_blocks():
    r = _call(check_far_part_107_us,
              operator_name="HeavyLift",
              pilot_holds_remote_pilot_certificate=True,
              uas_registered_with_faa=True,
              uas_remote_id_compliant=True,
              uas_weight_lbs=60.0)
    assert r["decision"] == "BLOCK"
    assert any("55" in f for f in r["findings"])


def test_part_137_agricultural_pathway():
    r = _call(check_far_part_107_us,
              operator_name="CropDuster Drones",
              is_agricultural=True)
    assert "Part 137" in r["pathway"]


# ──────────────────────────────────────────────────────────────────────
# check_easa_uas_reg_2019_947
# ──────────────────────────────────────────────────────────────────────

def test_easa_uas_clean_germany_open():
    r = _call(check_easa_uas_reg_2019_947,
              operator_name="DHL DroneCo GmbH",
              member_state="DE",
              operator_registered=True,
              uas_class_id="C2",
              uas_ce_marked=True,
              category="Open",
              pilot_competency_filed=True)
    assert r["decision"] == "AUTHORISED"


def test_easa_uas_missing_registration_blocks():
    r = _call(check_easa_uas_reg_2019_947,
              operator_name="Random Operator",
              member_state="FR",
              operator_registered=False,
              category="Open",
              pilot_competency_filed=True)
    assert r["decision"] == "BLOCK"
    assert any("Article 14" in f for f in r["findings"])


def test_easa_uas_invalid_class_blocks():
    r = _call(check_easa_uas_reg_2019_947,
              operator_name="Drone Op",
              member_state="ES",
              operator_registered=True,
              uas_class_id="C99",
              uas_ce_marked=True,
              category="Open",
              pilot_competency_filed=True)
    assert r["decision"] == "BLOCK"
    assert any("C99" in f for f in r["findings"])


# ──────────────────────────────────────────────────────────────────────
# prepare_caa_inspection_pack
# ──────────────────────────────────────────────────────────────────────

def test_inspection_pack_full_ready():
    r = _call(prepare_caa_inspection_pack,
              operator_name="Aerialscape Ltd",
              operator_id_caa="GBR-OP-12345",
              has_operations_manual=True,
              operations_manual_revision="Rev 3 (2026-02-01)",
              has_pilot_competence_record=True,
              has_risk_assessment=True,
              risk_assessment_method="SORA",
              has_insurance_certificate=True,
              insurance_expiry="2027-01-01",
              has_maintenance_log=True,
              has_emergency_response_plan=True,
              has_incident_register=True)
    assert r["decision"] == "INSPECTION_READY"
    assert r["missing_documents"] == []


def test_inspection_pack_missing_ops_manual_blocks():
    r = _call(prepare_caa_inspection_pack,
              operator_name="X",
              operator_id_caa="GBR-OP-1",
              has_operations_manual=False,
              has_pilot_competence_record=True,
              has_risk_assessment=True,
              has_insurance_certificate=True,
              insurance_expiry="2027-01-01",
              has_maintenance_log=True,
              has_emergency_response_plan=True,
              has_incident_register=True)
    assert r["decision"] == "BLOCK"
    assert "Operations Manual" in r["missing_documents"]


def test_inspection_pack_expired_insurance_blocks():
    r = _call(prepare_caa_inspection_pack,
              operator_name="X",
              operator_id_caa="GBR-OP-1",
              has_operations_manual=True,
              has_pilot_competence_record=True,
              has_risk_assessment=True,
              has_insurance_certificate=True,
              insurance_expiry="2020-01-01",
              has_maintenance_log=True,
              has_emergency_response_plan=True,
              has_incident_register=True)
    assert r["decision"] == "BLOCK"
    assert r["insurance_expired"] is True


# ──────────────────────────────────────────────────────────────────────
# Attestation + tables + HMAC
# ──────────────────────────────────────────────────────────────────────

def test_attestation_carries_ts_sig_issuer():
    r = _call(check_caa_operator_authorisation,
              operator_name="Test",
              has_operator_id=True,
              has_flyer_id=True,
              insurance_ec_785_2004=True,
              mtom_kg=2.0)
    assert "ts" in r and "sig" in r and "issuer" in r
    assert r["issuer"] == "meok-uas-commercial-drone-mcp"
    assert r["version"] == "1.0.0"


def test_hmac_signature_when_secret_set(monkeypatch):
    import server as srv
    monkeypatch.setattr(srv, "_HMAC_SECRET", "test-secret-key")
    payload = {"a": 1, "b": "two"}
    sig = srv._sign(payload)
    assert sig != "unsigned-no-key-configured"
    assert len(sig) == 64  # sha256 hex


def test_hmac_signature_unsigned_without_secret(monkeypatch):
    import server as srv
    monkeypatch.setattr(srv, "_HMAC_SECRET", "")
    sig = srv._sign({"x": 1})
    assert sig == "unsigned-no-key-configured"


def test_caa_authorisation_types_table():
    assert "GA" in CAA_AUTHORISATION_TYPES
    assert "SA" in CAA_AUTHORISATION_TYPES
    assert "OSC" in CAA_AUTHORISATION_TYPES


def test_open_category_subcats():
    assert {"A1", "A2", "A3"} <= set(OPEN_CATEGORY.keys())
    assert OPEN_CATEGORY["A3"]["max_mtom_kg"] == 25.0


def test_specific_category_table():
    assert "PDRA-01" in SPECIFIC_CATEGORY["pdra"]
    assert "Operations Manual" in SPECIFIC_CATEGORY["required_documents"]


def test_certified_category_table():
    assert any("type certificate" in r.lower() for r in CERTIFIED_CATEGORY["required"])


def test_uk_pilot_competence_table():
    assert "a2_cofc" in UK_PILOT_COMPETENCE
    assert "gvc" in UK_PILOT_COMPETENCE
    assert "oa_endorsement" in UK_PILOT_COMPETENCE


def test_part_107_rules_table():
    assert PART_107_RULES["max_altitude_ft_agl"] == 400
    assert PART_107_RULES["remote_id_required"] is True


def test_easa_uas_regs_table():
    assert "2019/947" in EASA_UAS_REGS
    assert "2019/945" in EASA_UAS_REGS
    assert "C2" in EASA_UAS_REGS["2019/945"]["classes"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
