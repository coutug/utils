#!/usr/bin/env python3
"""
Usage:
  python extract_projectv2_issues_export.py \
    --org-v2-project eosnationftw:7 --org-v2-project pinax-network:12 \
    --out export.csv [--users alice,bob]
Requires: Python 3.9+, requests, a GitHub token via --token or $GITHUB_TOKEN.
"""

import argparse
import csv
import os
import sys
import logging
import requests
from datetime import datetime, timezone

API_ROOT = "https://api.github.com"
GQL_ENDPOINT = f"{API_ROOT}/graphql"
API_VERSION = "2022-11-28"
USER_AGENT = "pinax-projectv2-export/1.6"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

GQL_RESOLVE_PROJECT = """
query($org: String!, $number: Int!, $cursor: String) {
  organization(login: $org) {
    projectV2(number: $number) {
      id
      title
      items(first: 100, after: $cursor) {
        nodes {
          content {
            __typename
            ... on Issue {
              title
              createdAt
              updatedAt
              assignees(first: 50) { nodes { login } }
              url
            }
          }
          fieldValues(first: 50) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { __typename ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""

class GH:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        })

    def gql(self, query: str, variables: dict) -> dict:
        r = self.s.post(GQL_ENDPOINT, json={"query": query, "variables": variables})
        logging.debug("GraphQL %s", r.status_code)
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            logging.error("GraphQL errors: %s", data["errors"]) 
            raise RuntimeError(data["errors"]) 
        return data["data"]


def extract_status(field_nodes):
    for fv in field_nodes or []:
        if fv.get("__typename") == "ProjectV2ItemFieldSingleSelectValue":
            field = fv.get("field") or {}
            if field.get("__typename") == "ProjectV2SingleSelectField" and (field.get("name") or "").lower() == "status":
                return fv.get("name") or ""
    return ""


def iter_project_items(gh: GH, org: str, number: int):
    cursor = None
    total = 0
    while True:
        data = gh.gql(GQL_RESOLVE_PROJECT, {"org": org, "number": number, "cursor": cursor})
        proj = (data.get("organization") or {}).get("projectV2")
        if not proj:
            raise RuntimeError(f"Project v2 not found: {org}:{number}")
        title = proj.get("title") or "ProjectV2"
        nodes = proj["items"]["nodes"]
        total += len(nodes)
        logging.info("%s:%s '%s' -> %d items (cum %d)", org, number, title, len(nodes), total)
        for n in nodes:
            yield title, n
        pi = proj["items"]["pageInfo"]
        if not pi["hasNextPage"]:
            break
        cursor = pi["endCursor"]


def main():
    ap = argparse.ArgumentParser(description="Export Project v2 Issues filtered by Done and date range")
    ap.add_argument("--org-v2-project", action="append", default=[], help="ORG:NUM; repeatable")
    ap.add_argument("--users", help="comma-separated logins or path to file")
    ap.add_argument("--out", default="export.csv")
    ap.add_argument("--token", default=os.getenv("GITHUB_TOKEN"))
    args = ap.parse_args()

    if not args.token:
        logging.error("Provide --token or GITHUB_TOKEN")
        sys.exit(2)
    if not args.org_v2_project:
        logging.error("Provide at least one --org-v2-project ORG:NUM")
        sys.exit(2)

    users_filter = []
    if args.users:
        if os.path.isfile(args.users):
            with open(args.users, "r", encoding="utf-8") as f:
                users_filter = [l.strip().lower() for l in f if l.strip()]
        else:
            users_filter = [u.strip().lower() for u in args.users.split(",") if u.strip()]
    if users_filter:
        logging.info("Assignee filter: %s", users_filter)

    gh = GH(args.token)

    start_date = datetime(2024, 7, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 6, 30, 23, 59, 59, tzinfo=timezone.utc)

    written = 0
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Project_title","item_type","assignees","title","status_current","created_at","last_updated_at","url"])

        for spec in args.org_v2_project:
            org, num_s = spec.split(":", 1)
            number = int(num_s)
            for project_title, node in iter_project_items(gh, org, number):
                content = node.get("content") or {}
                if content.get("__typename") != "Issue":
                    continue
                title = content.get("title") or ""
                created_at = content.get("createdAt") or ""
                updated_at = content.get("updatedAt") or ""
                assignees = [a.get("login") for a in ((content.get("assignees") or {}).get("nodes") or []) if a.get("login")]
                assignees_lower = [a.lower() for a in assignees]
                status = extract_status((node.get("fieldValues") or {}).get("nodes", []))
                if status != "Done":
                    continue
                if users_filter and not any(u in assignees_lower for u in users_filter):
                    logging.debug("skip issue no assignee match: %s", title[:120])
                    continue
                try:
                    updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00")).astimezone(timezone.utc) if updated_at else None
                except Exception:
                    updated_dt = None
                if not updated_dt or updated_dt < start_date or updated_dt > end_date:
                    continue
                url = content.get("url") or ""
                w.writerow([project_title, "Issue", ",".join(assignees), title, status, created_at, updated_at, url])
                written += 1

    logging.info("%d rows written to %s", written, args.out)
    if written == 0:
        logging.warning("No issues matched filters. Note: Projects v2 API has no per-status change timestamps.")

if __name__ == "__main__":
    main()
