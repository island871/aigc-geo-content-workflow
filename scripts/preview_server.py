#!/usr/bin/env python3
"""
Local Preview & Auto-Publish Server (`0.0.0.0:8090`).

Serves static preview pages under `trendee-aigc-geo/` AND exposes:
  - GET  /health       -> {"ok": true}
  - POST /api/publish  -> Receives Dify Workflow Stage 6 JSON payload, saves all
                          artifacts to `outputs/<slug>/`, runs `qa_validator`,
                          dynamically re-renders `preview/`, and returns live URLs.

Usage:
  python scripts/preview_server.py --port 8090
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import render_pages
from qa_validator import validate_case

PUBLISH_LOCK = threading.Lock()


def _safe_slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", (name or "live_run").strip().lower()).strip("_")
    if not slug:
        slug = "live_run"
    if not slug.startswith("live_"):
        slug = f"live_{slug}"
    return slug[:60]


def _parse_maybe_json(val: Any, default: Any) -> Any:
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return default
    return default


def publish_workflow_payload(payload: dict[str, Any], port: int) -> dict[str, Any]:
    """Persist Dify workflow output, run QA validation, and re-render preview HTML."""
    product_obj = _parse_maybe_json(payload.get("normalized_product_json"), {})
    dataset_id = (
        payload.get("dataset_id")
        or product_obj.get("dataset_id")
        or product_obj.get("product", {}).get("id")
        or "live_product"
    )
    slug = _safe_slug(str(dataset_id))
    out_dir = ROOT_DIR / "outputs" / slug

    with PUBLISH_LOCK:
        out_dir.mkdir(parents=True, exist_ok=True)
        input_json_path = out_dir / "input_product.json"
        input_json_path.write_text(json.dumps(product_obj, ensure_ascii=False, indent=2), encoding="utf-8")

        (out_dir / "blog.md").write_text(str(payload.get("final_blog_md", "")), encoding="utf-8")
        (out_dir / "pdp.md").write_text(str(payload.get("final_pdp_md", "")), encoding="utf-8")

        blog_meta = _parse_maybe_json(payload.get("blog_meta_json"), {})
        pdp_meta = _parse_maybe_json(payload.get("pdp_meta_json"), {})
        (out_dir / "meta.json").write_text(
            json.dumps({"blog": blog_meta, "product_page": pdp_meta}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for src_key, fname, default in [
            ("blog_jsonld", "blog_jsonld.json", {}),
            ("product_jsonld", "product_jsonld.json", {}),
            ("claim_provenance_json", "claim_provenance.json", []),
            ("blocked_claims_json", "blocked_claims.json", []),
            ("de_ai_comparisons_json", "de_ai_comparisons.json", []),
        ]:
            obj = _parse_maybe_json(payload.get(src_key), default)
            (out_dir / fname).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

        # Validate using standalone QA engine
        wc_mode = str(payload.get("word_count_mode", "pdf_default"))
        if wc_mode not in ("pdf_default", "json_override"):
            wc_mode = "pdf_default"
        qa_report = validate_case(input_json_path, out_dir, word_count_mode=wc_mode)
        (out_dir / "qa_report.json").write_text(json.dumps(qa_report, ensure_ascii=False, indent=2), encoding="utf-8")

        # Re-render live auto-published preview pages cleanly (keeps demo hub focused on live runs)
        render_pages.render_live_only()

    base = f"http://localhost:{port}"
    return {
        "published": True,
        "case_id": slug,
        "qa_passed": "PASS" if qa_report["overall_passed"] else "FAIL",
        "qa_score": f"{qa_report['passed_count']}/{qa_report['total_checks']}",
        "index_url": f"{base}/preview/index.html",
        "blog_url": f"{base}/preview/{slug}/blog.html",
        "pdp_url": f"{base}/preview/{slug}/pdp.html",
    }


class PreviewPublishHandler(SimpleHTTPRequestHandler):
    server_port: int = 8090

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "service": "trendee-geo-preview-publisher"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/api/publish":
            self._send_json(HTTPStatus.NOT_FOUND, {"published": False, "error": f"Unknown endpoint: {self.path}"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body)
            result = publish_workflow_payload(payload, self.server_port)
            print(f"[PUBLISHED] {result['case_id']} ({result['qa_passed']} {result['qa_score']}) -> {result['blog_url']}", flush=True)
            self._send_json(HTTPStatus.OK, result)
        except Exception as exc:
            print(f"[PUBLISH ERROR] {exc}", file=sys.stderr, flush=True)
            self._send_json(HTTPStatus.BAD_REQUEST, {"published": False, "error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local GEO preview & Dify auto-publish server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    handler_cls = functools.partial(PreviewPublishHandler, directory=str(ROOT_DIR))
    PreviewPublishHandler.server_port = args.port
    httpd = ThreadingHTTPServer((args.host, args.port), handler_cls)
    print(f"[OK] Preview & Auto-Publish Server listening on http://{args.host}:{args.port} (root={ROOT_DIR})", flush=True)
    print(f"     Preview Hub : http://localhost:{args.port}/preview/index.html", flush=True)
    print(f"     Publish API : POST http://localhost:{args.port}/api/publish", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
