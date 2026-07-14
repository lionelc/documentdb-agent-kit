# Scenario: Ecommerce Healthy Indexes (False-Positive Guard)

> **Fixed scenario.** Do not edit the fixture or contract to make a failing
> test pass.

## Goal

The most important regression guard: a **healthy, well-indexed** database must
produce **zero** redundancy findings. This catches the worst kind of detector
regression — one that starts flagging *good* indexes (false positives), which
would erode user trust faster than a missed finding.

## What the fixture plants

A clean e-commerce DB designed to have no redundancy:
- no index is a prefix of another
- no exact-duplicate or unique-shadow pairs
- no asc/desc reverse-variant pairs
- every secondary index is exercised by query traffic (so none look unused)

## Contract

[`expected-findings.yaml`](expected-findings.yaml):
- `max_structural_findings: 0` — strictly no structural false positives
- `max_total_findings: 0` — a clean DB yields zero findings

## Run

```bash
pytest scenarios/ecommerce-healthy-indexes
```
