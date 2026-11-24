#!/usr/bin/env python3
"""
Build and validate the Dify Workflow DSL (`workflows/geo_content_workflow.yml`)
directly from `prompts/*.md` and embedded Python 3 sandbox nodes so prompts
and workflow DSL never drift out of sync.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"
WORKFLOW_OUT = ROOT_DIR / "workflows" / "geo_content_workflow.yml"


def load_prompt_text(filename: str) -> str:
    """Extract the ```text ... ``` fenced prompt block from a prompts/*.md file."""
    content = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
    match = re.search(r"```text\s*\n(.*?)\n```", content, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Could not find ```text fenced block in {filename}")
    return match.group(1).strip()


STAGE_1_PARSE_CODE = r'''import json


def _flatten(obj, prefix=""):
    flat = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                flat.update(_flatten(v, path))
            elif isinstance(v, list):
                flat[path] = ", ".join(str(x) for x in v)
            elif v is not None and str(v).strip() != "":
                flat[path] = str(v)
    return flat


def main(product_json: str, extra_user_request: str, word_count_mode: str) -> dict:
    raw = (product_json or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:])

    data = json.loads(raw)

    brand = data.get("brand", {}) or {}
    product = data.get("product", {}) or {}
    facts = product.get("facts", {}) or {}
    content_req = data.get("content_requests") if isinstance(data.get("content_requests"), dict) else {}
    blog_req = content_req.get("blog") if isinstance(content_req.get("blog"), dict) else {}
    pdp_req = content_req.get("product_page") if isinstance(content_req.get("product_page"), dict) else {}
    paths = data.get("suggested_paths", {}) or {}

    # Flatten ONLY confirmed facts with exact JSON paths for provenance grounding
    confirmed_flat = {}
    if brand.get("name"):
        confirmed_flat["brand.name"] = str(brand["name"])
    for key in ("id", "name", "category"):
        if product.get(key):
            confirmed_flat[f"product.{key}"] = str(product[key])
    confirmed_flat.update(_flatten(facts, "product.facts"))
    if product.get("target_scenarios"):
        confirmed_flat["product.target_scenarios"] = ", ".join(
            str(s) for s in product["target_scenarios"]
        )

    # Detect absent common commerce attributes (generic, category-agnostic)
    missing_fields = []
    price_obj = facts.get("price")
    if not isinstance(price_obj, dict) or price_obj.get("value") is None:
        missing_fields.append("product.facts.price")
    if not facts.get("care"):
        missing_fields.append("product.facts.care")
    if not facts.get("colors"):
        missing_fields.append("product.facts.colors")
    if not facts.get("material"):
        missing_fields.append("product.facts.material")

    # Resolve word count strategy: PDF default (1200-1500) vs JSON override (e.g. 600-800)
    mode = (word_count_mode or "pdf_default").strip().lower()
    json_blog_range = blog_req.get("target_words", [600, 800])
    if mode == "json_override" and isinstance(json_blog_range, list) and len(json_blog_range) == 2:
        blog_range = [int(json_blog_range[0]), int(json_blog_range[1])]
    else:
        blog_range = [1200, 1500]

    json_pdp_range = pdp_req.get("target_words", [250, 400])
    if isinstance(json_pdp_range, list) and len(json_pdp_range) == 2:
        pdp_range = [int(json_pdp_range[0]), int(json_pdp_range[1])]
    else:
        pdp_range = [250, 400]

    unsupported_claims = data.get("unsupported_claims", []) or []
    extra_req = (extra_user_request or "").strip() or "None"

    return {
        "normalized_product_json": json.dumps(data, ensure_ascii=False, indent=2),
        "confirmed_facts_flat": json.dumps(confirmed_flat, ensure_ascii=False, indent=2),
        "missing_fields_json": json.dumps(missing_fields, ensure_ascii=False),
        "unsupported_claims_json": json.dumps(unsupported_claims, ensure_ascii=False),
        "extra_user_request_clean": extra_req,
        "brand_name": str(brand.get("name", "")),
        "product_name": str(product.get("name", "")),
        "product_category": str(product.get("category", "general")),
        "blog_topic": str(blog_req.get("topic", f"How to Choose {product.get('name', 'This Product')}")),
        "blog_word_range": f"{blog_range[0]}-{blog_range[1]}",
        "pdp_word_range": f"{pdp_range[0]}-{pdp_range[1]}",
        "suggested_blog_path": str(paths.get("blog", "/blog/buying-guide")),
        "suggested_pdp_path": str(paths.get("product_page", "/products/item")),
    }
'''


STAGE_6_JSONLD_QA_CODE = r'''import json
import re


def _extract_json(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {}
    fence = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, flags=re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _word_count(md: str) -> int:
    clean = re.sub(r"```.*?```", " ", md, flags=re.DOTALL)
    clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)
    clean = re.sub(r"[#*_`>|]", " ", clean)
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", clean))


def _count_faqs(md: str) -> int:
    # Count ### questions inside or after a FAQ heading
    faq_split = re.split(r"^##\s+.*FAQ.*$", md, flags=re.IGNORECASE | re.MULTILINE)
    if len(faq_split) < 2:
        return len(re.findall(r"^###\s+.*\?", md, flags=re.MULTILINE))
    return len(re.findall(r"^###\s+.+", faq_split[-1], flags=re.MULTILINE))


def main(
    normalized_product_json: str,
    confirmed_facts_flat: str,
    missing_fields_json: str,
    unsupported_claims_json: str,
    blog_word_range: str,
    pdp_word_range: str,
    suggested_blog_path: str,
    suggested_pdp_path: str,
    fact_checker_raw: str,
    polisher_raw: str,
) -> dict:
    product_data = json.loads(normalized_product_json)
    confirmed_flat = json.loads(confirmed_facts_flat)
    missing_fields = json.loads(missing_fields_json)
    unsupported_claims = json.loads(unsupported_claims_json)

    fact_obj = _extract_json(fact_checker_raw)
    polish_obj = _extract_json(polisher_raw)

    final_blog = polish_obj.get("final_blog_md", fact_obj.get("fact_checked_blog_md", ""))
    final_pdp = polish_obj.get("final_pdp_md", fact_obj.get("fact_checked_pdp_md", ""))
    if suggested_pdp_path:
        final_blog = final_blog.replace("{{suggested_pdp_path}}", suggested_pdp_path)
    if suggested_blog_path:
        final_pdp = final_pdp.replace("{{suggested_blog_path}}", suggested_blog_path)
    blog_meta = polish_obj.get("blog_meta", {})
    pdp_meta = polish_obj.get("pdp_meta", {})
    claim_provenance = fact_obj.get("claim_provenance", [])
    blocked_claims = fact_obj.get("blocked_claims", [])
    de_ai_comparisons = polish_obj.get("de_ai_comparisons", [])

    brand = product_data.get("brand", {}) or {}
    product = product_data.get("product", {}) or {}
    facts = product.get("facts", {}) or {}
    base_url = "https://example.com"

    # 1. Deterministically assemble BlogPosting JSON-LD
    blog_jsonld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": blog_meta.get("title") or product_data.get("content_requests", {}).get("blog", {}).get("topic", ""),
        "description": blog_meta.get("description", ""),
        "inLanguage": product_data.get("content_requests", {}).get("language", "en"),
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"{base_url}{suggested_blog_path}",
        },
        "author": {
            "@type": "Organization",
            "name": brand.get("name", "Editorial Team"),
        },
        "publisher": {
            "@type": "Organization",
            "name": brand.get("name", "Editorial Team"),
        },
        "about": {
            "@type": "Thing",
            "name": product.get("category", product.get("name", "")),
        },
        "mentions": {
            "@type": "Product",
            "name": f"{brand.get('name', '')} {product.get('name', '')}".strip(),
            "url": f"{base_url}{suggested_pdp_path}",
        },
    }

    # 2. Deterministically assemble Product JSON-LD (strictly omitting missing fields!)
    product_jsonld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "sku": product.get("id", ""),
        "name": f"{brand.get('name', '')} {product.get('name', '')}".strip(),
        "category": product.get("category", ""),
        "description": pdp_meta.get("description", ""),
        "brand": {
            "@type": "Brand",
            "name": brand.get("name", ""),
        },
        "url": f"{base_url}{suggested_pdp_path}",
    }
    if facts.get("material"):
        product_jsonld["material"] = facts["material"]
    if facts.get("colors"):
        product_jsonld["color"] = facts["colors"]
    if facts.get("sizes"):
        product_jsonld["size"] = facts["sizes"]

    additional_props = []
    for k, v in facts.items():
        if k in ("material", "colors", "sizes", "price"):
            continue
        if v is not None and str(v).strip() != "":
            additional_props.append({
                "@type": "PropertyValue",
                "name": k,
                "value": ", ".join(str(x) for x in v) if isinstance(v, list) else str(v),
            })
    if additional_props:
        product_jsonld["additionalProperty"] = additional_props

    # Only include offers when price is actually confirmed (NO fabricated availability or 0 price!)
    price_obj = facts.get("price")
    if isinstance(price_obj, dict) and price_obj.get("value") is not None and price_obj.get("currency"):
        product_jsonld["offers"] = {
            "@type": "Offer",
            "price": price_obj["value"],
            "priceCurrency": price_obj["currency"],
            "url": f"{base_url}{suggested_pdp_path}",
        }

    # 3. Run 6 Deterministic Automated QA Checks
    b_min, b_max = [int(x) for x in blog_word_range.split("-")]
    p_min, p_max = [int(x) for x in pdp_word_range.split("-")]
    blog_wc = _word_count(final_blog)
    pdp_wc = _word_count(final_pdp)

    blog_has_h1 = bool(re.search(r"^#\s+.+", final_blog, flags=re.MULTILINE))
    blog_h2_count = len(re.findall(r"^##\s+.+", final_blog, flags=re.MULTILINE))
    blog_faq_count = _count_faqs(final_blog)
    blog_has_pdp_link = suggested_pdp_path in final_blog

    pdp_has_h1 = bool(re.search(r"^#\s+.+", final_pdp, flags=re.MULTILINE))
    pdp_faq_count = _count_faqs(final_pdp)

    # Unsupported claim leak check (ignores negation/disclaimer sentences & FAQ questions)
    combined_lines = (final_blog + "\n" + final_pdp).splitlines()
    negation_markers = ("not ", "no ", "without ", "does not", "do not", "doesn't", "isn't", "aren't", "never ", "unconfirmed", "not listed", "not provided", "cannot claim", "avoid assuming", "question claims", "verify ", "frequently ask about")
    leaked_claims = []
    for claim in unsupported_claims:
        pattern = re.compile(re.escape(claim), flags=re.IGNORECASE)
        for line in combined_lines:
            clean_line = re.sub(r"[*_`]", "", line).strip()
            if clean_line.startswith("#") and clean_line.endswith("?"):
                continue
            if pattern.search(clean_line):
                low = clean_line.lower()
                if not any(neg in low for neg in negation_markers):
                    leaked_claims.append({"claim": claim, "line": clean_line[:160]})
                    break

    # Missing-field check
    missing_leaks = []
    if "product.facts.price" in missing_fields:
        if "offers" in product_jsonld:
            missing_leaks.append("Product JSON-LD illegally contains 'offers' when facts.price is missing")
        if re.search(r"\$\s*\d+|USD\s*\d+|\d+\s*USD", final_pdp, flags=re.IGNORECASE):
            missing_leaks.append("PDP contains currency/price figures when facts.price is missing")

    # JSON-LD structural validity check
    jsonld_ok = (
        blog_jsonld.get("@type") == "BlogPosting"
        and bool(blog_jsonld.get("headline"))
        and product_jsonld.get("@type") == "Product"
        and bool(product_jsonld.get("name"))
        and bool(product_jsonld.get("brand", {}).get("name"))
    )

    # Claim provenance JSON-path verification
    valid_provenance = [
        c for c in claim_provenance
        if isinstance(c, dict) and c.get("json_path") in confirmed_flat
    ]
    provenance_ok = len(valid_provenance) >= 5

    checks = {
        "1_word_count": {
            "passed": (b_min <= blog_wc <= b_max) and (p_min <= pdp_wc <= p_max),
            "blog_words": blog_wc,
            "blog_target": [b_min, b_max],
            "pdp_words": pdp_wc,
            "pdp_target": [p_min, p_max],
        },
        "2_geo_structure": {
            "passed": blog_has_h1 and blog_h2_count >= 3 and blog_faq_count >= 3 and blog_has_pdp_link and pdp_has_h1 and pdp_faq_count >= 3,
            "blog_h1": blog_has_h1,
            "blog_h2_count": blog_h2_count,
            "blog_faq_count": blog_faq_count,
            "blog_has_internal_link": blog_has_pdp_link,
            "pdp_h1": pdp_has_h1,
            "pdp_faq_count": pdp_faq_count,
        },
        "3_unsupported_claims_guardrail": {
            "passed": len(leaked_claims) == 0,
            "leaked_claims": leaked_claims,
        },
        "4_missing_fields_degradation": {
            "passed": len(missing_leaks) == 0,
            "missing_fields": missing_fields,
            "missing_leaks": missing_leaks,
        },
        "5_jsonld_validity": {
            "passed": jsonld_ok,
            "blog_type": blog_jsonld.get("@type"),
            "product_type": product_jsonld.get("@type"),
            "has_offers": "offers" in product_jsonld,
        },
        "6_claim_provenance_grounding": {
            "passed": provenance_ok,
            "verified_claim_count": len(valid_provenance),
            "required_min": 5,
        },
    }
    all_passed = all(c["passed"] for c in checks.values())

    publish_payload = {
        "dataset_id": product_data.get("dataset_id") or product.get("id") or "live_run",
        "word_count_mode": "json_override" if (b_min, b_max) != (1200, 1500) else "pdf_default",
        "normalized_product_json": product_data,
        "final_blog_md": final_blog,
        "final_pdp_md": final_pdp,
        "blog_meta_json": blog_meta,
        "pdp_meta_json": pdp_meta,
        "blog_jsonld": blog_jsonld,
        "product_jsonld": product_jsonld,
        "claim_provenance_json": claim_provenance,
        "blocked_claims_json": blocked_claims,
        "de_ai_comparisons_json": de_ai_comparisons,
    }

    return {
        "final_blog_md": final_blog,
        "final_pdp_md": final_pdp,
        "blog_meta_json": json.dumps(blog_meta, ensure_ascii=False, indent=2),
        "pdp_meta_json": json.dumps(pdp_meta, ensure_ascii=False, indent=2),
        "blog_jsonld": json.dumps(blog_jsonld, ensure_ascii=False, indent=2),
        "product_jsonld": json.dumps(product_jsonld, ensure_ascii=False, indent=2),
        "claim_provenance_json": json.dumps(claim_provenance, ensure_ascii=False, indent=2),
        "blocked_claims_json": json.dumps(blocked_claims, ensure_ascii=False, indent=2),
        "de_ai_comparisons_json": json.dumps(de_ai_comparisons, ensure_ascii=False, indent=2),
        "qa_report_json": json.dumps({"overall_passed": all_passed, "checks": checks}, ensure_ascii=False, indent=2),
        "qa_passed": "PASS" if all_passed else "FAIL",
        "publish_payload_json": json.dumps(publish_payload, ensure_ascii=False),
    }
'''


def _make_llm_node(
    node_id: str,
    title: str,
    desc: str,
    x: int,
    y: int,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "custom",
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "sourcePosition": "right",
        "targetPosition": "left",
        "width": 244,
        "height": 98,
        "data": {
            "type": "llm",
            "title": title,
            "desc": desc,
            "selected": False,
            "context": {"enabled": False, "variable_selector": []},
            "model": {
                "provider": "langgenius/openai/openai",
                "name": "gpt-4o",
                "mode": "chat",
                "completion_params": {
                    "temperature": temperature,
                },
            },
            "prompt_template": [
                {"id": f"{node_id}_sys", "role": "system", "text": system_prompt},
                {"id": f"{node_id}_usr", "role": "user", "text": user_prompt},
            ],
            "variables": [],
            "vision": {"enabled": False},
        },
    }


def _make_edge(
    src: str,
    src_type: str,
    tgt: str,
    tgt_type: str,
    src_handle: str = "source",
) -> dict[str, Any]:
    return {
        "id": f"{src}-{src_handle}-{tgt}-target",
        "type": "custom",
        "source": src,
        "sourceHandle": src_handle,
        "target": tgt,
        "targetHandle": "target",
        "zIndex": 0,
        "data": {
            "isInIteration": False,
            "sourceType": src_type,
            "targetType": tgt_type,
        },
    }


def build_dsl() -> dict[str, Any]:
    # Verify both embedded Python code blocks parse cleanly before emitting YAML
    ast.parse(STAGE_1_PARSE_CODE)
    ast.parse(STAGE_6_JSONLD_QA_CODE)

    p_outline = load_prompt_text("01_outline_planner.md")
    p_blog = load_prompt_text("02_blog_draft.md")
    p_pdp = load_prompt_text("03_pdp_draft.md")
    p_fact = load_prompt_text("04_fact_checker.md")
    p_polish = load_prompt_text("05_de_ai_polisher.md")

    nodes = [
        # 0. Start Node (Dual-mode: direct .json file upload OR raw JSON text paste/API)
        {
            "id": "node_start",
            "type": "custom",
            "position": {"x": 40, "y": 260},
            "positionAbsolute": {"x": 40, "y": 260},
            "sourcePosition": "right",
            "targetPosition": "left",
            "width": 244,
            "height": 170,
            "data": {
                "type": "start",
                "title": "0. 输入产品 JSON",
                "desc": "支持直接上传 .json 文件或粘贴 JSON 文本（二选一），兼容任意品类与 API 调用",
                "selected": False,
                "variables": [
                    {
                        "label": "product_json_file (直接上传产品 .json 文件，推荐)",
                        "variable": "product_json_file",
                        "type": "file",
                        "required": False,
                        "allowed_file_types": ["custom", "document"],
                        "allowed_file_extensions": [".json", ".txt"],
                        "allowed_file_upload_methods": ["local_file", "remote_url"],
                        "options": [],
                    },
                    {
                        "label": "product_json (或直接粘贴 JSON 文本 / API 传参)",
                        "variable": "product_json",
                        "type": "paragraph",
                        "required": False,
                        "max_length": 16000,
                        "options": [],
                    },
                    {
                        "label": "extra_user_request (可选，用于诱导虚构卖点测试)",
                        "variable": "extra_user_request",
                        "type": "paragraph",
                        "required": False,
                        "max_length": 2000,
                        "options": [],
                    },
                    {
                        "label": "word_count_mode (默认按 PDF 1200-1500 词，或按 JSON 覆盖)",
                        "variable": "word_count_mode",
                        "type": "select",
                        "required": True,
                        "default": "pdf_default",
                        "options": ["pdf_default", "json_override"],
                    },
                ],
            },
        },
        # 0B. IF/ELSE Node: Check whether a .json file was uploaded
        {
            "id": "node_check_file",
            "type": "custom",
            "position": {"x": 340, "y": 260},
            "positionAbsolute": {"x": 340, "y": 260},
            "sourcePosition": "right",
            "targetPosition": "left",
            "width": 244,
            "height": 126,
            "data": {
                "type": "if-else",
                "title": "0B. 判断是否上传文件",
                "desc": "若上传了 .json 文件则自动提取文本，否则使用文本框/API 传入的 JSON",
                "selected": False,
                "cases": [
                    {
                        "case_id": "true",
                        "id": "true",
                        "logical_operator": "and",
                        "conditions": [
                            {
                                "id": "cond_has_json_file",
                                "varType": "file",
                                "variable_selector": ["node_start", "product_json_file"],
                                "comparison_operator": "exists",
                                "value": "",
                            }
                        ],
                    }
                ],
            },
        },
        # 0C. Document Extractor Node: Read uploaded .json file into string
        {
            "id": "node_doc_extractor",
            "type": "custom",
            "position": {"x": 640, "y": 150},
            "positionAbsolute": {"x": 640, "y": 150},
            "sourcePosition": "right",
            "targetPosition": "left",
            "width": 244,
            "height": 98,
            "data": {
                "type": "document-extractor",
                "title": "0C. 读取 JSON 文件内容",
                "desc": "自动读取上传的 .json 文件文本内容",
                "selected": False,
                "is_array_file": False,
                "variable_selector": ["node_start", "product_json_file"],
            },
        },
        # 0D. Variable Aggregator Node: Merge file text OR pasted text into single string
        {
            "id": "node_input_merge",
            "type": "custom",
            "position": {"x": 940, "y": 260},
            "positionAbsolute": {"x": 940, "y": 260},
            "sourcePosition": "right",
            "targetPosition": "left",
            "width": 244,
            "height": 108,
            "data": {
                "type": "variable-aggregator",
                "title": "0D. 汇聚 JSON 文本",
                "desc": "统一文件提取内容与文本框输入，输出给下游解析节点",
                "selected": False,
                "output_type": "string",
                "variables": [
                    ["node_doc_extractor", "text"],
                    ["node_start", "product_json"],
                ],
                "advanced_settings": {"group_enabled": False, "groups": []},
            },
        },
        # 1. Stage 1 Code Node: Parse & Fact Contract
        {
            "id": "node_parse_product",
            "type": "custom",
            "position": {"x": 1240, "y": 260},
            "positionAbsolute": {"x": 1240, "y": 260},
            "sourcePosition": "right",
            "targetPosition": "left",
            "width": 244,
            "height": 98,
            "data": {
                "type": "code",
                "title": "1. 产品解析与事实契约",
                "desc": "动态提取 JSON 路径事实、识别缺失字段、生成禁用主张清单与字数范围",
                "selected": False,
                "code_language": "python3",
                "code": STAGE_1_PARSE_CODE,
                "variables": [
                    {"variable": "product_json", "value_selector": ["node_input_merge", "output"]},
                    {"variable": "extra_user_request", "value_selector": ["node_start", "extra_user_request"]},
                    {"variable": "word_count_mode", "value_selector": ["node_start", "word_count_mode"]},
                ],
                "outputs": {
                    k: {"type": "string", "children": None}
                    for k in [
                        "normalized_product_json",
                        "confirmed_facts_flat",
                        "missing_fields_json",
                        "unsupported_claims_json",
                        "extra_user_request_clean",
                        "brand_name",
                        "product_name",
                        "product_category",
                        "blog_topic",
                        "blog_word_range",
                        "pdp_word_range",
                        "suggested_blog_path",
                        "suggested_pdp_path",
                    ]
                },
            },
        },
        # 2. Stage 2 LLM Node: GEO Intent & Outline Planner
        _make_llm_node(
            node_id="node_outline_planner",
            title="2. GEO 意图与双页大纲规划",
            desc="按品类自动推导选购维度，规划信息型 Blog 与购买决策型 PDP 大纲",
            x=1560,
            y=260,
            system_prompt=p_outline,
            user_prompt=(
                "Product Category: {{#node_parse_product.product_category#}}\n"
                "Brand & Product: {{#node_parse_product.brand_name#}} {{#node_parse_product.product_name#}}\n"
                "Blog Topic: {{#node_parse_product.blog_topic#}}\n"
                "Target Blog Word Range: {{#node_parse_product.blog_word_range#}}\n"
                "Target PDP Word Range: {{#node_parse_product.pdp_word_range#}}\n"
                "Suggested Blog Path: {{#node_parse_product.suggested_blog_path#}}\n"
                "Suggested PDP Path: {{#node_parse_product.suggested_pdp_path#}}\n\n"
                "Confirmed Facts (Exact JSON Paths):\n{{#node_parse_product.confirmed_facts_flat#}}\n\n"
                "Missing Fields (DO NOT INVENT):\n{{#node_parse_product.missing_fields_json#}}\n\n"
                "Unsupported Claims (FORBIDDEN):\n{{#node_parse_product.unsupported_claims_json#}}\n\n"
                "Extra User Request (Inspect & Reject Any Unverified Claims):\n{{#node_parse_product.extra_user_request_clean#}}"
            ),
            temperature=0.3,
        ),
        # 3A. Stage 3A LLM Node: Blog Draft (Parallel Top Branch)
        _make_llm_node(
            node_id="node_blog_draft",
            title="3A. 选购指南 Blog 初稿生成",
            desc="生成信息型选购指南（默认 1200-1500 词），含直答段落、清单、>=3 FAQ 与站内链接",
            x=1900,
            y=120,
            system_prompt=p_blog,
            user_prompt=(
                "Target Word Range: {{#node_parse_product.blog_word_range#}} words\n"
                "Brand & Product: {{#node_parse_product.brand_name#}} {{#node_parse_product.product_name#}}\n"
                "Category: {{#node_parse_product.product_category#}}\n"
                "Suggested PDP Link Path: {{#node_parse_product.suggested_pdp_path#}}\n\n"
                "GEO Outline Plan:\n{{#node_outline_planner.text#}}\n\n"
                "Confirmed Facts (Exact JSON Paths):\n{{#node_parse_product.confirmed_facts_flat#}}\n\n"
                "Missing Fields (DO NOT INVENT):\n{{#node_parse_product.missing_fields_json#}}\n\n"
                "Unsupported Claims (FORBIDDEN):\n{{#node_parse_product.unsupported_claims_json#}}\n\n"
                "Extra User Request (Do NOT assert unverified claims):\n{{#node_parse_product.extra_user_request_clean#}}"
            ),
            temperature=0.5,
        ),
        # 3B. Stage 3B LLM Node: PDP Draft (Parallel Bottom Branch)
        _make_llm_node(
            node_id="node_pdp_draft",
            title="3B. 产品详情页 PDP 初稿生成",
            desc="生成购买决策型详情页（250-400 词），含确认参数、适用判断与 >=3 购买 FAQ",
            x=1900,
            y=400,
            system_prompt=p_pdp,
            user_prompt=(
                "Target Word Range: {{#node_parse_product.pdp_word_range#}} words\n"
                "Brand & Product: {{#node_parse_product.brand_name#}} {{#node_parse_product.product_name#}}\n"
                "Category: {{#node_parse_product.product_category#}}\n"
                "Suggested Blog Link Path: {{#node_parse_product.suggested_blog_path#}}\n\n"
                "GEO Outline Plan:\n{{#node_outline_planner.text#}}\n\n"
                "Confirmed Facts (Exact JSON Paths):\n{{#node_parse_product.confirmed_facts_flat#}}\n\n"
                "Missing Fields (DO NOT INVENT):\n{{#node_parse_product.missing_fields_json#}}\n\n"
                "Unsupported Claims (FORBIDDEN):\n{{#node_parse_product.unsupported_claims_json#}}\n\n"
                "Extra User Request (Do NOT assert unverified claims):\n{{#node_parse_product.extra_user_request_clean#}}"
            ),
            temperature=0.4,
        ),
        # 4. Stage 4 LLM Node: Fact Verification & Claim Provenance
        _make_llm_node(
            node_id="node_fact_checker",
            title="4. 事实核查与禁用主张审计",
            desc="核验双页主张并映射 JSON 路径来源，拦截诱导虚构卖点与缺失字段臆测",
            x=2240,
            y=260,
            system_prompt=p_fact,
            user_prompt=(
                "Target Blog Word Range: {{#node_parse_product.blog_word_range#}}\n"
                "Target PDP Word Range: {{#node_parse_product.pdp_word_range#}}\n\n"
                "Confirmed Facts (Exact JSON Paths):\n{{#node_parse_product.confirmed_facts_flat#}}\n\n"
                "Missing Fields (Must NOT be fabricated):\n{{#node_parse_product.missing_fields_json#}}\n\n"
                "Unsupported Claims (Forbidden):\n{{#node_parse_product.unsupported_claims_json#}}\n\n"
                "Extra User Request:\n{{#node_parse_product.extra_user_request_clean#}}\n\n"
                "=== BLOG DRAFT ===\n{{#node_blog_draft.text#}}\n\n"
                "=== PDP DRAFT ===\n{{#node_pdp_draft.text#}}"
            ),
            temperature=0.1,
        ),
        # 5. Stage 5 LLM Node: Independent De-AI-fication Polish
        _make_llm_node(
            node_id="node_de_ai_polisher",
            title="5. 独立“去 AI 味”语言润色",
            desc="去除空泛赞美、套路开头与重复句式，输出终稿、Meta 与 >=2 组改写前后对比",
            x=2580,
            y=260,
            system_prompt=p_polish,
            user_prompt=(
                "Target Blog Word Range: {{#node_parse_product.blog_word_range#}}\n"
                "Target PDP Word Range: {{#node_parse_product.pdp_word_range#}}\n"
                "Suggested PDP Link Path: {{#node_parse_product.suggested_pdp_path#}}\n\n"
                "Confirmed Facts (Strict Boundary - DO NOT ADD NEW PRODUCT FACTS):\n{{#node_parse_product.confirmed_facts_flat#}}\n\n"
                "Missing Fields (DO NOT INVENT):\n{{#node_parse_product.missing_fields_json#}}\n\n"
                "Unsupported Claims (FORBIDDEN):\n{{#node_parse_product.unsupported_claims_json#}}\n\n"
                "Fact-Checked Content JSON:\n{{#node_fact_checker.text#}}"
            ),
            temperature=0.4,
        ),
        # 6. Stage 6 Code Node: JSON-LD Assembly & Automated QA
        {
            "id": "node_jsonld_qa",
            "type": "custom",
            "position": {"x": 2920, "y": 260},
            "positionAbsolute": {"x": 2920, "y": 260},
            "sourcePosition": "right",
            "targetPosition": "left",
            "width": 244,
            "height": 98,
            "data": {
                "type": "code",
                "title": "6. JSON-LD 组装与自动化质检",
                "desc": "程序化组装 BlogPosting/Product JSON-LD（缺失字段自动降级）并执行 6 项自动质检",
                "selected": False,
                "code_language": "python3",
                "code": STAGE_6_JSONLD_QA_CODE,
                "variables": [
                    {"variable": "normalized_product_json", "value_selector": ["node_parse_product", "normalized_product_json"]},
                    {"variable": "confirmed_facts_flat", "value_selector": ["node_parse_product", "confirmed_facts_flat"]},
                    {"variable": "missing_fields_json", "value_selector": ["node_parse_product", "missing_fields_json"]},
                    {"variable": "unsupported_claims_json", "value_selector": ["node_parse_product", "unsupported_claims_json"]},
                    {"variable": "blog_word_range", "value_selector": ["node_parse_product", "blog_word_range"]},
                    {"variable": "pdp_word_range", "value_selector": ["node_parse_product", "pdp_word_range"]},
                    {"variable": "suggested_blog_path", "value_selector": ["node_parse_product", "suggested_blog_path"]},
                    {"variable": "suggested_pdp_path", "value_selector": ["node_parse_product", "suggested_pdp_path"]},
                    {"variable": "fact_checker_raw", "value_selector": ["node_fact_checker", "text"]},
                    {"variable": "polisher_raw", "value_selector": ["node_de_ai_polisher", "text"]},
                ],
                "outputs": {
                    k: {"type": "string", "children": None}
                    for k in [
                        "final_blog_md",
                        "final_pdp_md",
                        "blog_meta_json",
                        "pdp_meta_json",
                        "blog_jsonld",
                        "product_jsonld",
                        "claim_provenance_json",
                        "blocked_claims_json",
                        "de_ai_comparisons_json",
                        "qa_report_json",
                        "qa_passed",
                        "publish_payload_json",
                    ]
                },
            },
        },
        # 6B. Auto-Publish HTTP Request Node (Fail-safe default-value if preview server is off)
        {
            "id": "node_auto_publish",
            "type": "custom",
            "position": {"x": 3240, "y": 260},
            "positionAbsolute": {"x": 3240, "y": 260},
            "sourcePosition": "right",
            "targetPosition": "left",
            "width": 244,
            "height": 110,
            "data": {
                "type": "http-request",
                "title": "6B. 自动发布到本地预览站",
                "desc": "自动推送结果到 preview_server.py 渲染网页；若未启动本地预览服务则容错跳过",
                "selected": False,
                "method": "post",
                "url": "http://host.docker.internal:8090/api/publish",
                "authorization": {"type": "no-auth", "config": None},
                "headers": "Content-Type:application/json",
                "params": "",
                "body": {
                    "type": "json",
                    "data": [
                        {
                            "id": "body_json_0",
                            "key": "",
                            "type": "text",
                            "value": "{{#node_jsonld_qa.publish_payload_json#}}",
                        }
                    ],
                },
                "timeout": {"connect": 5, "read": 15, "write": 10},
                "retry_config": {"retry_enabled": False, "max_retries": 1, "retry_interval": 1000},
                "error_strategy": "default-value",
                "default_value": [
                    {
                        "key": "body",
                        "type": "string",
                        "value": '{"published": false, "note": "Local preview_server.py not running (safe fallback)"}',
                    },
                    {"key": "status_code", "type": "number", "value": 0},
                    {"key": "headers", "type": "object", "value": "{}"},
                ],
                "variables": [],
            },
        },
        # 7. End Node
        {
            "id": "node_end",
            "type": "custom",
            "position": {"x": 3560, "y": 260},
            "positionAbsolute": {"x": 3560, "y": 260},
            "sourcePosition": "right",
            "targetPosition": "left",
            "width": 244,
            "height": 140,
            "data": {
                "type": "end",
                "title": "7. 结构化输出",
                "desc": "输出自动发布网页链接、双页 Markdown、Meta、JSON-LD、事实来源、去 AI 味对比与自动质检报告",
                "selected": False,
                "outputs": [
                    {"variable": "published_result_json", "value_selector": ["node_auto_publish", "body"]},
                    *[
                        {"variable": var, "value_selector": ["node_jsonld_qa", var]}
                        for var in [
                            "qa_passed",
                            "qa_report_json",
                            "final_blog_md",
                            "final_pdp_md",
                            "blog_meta_json",
                            "pdp_meta_json",
                            "blog_jsonld",
                            "product_jsonld",
                            "claim_provenance_json",
                            "blocked_claims_json",
                            "de_ai_comparisons_json",
                        ]
                    ],
                ],
            },
        },
    ]

    edges = [
        _make_edge("node_start", "start", "node_check_file", "if-else"),
        _make_edge("node_check_file", "if-else", "node_doc_extractor", "document-extractor", src_handle="true"),
        _make_edge("node_doc_extractor", "document-extractor", "node_input_merge", "variable-aggregator"),
        _make_edge("node_check_file", "if-else", "node_input_merge", "variable-aggregator", src_handle="false"),
        _make_edge("node_input_merge", "variable-aggregator", "node_parse_product", "code"),
        _make_edge("node_parse_product", "code", "node_outline_planner", "llm"),
        _make_edge("node_outline_planner", "llm", "node_blog_draft", "llm"),
        _make_edge("node_outline_planner", "llm", "node_pdp_draft", "llm"),
        _make_edge("node_blog_draft", "llm", "node_fact_checker", "llm"),
        _make_edge("node_pdp_draft", "llm", "node_fact_checker", "llm"),
        _make_edge("node_fact_checker", "llm", "node_de_ai_polisher", "llm"),
        _make_edge("node_de_ai_polisher", "llm", "node_jsonld_qa", "code"),
        _make_edge("node_jsonld_qa", "code", "node_auto_publish", "http-request"),
        _make_edge("node_auto_publish", "http-request", "node_end", "end"),
    ]

    dsl = {
        "app": {
            "name": "GEO Blog + Product Detail Page Workflow (Reusable)",
            "description": (
                "Cross-category GEO content production workflow: Product Parsing -> "
                "Intent/Outline -> Parallel Blog & PDP Generation -> Fact Checking -> "
                "De-AI Polishing -> JSON-LD Assembly & Automated QA."
            ),
            "icon": "📝",
            "icon_background": "#E8F4FD",
            "mode": "workflow",
            "use_icon_as_answer_icon": False,
        },
        "dependencies": [],
        "kind": "app",
        "version": "0.1.5",
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [],
            "features": {
                "file_upload": {
                    "enabled": True,
                    "number_limits": 1,
                    "allowed_file_types": ["document", "custom"],
                    "allowed_file_extensions": [".json", ".txt"],
                    "allowed_file_upload_methods": ["local_file", "remote_url"],
                },
                "opening_statement": "",
                "retriever_resource": {"enabled": False},
                "sensitive_word_avoidance": {"enabled": False},
                "speech_to_text": {"enabled": False},
                "suggested_questions": [],
                "suggested_questions_after_answer": {"enabled": False},
                "text_to_speech": {"enabled": False},
            },
            "graph": {
                "edges": edges,
                "nodes": nodes,
                "viewport": {"x": 0, "y": 0, "zoom": 0.75},
            },
        },
    }
    return dsl


class LiteralDumper(yaml.SafeDumper):
    pass


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


LiteralDumper.add_representer(str, _str_representer)


def validate_dsl_integrity(dsl: dict[str, Any]) -> None:
    nodes = dsl["workflow"]["graph"]["nodes"]
    edges = dsl["workflow"]["graph"]["edges"]
    node_map = {n["id"]: n for n in nodes}

    # Check all edges point to existing nodes
    for e in edges:
        assert e["source"] in node_map, f"Missing edge source: {e['source']}"
        assert e["target"] in node_map, f"Missing edge target: {e['target']}"

    # Check all variable selectors reference valid upstream node IDs
    for n in nodes:
        data = n["data"]
        for v in data.get("variables", []):
            if isinstance(v, list):
                assert v[0] in node_map, f"Invalid aggregator selector node {v[0]} in {n['id']}"
                continue
            sel = v.get("value_selector")
            if sel:
                assert sel[0] in node_map, f"Invalid selector node {sel[0]} in {n['id']}"
        for out in data.get("outputs", []) if isinstance(data.get("outputs"), list) else []:
            sel = out.get("value_selector")
            if sel:
                assert sel[0] in node_map, f"Invalid end selector {sel[0]}"
        for pt in data.get("prompt_template", []):
            for ref_node, _ in re.findall(r"\{\{#([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\}\}", pt.get("text", "")):
                assert ref_node in node_map, f"Invalid prompt template ref {ref_node} in {n['id']}"


def main() -> None:
    dsl = build_dsl()
    validate_dsl_integrity(dsl)
    WORKFLOW_OUT.parent.mkdir(parents=True, exist_ok=True)
    yaml_text = yaml.dump(dsl, Dumper=LiteralDumper, allow_unicode=True, sort_keys=False, width=120)
    WORKFLOW_OUT.write_text(yaml_text, encoding="utf-8")

    # Round-trip reload verification
    reloaded = yaml.safe_load(WORKFLOW_OUT.read_text(encoding="utf-8"))
    validate_dsl_integrity(reloaded)
    print(f"[OK] Built and validated Dify Workflow DSL: {WORKFLOW_OUT} ({len(dsl['workflow']['graph']['nodes'])} nodes, {len(dsl['workflow']['graph']['edges'])} edges)")


if __name__ == "__main__":
    main()
