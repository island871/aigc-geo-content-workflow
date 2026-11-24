#!/usr/bin/env python3
"""
Automated GEO Content & Fact-Grounding Quality Validator.

Implements 7 deterministic checks:
  1. word_count_compliance      - Blog (1200-1500 default or JSON override) & PDP (250-400)
  2. geo_structure_and_meta     - H1, >=3 H2, >=3 FAQs per page, internal link, Meta lengths
  3. unsupported_claim_guardrail- Detects ungrounded/forbidden claim assertions
  4. missing_field_degradation  - Ensures absent price/care are never fabricated in copy or JSON-LD
  5. jsonld_schema_validity     - Validates Schema.org BlogPosting & Product JSON-LD integrity
  6. claim_provenance_grounding - Verifies >=5 claims trace to real JSON paths & exact values
  7. de_ai_editorial_quality    - Checks absence of common AI clichés & >=2 Before/After edits
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent

AI_CLICHE_PATTERNS = [
    r"\bin today'?s fast[- ]paced world\b",
    r"\blook no further\b",
    r"\belevate your\b",
    r"\bseamlessly transitions?\b",
    r"\bgame[- ]changer\b",
    r"\btimeless elegance\b",
    r"\bcrafted to perfection\b",
    r"\bultimate companion\b",
    r"\beffortless sophistication\b",
    r"\bredefines? comfort\b",
]

NEGATION_MARKERS = (
    "not ",
    "no ",
    "without ",
    "does not",
    "do not",
    "doesn't",
    "isn't",
    "aren't",
    "never ",
    "unconfirmed",
    "not listed",
    "not provided",
    "not specified",
    "not stated",
    "not included",
    "cannot claim",
    "avoid assuming",
    "don't assume",
    "do not assume",
    "rather than claiming",
    "no guarantee",
    "question claims",
    "verify ",
    "frequently ask about",
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    summary: str
    details: dict[str, Any]


def flatten_product_facts(product_data: dict[str, Any]) -> dict[str, str]:
    """Flatten confirmed product fields into exact dotted JSON paths."""
    flat: dict[str, str] = {}

    def _walk(obj: Any, prefix: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                path = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    _walk(v, path)
                elif isinstance(v, list):
                    flat[path] = ", ".join(str(x) for x in v)
                elif v is not None and str(v).strip() != "":
                    flat[path] = str(v)

    brand = product_data.get("brand", {}) or {}
    if brand.get("name"):
        flat["brand.name"] = str(brand["name"])

    product = product_data.get("product", {}) or {}
    for key in ("id", "name", "category"):
        if product.get(key):
            flat[f"product.{key}"] = str(product[key])

    _walk(product.get("facts", {}) or {}, "product.facts")
    if product.get("target_scenarios"):
        flat["product.target_scenarios"] = ", ".join(str(s) for s in product["target_scenarios"])
    return flat


def count_words(markdown_text: str) -> int:
    clean = re.sub(r"```.*?```", " ", markdown_text, flags=re.DOTALL)
    clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)
    clean = re.sub(r"[#*_`>|]", " ", clean)
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", clean))


def count_faqs(markdown_text: str) -> int:
    faq_split = re.split(r"^##\s+.*FAQ.*$", markdown_text, flags=re.IGNORECASE | re.MULTILINE)
    if len(faq_split) < 2:
        return len(re.findall(r"^###\s+.*\?", markdown_text, flags=re.MULTILINE))
    return len(re.findall(r"^###\s+.+", faq_split[-1], flags=re.MULTILINE))


def _scan_claim_leaks(text: str, forbidden_terms: list[str]) -> list[dict[str, str]]:
    leaks: list[dict[str, str]] = []
    # Split into sentences so negation check is local to the sentence
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for term in forbidden_terms:
        norm_term = term.strip()
        if not norm_term:
            continue
        # Handle slash-separated terms like "ratings/reviews"
        subterms = [t.strip() for t in norm_term.split("/") if t.strip()]
        for sub in subterms:
            pattern = re.compile(r"\b" + re.escape(sub) + r"\b", flags=re.IGNORECASE)
            for sent in sentences:
                stripped = re.sub(r"[*_`]", "", sent).strip()
                # Interrogative FAQ headings (e.g. "### Is this shirt wrinkle-free?") ask rather than assert
                if stripped.startswith("#") and stripped.endswith("?"):
                    continue
                if pattern.search(stripped):
                    low = stripped.lower()
                    if not any(neg in low for neg in NEGATION_MARKERS):
                        leaks.append({"term": sub, "sentence": stripped[:180]})
                        break
    return leaks


def validate_case(
    product_json_path: Path,
    output_dir: Path,
    word_count_mode: str = "pdf_default",
    extra_forbidden: list[str] | None = None,
    require_de_ai_pairs: bool = False,
) -> dict[str, Any]:
    product_data = json.loads(product_json_path.read_text(encoding="utf-8"))
    confirmed_flat = flatten_product_facts(product_data)

    blog_md = (output_dir / "blog.md").read_text(encoding="utf-8")
    pdp_md = (output_dir / "pdp.md").read_text(encoding="utf-8")
    meta = json.loads((output_dir / "meta.json").read_text(encoding="utf-8"))
    blog_jsonld = json.loads((output_dir / "blog_jsonld.json").read_text(encoding="utf-8"))
    product_jsonld = json.loads((output_dir / "product_jsonld.json").read_text(encoding="utf-8"))
    provenance = json.loads((output_dir / "claim_provenance.json").read_text(encoding="utf-8"))

    de_ai_path = output_dir / "de_ai_comparisons.json"
    de_ai_comparisons = json.loads(de_ai_path.read_text(encoding="utf-8")) if de_ai_path.exists() else []

    results: list[CheckResult] = []

    # --- Check 1: Word Count ---
    content_req = product_data.get("content_requests", {}) or {}
    if word_count_mode == "json_override":
        b_min, b_max = content_req.get("blog", {}).get("target_words", [600, 800])
    else:
        b_min, b_max = [1200, 1500]
    p_min, p_max = content_req.get("product_page", {}).get("target_words", [250, 400])

    blog_wc = count_words(blog_md)
    pdp_wc = count_words(pdp_md)
    wc_pass = (b_min <= blog_wc <= b_max) and (p_min <= pdp_wc <= p_max)
    results.append(
        CheckResult(
            name="1_word_count_compliance",
            passed=wc_pass,
            summary=f"Blog={blog_wc} words (target {b_min}-{b_max}), PDP={pdp_wc} words (target {p_min}-{p_max})",
            details={
                "blog_words": blog_wc,
                "blog_target": [b_min, b_max],
                "pdp_words": pdp_wc,
                "pdp_target": [p_min, p_max],
                "word_count_mode": word_count_mode,
            },
        )
    )

    # --- Check 2: GEO Structure & Meta ---
    suggested_pdp = product_data.get("suggested_paths", {}).get("product_page", "")
    blog_h1 = len(re.findall(r"^#\s+.+", blog_md, flags=re.MULTILINE))
    blog_h2 = len(re.findall(r"^##\s+.+", blog_md, flags=re.MULTILINE))
    blog_faq = count_faqs(blog_md)
    blog_has_link = bool(suggested_pdp and suggested_pdp in blog_md)

    pdp_h1 = len(re.findall(r"^#\s+.+", pdp_md, flags=re.MULTILINE))
    pdp_h2 = len(re.findall(r"^##\s+.+", pdp_md, flags=re.MULTILINE))
    pdp_faq = count_faqs(pdp_md)

    b_meta = meta.get("blog", {})
    p_meta = meta.get("product_page", {})
    meta_ok = all(
        [
            25 <= len(b_meta.get("title", "")) <= 75,
            100 <= len(b_meta.get("description", "")) <= 175,
            20 <= len(p_meta.get("title", "")) <= 75,
            100 <= len(p_meta.get("description", "")) <= 175,
        ]
    )

    geo_pass = (
        blog_h1 == 1
        and blog_h2 >= 3
        and blog_faq >= 3
        and blog_has_link
        and pdp_h1 == 1
        and pdp_h2 >= 2
        and pdp_faq >= 3
        and meta_ok
    )
    results.append(
        CheckResult(
            name="2_geo_structure_and_meta",
            passed=geo_pass,
            summary=(
                f"Blog(H1={blog_h1}, H2={blog_h2}, FAQ={blog_faq}, PDP_Link={blog_has_link}) | "
                f"PDP(H1={pdp_h1}, H2={pdp_h2}, FAQ={pdp_faq}) | MetaOK={meta_ok}"
            ),
            details={
                "blog_h1": blog_h1,
                "blog_h2": blog_h2,
                "blog_faq": blog_faq,
                "blog_has_internal_link": blog_has_link,
                "pdp_h1": pdp_h1,
                "pdp_h2": pdp_h2,
                "pdp_faq": pdp_faq,
                "meta_lengths": {
                    "blog_title": len(b_meta.get("title", "")),
                    "blog_desc": len(b_meta.get("description", "")),
                    "pdp_title": len(p_meta.get("title", "")),
                    "pdp_desc": len(p_meta.get("description", "")),
                },
            },
        )
    )

    # --- Check 3: Unsupported Claims Guardrail ---
    forbidden = list(product_data.get("unsupported_claims", []) or [])
    if extra_forbidden:
        forbidden.extend(extra_forbidden)
    combined_copy = f"{blog_md}\n\n{pdp_md}\n\n{json.dumps(meta)}"
    leaks = _scan_claim_leaks(combined_copy, forbidden)
    results.append(
        CheckResult(
            name="3_unsupported_claim_guardrail",
            passed=len(leaks) == 0,
            summary=f"Checked {len(forbidden)} forbidden claim patterns; {len(leaks)} unguarded leaks found",
            details={"forbidden_checked": forbidden, "leaks": leaks},
        )
    )

    # --- Check 4: Missing-Field Graceful Degradation ---
    facts = product_data.get("product", {}).get("facts", {}) or {}
    price_missing = not isinstance(facts.get("price"), dict) or facts.get("price", {}).get("value") is None
    care_missing = not bool(facts.get("care"))
    missing_issues: list[str] = []

    if price_missing:
        if "offers" in product_jsonld:
            missing_issues.append("Product JSON-LD includes 'offers' despite missing facts.price")
        if re.search(r"\$\s*\d+|USD\s*\d+|\d+\s*USD", pdp_md, flags=re.IGNORECASE):
            missing_issues.append("PDP text contains currency/price numbers despite missing facts.price")
    if care_missing:
        care_verb_pattern = re.compile(
            r"\b(cold water|machine wash|hand wash|air dry|tumble dry|dry clean)\b",
            flags=re.IGNORECASE,
        )
        for sent in re.split(r"(?<=[.!?])\s+|\n+", pdp_md):
            if care_verb_pattern.search(sent) and not any(neg in sent.lower() for neg in NEGATION_MARKERS):
                missing_issues.append(f"PDP fabricates care instruction despite missing facts.care: {sent.strip()[:120]}")
                break

    results.append(
        CheckResult(
            name="4_missing_field_degradation",
            passed=len(missing_issues) == 0,
            summary=f"price_missing={price_missing}, care_missing={care_missing}, issues={len(missing_issues)}",
            details={
                "price_missing": price_missing,
                "care_missing": care_missing,
                "issues": missing_issues,
            },
        )
    )

    # --- Check 5: Schema.org JSON-LD Validity ---
    jsonld_errors: list[str] = []
    if blog_jsonld.get("@context") != "https://schema.org" or blog_jsonld.get("@type") != "BlogPosting":
        jsonld_errors.append("Invalid BlogPosting @context or @type")
    if not blog_jsonld.get("headline") or not blog_jsonld.get("description"):
        jsonld_errors.append("BlogPosting missing headline or description")
    if product_jsonld.get("@context") != "https://schema.org" or product_jsonld.get("@type") != "Product":
        jsonld_errors.append("Invalid Product @context or @type")
    if not product_jsonld.get("name") or not product_jsonld.get("brand", {}).get("name"):
        jsonld_errors.append("Product JSON-LD missing name or brand.name")
    if not price_missing:
        offers = product_jsonld.get("offers", {})
        expected_val = facts["price"]["value"]
        expected_cur = facts["price"]["currency"]
        if offers.get("price") != expected_val or offers.get("priceCurrency") != expected_cur:
            jsonld_errors.append(f"Product JSON-LD offers mismatch: got {offers}, expected {expected_val} {expected_cur}")
    if "aggregateRating" in product_jsonld or "review" in product_jsonld:
        jsonld_errors.append("Product JSON-LD illegally fabricates ratings/reviews")
    if "availability" in product_jsonld.get("offers", {}):
        jsonld_errors.append("Product JSON-LD illegally fabricates stock availability")

    results.append(
        CheckResult(
            name="5_jsonld_schema_validity",
            passed=len(jsonld_errors) == 0,
            summary=f"BlogPosting & Product JSON-LD valid={len(jsonld_errors) == 0} ({len(jsonld_errors)} errors)",
            details={"errors": jsonld_errors, "has_offers": "offers" in product_jsonld},
        )
    )

    # --- Check 6: Claim Provenance Grounding ---
    verified_claims = 0
    invalid_claims: list[dict[str, Any]] = []
    for item in provenance:
        jp = item.get("json_path", "")
        sv = str(item.get("source_value", "")).strip()
        if jp in confirmed_flat and sv.lower() in confirmed_flat[jp].lower() or (
            jp in confirmed_flat and confirmed_flat[jp].lower() in sv.lower()
        ):
            verified_claims += 1
        else:
            invalid_claims.append(
                {
                    "claim_id": item.get("claim_id"),
                    "json_path": jp,
                    "claimed_source_value": sv,
                    "actual_json_value": confirmed_flat.get(jp, "<PATH_NOT_FOUND>"),
                }
            )
    prov_pass = verified_claims >= 5 and len(invalid_claims) == 0
    results.append(
        CheckResult(
            name="6_claim_provenance_grounding",
            passed=prov_pass,
            summary=f"{verified_claims} claims verified against exact JSON paths (min 5), {len(invalid_claims)} invalid",
            details={"verified_claims": verified_claims, "invalid_claims": invalid_claims},
        )
    )

    # --- Check 7: De-AI Editorial Quality ---
    cliche_hits: list[str] = []
    for pat in AI_CLICHE_PATTERNS:
        if re.search(pat, blog_md + "\n" + pdp_md, flags=re.IGNORECASE):
            cliche_hits.append(pat)
    de_ai_count_ok = (len(de_ai_comparisons) >= 2) if require_de_ai_pairs else True
    de_ai_pass = (len(cliche_hits) == 0) and de_ai_count_ok
    results.append(
        CheckResult(
            name="7_de_ai_editorial_quality",
            passed=de_ai_pass,
            summary=f"AI clichés found={len(cliche_hits)}, Before/After comparison pairs={len(de_ai_comparisons)}",
            details={"cliche_hits": cliche_hits, "comparison_pairs": len(de_ai_comparisons)},
        )
    )

    overall_passed = all(r.passed for r in results)
    return {
        "case": output_dir.name,
        "dataset": product_data.get("dataset_id", product_json_path.name),
        "overall_passed": overall_passed,
        "passed_count": sum(1 for r in results if r.passed),
        "total_checks": len(results),
        "checks": [asdict(r) for r in results],
    }


def run_all_cases() -> tuple[list[dict[str, Any]], bool]:
    cases = [
        (
            ROOT_DIR / "data" / "AIGC_LUMA_product.json",
            ROOT_DIR / "outputs" / "luma_normal",
            "pdf_default",
            None,
            True,
        ),
        (
            ROOT_DIR / "data" / "AIGC_LUMA_product.json",
            ROOT_DIR / "outputs" / "luma_unsupported_claim",
            "pdf_default",
            ["wrinkle-free", "UV-protective", "free 30-day returns", "30-day returns"],
            False,
        ),
        (
            ROOT_DIR / "data" / "AIGC_LUMA_missing_data.json",
            ROOT_DIR / "outputs" / "luma_missing_data",
            "pdf_default",
            None,
            False,
        ),
        (
            ROOT_DIR / "data" / "AIGC_ORBIT_product.json",
            ROOT_DIR / "outputs" / "orbit_normal",
            "pdf_default",
            None,
            False,
        ),
    ]

    reports: list[dict[str, Any]] = []
    for prod_path, out_dir, wc_mode, extra_forb, req_pairs in cases:
        if not out_dir.exists():
            continue
        rep = validate_case(prod_path, out_dir, wc_mode, extra_forb, req_pairs)
        (out_dir / "qa_report.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        reports.append(rep)

    summary_json = ROOT_DIR / "outputs" / "qa_summary_report.json"
    summary_md = ROOT_DIR / "outputs" / "qa_summary_report.md"
    summary_json.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Automated QA Verification Summary",
        "",
        "| Test Case | Dataset | Result | Passed Checks | Blog Words | PDP Words |",
        "| :--- | :--- | :---: | :---: | :---: | :---: |",
    ]
    for r in reports:
        wc = r["checks"][0]["details"]
        status = "PASS" if r["overall_passed"] else "FAIL"
        md_lines.append(
            f"| `{r['case']}` | `{r['dataset']}` | **{status}** | "
            f"{r['passed_count']}/{r['total_checks']} | {wc['blog_words']} | {wc['pdp_words']} |"
        )
    md_lines.append("")
    for r in reports:
        md_lines.append(f"## Case: `{r['case']}` ({'PASS' if r['overall_passed'] else 'FAIL'})")
        for c in r["checks"]:
            icon = "PASS" if c["passed"] else "FAIL"
            md_lines.append(f"- **[{icon}] `{c['name']}`**: {c['summary']}")
        md_lines.append("")

    summary_md.write_text("\n".join(md_lines), encoding="utf-8")
    all_ok = len(reports) > 0 and all(r["overall_passed"] for r in reports)
    return reports, all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GEO Blog + PDP outputs against product JSON.")
    parser.add_argument("--all", action="store_true", help="Validate all 4 test cases under outputs/.")
    parser.add_argument("--input", type=Path, help="Path to product JSON.")
    parser.add_argument("--output-dir", type=Path, help="Directory containing generated outputs.")
    parser.add_argument("--word-count-mode", default="pdf_default", choices=["pdf_default", "json_override"])
    args = parser.parse_args()

    if args.all:
        reports, all_ok = run_all_cases()
        for r in reports:
            status = "PASS" if r["overall_passed"] else "FAIL"
            print(f"[{status}] {r['case']}: {r['passed_count']}/{r['total_checks']} checks passed")
            for c in r["checks"]:
                if not c["passed"]:
                    print(f"   -> FAILED {c['name']}: {c['summary']} | {c['details']}")
        sys.exit(0 if all_ok else 1)

    if not args.input or not args.output_dir:
        parser.error("Provide --all OR both --input and --output-dir.")

    rep = validate_case(args.input, args.output_dir, args.word_count_mode)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    sys.exit(0 if rep["overall_passed"] else 1)


if __name__ == "__main__":
    main()
