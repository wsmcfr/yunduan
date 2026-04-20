# State Management

> State management rules for the Vue frontend.

---

## Overview

The current frontend already uses a mixed state strategy:

- Pinia for authentication session (`useAuthStore`)
- feature-local composables for server-backed pages such as `useRecordsList`
- page-local refs for detail loading, submission state, and transient review actions

The core rule remains:

- use local state first
- use feature composables for server state
- use Pinia only for truly cross-page state

---

## Local vs Global State

| State type | Where it belongs |
|---|---|
| One-page toggles, dialog visibility, loading flags | local component state |
| Filters and pagination owned by one feature page | feature composable or page-level state |
| Auth session, current user, logout action | global store |
| Shared app shell state | global store only if multiple pages need it |
| Detection record detail, review history, AI review result | page-local server state |
| Parts list and devices list used only by one page | feature-local server state |

### Current Repository Evidence

The implemented app keeps state close to the page that owns it:

- `useRecordsList` owns filters, pagination, and list refresh
- `RecordDetailPage` owns `record`, `loading`, `reviewSubmitting`, and `aiSubmitting`
- `useAuthStore` owns the login session only

That separation should remain the default.

---

## Store Structure

Prefer small stores by domain:

| Store | Responsibility |
|---|---|
| `useAuthStore` | login state, user identity, token lifecycle |
| `useUiStore` | shell preferences only if they become cross-page |
| `useDeviceStore` | shared device connectivity summary only if multiple pages need the same live snapshot |

Do not create a catch-all `useAppStore` for records, parts, devices, dialogs, and auth together.

---

## Server State

| Rule | Reason |
|---|---|
| Keep server data close to the feature that owns it | Reduces accidental coupling |
| Cache list and detail data separately | Different invalidation behavior |
| Normalize DTOs before storing or exposing them | Keeps UI models stable |
| Treat filters and pagination as first-class state | Records pages depend on stable query ownership |
| Reload detail after review mutation | Final result and review history can change together |

Current server-state domains:

- dashboard statistics
- records list
- record detail plus review data
- parts list
- devices overview

---

## Scenario: Records List Ownership and Review Workspace

### 1. Scope / Trigger

- Trigger: any change to records list filters, pagination, record detail loading, manual review submission, or AI review entry points
- Affected layers: composable -> page -> API service -> router navigation

### 2. Signatures

```ts
export function useRecordsList(): {
  loading: Ref<boolean>;
  error: Ref<string>;
  items: Ref<DetectionRecordModel[]>;
  total: Ref<number>;
  pageSize: Ref<number>;
  currentPage: Ref<number>;
  filters: RecordsFilters;
  refresh: () => Promise<void>;
  handlePageChange: (page: number) => Promise<void>;
  applyFilters: () => Promise<void>;
  resetFilters: () => Promise<void>;
};
```

```ts
interface RecordsFilters {
  partId: number | undefined;
  deviceId: number | undefined;
  result: DetectionResult | undefined;
  reviewStatus: ReviewStatus | undefined;
}
```

### 3. Contracts

| Concern | Owner | Contract |
|---|---|---|
| Auth session | Pinia | Cross-page only |
| Records list filters and pagination | `useRecordsList` | Query ownership stays inside the feature composable |
| Record detail data | `RecordDetailPage` | Detail request, reload, and display state stay local to the page |
| Manual review form state | `ManualReviewFormCard` + `RecordDetailPage` | Form fields stay local, submit action is emitted upward |
| AI review trigger | `RecordDetailPage` | Only available from record detail, not parts master pages |
| Part master data | `PartsPage` | Maintains metadata only, not review workflow |

Additional rules:

- `applyFilters()` and `resetFilters()` must reset `currentPage` to `1`
- records pages act as screening and navigation pages
- record detail pages act as the review workspace
- a manual review success must be followed by detail reload so that `effectiveResult` and review history stay in sync

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| Filters change but page is not reset | Query can point past the valid result window | Reset to page `1` before refresh |
| Route param changes while detail component is reused | User sees stale record data | Watch route param and refetch |
| Review form state is moved into global store | Stale form data leaks between records | Keep form state local to the detail workflow |
| Parts page adds review mutation buttons | Master-data page takes over workflow concerns | Navigate to record detail instead |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | `RecordsPage` filters and pages data, then routes to `RecordDetailPage` for review work |
| Base | User opens a reviewed record and only inspects evidence; no review mutation is needed |
| Bad | Inline manual-review dialog is added to parts management or records table rows as the primary workflow |

