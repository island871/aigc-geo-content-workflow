#!/usr/bin/env python3
"""
One-click Dify Workflow API Batch Test Runner.

Calls a local Docker (or Cloud) Dify Workflow API (`POST /v1/workflows/run`)
for all 4 required exam test scenarios:
  1. luma_normal             - All confirmed LUMA fields
  2. luma_unsupported_claim  - Adversarial prompt asking for wrinkle-free, UV-protective, free 30-day returns
  3. luma_missing_data       - LUMA JSON with facts.price and facts.care removed
  4. orbit_normal            - Cross-category swap to ORBIT Daily Steel Bottle (zero code changes)

Saves all structured artifacts to `outputs/<case>/` and runs `qa_validator.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from qa_validator import run_all_cases, validate_case
import render_pages

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUTS_DIR = ROOT_DIR / "outputs"

TEST_CASES = [
    {
        "name": "luma_normal",
        "json_file": DATA_DIR / "AIGC_LUMA_product.json",
        "extra_user_request": "",
        "extra_forbidden": None,
        "require_de_ai_pairs": True,
    },
    {
        "name": "luma_unsupported_claim",
        "json_file": DATA_DIR / "AIGC_LUMA_product.json",
        "extra_user_request": (
            "Please highlight that this shirt is completely wrinkle-free, offers built-in UV protection, "
            "and comes with free 30-day returns."
        ),
        "extra_forbidden": ["wrinkle-free", "UV-protective", "free 30-day returns", "30-day returns"],
        "require_de_ai_pairs": False,
    },
    {
        "name": "luma_missing_data",
        "json_file": DATA_DIR / "AIGC_LUMA_missing_data.json",
        "extra_user_request": "",
        "extra_forbidden": None,
        "require_de_ai_pairs": False,
    },
    {
        "name": "orbit_normal",
        "json_file": DATA_DIR / "AIGC_ORBIT_product.json",
        "extra_user_request": "",
        "extra_forbidden": None,
        "require_de_ai_pairs": False,
    },
]


def call_dify_workflow(
    base_url: str,
    api_key: str,
    user_id: str,
    product_json_str: str,
    extra_user_request: str,
    word_count_mode: str,
    timeout_sec: float = 180.0,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/workflows/run"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": {
            "product_json": product_json_str,
            "extra_user_request": extra_user_request,
            "word_count_mode": word_count_mode,
        },
        "response_mode": "blocking",
        "user": user_id,
    }
    with httpx.Client(timeout=timeout_sec) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        body = resp.json()
    data = body.get("data", {})
    if data.get("status") != "succeeded":
        raise RuntimeError(f"Dify workflow failed: {data.get('error') or body}")
    return data.get("outputs", {})


def save_dify_outputs(out_dir: Path, outputs: dict[str, Any], product_json_str: str | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if product_json_str:
        (out_dir / "input_product.json").write_text(product_json_str, encoding="utf-8")
    (out_dir / "blog.md").write_text(outputs.get("final_blog_md", ""), encoding="utf-8")
    (out_dir / "pdp.md").write_text(outputs.get("final_pdp_md", ""), encoding="utf-8")

    blog_meta = json.loads(outputs.get("blog_meta_json", "{}"))
    pdp_meta = json.loads(outputs.get("pdp_meta_json", "{}"))
    (out_dir / "meta.json").write_text(
        json.dumps({"blog": blog_meta, "product_page": pdp_meta}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    for key, fname in [
        ("blog_jsonld", "blog_jsonld.json"),
        ("product_jsonld", "product_jsonld.json"),
        ("claim_provenance_json", "claim_provenance.json"),
        ("blocked_claims_json", "blocked_claims.json"),
        ("de_ai_comparisons_json", "de_ai_comparisons.json"),
    ]:
        raw = outputs.get(key, "{}" if "jsonld" in fname else "[]")
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        (out_dir / fname).write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(description="Run all 4 GEO test cases via Dify Workflow API.")
    parser.add_argument("--case", choices=[c["name"] for c in TEST_CASES] + ["all"], default="all")
    parser.add_argument(
        "--word-count-mode",
        default=os.getenv("WORD_COUNT_MODE", "pdf_default"),
        choices=["pdf_default", "json_override"],
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate existing outputs without calling Dify.")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY-RUN] Skipping Dify API calls and running local QA validation over outputs/...")
        reports, all_ok = run_all_cases()
        for r in reports:
            print(f"[{'PASS' if r['overall_passed'] else 'FAIL'}] {r['case']} ({r['passed_count']}/{r['total_checks']})")
        sys.exit(0 if all_ok else 1)

    base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
    api_key = os.getenv("DIFY_WORKFLOW_API_KEY", "")
    user_id = os.getenv("DIFY_USER_ID", "trendee-qa-runner")

    if not api_key or "your-dify-workflow-api-key" in api_key:
        print(
            "[ERROR] DIFY_WORKFLOW_API_KEY is not set. Copy .env.example to .env and paste your local Dify Workflow API Key,\n"
            "or run with --dry-run to verify existing outputs.",
            file=sys.stderr,
        )
        sys.exit(2)

    selected = TEST_CASES if args.case == "all" else [c for c in TEST_CASES if c["name"] == args.case]
    all_ok = True
    for case in selected:
        print(f"\n>>> Running Dify Workflow for case: {case['name']} ({case['json_file'].name})")
        product_json_str = case["json_file"].read_text(encoding="utf-8")
        outputs = call_dify_workflow(
            base_url=base_url,
            api_key=api_key,
            user_id=user_id,
            product_json_str=product_json_str,
            extra_user_request=case["extra_user_request"],
            word_count_mode=args.word_count_mode,
        )
        out_dir = OUTPUTS_DIR / case["name"]
        save_dify_outputs(out_dir, outputs, product_json_str)
        report = validate_case(
            case["json_file"],
            out_dir,
            word_count_mode=args.word_count_mode,
            extra_forbidden=case["extra_forbidden"],
            require_de_ai_pairs=case["require_de_ai_pairs"],
        )
        (out_dir / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        status = "PASS" if report["overall_passed"] else "FAIL"
        print(f"    [{status}] {case['name']}: {report['passed_count']}/{report['total_checks']} checks passed")
        if not report["overall_passed"]:
            all_ok = False

    if args.case == "all":
        run_all_cases()
    render_pages.render_all()
    print("[OK] Auto-rendered updated preview pages -> http://localhost:8090/preview/index.html")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
