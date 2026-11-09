#!/usr/bin/env python3
"""Deploy converted Sigma rules to Kibana as EQL detection rules.

Each Sigma rule becomes one Kibana rule whose rule_id is the Sigma `id`, so a
redeploy updates the same rule instead of creating a duplicate (upsert).

Inputs:
  detections/sigma/**/*.yml   rule metadata (title, level, tags, ...)
  converted/eql/<name>.eql    query produced by the sigma-convert job

Environment:
  KIBANA_URL       e.g. http://10.10.60.10:5601
  KIBANA_API_KEY   encoded API key (masked, protected CI variable)

  --dry-run        build and print the rule bodies; no network calls
"""
import argparse
import json
import os
import pathlib
import sys

import yaml

SIGMA_DIR = pathlib.Path("detections/sigma")
EQL_DIR = pathlib.Path("converted/eql")

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


def build_rule(rule_path: pathlib.Path) -> dict:
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
    bodies = [build_rule(p) for p in rules]

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
