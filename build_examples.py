#!/usr/bin/env python3
"""Generate the deliberately oversized body of examples/bad/AGENTS.md.

Run from the project root:

    python3 build_examples.py

Why this exists: the size-budget checks (AGL005/AGL006) need a file that looks
like a real AGENTS.md that grew by accretion, and the near-duplicate check
(AGL004) must *not* fire on ordinary prose. Both need a few hundred lines of
text that is varied enough to be realistic, which is tedious and error-prone to
hand-write, so it is composed here from disjoint word pools and then checked:
the script asserts that no two generated bullets are near-duplicates under the
same threshold the linter uses (0.85 token Jaccard).

Every identifier in the output is invented. There are no credentials, no real
hostnames and no real product names.
"""

from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "examples" / "bad" / "AGENTS.md"
NEAR_DUPLICATE_SIMILARITY = 0.85

PREFIX = """# AGENTS.md

Always run `npm test` before opening a pull request.

This file has grown by accretion: every incident added a line and nothing was
ever removed. Read the whole thing, or the agent will miss something.

## Commands

- Always use spaces for indentation in this repository.
- Never use tabs in this repository.
- Run `npm test` before opening a pull request.

## Code style

- Write clean code.
- Keep the diff small.

## Frontend

- Always use two-space indentation in `.tsx` files.
- Components live in `src/components/` and are exported by name.

### Release notes

## Deployment

- Commit directly to main in this repository.
- Never commit directly to main in this repository.
- See `docs/deploy-runbook.md` for the full procedure.
- Ask your teammate before changing the CI pipeline.

#### Post-deploy checks

- Should you check the error budget after every deploy?
- Verify that `ops/grafana/errors.json` shows no new alerts.

## House rules

- Comments are required for every exported function in this repository.
- Comments are never allowed in this repository.
- Run `npm test` before opening a pull request.

## Long tail

The bullet list below is the accumulated tail of the file: eight years of
incident notes, one line at a time. Nothing in it names the same subject twice
in the same words, which is exactly why nobody has ever pruned it.
"""

# Two sentence templates with deliberately disjoint word pools, so that no two
# generated bullets can be near-duplicates of each other.
CAPABILITIES = [
    "audits", "batches", "brokers", "caches", "collates", "compacts", "derives",
    "dispatches", "enriches", "escalates", "fingerprints", "hedges", "indexes",
    "ingests", "interleaves", "jitters", "joins", "keys", "locks", "maps",
    "mirrors", "normalises", "orders", "paginates", "quantises", "queues",
    "reconciles", "redacts", "replays", "rescores", "rotates", "samples",
    "seals", "segments", "shards", "signals", "snapshots", "streams",
    "summarises", "throttles", "traces", "trims", "unwinds", "validates",
    "versions", "warms", "widens", "yields", "zips",
    "annotates",
    "archives",
    "attaches",
    "balances",
    "bins",
    "bumps",
    "clamps",
    "clusters",
    "coalesces",
    "colourises",
    "compares",
    "compiles",
    "condenses",
    "correlates",
    "counts",
    "crops",
    "debounces",
    "decodes",
    "dedupes",
    "deflates",
    "delimits",
    "deltas",
    "densifies",
    "deprecates",
    "detects",
    "drains",
    "drops",
    "elevates",
    "embeds",
    "encodes",
    "expands",
    "explains",
    "flattens",
    "flushes",
    "formats",
    "fuses",
    "gates",
    "groups",
    "hashes",
    "hoists",
    "hydrates",
    "infers",
    "inlines",
    "labels",
    "learns",
    "links",
    "loads",
    "merges",
    "mints",
    "mutes",
    "names",
    "nests",
    "parses",
    "patches",
    "pins",
    "pivots",
    "polls",
    "predicts",
    "prunes",
    "ranks",
    "rates",
    "rebalances",
    "renders",
    "reserves",
    "resolves",
    "restores",
    "retries",
    "rolls",
    "routes",
    "scales",
    "scores",
    "scrubs",
    "sorts",
    "splits",
    "stages",
    "stamps",
    "subtracts",
    "swaps",
    "tallies",
    "tests",
    "tickets",
    "tiles",
    "toggles",
    "tokenises",
    "totals",
    "tracks",
    "truncates",
    "tunes",
    "unions",
    "uploads",
    "weights",
    "wraps",
]

ASSETS = [
    "address records", "carrier quotes", "catalog snapshots", "contract prices",
    "currency rates", "delivery windows", "disposition reasons", "feature flags",
    "grant changes", "import batches", "inventory events", "invoice mappings",
    "latency spans", "ledger entries", "notification jobs", "partner certificates",
    "payment intents", "permission grants", "purchase orders", "rate cards",
    "receipt lines", "renewal dates", "return labels", "routing tables",
    "search phrases", "settlement files", "shipment plans", "signing keys",
    "support exports", "tax rules", "ticket queues", "trial metrics",
    "vendor feeds", "warehouse transfers", "webhook retries", "zone assignments",
    "access logs",
    "alert rules",
    "billing cycles",
    "bucket policies",
    "callback URLs",
    "capacity plans",
    "chargeback reports",
    "cluster sizes",
    "code owners",
    "consent records",
    "cost centres",
    "coupon codes",
    "credential rotations",
    "data contracts",
    "device tokens",
    "dispatch queues",
    "document templates",
    "edge caches",
    "email templates",
    "entitlement rules",
    "error budgets",
    "export manifests",
    "field mappings",
    "gateway routes",
    "identity providers",
    "incident timelines",
    "index templates",
    "key rotations",
    "label sets",
    "locale bundles",
    "message templates",
    "metric rollups",
    "network policies",
    "onboarding checklists",
    "order snapshots",
    "override rules",
    "partner contracts",
    "phase plans",
    "pipeline templates",
    "polling intervals",
    "price lists",
    "quota ledgers",
    "replay archives",
    "retention policies",
    "runbook steps",
    "schema revisions",
    "service accounts",
    "session records",
    "sign-off logs",
    "snapshot schedules",
    "staging fixtures",
    "status pages",
    "sync cursors",
    "tag taxonomies",
    "tenant mappings",
    "threshold alerts",
    "upgrade paths",
    "usage reports",
    "webhook secrets",
]

