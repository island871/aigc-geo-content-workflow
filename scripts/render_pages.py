#!/usr/bin/env python3
"""
Category-Agnostic Static HTML Page Renderer for GEO Blog + PDP Deliverables.

Automatically discovers EVERY output folder under `outputs/` (including any new
cross-category product JSON run!) or renders a specific folder via CLI flags:
  - `preview/index.html`        (Dynamic Showcase Hub + Task 2 V1->V2 Gallery)
  - `preview/<case>/blog.html`  (BlogPosting JSON-LD in <head>, Meta tags, clickable link to PDP)
  - `preview/<case>/pdp.html`   (Product JSON-LD in <head>, Meta tags, dynamic spec chips, link to Blog)

Zero external dependencies beyond Python standard library.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUTS_DIR = ROOT_DIR / "outputs"
PREVIEW_DIR = ROOT_DIR / "preview"

# Optional visual asset bindings for SKUs that have generated Task 2 imagery
KNOWN_CASE_VISUALS: dict[str, dict[str, Any]] = {
    "luma_normal": {
        "label": "LUMA Everyday Linen Shirt — Normal",
        "badge": "Primary Deliverable · Normal",
        "data_file": DATA_DIR / "AIGC_LUMA_product.json",
        "blog_hero": "../../images/final/blog_banner_white_linen_16x9_labeled.jpg",
        "blog_caption": (
            "AI visual illustration: A gender-neutral relaxed-fit 100% linen long-sleeve shirt in White "
            "worn during a sunlit morning commute, showing natural flax drape and breathable everyday styling."
        ),
        "blog_alt": (
            "AI visual illustration of a person walking through a sunlit modern transit station wearing a "
            "relaxed-fit white 100% linen long-sleeve shirt, grey relaxed trousers, and a canvas tote bag"
        ),
        "pdp_hero": "../../images/final/pdp_light_blue_1x1_labeled.jpg",
        "pdp_caption": (
            "AI visual illustration: Studio product detail view of the LUMA Everyday Linen Shirt in Light Blue, "
            "highlighting its 100% linen slub texture, dropped-shoulder relaxed fit, and full-length sleeves."
        ),
        "pdp_alt": (
            "AI visual illustration showing a front studio view of a pale light blue 100% linen long-sleeve shirt "
            "in a relaxed gender-neutral fit hanging on a pale wooden hanger against an off-white background"
        ),
    },
    "luma_unsupported_claim": {
        "label": "LUMA Linen Shirt — Unsupported Claim Guardrail",
        "badge": "Adversarial Test · 3 Claims Blocked",
        "data_file": DATA_DIR / "AIGC_LUMA_product.json",
        "blog_hero": "../../images/final/blog_banner_white_linen_16x9_labeled.jpg",
        "blog_caption": "AI visual illustration: LUMA Everyday Linen Shirt in White (adversarial claim guardrail test).",
        "blog_alt": "AI visual illustration of white relaxed-fit 100% linen shirt in commute setting",
        "pdp_hero": "../../images/final/pdp_light_blue_1x1_labeled.jpg",
        "pdp_caption": "AI visual illustration: LUMA Everyday Linen Shirt in Light Blue (adversarial claim guardrail test).",
        "pdp_alt": "AI visual illustration of pale light blue relaxed-fit 100% linen shirt on pale wood hanger",
    },
    "luma_missing_data": {
        "label": "LUMA Linen Shirt — Missing Price & Care",
        "badge": "Missing-Data Test · No Fabricated Offers",
        "data_file": DATA_DIR / "AIGC_LUMA_missing_data.json",
        "blog_hero": "../../images/final/blog_banner_white_linen_16x9_labeled.jpg",
        "blog_caption": "AI visual illustration: LUMA Everyday Linen Shirt in White (missing price/care graceful degradation test).",
        "blog_alt": "AI visual illustration of white relaxed-fit 100% linen shirt in commute setting",
        "pdp_hero": "../../images/final/pdp_light_blue_1x1_labeled.jpg",
        "pdp_caption": "AI visual illustration: LUMA Everyday Linen Shirt in Light Blue (price & care omitted from JSON).",
        "pdp_alt": "AI visual illustration of pale light blue relaxed-fit 100% linen shirt on pale wood hanger",
    },
    "orbit_normal": {
        "label": "ORBIT Daily Steel Bottle — Cross-Category Reuse",
        "badge": "Cross-Category Verification · Drinkware",
        "data_file": DATA_DIR / "AIGC_ORBIT_product.json",
        "blog_hero": None,
        "blog_caption": "",
        "blog_alt": "",
        "pdp_hero": None,
        "pdp_caption": "",
        "pdp_alt": "",
    },
}

SWATCH_HEX = {
    "white": "#F7F7F4",
    "ivory": "#F5F2E9",
    "cream": "#EFEAD8",
    "beige": "#D8CCB8",
    "sand": "#D2C2A8",
    "oatmeal": "#DCD4C4",
    "black": "#1E2124",
    "charcoal": "#3B4046",
    "gray": "#8D949C",
    "grey": "#8D949C",
    "silver": "#C9CDD1",
    "navy": "#22344D",
    "blue": "#3B6EA5",
    "light blue": "#B7D3E8",
    "sky blue": "#A8CBE8",
    "forest green": "#2E4E3B",
    "olive": "#5F6B46",
    "sage": "#8CA08B",
    "green": "#3E6B4E",
    "brown": "#6D4C3D",
    "tan": "#C19A6B",
    "terracotta": "#B86049",
    "red": "#A93B3B",
    "burgundy": "#6D2835",
    "yellow": "#E0B94B",
    "orange": "#D97938",
    "pink": "#E3B6C1",
    "purple": "#6B5B8E",
    "copper": "#B8734B",
    "gold": "#C9A55A",
}


def resolve_swatch_color(color_name: str) -> str:
    low = color_name.strip().lower()
    if low in SWATCH_HEX:
        return SWATCH_HEX[low]
    for k, v in SWATCH_HEX.items():
        if k in low:
            return v
    return "#D6D3CC"


def discover_product_json(out_dir: Path, explicit_input: Path | None = None) -> dict[str, Any]:
    """Load product JSON from explicit flag, saved input_product.json, known map, or product_jsonld fallback."""
    if explicit_input and explicit_input.exists():
        return json.loads(explicit_input.read_text(encoding="utf-8"))
    saved_input = out_dir / "input_product.json"
    if saved_input.exists():
        return json.loads(saved_input.read_text(encoding="utf-8"))
    known = KNOWN_CASE_VISUALS.get(out_dir.name, {})
    if known.get("data_file") and Path(known["data_file"]).exists():
        return json.loads(Path(known["data_file"]).read_text(encoding="utf-8"))

    # Synthesize minimal product metadata dynamically from product_jsonld.json for arbitrary new categories
    p_ld = json.loads((out_dir / "product_jsonld.json").read_text(encoding="utf-8"))
    b_ld = json.loads((out_dir / "blog_jsonld.json").read_text(encoding="utf-8"))
    brand_name = p_ld.get("brand", {}).get("name", "Brand")
    full_name = p_ld.get("name", out_dir.name)
    prod_name = full_name[len(brand_name) :].strip() if full_name.startswith(brand_name) else full_name
    facts: dict[str, Any] = {}
    if p_ld.get("material"):
        facts["material"] = p_ld["material"]
    if p_ld.get("color"):
        facts["colors"] = p_ld["color"] if isinstance(p_ld["color"], list) else [p_ld["color"]]
    if p_ld.get("size"):
        facts["sizes"] = p_ld["size"] if isinstance(p_ld["size"], list) else [p_ld["size"]]
    for prop in p_ld.get("additionalProperty", []):
        if prop.get("name") and prop.get("value"):
            facts[prop["name"]] = prop["value"]
    if isinstance(p_ld.get("offers"), dict) and p_ld["offers"].get("price") is not None:
        facts["price"] = {
            "value": p_ld["offers"]["price"],
            "currency": p_ld["offers"].get("priceCurrency", "USD"),
        }

    pdp_url = p_ld.get("url", "/products/item")
    blog_url = b_ld.get("mainEntityOfPage", {}).get("@id", "/blog/buying-guide")
    pdp_path = re.sub(r"^https?://[^/]+", "", pdp_url)
    blog_path = re.sub(r"^https?://[^/]+", "", blog_url)
    return {
        "brand": {"name": brand_name},
        "product": {
            "id": p_ld.get("sku", out_dir.name.upper()),
            "name": prod_name or full_name,
            "category": p_ld.get("category", "general"),
            "facts": facts,
        },
        "suggested_paths": {"blog": blog_path, "product_page": pdp_path},
    }


def inline_md(text: str, link_rewrites: dict[str, str]) -> str:
    escaped = html.escape(text)

    def _replace_link(m: re.Match[str]) -> str:
        label, href = m.group(1), m.group(2)
        target = link_rewrites.get(href, href)
        return f'<a class="inline-link" href="{html.escape(target)}">{label}</a>'

    escaped = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", _replace_link, escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def markdown_to_html(md_text: str, link_rewrites: dict[str, str], skip_first_h1: bool = False) -> str:
    lines = md_text.splitlines()
    out: list[str] = []
    i = 0
    skipped_h1 = False

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        m_h = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m_h:
            level = len(m_h.group(1))
            content = inline_md(m_h.group(2).strip(), link_rewrites)
            if level == 1 and skip_first_h1 and not skipped_h1:
                skipped_h1 = True
                i += 1
                continue
            out.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            headers = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th_html = "".join(f"<th>{inline_md(h, link_rewrites)}</th>" for h in headers)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{inline_md(c, link_rewrites)}</td>" for c in row) + "</tr>"
                for row in rows
            )
            out.append(f'<div class="table-wrap"><table><thead><tr>{th_html}</tr></thead><tbody>{body_html}</tbody></table></div>')
            continue

        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(inline_md(re.sub(r"^[-*]\s+", "", lines[i].strip()), link_rewrites))
                i += 1
            out.append("<ul>" + "".join(f"<li>{it}</li>" for it in items) + "</ul>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(inline_md(re.sub(r"^\d+\.\s+", "", lines[i].strip()), link_rewrites))
                i += 1
            out.append("<ol>" + "".join(f"<li>{it}</li>" for it in items) + "</ol>")
            continue

        para_lines = [stripped]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].strip().startswith("#")
            and not lines[i].strip().startswith("|")
            and not re.match(r"^[-*]\s+", lines[i].strip())
            and not re.match(r"^\d+\.\s+", lines[i].strip())
        ):
            para_lines.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline_md(' '.join(para_lines), link_rewrites)}</p>")

    return "\n".join(out)


BASE_CSS = """
:root {
  --bg: #faf9f6;
  --surface: #ffffff;
  --surface-soft: #f3f1ec;
  --ink: #181b1e;
  --muted: #5a6168;
  --border: #e5e2db;
  --accent: #1f5c43;
  --accent-soft: #e9f3ee;
  --warn-bg: #fdf3e7;
  --warn-ink: #8a4b08;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--bg);
  color: var(--ink);
  line-height: 1.72;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(250, 249, 246, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
}
.topbar-inner {
  max-width: 1120px;
  margin: 0 auto;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.brand-mark { font-weight: 700; letter-spacing: 0.08em; font-size: 15px; color: var(--ink); }
.nav-links { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.nav-pill {
  padding: 6px 13px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  color: var(--muted);
  border: 1px solid transparent;
}
.nav-pill:hover { background: var(--surface-soft); text-decoration: none; color: var(--ink); }
.nav-pill.active { background: var(--ink); color: #fff; }
.qa-pill {
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: var(--accent-soft);
  color: var(--accent);
}
.container { max-width: 820px; margin: 0 auto; padding: 36px 24px 80px; }
.container-wide { max-width: 1120px; margin: 0 auto; padding: 36px 24px 80px; }
.eyebrow {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 4px 10px;
  border-radius: 6px;
  margin-bottom: 14px;
}
h1 { font-size: clamp(28px, 4vw, 38px); line-height: 1.22; letter-spacing: -0.02em; margin: 0 0 18px; }
h2 { font-size: 22px; line-height: 1.32; margin: 38px 0 12px; padding-top: 10px; border-top: 1px solid var(--border); }
h3 { font-size: 17px; line-height: 1.4; margin: 22px 0 8px; color: var(--ink); }
p { margin: 0 0 15px; color: #262b30; }
ul, ol { margin: 0 0 18px; padding-left: 22px; }
li { margin-bottom: 8px; color: #262b30; }
code {
  background: var(--surface-soft);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.88em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.hero-figure {
  margin: 22px 0 32px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 6px 24px rgba(24, 27, 30, 0.05);
}
.hero-figure img { display: block; width: 100%; height: auto; }
.hero-figure figcaption {
  padding: 12px 16px;
  font-size: 13px;
  color: var(--muted);
  border-top: 1px solid var(--border);
  background: var(--surface);
}
.table-wrap { overflow-x: auto; margin: 20px 0 24px; }
table { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; font-size: 14px; }
th, td { text-align: left; padding: 11px 14px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { background: var(--surface-soft); font-weight: 600; color: var(--ink); }
tr:last-child td { border-bottom: none; }
.inline-link { font-weight: 600; border-bottom: 1px solid rgba(31, 92, 67, 0.35); }
.pdp-grid {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(300px, 1.05fr);
  gap: 36px;
  align-items: start;
  margin-bottom: 36px;
}
@media (max-width: 820px) { .pdp-grid { grid-template-columns: 1fr; } }
.pdp-summary-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 28px; }
.price-tag { font-size: 26px; font-weight: 700; margin: 8px 0 16px; color: var(--ink); }
.price-missing {
  display: inline-block;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--warn-bg);
  color: var(--warn-ink);
  font-size: 13px;
  font-weight: 500;
  margin: 8px 0 16px;
}
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 18px; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
}
.swatch { width: 13px; height: 13px; border-radius: 50%; border: 1px solid rgba(0,0,0,0.18); display: inline-block; }
.cta-row { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 20px; }
.btn-primary {
  display: inline-block;
  padding: 11px 18px;
  border-radius: 10px;
  background: var(--ink);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}
.btn-secondary {
  display: inline-block;
  padding: 11px 18px;
  border-radius: 10px;
  background: var(--surface-soft);
  color: var(--ink);
  border: 1px solid var(--border);
  font-size: 14px;
  font-weight: 600;
}
.btn-primary:hover, .btn-secondary:hover { text-decoration: none; opacity: 0.92; }
.dynamic-placeholder {
  aspect-ratio: 1 / 1;
  background: linear-gradient(145deg, #274435 0%, #3b5e4c 52%, #dce2de 100%);
  border-radius: 14px;
  padding: 28px;
  color: #fff;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.inspector {
  margin-top: 48px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 24px;
}
.inspector details { border-top: 1px solid var(--border); padding: 12px 0; }
.inspector details:first-of-type { border-top: none; }
.inspector summary { cursor: pointer; font-weight: 600; font-size: 14px; color: var(--ink); }
pre {
  background: #14181d;
  color: #e6edf3;
  padding: 14px 16px;
  border-radius: 10px;
  overflow-x: auto;
  font-size: 12.5px;
  line-height: 1.55;
}
.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 12px 0; }
@media (max-width: 720px) { .compare-grid { grid-template-columns: 1fr; } }
.before-box { background: #fdf2f2; border: 1px solid #f4cccc; border-radius: 10px; padding: 14px; font-size: 13.5px; }
.after-box { background: #eef7f1; border: 1px solid #c3e2cf; border-radius: 10px; padding: 14px; font-size: 13.5px; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 24px; }
.hub-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 14px;
}
"""


def build_inspector_html(
    page_kind: str,
    meta_entry: dict[str, str],
    jsonld_obj: dict[str, Any],
    provenance: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
    de_ai: list[dict[str, Any]],
    qa_report: dict[str, Any],
) -> str:
    qa_rows = "".join(
        f'<tr><td><code>{html.escape(c["name"])}</code></td>'
        f'<td><strong>{"PASS" if c["passed"] else "FAIL"}</strong></td>'
        f'<td>{html.escape(c["summary"])}</td></tr>'
        for c in qa_report.get("checks", [])
    )
    prov_rows = "".join(
        f'<tr><td><code>{html.escape(str(p.get("claim_id","")))}</code></td>'
        f'<td>{html.escape(str(p.get("claim_text","")))}</td>'
        f'<td><code>{html.escape(str(p.get("json_path","")))}</code></td>'
        f'<td>{html.escape(str(p.get("source_value","")))}</td></tr>'
        for p in provenance
    )
    de_ai_html = ""
    if de_ai:
        blocks = []
        for item in de_ai:
            blocks.append(
                f'<div><strong>{html.escape(item.get("id",""))} — {html.escape(item.get("section",""))}</strong>'
                f'<div class="compare-grid">'
                f'<div class="before-box"><strong>Before (AI Tone):</strong><br>{html.escape(item.get("before_en",""))}</div>'
                f'<div class="after-box"><strong>After (Polished):</strong><br>{html.escape(item.get("after_en",""))}</div>'
                f'</div><p style="font-size:13px;color:var(--muted);"><strong>修改依据：</strong>{html.escape(item.get("rationale_zh",""))}</p></div>'
            )
        de_ai_html = f'<details><summary>De-AI Editorial Comparisons ({len(de_ai)} Before/After Pairs)</summary>{"".join(blocks)}</details>'

    blocked_html = ""
    if blocked:
        b_rows = "".join(
            f'<tr><td><strong>{html.escape(b.get("claim",""))}</strong></td>'
            f'<td><code>{html.escape(b.get("source",""))}</code></td>'
            f'<td>{html.escape(b.get("action_taken",""))}</td></tr>'
            for b in blocked
        )
        blocked_html = (
            f'<details open><summary>Blocked Unsupported Claims ({len(blocked)} Intercepted)</summary>'
            f'<div class="table-wrap"><table><thead><tr><th>Claim</th><th>Source</th><th>Action Taken</th></tr></thead>'
            f'<tbody>{b_rows}</tbody></table></div></details>'
        )

    title_str = meta_entry.get("title", "")
    desc_str = meta_entry.get("description", "")
    return f"""
<section class="inspector" id="geo-inspector">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px;">
    <strong style="font-size:15px;">GEO / JSON-LD & Automated QA Inspector</strong>
    <span class="qa-pill">QA {qa_report.get("passed_count", 0)}/{qa_report.get("total_checks", 0)} {"PASS" if qa_report.get("overall_passed") else "FAIL"}</span>
  </div>
  <details>
    <summary>Meta Tags & Embedded Schema.org {html.escape(page_kind)} JSON-LD (Also injected in &lt;head&gt;)</summary>
    <p style="margin-top:10px;font-size:13.5px;"><strong>Meta Title ({len(title_str)} chars):</strong> {html.escape(title_str)}<br>
    <strong>Meta Description ({len(desc_str)} chars):</strong> {html.escape(desc_str)}</p>
    <pre>{html.escape(json.dumps(jsonld_obj, ensure_ascii=False, indent=2))}</pre>
  </details>
  <details>
    <summary>Automated QA Verification Report ({qa_report.get("passed_count", 0)}/{qa_report.get("total_checks", 0)} Checks Passed)</summary>
    <div class="table-wrap"><table><thead><tr><th>Check</th><th>Status</th><th>Summary</th></tr></thead><tbody>{qa_rows}</tbody></table></div>
  </details>
  <details>
    <summary>Fact-Grounding Claim Provenance ({len(provenance)} Verified Claims → JSON Paths)</summary>
    <div class="table-wrap"><table><thead><tr><th>ID</th><th>Claim</th><th>JSON Path</th><th>Confirmed Source Value</th></tr></thead><tbody>{prov_rows}</tbody></table></div>
  </details>
  {blocked_html}
  {de_ai_html}
</section>
"""


def render_case_dir(out_dir: Path, explicit_input: Path | None = None) -> dict[str, Any]:
    cid = out_dir.name
    dest_dir = PREVIEW_DIR / cid
    dest_dir.mkdir(parents=True, exist_ok=True)

    product_data = discover_product_json(out_dir, explicit_input)
    visual_cfg = dict(KNOWN_CASE_VISUALS.get(cid, {}))
    # Auto-attach Task 2 LUMA imagery to live Dify runs of LUMA as well
    if not visual_cfg and "luma" in cid.lower():
        luma_base = KNOWN_CASE_VISUALS["luma_normal"]
        visual_cfg = {
            "label": f"{product_data['brand']['name']} {product_data['product'].get('name', cid)} — Live Dify Run",
            "badge": "Live Dify Auto-Published",
            "blog_hero": luma_base["blog_hero"],
            "blog_caption": luma_base["blog_caption"],
            "blog_alt": luma_base["blog_alt"],
            "pdp_hero": luma_base["pdp_hero"],
            "pdp_caption": luma_base["pdp_caption"],
            "pdp_alt": luma_base["pdp_alt"],
        }

    blog_md = (out_dir / "blog.md").read_text(encoding="utf-8")
    pdp_md = (out_dir / "pdp.md").read_text(encoding="utf-8")
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    blog_jsonld = json.loads((out_dir / "blog_jsonld.json").read_text(encoding="utf-8"))
    product_jsonld = json.loads((out_dir / "product_jsonld.json").read_text(encoding="utf-8"))
    provenance = json.loads((out_dir / "claim_provenance.json").read_text(encoding="utf-8"))
    blocked = json.loads((out_dir / "blocked_claims.json").read_text(encoding="utf-8")) if (out_dir / "blocked_claims.json").exists() else []
    de_ai = json.loads((out_dir / "de_ai_comparisons.json").read_text(encoding="utf-8")) if (out_dir / "de_ai_comparisons.json").exists() else []
    qa_report = json.loads((out_dir / "qa_report.json").read_text(encoding="utf-8")) if (out_dir / "qa_report.json").exists() else {
        "overall_passed": True,
        "passed_count": 0,
        "total_checks": 0,
        "checks": [],
    }

    brand = product_data["brand"]["name"]
    product = product_data["product"]
    facts = product.get("facts", {})
    paths = product_data.get("suggested_paths", {})
    link_rewrites = {
        "/products/item": "./pdp.html",
        "/blog/buying-guide": "./blog.html",
    }
    if paths.get("product_page"):
        link_rewrites[paths["product_page"]] = "./pdp.html"
    if paths.get("blog"):
        link_rewrites[paths["blog"]] = "./blog.html"

    label = visual_cfg.get("label") or f"{brand} {product.get('name', cid)}"
    badge = visual_cfg.get("badge") or f"Dynamic Category · {product.get('category', 'general')}"
    qa_badge = f'QA {qa_report.get("passed_count", 0)}/{qa_report.get("total_checks", 0)} {"PASS" if qa_report.get("overall_passed") else "FAIL"}'

    # --- 1. Render Blog HTML ---
    blog_h1_match = re.search(r"^#\s+(.+)$", blog_md, flags=re.MULTILINE)
    blog_h1 = blog_h1_match.group(1).strip() if blog_h1_match else meta["blog"]["title"]
    blog_body_html = markdown_to_html(blog_md, link_rewrites, skip_first_h1=True)

    # Dynamic key facts summary for categories without dedicated Task 2 imagery
    highlight_specs = [
        str(v) for k, v in facts.items()
        if k not in ("colors", "sizes", "price", "care") and v and not isinstance(v, (dict, list))
    ][:3]

    if visual_cfg.get("blog_hero"):
        blog_hero_html = (
            f'<figure class="hero-figure">'
            f'<img src="{visual_cfg["blog_hero"]}" alt="{html.escape(visual_cfg["blog_alt"])}">'
            f'<figcaption>{html.escape(visual_cfg["blog_caption"])}</figcaption>'
            f'</figure>'
        )
    else:
        blog_hero_html = (
            f'<div class="hero-figure" style="padding:26px 28px;background:linear-gradient(125deg,#1d3b2c,#355c47);color:#fff;">'
            f'<div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;">Cross-Category GEO Buying Guide · {html.escape(product.get("category", "general"))}</div>'
            f'<div style="font-size:20px;font-weight:600;margin-top:8px;">{html.escape(brand)} {html.escape(product.get("name", ""))} ({html.escape(" · ".join(highlight_specs))})</div>'
            f'<div style="font-size:13px;opacity:0.85;margin-top:6px;">Visual prompt spec compiled automatically via <code>scripts/batch_image_pipeline.py</code> for 100-SKU image scaling.</div>'
            f'</div>'
        )

    blog_inspector = build_inspector_html("BlogPosting", meta["blog"], blog_jsonld, provenance, blocked, de_ai, qa_report)
    blog_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(meta["blog"]["title"])}</title>
  <meta name="description" content="{html.escape(meta["blog"]["description"])}">
  <script type="application/ld+json">
{json.dumps(blog_jsonld, ensure_ascii=False, indent=2)}
  </script>
  <style>{BASE_CSS}</style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <a class="brand-mark" href="../index.html">{html.escape(brand)} · GEO PREVIEW</a>
      <nav class="nav-links">
        <a class="nav-pill" href="../index.html">All Cases</a>
        <a class="nav-pill active" href="./blog.html">Buying Guide Blog</a>
        <a class="nav-pill" href="./pdp.html">Product Detail Page</a>
        <a class="nav-pill" href="#geo-inspector">JSON-LD & QA</a>
        <span class="qa-pill">{qa_badge}</span>
      </nav>
    </div>
  </header>
  <main class="container">
    <span class="eyebrow">Informational GEO Buying Guide · {html.escape(badge)}</span>
    <h1>{html.escape(blog_h1)}</h1>
    {blog_hero_html}
    <article>{blog_body_html}</article>
    {blog_inspector}
  </main>
</body>
</html>
"""
    (dest_dir / "blog.html").write_text(blog_html, encoding="utf-8")

    # --- 2. Render PDP HTML ---
    pdp_h1_match = re.search(r"^#\s+(.+)$", pdp_md, flags=re.MULTILINE)
    pdp_h1 = pdp_h1_match.group(1).strip() if pdp_h1_match else f"{brand} {product.get('name', '')}"
    pdp_body_html = markdown_to_html(pdp_md, link_rewrites, skip_first_h1=True)

    if visual_cfg.get("pdp_hero"):
        pdp_visual_html = (
            f'<figure class="hero-figure" style="margin:0;">'
            f'<img src="{visual_cfg["pdp_hero"]}" alt="{html.escape(visual_cfg["pdp_alt"])}">'
            f'<figcaption>{html.escape(visual_cfg["pdp_caption"])}</figcaption>'
            f'</figure>'
        )
    else:
        colors_str = ", ".join(facts.get("colors", [])) if isinstance(facts.get("colors"), list) else str(facts.get("colors", ""))
        pdp_visual_html = (
            f'<div class="dynamic-placeholder">'
            f'<div><div style="font-size:12px;letter-spacing:0.1em;text-transform:uppercase;opacity:0.85;">{html.escape(brand)} · {html.escape(str(product.get("id", "")))}</div>'
            f'<div style="font-size:28px;font-weight:700;margin-top:8px;">{html.escape(product.get("name", ""))}</div></div>'
            f'<div style="font-size:14px;line-height:1.6;background:rgba(0,0,0,0.22);padding:14px 16px;border-radius:10px;">'
            f'<strong>Cross-Category Dynamic Spec Card</strong><br>'
            f'{html.escape(" · ".join(highlight_specs))}<br>'
            f'{f"Colors: {html.escape(colors_str)}" if colors_str else ""}</div>'
            f'</div>'
        )

    price_obj = facts.get("price")
    if isinstance(price_obj, dict) and price_obj.get("value") is not None:
        price_html = f'<div class="price-tag">{html.escape(str(price_obj.get("currency", "USD")))} {html.escape(str(price_obj["value"]))}</div>'
    else:
        price_html = '<div class="price-missing">Price omitted in current product JSON — verify live price at checkout (JSON-LD <code>offers</code> intentionally omitted)</div>'

    colors_list = facts.get("colors", []) if isinstance(facts.get("colors"), list) else []
    color_chips = "".join(
        f'<span class="chip"><span class="swatch" style="background:{resolve_swatch_color(str(c))};"></span>{html.escape(str(c))}</span>'
        for c in colors_list
    )
    sizes_list = facts.get("sizes", []) if isinstance(facts.get("sizes"), list) else []
    size_chips = "".join(f'<span class="chip">{html.escape(str(s))}</span>' for s in sizes_list)

    # Render ALL non-color/non-size/non-price/non-care scalar specs dynamically (category-agnostic!)
    spec_chips = "".join(
        f'<span class="chip">{html.escape(str(v))}</span>'
        for k, v in facts.items()
        if k not in ("colors", "sizes", "price", "care") and v and not isinstance(v, (dict, list))
    )

    pdp_inspector = build_inspector_html("Product", meta["product_page"], product_jsonld, provenance, blocked, de_ai, qa_report)
    pdp_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(meta["product_page"]["title"])}</title>
  <meta name="description" content="{html.escape(meta["product_page"]["description"])}">
  <script type="application/ld+json">
{json.dumps(product_jsonld, ensure_ascii=False, indent=2)}
  </script>
  <style>{BASE_CSS}</style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <a class="brand-mark" href="../index.html">{html.escape(brand)} · GEO PREVIEW</a>
      <nav class="nav-links">
        <a class="nav-pill" href="../index.html">All Cases</a>
        <a class="nav-pill" href="./blog.html">Buying Guide Blog</a>
        <a class="nav-pill active" href="./pdp.html">Product Detail Page</a>
        <a class="nav-pill" href="#geo-inspector">JSON-LD & QA</a>
        <span class="qa-pill">{qa_badge}</span>
      </nav>
    </div>
  </header>
  <main class="container-wide">
    <div class="pdp-grid">
      <div>{pdp_visual_html}</div>
      <div class="pdp-summary-card">
        <span class="eyebrow">{html.escape(brand)} · SKU {html.escape(str(product.get("id", "")))} · {html.escape(badge)}</span>
        <h1 style="margin-bottom:6px;">{html.escape(pdp_h1)}</h1>
        {price_html}
        {f'<div style="font-size:13px;font-weight:600;color:var(--muted);">Confirmed Attributes</div><div class="chip-row">{spec_chips}</div>' if spec_chips else ''}
        {f'<div style="font-size:13px;font-weight:600;color:var(--muted);">Confirmed Colors</div><div class="chip-row">{color_chips}</div>' if color_chips else ''}
        {f'<div style="font-size:13px;font-weight:600;color:var(--muted);">Confirmed Sizes</div><div class="chip-row">{size_chips}</div>' if size_chips else ''}
        <div class="cta-row">
          <a class="btn-primary" href="./blog.html">Read Full Buying Guide →</a>
          <a class="btn-secondary" href="#geo-inspector">Inspect Product JSON-LD</a>
        </div>
      </div>
    </div>
    <article style="max-width:820px;">{pdp_body_html}</article>
    {pdp_inspector}
  </main>
</body>
</html>
"""
    (dest_dir / "pdp.html").write_text(pdp_html, encoding="utf-8")

    wc = qa_report["checks"][0]["details"] if qa_report.get("checks") else {"blog_words": len(blog_md.split()), "pdp_words": len(pdp_md.split())}
    return {
        "id": cid,
        "label": label,
        "badge": badge,
        "blog_words": wc["blog_words"],
        "pdp_words": wc["pdp_words"],
        "qa_badge": qa_badge,
    }


def render_index(summaries: list[dict[str, Any]]) -> None:
    cards = []
    for s in summaries:
        cards.append(
            f'<div class="hub-card">'
            f'<div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px;">'
            f'<span class="eyebrow" style="margin:0;">{html.escape(s["badge"])}</span>'
            f'<span class="qa-pill">{html.escape(s["qa_badge"])}</span>'
            f'</div>'
            f'<h3 style="margin:8px 0 6px;">{html.escape(s["label"])}</h3>'
            f'<p style="font-size:13.5px;color:var(--muted);margin:0;">Blog: <strong>{s["blog_words"]} words</strong> · PDP: <strong>{s["pdp_words"]} words</strong></p>'
            f'</div>'
            f'<div class="cta-row" style="margin-top:8px;">'
            f'<a class="btn-primary" href="./{s["id"]}/blog.html">Open Blog Page</a>'
            f'<a class="btn-secondary" href="./{s["id"]}/pdp.html">Open PDP Page</a>'
            f'</div></div>'
        )

    if not cards:
        cards_block = (
            '<div class="hub-card" style="text-align:center;padding:44px 28px;border-style:dashed;">'
            '<div style="font-size:18px;font-weight:600;margin-bottom:8px;">暂无已发布页面 · Waiting for Dify Workflow Run</div>'
            '<p style="color:var(--muted);margin:0;">在 Dify 画布上传 <code>AIGC_LUMA_product.json</code> 或 <code>AIGC_ORBIT_product.json</code> 并点击「开始运行」，完成后将自动发布到此处，刷新即可查看。</p>'
            '</div>'
        )
    else:
        cards_block = f'<div class="card-grid">{"".join(cards)}</div>'

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trendee AIGC GEO Content & Multimodal Preview Hub</title>
  <style>{BASE_CSS}</style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <span class="brand-mark">TRENDEE AIGC · GEO LIVE PAGE PREVIEW</span>
      <span class="qa-pill">{len(summaries)} Published Cases</span>
    </div>
  </header>
  <main class="container-wide">
    <span class="eyebrow">Task 1 + Task 2 Deliverable Showcase</span>
    <h1>Rendered GEO Blog &amp; Product Detail Pages</h1>
    <p style="max-width:740px;color:var(--muted);">
      Pages auto-publish here directly from the Dify Workflow (Node 6B → <code>POST /api/publish</code>) with real <code>&lt;head&gt;</code> JSON-LD, Meta tags, clickable internal links, and 7-check automated QA.
    </p>
    {cards_block}

    <h2 style="margin-top:52px;">Task 2 — Multimodal Image Iteration (V1 Baseline → V2 Optimized)</h2>
    <figure class="hero-figure">
      <img src="../images/comparison/pdp_light_blue_v1_vs_v2.jpg" alt="Side-by-side comparison of V1 baseline and V2 optimized light blue relaxed-fit linen shirt">
      <figcaption>V1 → V2 Optimization: Fixed slim/stiff cut, closed collar, mismatched blue plastic buttons, and flat gray lighting to match the LUMA-001 JSON facts and 16:9 Blog Banner SKU consistency.</figcaption>
    </figure>
  </main>
</body>
</html>
"""
    (PREVIEW_DIR / "index.html").write_text(index_html, encoding="utf-8")


def render_live_only() -> list[dict[str, Any]]:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    found_dirs = [
        d for d in sorted(OUTPUTS_DIR.iterdir())
        if d.is_dir() and d.name.startswith("live_") and (d / "blog.md").exists() and (d / "pdp.md").exists()
    ]
    summaries = [render_case_dir(d) for d in found_dirs]
    render_index(summaries)
    return summaries


def render_all() -> list[dict[str, Any]]:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    preferred_order = list(KNOWN_CASE_VISUALS.keys())
    found_dirs = [
        d for d in sorted(OUTPUTS_DIR.iterdir())
        if d.is_dir() and (d / "blog.md").exists() and (d / "pdp.md").exists()
    ]
    found_dirs.sort(key=lambda p: (preferred_order.index(p.name) if p.name in preferred_order else 999, p.name))

    summaries = [render_case_dir(d) for d in found_dirs]
    render_index(summaries)
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Dynamically render GEO Blog & PDP HTML pages for any product category.")
    parser.add_argument("--output-dir", type=Path, help="Optional single output directory to render.")
    parser.add_argument("--input", type=Path, help="Optional product JSON matching --output-dir.")
    args = parser.parse_args()

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    if args.output_dir:
        summary = render_case_dir(args.output_dir, args.input)
        print(f"[OK] Rendered {summary['id']} -> {PREVIEW_DIR / summary['id']}")
        return

    summaries = render_all()
    print(f"[OK] Dynamically rendered preview hub + {len(summaries) * 2} HTML pages -> {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
