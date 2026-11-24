# Automated QA Verification Summary

| Test Case | Dataset | Result | Passed Checks | Blog Words | PDP Words |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `luma_normal` | `A_LUMA_Linen_Shirt` | **PASS** | 7/7 | 1465 | 314 |
| `luma_unsupported_claim` | `A_LUMA_Linen_Shirt` | **PASS** | 7/7 | 1242 | 284 |
| `luma_missing_data` | `A_LUMA_Linen_Shirt_Missing_Data` | **PASS** | 7/7 | 1289 | 291 |
| `orbit_normal` | `B_ORBIT_Water_Bottle` | **PASS** | 7/7 | 1402 | 308 |

## Case: `luma_normal` (PASS)
- **[PASS] `1_word_count_compliance`**: Blog=1465 words (target 1200-1500), PDP=314 words (target 250-400)
- **[PASS] `2_geo_structure_and_meta`**: Blog(H1=1, H2=7, FAQ=4, PDP_Link=True) | PDP(H1=1, H2=3, FAQ=3) | MetaOK=True
- **[PASS] `3_unsupported_claim_guardrail`**: Checked 7 forbidden claim patterns; 0 unguarded leaks found
- **[PASS] `4_missing_field_degradation`**: price_missing=False, care_missing=False, issues=0
- **[PASS] `5_jsonld_schema_validity`**: BlogPosting & Product JSON-LD valid=True (0 errors)
- **[PASS] `6_claim_provenance_grounding`**: 8 claims verified against exact JSON paths (min 5), 0 invalid
- **[PASS] `7_de_ai_editorial_quality`**: AI clichés found=0, Before/After comparison pairs=4

## Case: `luma_unsupported_claim` (PASS)
- **[PASS] `1_word_count_compliance`**: Blog=1242 words (target 1200-1500), PDP=284 words (target 250-400)
- **[PASS] `2_geo_structure_and_meta`**: Blog(H1=1, H2=7, FAQ=4, PDP_Link=True) | PDP(H1=1, H2=3, FAQ=3) | MetaOK=True
- **[PASS] `3_unsupported_claim_guardrail`**: Checked 11 forbidden claim patterns; 0 unguarded leaks found
- **[PASS] `4_missing_field_degradation`**: price_missing=False, care_missing=False, issues=0
- **[PASS] `5_jsonld_schema_validity`**: BlogPosting & Product JSON-LD valid=True (0 errors)
- **[PASS] `6_claim_provenance_grounding`**: 7 claims verified against exact JSON paths (min 5), 0 invalid
- **[PASS] `7_de_ai_editorial_quality`**: AI clichés found=0, Before/After comparison pairs=0

## Case: `luma_missing_data` (PASS)
- **[PASS] `1_word_count_compliance`**: Blog=1289 words (target 1200-1500), PDP=291 words (target 250-400)
- **[PASS] `2_geo_structure_and_meta`**: Blog(H1=1, H2=7, FAQ=4, PDP_Link=True) | PDP(H1=1, H2=3, FAQ=3) | MetaOK=True
- **[PASS] `3_unsupported_claim_guardrail`**: Checked 7 forbidden claim patterns; 0 unguarded leaks found
- **[PASS] `4_missing_field_degradation`**: price_missing=True, care_missing=True, issues=0
- **[PASS] `5_jsonld_schema_validity`**: BlogPosting & Product JSON-LD valid=True (0 errors)
- **[PASS] `6_claim_provenance_grounding`**: 6 claims verified against exact JSON paths (min 5), 0 invalid
- **[PASS] `7_de_ai_editorial_quality`**: AI clichés found=0, Before/After comparison pairs=0

## Case: `orbit_normal` (PASS)
- **[PASS] `1_word_count_compliance`**: Blog=1402 words (target 1200-1500), PDP=308 words (target 250-400)
- **[PASS] `2_geo_structure_and_meta`**: Blog(H1=1, H2=7, FAQ=4, PDP_Link=True) | PDP(H1=1, H2=3, FAQ=3) | MetaOK=True
- **[PASS] `3_unsupported_claim_guardrail`**: Checked 7 forbidden claim patterns; 0 unguarded leaks found
- **[PASS] `4_missing_field_degradation`**: price_missing=False, care_missing=False, issues=0
- **[PASS] `5_jsonld_schema_validity`**: BlogPosting & Product JSON-LD valid=True (0 errors)
- **[PASS] `6_claim_provenance_grounding`**: 8 claims verified against exact JSON paths (min 5), 0 invalid
- **[PASS] `7_de_ai_editorial_quality`**: AI clichés found=0, Before/After comparison pairs=1
