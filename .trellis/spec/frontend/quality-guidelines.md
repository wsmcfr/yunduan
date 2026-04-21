# Quality Guidelines

> Frontend quality standards and review criteria.

---

## Overview

The web frontend has not been scaffolded yet, so quality review is currently about keeping the first implementation aligned with the confirmed stack and avoiding drift between planning documents, API contracts, and UI code.

The current repository already suggests two useful quality signals:

- the page map is explicit
- the QML prototype names UI state clearly and groups it intentionally

The web app should preserve those strengths.

---

## Code Review Checklist

| Check | Expected standard |
|---|---|
| Route ownership | Page components map cleanly to the planned route structure |
| Component size | Pages compose child components instead of inlining everything |
| Data flow | API calls do not live inside small presentational components |
| State ownership | Local, server, and global state are not mixed arbitrarily |
| Contracts | DTO mapping is explicit when backend shape differs from UI shape |
| Empty/error/loading states | Every data-driven page handles them deliberately |
| Reuse | Shared labels, routes, statuses, and endpoint paths are not duplicated blindly |

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Building the cloud dashboard directly in QML because a prototype exists | The project now targets a cloud web frontend |
| Embedding backend URLs and object-storage paths directly in components | Hard to change and test |
| Duplicating route strings such as `/records` or `/devices` in many files | Creates drift |
| Hiding API transformations inside templates or render functions | Makes cross-layer bugs hard to trace |
| Giant `DashboardPage` or `RecordsPage` files with all logic inline | Hard to maintain |

---

## Testing Expectations

### Bootstrap baseline

| Area | Minimum expectation |
|---|---|
| Page routing | Smoke tests for primary routes |
| Feature logic | Unit tests for filters, mapping, and status formatting |
| API layer | Tests for response normalization and failure handling |
| UI states | Loading, empty, error, and success rendering coverage for main data pages |

### Done means

- lint and type-check pass
- changed routes and contracts are documented
- new features include at least one happy-path and one failure or empty-state check

---

## Convention: Temporary Public Login Helper Copy Must Stay Non-Production

**What**: While the current login page is still a temporary helper-style screen, any helper text, placeholder credential hint, or demo copy on the public login page must use non-working placeholder credentials.

**Why**:

- this project is deployed on the public internet, not only on a local LAN
- the login page source is part of the shipped frontend bundle and is visible to anyone who loads the page
- real production credentials must never be documented in frontend copy, placeholders, or static assets
- this rule is about the temporary helper copy only; it does not prevent replacing the whole screen later with a proper login / registration flow

**Example**:

```vue
<p class="login-tip">
  Demo only: `admin / admin123`
</p>
```

```vue
<!-- Do not ship the real public-production credential pair in the UI. -->
<p class="login-tip">
  admin / <real-production-password>
</p>
```

**Related**: keep real credentials in backend config, secret stores, or operator-only runbooks, not in frontend code or public hints. When the product later moves to a real login / registration UI, this temporary helper-copy rule can be removed together with the placeholder text itself.

---

## Examples

| Repository evidence | Quality takeaway |
|---|---|
| `MainPagePrototype.qml` small helper functions such as `statusColor` and `beatText` | View formatting logic should stay small and readable |
| `MainPagePrototype.qml` explicit screen sections | Composition should remain intentional in the web UI |
| `工业缺陷检测系统完整方案.md` route map | Page structure should be stable and reviewable, not invented ad hoc per feature |

---

## Common Mistakes

| Mistake | Why it is a problem |
|---|---|
| Treating a prototype screen as a final design system | Leads to hard-coded shortcuts |
| Keeping business logic in template expressions | Hard to test and review |
| Forgetting empty/error states while focusing only on the success path | Users lose trust quickly |
| Repeating status text and badge logic in every page | Causes inconsistent UI behavior |
| Shipping real production credentials in login helper copy | Exposes operator secrets through public frontend assets |

---

## Convention: Formal Auth Pages Must Not Prefill or Expose Credentials

Once the project moves beyond the temporary helper login screen and into a real login / registration / password-reset flow:

- do not prefill usernames, demo passwords, or real operator credentials into auth form state
- do not render any “current production account” hint in the public auth UI
- do not expose readable access tokens in page state, hidden fields, or browser storage

Why:

- real auth pages are part of the public internet surface
- prefilled credentials drift into screenshots, screen recordings, and browser autofill snapshots
- token exposure undermines the security benefit of moving the session to `HttpOnly Cookie`
