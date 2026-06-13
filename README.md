<!-- mcp-name: io.github.CSOAI-ORG/meok-uas-commercial-drone-mcp -->
[![MCP Scorecard: 84/100](https://img.shields.io/badge/proofof.ai-84%2F100-5b21b6)](https://proofof.ai/scorecard/meok-uas-commercial-drone-mcp.html)

# meok-uas-commercial-drone-mcp

[![PyPI](https://img.shields.io/badge/PyPI-1.0.0-blue)](https://pypi.org/project/meok-uas-commercial-drone-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/MCP-1.3.0+-green)](https://modelcontextprotocol.io)

> Commercial drone / UAS compliance toolkit. UK CAA CAP 722 + Air Navigation Order, EU 2019/947 + 2019/945, US FAA Part 107, ICAO Annex 13. Royal Mail / NHS / Wing / Amazon Prime Air / Aerialscape grade. By **MEOK AI Labs**.

## Why this exists

Commercial drone logistics is now a real industry — Royal Mail flying mail to the Isles of Scilly, NHS shifting pathology samples between hospitals by drone, Wing & Amazon Prime Air delivering parcels, Aerialscape's BVLOS routes. The UK drone market is forecast at **£1bn by 2030**.

Every commercial UAS operator is squeezed between:

- **UK CAA CAP 722** — UAS regulations (Operational Authorisation, OSC)
- **UK Air Navigation Order 2016** — as amended for UAS
- **EU Regulation 2019/947 + 2019/945** — Categories (Open / Specific / Certified) + Manufacturer reqs
- **US FAA Part 107** — sUAS commercial operations + Part 137 agricultural
- **ICAO Annex 13** — incident reporting

A single Specific category flight without a valid Operational Authorisation = **£5,000 CAA fine** per occurrence + grounding. NHS routes that fail an OSC review get pulled the day before launch.

This MCP gives the callable compliance toolkit for drone fleets.

## Install

```bash
pip install meok-uas-commercial-drone-mcp
```

## Claude Desktop config

```json
{
  "mcpServers": {
    "uas-commercial-drone": {
      "command": "meok-uas-commercial-drone-mcp"
    }
  }
}
```

## Tools (8)

| Tool | Use case |
|------|----------|
| `check_caa_operator_authorisation` | UK CAA OSC + GA vs SA pathway. |
| `check_uas_open_category` | Open A1/A2/A3 — sub-25kg, no operating auth. |
| `check_uas_specific_category` | Specific needs Operational Authorisation + SORA. |
| `check_uas_certified_category` | Certified = manned-aircraft rules (BVLOS / passenger). |
| `check_remote_pilot_competence` | A2 CofC + GVC + Operational Authorisation endorsements. |
| `check_far_part_107_us` | US FAA Part 107 sUAS commercial. |
| `check_easa_uas_reg_2019_947` | EU 2019/947 + 2019/945. |
| `prepare_caa_inspection_pack` | CAA SUA inspection — Ops Manual, pilot record, RA, insurance. |

## Pricing

- **Free** — MIT self-host
- **Starter** — £99/mo (signed attestations + email support)
- **Pro** — £299/mo (multi-pilot dashboards + OSC drafting helper)
- **Fleet** — £1,499/mo (fleet-grade, audit-export, SLA, NHS/Royal Mail tier)

[Subscribe Pro → £299/mo](https://buy.stripe.com/aFa7sNcgAdQS0ZT1Uc8k91t) · [Talk to Nick](mailto:nicholas@meok.ai)

## Regulatory basis

- **UK CAA CAP 722** — UAS regulations (latest revision)
- **UK Air Navigation Order 2016** — as amended for UAS
- **EU Regulation 2019/947** — Categories of UAS operation
- **EU Regulation 2019/945** — UAS class identification + manufacturer reqs
- **US FAA Part 107** — sUAS commercial (14 CFR Part 107)
- **US FAA Part 137** — agricultural aircraft operations
- **ICAO Annex 13** — Aircraft Accident and Incident Investigation

## Sign your responses (production)

```bash
export MEOK_HMAC_SECRET="your-secret"
meok-uas-commercial-drone-mcp
```

Every tool response returns an HMAC-SHA256 signature for audit-trail evidence.

## Companion MCPs

Part of the **MEOK Transport Compliance** stack on haulage.app:

- `meok-car-transport-uk-mcp` — DVSA + tacho + C&U (road)
- `meok-ev-recall-transport-mcp` — ADR Class 9 (road)
- `meok-iata-dgr-air-cargo-mcp` — air cargo dangerous goods
- `meok-uas-commercial-drone-mcp` — this one (drone)
- `meok-vehicle-handover-mcp` — NAMA + BVRLA + POD

## License

MIT © 2026 Nicholas Templeman / MEOK AI Labs · [haulage.app](https://haulage.app)