QUALIFIERS = [
    "for the billing group", "for the catalog group", "for the growth group",
    "for the logistics group", "for the platform group", "for the returns group",
    "for the support group", "for the treasury group", "for the vendor group",
    "for the warehouse group", "during the nightly window",
    "during the weekly close", "before the partner sync", "after the audit pass",
    "for the analytics group",
    "for the compliance group",
    "for the data group",
    "for the developer group",
    "for the finance group",
    "for the identity group",
    "for the incident group",
    "for the mobile group",
    "for the network group",
    "for the observability group",
    "for the partner group",
    "for the release group",
    "for the security group",
    "for the storage group",
    "during the monthly review",
    "during the quarterly audit",
    "before the release cut",
    "after the rollback drill",
    "on the east cluster",
    "on the west cluster",
]

# Second template pool: no word here appears in CAPABILITIES or ASSETS.
SCHEDULE_VERBS = [
    "advise", "confirm", "decide", "enquire", "gather", "inspect", "judge",
    "lecture", "mention", "notice", "observe", "ponder", "question", "recall",
    "reflect", "regard", "remark", "report", "review", "study", "survey", "weigh",
]


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def token_set(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9][a-z0-9_.+-]*", text.lower()))


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b)


BLOCK_SIZE = 24


def _free_index(start: int, used: set[int], size: int) -> int:
    index = start % size
    while index in used:
        index = (index + 1) % size
    return index


def build_bullets(count: int) -> list[str]:
    """Compose bullets so that no two can be near-duplicates of each other.

    Inside a block of BLOCK_SIZE bullets every verb index and every asset index
    is used at most once (verb advances by 1, asset by 3, so the two can never
    align twice), and each block uses one qualifier. Across blocks the asset
    offset shifts by 7, so a repeated verb is always paired with a different
    asset and a different qualifier.
    """
    bullets: list[str] = []
    block_index = 0
    schedule_index = 0

    while len(bullets) < count:
        qualifier = QUALIFIERS[block_index % len(QUALIFIERS)]
        used_verbs: set[int] = set()
        used_assets: set[int] = set()
        for _ in range(BLOCK_SIZE):
            if len(bullets) >= count:
                break
            verb_index = _free_index(block_index * 5 + len(used_verbs),
                                     used_verbs, len(CAPABILITIES))
            asset_index = _free_index(block_index * 7 + len(used_assets) * 3,
                                      used_assets, len(ASSETS))
            used_verbs.add(verb_index)
            used_assets.add(asset_index)
            bullets.append(
                f"- The pipeline {CAPABILITIES[verb_index]} "
                f"{ASSETS[asset_index]} {qualifier}."
            )
        if len(bullets) < count and block_index % 2 == 1:
            schedule = SCHEDULE_VERBS[schedule_index % len(SCHEDULE_VERBS)]
            bullets.append(
                f"- Reviewers {schedule} the draft {qualifier} before sign-off."
            )
            schedule_index += 1
        block_index += 1
    return bullets[:count]


def build_body(bullets: list[str]) -> str:
    chunks: list[str] = [""]
    for index in range(0, len(bullets), BLOCK_SIZE):
        block = bullets[index:index + BLOCK_SIZE]
        module = f"mod-{index // BLOCK_SIZE:03d}"
        chunks.append(f"### Accumulated notes {module}")
        chunks.append("")
        chunks.extend(block)
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def check_not_near_duplicates(bullets: list[str]) -> tuple[float, str, str]:
    worst = 0.0
    worst_pair = ("", "")
    tokens = [(b, token_set(b)) for b in bullets]
    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens)):
            sim = similarity(tokens[i][1], tokens[j][1])
            if sim > worst:
                worst = sim
                worst_pair = (tokens[i][0], tokens[j][0])
    return worst, worst_pair[0], worst_pair[1]


def main() -> int:
    # Grow the filler until the file genuinely exceeds both default budgets
    # (500 lines / 6000 words) without crossing the near-duplicate threshold.
    count = 120
    while True:
        bullets = build_bullets(count)
        text = PREFIX + build_body(bullets)
        lines = text.count("\n") + (0 if text.endswith("\n") else 1)
        words = word_count(text)
        if lines > 500 and words > 6000:
            break
        count += 40
        if count > 5000:
            print("ERROR: could not reach the size budget", file=sys.stderr)
            return 1

    worst, a, b = check_not_near_duplicates(bullets)
    print(f"target: {TARGET}")
    print(f"bullets={len(bullets)} lines={lines} words={words}")
    print(f"worst bullet similarity={worst:.2f}")
    if worst >= NEAR_DUPLICATE_SIMILARITY:
        print(f"ERROR: two generated bullets are near-duplicates:\n  {a}\n  {b}",
              file=sys.stderr)
        return 1
    if lines <= 500 or words <= 6000:
        print("ERROR: the generated file does not exceed both size budgets",
              file=sys.stderr)
        return 1

    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
