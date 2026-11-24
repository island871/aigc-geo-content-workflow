# Task 2 — Multimodal Image Assets, V1→V2 Optimization & 100-SKU Scaling Plan

> **Visual Disclosure:** Because `LUMA Everyday Linen Shirt` (`LUMA-001`) is a fictional brand with no physical sample photography, all images are explicitly marked **“AI 视觉示意 | AI Visual Illustration”** in `images/final/` (untouched raw originals are preserved in `images/raw/`).

---

## 1. Final Image Assets & Metadata

### Image ① — Blog Banner (16:9)
- **Labeled Delivery File:** `images/final/blog_banner_white_linen_16x9_labeled.jpg` (1376 × 768, 16:9)
- **Raw Original:** `images/raw/blog_banner_white_linen_16x9.jpg`
- **Tool / Model:** Gemini Image Generation (Imagen-based multimodal model via built-in `image-generator` pipeline)
- **Key Parameters:** Aspect ratio `16:9`, editorial 50mm daylight framing, soft warm morning window light (`5200K`), zero text/logo negative constraints
- **JSON Consistency Verification:** `White` (`product.facts.colors[0]`) · `100% linen` visible matte slub weave (`product.facts.material`) · `gender-neutral long-sleeve shirt` (`product.facts.type`) · `relaxed fit` (`product.facts.fit`) · `work and commute / travel` transit walkway with minimalist tote (`product.target_scenarios`)
- **English Caption:**
  > *AI visual illustration: A gender-neutral relaxed-fit 100% linen long-sleeve shirt in White worn during a sunlit morning commute, showing natural flax drape and breathable everyday styling.*
- **English Alt Text:**
  > `AI visual illustration of a person walking through a sunlit modern transit station wearing a relaxed-fit white 100% linen long-sleeve shirt, grey relaxed trousers, and a canvas tote bag`

**Prompt Used (Final 16:9):**
```text
Editorial lifestyle photograph (16:9 wide frame) of a gender-neutral person walking naturally through a sunlit modern architectural transit station walkway carrying a minimalist canvas tote bag. Primary focus: a crisp WHITE, gender-neutral, long-sleeve, relaxed-fit 100% linen button-down shirt with clearly visible organic woven linen slub texture, natural matte drape, soft natural creases, relaxed shoulders, sleeves casually cuffed once at the wrist, paired with stone-grey relaxed trousers. Clean breathing room on the left for a blog header, shot on 50mm prime lens, soft warm morning daylight through tall windows, calm neutral palette. Strictly no text, no watermarks, no brand logos, no tight slim-fit tailoring, no synthetic sheen.
```

---

### Image ② — Product Detail Image (1:1, Final V2 Optimized)
- **Labeled Delivery File:** `images/final/pdp_light_blue_1x1_labeled.jpg` (1024 × 1024, 1:1)
- **Raw Original (V2):** `images/raw/pdp_light_blue_v2_after.jpg`
- **Before Baseline (V1):** `images/raw/pdp_light_blue_v1_before.jpg`
- **Side-by-Side Comparison Board:** `images/comparison/pdp_light_blue_v1_vs_v2.jpg`
- **Tool / Model:** Gemini Image Generation (`image-generator`)
- **Key Parameters:** Aspect ratio `1:1`, 50mm prime studio lens, upper-left 45° raking daylight (`5200K`), seamless warm off-white backdrop (`#F4F1EC`), strict SKU hardware & negative constraints
- **JSON Consistency Verification:** `Light Blue` (`product.facts.colors[1]`) · `100% linen` slub weave (`product.facts.material`) · `gender-neutral long-sleeve shirt` (`product.facts.type`) · `relaxed fit` dropped shoulders & straight drape (`product.facts.fit`) · Cross-SKU match with Image ① (identical warm cream shell buttons + single left chest pocket)
- **English Caption:**
  > *AI visual illustration: Studio product detail view of the LUMA Everyday Linen Shirt in Light Blue, highlighting its 100% linen slub texture, dropped-shoulder relaxed fit, and full-length sleeves.*
- **English Alt Text:**
  > `AI visual illustration showing a front studio view of a pale light blue 100% linen long-sleeve shirt in a relaxed gender-neutral fit hanging on a pale wooden hanger against an off-white background`

---

## 2. Iterative Optimization: V1 (Before) → V2 (After)

See side-by-side visual board: `images/comparison/pdp_light_blue_v1_vs_v2.jpg`.

| Dimension | V1 Baseline (Before) | Visual Problem Diagnosed in V1 | V2 Optimization Applied (After) |
| :--- | :--- | :--- | :--- |
| **Silhouette / Fit** | Narrow regular/slim shoulders, flat stiff outline, top collar buttoned tight | Fails to convey JSON `relaxed fit` and `gender-neutral` ease; looks like a formal slim dress shirt | Specified generous dropped shoulders, straight roomy torso, natural 3D volume hanging on a minimalist pale-oak hanger, top button casually undone |
| **Cross-Image SKU Consistency** | Dyed-to-match blue plastic buttons | Conflicts with Image ① (White Blog Banner), which features warm cream/ivory matte buttons—breaks same-SKU visual trust | Explicitly locked **natural warm off-white/cream matte shell buttons** and matching single left chest pocket across both colorways |
| **Material Texture (100% Linen)** | Flat front-on cool lighting (`#DCDCDC` gray background) | Washes out flax slub micro-texture; fabric reads closer to smooth cotton chambray than breathable 100% linen | Changed to **45° upper-left raking natural daylight (5200K)** against warm off-white matte backdrop (`#F4F1EC`) to accentuate authentic cross-grain linen slub weave |
| **Color Accuracy** | Slightly saturated medium cornflower blue under cool light | Drifts slightly darker/cooler than soft natural Light Blue linen | Anchored pale desaturated flax-dyed sky blue under neutral warm daylight |

