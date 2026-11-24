from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_dify_dsl import build_dsl, validate_dsl_integrity
from scripts.qa_validator import count_words, flatten_product_facts, validate_case

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_dify_dsl_schema_and_selectors() -> None:
    dsl = build_dsl()
    validate_dsl_integrity(dsl)
    assert dsl["kind"] == "app"
    assert dsl["app"]["mode"] == "workflow"
    assert len(dsl["workflow"]["graph"]["nodes"]) == 13
    assert len(dsl["workflow"]["graph"]["edges"]) == 14


def test_flatten_product_facts_cross_category() -> None:
    luma = json.loads((ROOT_DIR / "data" / "AIGC_LUMA_product.json").read_text(encoding="utf-8"))
    orbit = json.loads((ROOT_DIR / "data" / "AIGC_ORBIT_product.json").read_text(encoding="utf-8"))

    luma_flat = flatten_product_facts(luma)
    orbit_flat = flatten_product_facts(orbit)

    assert luma_flat["product.facts.material"] == "100% linen"
    assert luma_flat["product.facts.price.value"] == "59"
    assert orbit_flat["product.facts.capacity"] == "600 mL"
    assert orbit_flat["product.facts.lid"] == "screw-top lid"


def test_qa_validator_catches_unsupported_claim_and_missing_price_leak(tmp_path: Path) -> None:
    prod_path = ROOT_DIR / "data" / "AIGC_LUMA_missing_data.json"
    out_dir = tmp_path / "bad_case"
    out_dir.mkdir()

    # Fabricates wrinkle-free + fake price + fake offers in JSON-LD
    blog_words = " ".join(["linen"] * 1250)
    (out_dir / "blog.md").write_text(
        f"# Bad Guide\n\n## Section 1\n\nThis shirt is wrinkle-free. {blog_words}\n\n"
        "## Section 2\n\nCheck [LUMA](/products/everyday-linen-shirt).\n\n"
        "## FAQ\n\n### Q1?\nA1.\n\n### Q2?\nA2.\n\n### Q3?\nA3.\n",
        encoding="utf-8",
    )
    pdp_words = " ".join(["shirt"] * 280)
    (out_dir / "pdp.md").write_text(
        f"# LUMA Shirt\n\n## Details\n\nCosts $59 and cold water wash. {pdp_words}\n\n"
        "## FAQ\n\n### Q1?\nA1.\n\n### Q2?\nA2.\n\n### Q3?\nA3.\n",
        encoding="utf-8",
    )
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "blog": {"title": "How to Choose a Linen Shirt for Daily Wear", "description": "A" * 130},
                "product_page": {"title": "LUMA Everyday Linen Shirt Details", "description": "B" * 130},
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "blog_jsonld.json").write_text(
        json.dumps({"@context": "https://schema.org", "@type": "BlogPosting", "headline": "H", "description": "D"}),
        encoding="utf-8",
    )
    (out_dir / "product_jsonld.json").write_text(
        json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "LUMA Everyday Linen Shirt",
                "brand": {"@type": "Brand", "name": "LUMA"},
                "offers": {"@type": "Offer", "price": 59, "priceCurrency": "USD"},
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "claim_provenance.json").write_text("[]", encoding="utf-8")

    report = validate_case(prod_path, out_dir)
    checks = {c["name"]: c for c in report["checks"]}
    assert report["overall_passed"] is False
    assert checks["3_unsupported_claim_guardrail"]["passed"] is False
    assert checks["4_missing_field_degradation"]["passed"] is False
    assert checks["6_claim_provenance_grounding"]["passed"] is False