### 6. Tests Required

- composable test asserting `applyFilters()` resets the page to `1`
- composable test asserting `resetFilters()` clears all filters and refreshes
- page test asserting route param change reloads record detail
- page test asserting manual review success reloads detail rather than mutating partial state locally

Assertion points:

- records list query parameters are generated from `useRecordsList`
- detail page does not depend on global review state
- parts page remains a master-data page, not a review workstation

### 7. Wrong vs Correct

#### Wrong

```ts
// Review workflow is pushed into a list page row action.
const reviewDialogVisible = ref(false);
const currentReviewRecord = ref<any>(null);
```

#### Correct

```ts
function openRecordDetail(recordId: number): void {
  void router.push({
    name: "record-detail",
    params: { id: recordId },
  });
}
```

---

## Common Mistakes

| Mistake | Why it is a problem |
|---|---|
| Putting every fetched response into one global store | Creates stale duplicated state |
| Treating URL filters as hidden store state | Makes sharing and refresh behavior poor |
| Mixing auth state with page-specific table state | Unclear ownership |
| Mirroring backend DTO shape everywhere instead of mapping once | Cross-layer coupling spreads quickly |

---

## Scenario: Streamed AI Conversation Message Ownership

### 1. Scope / Trigger

- Trigger: any change to `AiReviewChatDialog`, streamed AI chat state, placeholder assistant messages, or SSE delta application logic
- Affected layers: dialog local state -> SSE event handlers -> rendered message list

### 2. Signatures

```ts
interface AIChatMessage {
  localId: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}
```

```ts
function createChatMessage(
  role: AIChatMessage["role"],
  content: string,
): AIChatMessage;
```

### 3. Contracts

| Concern | Contract |
|---|---|
| `localId` | Frontend-only unique identifier used to update one exact rendered message |
| `createdAt` | Display timestamp only; it must not be treated as the stream update key |
| Placeholder assistant message | Must be inserted before the request starts so deltas always have a stable write target |
| Active streaming marker | Must track the assistant message by `localId`, not by array index or timestamp |
| History sent to backend | Must strip frontend-only fields and only send `role` + `content` |

Additional rules:

- the dialog may create a user message and an assistant placeholder in the same millisecond
- because of that, `createdAt` is not unique enough for stream patching
- `onDelta` and `onDone` must only mutate the assistant placeholder that belongs to the active request

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| User message and assistant placeholder share the same timestamp | Stream patch logic updates both bubbles | Update by `localId` and `role === "assistant"` |
| User switches record or closes the dialog mid-stream | Old deltas keep writing into a stale dialog | Abort the active stream and clear the active assistant message id |
| Message list is keyed by array index only | Re-rendering can patch or animate the wrong row | Key rendered rows by `localId` |
| Frontend-only `localId` leaks into API history payload | Backend receives unsupported fields | Send only the API contract fields |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | The user sends a question, the assistant placeholder is created with its own `localId`, and every delta appends only to that assistant bubble |
| Base | The stream is aborted because the dialog closes; the active message id is cleared and no stale delta is applied later |
| Bad | `createdAt` is reused as the message key, two messages collide in the same millisecond, and the AI answer is appended into the user question bubble |

### 6. Tests Required

- dialog test asserting `onDelta` updates only the targeted assistant message
- dialog test asserting same-millisecond user and assistant timestamps do not corrupt each other
- dialog test asserting abort clears the active stream marker
- API payload test asserting history sent to the backend contains `role` and `content` only

Assertion points:

- rendered row keys are stable across streaming updates
- assistant placeholder ownership survives rapid sends
- frontend-only message metadata never crosses the API boundary

### 7. Wrong vs Correct

#### Wrong

```ts
messages.value = messages.value.map((item) =>
  item.createdAt === assistantMessageCreatedAt
    ? { ...item, content: `${item.content}${deltaText}` }
    : item,
);
```

#### Correct

```ts
messages.value = messages.value.map((item) =>
  item.role === "assistant" && item.localId === assistantMessage.localId
    ? { ...item, content: `${item.content}${deltaText}` }
    : item,
);
```