**V1 Prompt (Baseline):**
```text
A light blue long-sleeve linen shirt, clean e-commerce product photo on a plain light studio background, front view, studio lighting, 1:1 square. No text, no logos, no watermarks.
```

**V2 Prompt (Optimized):**
```text
Centered 1:1 square studio e-commerce product photograph of a LIGHT BLUE (soft pale sky blue, desaturated natural flax-dyed tone), gender-neutral, long-sleeve, unmistakably RELAXED-FIT 100% linen button-down shirt. Generous dropped shoulders, visibly roomy straight-cut torso, relaxed full-length sleeves with buttoned cuffs, relaxed shirt collar with top button casually undone. Natural warm off-white/cream matte shell buttons down the front placket (not dyed blue plastic buttons) and one clean left chest patch pocket. Clearly visible authentic 100% pure linen slub weave and organic matte drape folds. Hanging naturally with realistic 3D volume on a minimalist thin pale-oak wooden hanger against a seamless warm off-white matte backdrop (#F4F1EC). Soft directional 5200K natural daylight raking from upper left at 45 degrees, 50mm prime lens. No text, no neck-tag text, no logos, no watermarks, no slim-fit tailoring.
```

---

## 3. Equivalent Safe Midjourney v6.1 Web Prompts (Optional Manual Swap)

> **Security & Compliance Note:** Personal Midjourney account Cookie / Discord self-bot automation violates Midjourney ToS and carries account-ban risk. For **manual creative generation** on Midjourney Web/Discord, the equivalent prompts below can be pasted safely; for **automated 100-SKU production**, use compliant official APIs (Section 4).

- **MJ Blog Banner (16:9):**
  `Editorial lifestyle photograph of a gender-neutral commuter walking through a sunlit modern concrete and wood transit station, wearing a crisp white relaxed-fit 100% linen long-sleeve button-down shirt with visible slub weave and cream matte buttons, cuffed once at wrist, stone-grey relaxed trousers, minimalist canvas tote bag, breathing room on left side, 50mm lens, warm 5200K morning light --ar 16:9 --v 6.1 --style raw --s 150 --no text watermark logo slim fit synthetic sheen`
- **MJ PDP Detail (1:1):**
  `Minimalist e-commerce studio photograph of a pale light blue relaxed-fit gender-neutral 100% linen long-sleeve button-down shirt with dropped shoulders, cream matte shell buttons, single left chest pocket, top button undone, visible flax slub weave texture, hanging on a thin pale oak wooden hanger against a warm off-white matte wall #F4F1EC, soft 45-degree upper-left daylight, 50mm lens --ar 1:1 --v 6.1 --style raw --s 120 --no text watermark logo neck tag blue plastic buttons slim fit`

---

## 4. Scaling to 100 SKUs (`scripts/batch_image_pipeline.py`)

To scale cleanly from 1 SKU (`LUMA-001`) to 100+ SKUs across categories without sacrificing visual consistency:

1. **Dynamic JSON → Prompt Compilation:** `scripts/batch_image_pipeline.py` reads any catalog JSON (`brand`, `category`, `material`, `fit/capacity/lid`, `colors`, `target_scenarios`) and compiles standardized `blog_banner` (16:9) + `pdp_hero` (1:1) job specs (`images/batch_jobs_manifest.jsonl`) with zero hardcoded category templates.
2. **Visual Consistency Controls (3 Layers):**
   - **Global Brand Style Lock (`BRAND_STYLE_LOCK`)**: Fixes color temperature (`5200K`), 50mm lens, backdrop hex (`#F4F1EC`), and negative constraints across all 100 SKUs.
   - **SKU Variant Anchor / Image-to-Image Lock**: For multi-color SKUs (e.g., White vs. Light Blue), generate one approved master geometry/hardware reference first, then drive secondary colorways via image-conditioned editing (`gpt-image-1` edit / Flux Kontext / Imagen subject-reference) so buttons, pockets, and silhouettes stay identical.
   - **Automated VLM Visual QA Gate**: Run a multimodal judge (checking color match, material texture, aspect ratio, zero text/artifact hallucinations, and sleeve/component accuracy) before routing outputs.
3. **Compliant API Dispatch & Error Retry:** Dispatch via official commercial APIs (**OpenAI `gpt-image-1` / Google Imagen 3 / Black Forest Labs Flux Pro API** — avoiding unofficial Cookie/self-bot scrapers that risk bans) with async concurrency throttling, exponential backoff retries (3 attempts: 1s → 2s → 4s), and dead-letter JSONL logging.
4. **Human-in-the-Loop (HITL) Review & Disclosure:** Auto-pass high-confidence VLM-verified assets into a lightweight review queue (`review_state: pending_human_signoff`), flag borderline color/geometry failures for targeted regeneration, and automatically stamp the `"AI 视觉示意"` disclosure badge via `stamp_ai_illustration_badge()` whenever real studio photos are unavailable.
