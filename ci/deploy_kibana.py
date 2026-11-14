#!/usr/bin/env python3
"""Deploy converted Sigma rules to Kibana as EQL detection rules.

Each Sigma rule becomes one Kibana rule whose rule_id is the Sigma `id`, so a
redeploy updates the same rule instead of creating a duplicate (upsert).

Inputs:
  detections/sigma/**/*.yml   rule metadata (title, level, tags, ...)
  converted/eql/<name>.eql    query produced by the sigma-convert job
  ci/attack_map.yml           ATT&CK IDs, names and tactics for the threat field

Environment:
  KIBANA_URL       e.g. http://10.10.60.10:5601
  KIBANA_API_KEY   encoded API key (masked, protected CI variable)

  --dry-run        build and print the rule bodies; no network calls
"""
import argparse
import json
import os
import pathlib
import re
import sys

import yaml

SIGMA_DIR = pathlib.Path("detections/sigma")
EQL_DIR = pathlib.Path("converted/eql")
ATTACK_MAP = pathlib.Path("ci/attack_map.yml")
ATTACK_URL = "https://attack.mitre.org"
TECHNIQUE_TAG = re.compile(r"t\d{4}(\.\d{3})?")
GROUP_OR_SOFTWARE_TAG = re.compile(r"[gs]\d{4}")

# Sigma logsource (product, category) -> Elastic index patterns
INDEX_MAP = {
    ("windows", "process_creation"): [
        "logs-windows.sysmon_operational-*",
        "logs-system.security-*",
    ],
}
SEVERITY = {"informational": "low", "low": "low", "medium": "medium",
            "high": "high", "critical": "critical"}
RISK_SCORE = {"informational": 21, "low": 21, "medium": 47,
              "high": 73, "critical": 99}


def build_threat(tags: list, attack: dict, rule_path: pathlib.Path) -> list:
    """Turn flat Sigma ATT&CK tags into Kibana's nested threat field.

    Each technique is placed under the tactics it belongs to in ATT&CK *and*
    that the rule is tagged with. Unknown tags and techniques whose tactics
    aren't tagged on the rule fail the build instead of being skipped.
    """
    tactic_tags, technique_ids, errors = [], [], []
    for tag in tags:
        if not tag.startswith("attack."):
            continue
        value = tag[len("attack."):].lower()
        if TECHNIQUE_TAG.fullmatch(value):
            technique_ids.append(value.upper())
        elif GROUP_OR_SOFTWARE_TAG.fullmatch(value):
            continue  # threat groups and software aren't part of Kibana's threat field
        elif value in attack["tactics"]:
            tactic_tags.append(value)
        else:
            errors.append(f"unknown tactic tag '{tag}': add it to {ATTACK_MAP}")

    techniques = attack["techniques"]

    def tactics_of(tid: str) -> list:
        entry = techniques[tid]
        if "tactics" in entry:
            return entry["tactics"]
        return techniques[tid.split(".")[0]]["tactics"]  # sub-technique inherits

    tree = {}  # tactic -> {parent technique -> [sub-techniques]}
    for tid in technique_ids:
        parent = tid.split(".")[0]
        missing = [t for t in (tid, parent) if t not in techniques]
        if missing:
            errors.append(f"unknown technique {', '.join(dict.fromkeys(missing))}: add it to {ATTACK_MAP}")
            continue
        matched = [t for t in tactics_of(tid) if t in tactic_tags]
        if not matched:
            expected = ", ".join(f"attack.{t}" for t in tactics_of(tid))
            errors.append(f"{tid} belongs to {expected}, but the rule isn't tagged with it")
            continue
        for tactic in matched:
            subs = tree.setdefault(tactic, {}).setdefault(parent, [])
            if "." in tid and tid not in subs:
                subs.append(tid)

    if errors:
        sys.exit(f"ERROR: {rule_path}: ATT&CK mapping failed:\n" + "\n".join(f"  - {e}" for e in errors))

    threat = []
    for tactic in dict.fromkeys(tactic_tags):
        t = attack["tactics"][tactic]
        entry = {
            "framework": "MITRE ATT&CK",
            "tactic": {"id": t["id"], "name": t["name"], "reference": f"{ATTACK_URL}/tactics/{t['id']}/"},
            "technique": [],
        }
        for parent, subs in tree.get(tactic, {}).items():
            technique = {"id": parent, "name": techniques[parent]["name"],
                         "reference": f"{ATTACK_URL}/techniques/{parent}/"}
            if subs:
                technique["subtechnique"] = [
                    {"id": s, "name": techniques[s]["name"],
                     "reference": f"{ATTACK_URL}/techniques/{s.replace('.', '/')}/"}
                    for s in subs]
            entry["technique"].append(technique)
        threat.append(entry)
    return threat


