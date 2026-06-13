---
doc_id: l2-sar-template
title: "Suspicious Activity Report (SAR) — Narrative Template"
source_layer: 2
clearance: compliance
account: null
doc_type: sar_template
source_uri: "atlas://compliance/templates/sar-narrative-template.md"
contains_pii: false
---

# Suspicious Activity Report (SAR) — Narrative Template

Use this template to draft the SAR narrative. The narrative must answer **who,
what, when, where, why, and how**. Do not disclose the existence of this SAR to
the subject.

## Header
- Filing institution: Atlas Bank
- Subject account: `{{account_number}}`
- Subject name: `{{subject_legal_name}}`
- Suspicious activity period: `{{start_date}}` to `{{end_date}}`
- Aggregate amount: `{{amount_usd}}`
- Primary typology: `{{typology}}`

## Narrative (5W + H)
> On `{{detection_date}}`, Atlas Bank detected `{{summary_of_activity}}` involving
> account `{{account_number}}` held by `{{subject_legal_name}}`. The activity
> aggregated `{{amount_usd}}` and is characterized as `{{typology}}` because
> `{{reason}}`. Funds `{{source_and_disposition}}`. The activity is inconsistent
> with the customer's expected profile (`{{expected_profile}}`).

## Required attachments
- Exception register entries supporting the filing.
- Transaction detail (dates, amounts, branches/counterparties).

## Approval
SAR filings require **BSA Officer** approval before submission to FinCEN.
