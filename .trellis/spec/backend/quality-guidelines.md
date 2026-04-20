# Quality Guidelines

> Backend quality standards and review criteria.

---

## Overview

Because the backend has not been scaffolded yet, quality in this project means two things:

1. stay aligned with the confirmed cloud stack (`FastAPI + SQLAlchemy + MySQL + COS`)
2. avoid turning planning snippets into production architecture

These rules are the minimum standard for the first backend implementation.

---

## Code Review Checklist

| Check | Expected standard |
|---|---|
| Layering | Routes stay thin; services own workflows; repositories own DB access |
| Type hints | Public functions and service entry points are typed |
| Config | Secrets and endpoints come from config or env, not inline literals |
| Payload contracts | Request and response schemas are explicit and reviewed when changed |
| Failure handling | Storage, AI, and DB failures are handled deliberately |
| Pagination | List endpoints are bounded and ordered |
| Naming | Files, modules, and DB entities follow the naming rules in this spec |

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Shipping prototype code straight from Markdown into production | Prototype snippets are intentionally simplified |
| Writing business logic directly inside FastAPI route functions | Makes testing and reuse harder |
| Hard-coding COS credentials, AI API keys, or DB URLs | Unsafe and not deployable |
| Returning raw ORM objects without schema review | Leaks internal fields and couples layers |
| Using object storage as a database or vice versa | Breaks separation of concerns |

---

## PDF Layout Quality

### Convention: Direct-Draw PDF Renderers Need Pagination Regression Tests

When a backend service draws PDF pages directly with `reportlab` canvas commands, layout bugs do not fail loudly.
The PDF can still be generated while cards, charts, or bullet lists silently overflow the page bottom.

Implementation contract:

- any renderer that positions panels with explicit `x/y/width/height` values must reserve a stable footer-safe area
- do not keep stacking sections onto the first page once the remaining height is smaller than the next block budget
- split summary, appendix, or AI text into explicit later pages instead of relying on one oversized first page
- unit tests should validate pagination behavior by patching the renderer dependency and using a fake canvas object
- those tests should assert signals such as `showPage()` count, later-page section titles, and successful byte output
- do not make pagination tests depend on the local machine having `reportlab` installed

Example:

```python
with (
    patch.object(renderer, "_load_reportlab", return_value=fake_modules),
    patch.object(renderer, "_ensure_font_registered", return_value="FakeFont"),
):
    pdf_bytes, _ = renderer.build_pdf(overview=overview, ai_analysis=None)

assert pdf_bytes.startswith(b"%PDF")
assert fake_canvas.show_page_calls == 1
assert "关键发现与样本摘要" in fake_canvas.drawn_strings
```

Why:

- raw PDF bytes are poor regression oracles for pagination problems
- local development environments may intentionally omit `reportlab`
- a fake canvas catches the real failure mode here: content stayed on the wrong page or never paged at all

### Common Mistake: Treating "PDF Generated Successfully" as Layout Success

**Symptom**: The lightweight PDF opens, but the lower panels are clipped, crowded, or pushed beyond the printable area.

**Cause**: Direct-draw renderers use absolute vertical coordinates; if the page budget is not recalculated, one more panel can silently overflow A4.

**Fix**: Move supporting sections such as key findings, gallery summary, or AI appendix to dedicated pages and keep a fixed footer-safe area on each page.

**Prevention**:

- add a fake-canvas pagination test whenever a new direct-draw panel is introduced
- assert later-page titles and `showPage()` counts
- if a renderer change is deployed, follow with one real server-side smoke render instead of trusting unit tests alone

---

## Testing Expectations

### Bootstrap baseline

| Area | Minimum expectation |
|---|---|
| Route layer | Smoke tests for primary endpoints |
| Service layer | Unit tests for record creation, review decisions, and integration failure paths |
| Repository layer | Query tests for filtering, sorting, and pagination |
| Integration layer | Mocked tests for COS and AI review clients |
| Server-rendered PDF | Verify both the renderer decision path and the manual-layout pagination path |

### Done means

- code follows the directory and naming guidelines
- lint and type checks pass
- changed API contracts are documented
- at least one good-path and one failure-path test exist for new backend behavior
- direct-draw PDF changes include a pagination regression test that does not rely on optional local PDF libraries

---

## Examples

| Repository evidence | Quality takeaway |
|---|---|
| `工业缺陷检测系统完整方案.md` imports `database`, `models`, and `schemas` separately | The intended shape already separates concerns |
| `工业缺陷检测系统完整方案.md` uses paginated list retrieval with ordering | Bounded queries are already part of the plan |
| `STM32MP157DAA1工业缺陷检测系统综合方案.md` separates backend, storage, and cloud roles | Cross-layer boundaries matter from the first scaffold |

---

## Common Mistakes

| Mistake | Why it matters |
|---|---|
| Keeping all first-pass backend code in one file because "the project is still small" | Small projects become large quickly |
| Building frontend payloads straight from ORM fields without DTO review | Creates brittle coupling |
| Treating AI review as synchronous route-only logic | Makes latency and retries painful |