def build_rule(rule_path: pathlib.Path, attack: dict) -> dict:
    sigma = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
    eql_path = EQL_DIR / f"{rule_path.stem}.eql"
    if not eql_path.exists():
        sys.exit(f"ERROR: {eql_path} missing; did sigma-convert run?")
    logsource = sigma.get("logsource", {})
    key = (logsource.get("product"), logsource.get("category"))
    if key not in INDEX_MAP:
        sys.exit(f"ERROR: {rule_path}: no index mapping for logsource {key}; add it to INDEX_MAP")
    level = sigma.get("level", "medium")
    commit = os.environ.get("CI_COMMIT_SHORT_SHA", "local")
    return {
        "rule_id": sigma["id"],
        "name": sigma["title"],
        "description": " ".join(sigma.get("description", "").split()),
        "type": "eql",
        "language": "eql",
        "query": eql_path.read_text(encoding="utf-8").strip(),
        "index": INDEX_MAP[key],
        "severity": SEVERITY[level],
        "risk_score": RISK_SCORE[level],
        "interval": "5m",
        "from": "now-6m",
        "enabled": True,
        "author": [a.strip() for a in sigma.get("author", "").split(",") if a.strip()],
        "license": sigma.get("license", ""),
        "references": sigma.get("references", []),
        "false_positives": sigma.get("falsepositives", []),
        "tags": ["Sigma", "Detection as code"] + sigma.get("tags", []),
        "threat": build_threat(sigma.get("tags", []), attack, rule_path),
        "note": (f"Source: `{rule_path.as_posix()}` at commit `{commit}`.\n\n"
                 "Managed by CI: change this rule in Git, not in Kibana. "
                 "Edits made here are overwritten on the next deploy."),
    }


def upsert(session, base_url: str, body: dict) -> None:
    api = f"{base_url}/api/detection_engine/rules"
    rule_id = body["rule_id"]
    found = session.get(api, params={"rule_id": rule_id}, timeout=30)
    if found.status_code == 200:
        resp, action = session.put(api, json=body, timeout=30), "updated"
    elif found.status_code == 404:
        resp, action = session.post(api, json=body, timeout=30), "created"
    else:
        sys.exit(f"ERROR: lookup of {rule_id} failed: HTTP {found.status_code} {found.text}")
    if not resp.ok:
        sys.exit(f"ERROR: {action[:-1]} of {rule_id} failed: HTTP {resp.status_code} {resp.text}")
    out = resp.json()
    print(f"{action}: {out['name']} | rule_id={rule_id} | revision={out.get('revision')} | enabled={out.get('enabled')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rules = sorted(SIGMA_DIR.rglob("*.yml"))
    if not rules:
        sys.exit("ERROR: no Sigma rules found")
    attack = yaml.safe_load(ATTACK_MAP.read_text(encoding="utf-8"))
    bodies = [build_rule(p, attack) for p in rules]

    if args.dry_run:
        for body in bodies:
            print(json.dumps(body, indent=2, ensure_ascii=False))
        print(f"dry run: {len(bodies)} rule(s) would be deployed")
        return

    import requests  # only needed for a real deploy
    url = os.environ["KIBANA_URL"].rstrip("/")
    key = os.environ.get("KIBANA_API_KEY")
    if not key:
        sys.exit("ERROR: KIBANA_API_KEY is not set (it is a protected variable: deploy runs on main only)")
    session = requests.Session()
    session.headers.update({
        "Authorization": f"ApiKey {key}",
        "kbn-xsrf": "true",
        "elastic-api-version": "2023-10-31",
    })
    for body in bodies:
        upsert(session, url, body)
    print(f"deployed {len(bodies)} rule(s) to {url}")


if __name__ == "__main__":
    main()
