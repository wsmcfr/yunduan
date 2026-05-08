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

## Scenario: Management List Pagination and Derived Resource Refresh

### 1. Scope / Trigger

- Trigger: any change to a server-paginated management page such as `RecordsPage`, `PartsPage`, `DevicesPage`, system users, gateway/model lists, or other table pages that show resource summary cards derived from backend data.
- Affected layers: page-local pagination state -> API query `skip/limit` -> table rows -> derived cards/options/summary resources -> destructive or create/update actions.

### 2. Signatures

```ts
const pageSize = ref(10);
const currentPage = ref(1);

async function loadDevices(): Promise<void>;
async function loadParts(): Promise<void>;
async function refreshRecordsView(): Promise<void>;

async function handlePageChange(page: number): Promise<void>;
async function handlePageSizeChange(nextPageSize: number): Promise<void>;
```

```vue
<ElPagination
  background
  layout="sizes, prev, pager, next, total"
  :page-size="pageSize"
  :page-sizes="[10, 20, 50, 100]"
  :total="total"
  :current-page="currentPage"
  @size-change="handlePageSizeChange"
  @current-change="handlePageChange"
/>
```

```ts
async function refreshRecordsView(): Promise<void> {
  await Promise.all([loadOptions(), refresh()]);
}
```

### 3. Contracts

| Concern | Owner | Contract |
|---|---|---|
| Page-size UI | Every server-paginated management page | Expose `sizes` in `ElPagination`, with `[10, 20, 50, 100]` unless the backend route documents a smaller max |
| Page-size state | Page or feature composable | `handlePageSizeChange(nextPageSize)` updates `pageSize`, resets `currentPage` to `1`, then reloads from the backend |
| Page change state | Page or feature composable | `handlePageChange(page)` updates `currentPage`, then reloads from the backend |
| Derived resource cards | Page-level server state | Cards such as category entry, record count, image count, latest upload, and source device must come from freshly loaded backend resource data |
| Mutations that affect summaries | Mutation handler | After delete/create/update/toggle, refresh every server resource used by the visible page, not only the table rows |
| Manual refresh button | Page-level action | Refresh both the main list and its derived resource options/cards when the page renders those resources together |

Additional rules:

- do not assume that a table reload refreshes category cards if those cards are computed from a separate `parts`, `devices`, `users`, or options request
- do not locally subtract totals, record counts, image counts, or category counts after destructive actions; reload the server snapshot
- if a page shows a "current page" category rail, changing page size should reset the selected category to the all/default entry unless the category is backed by a full independent resource list
- if `loadOptions()` feeds both dropdowns and visual cards, manual refresh and destructive actions must call it too

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| `pageSize` is sent as `limit`, but `ElPagination` omits `sizes` | The backend supports page-size changes, but users cannot control it | Add `layout="sizes, prev, pager, next, total"` and `@size-change` |
| Page size changes while the old `currentPage` is kept | `skip` can jump to an unexpected window or an empty page | Reset `currentPage = 1` before reload |
| Record delete only calls `refresh()` for the record table | Category cards based on `parts` still show stale record/image counts | Call a combined refresh such as `refreshRecordsView()` that reloads options/cards and table data |
| Device delete removes records, but devices page is not reloaded | Record count and image metadata shown in the row stay stale | Reload the devices list after delete succeeds |
| Part status toggle reloads the table but keeps an invalid selected category | Detail table and category card can point at different resource slices | Reset or validate the selected category after the backend reload |
| Manual refresh only reloads table rows | User-visible cards continue to show stale resources | Wire refresh button to the same combined resource refresh used after mutations |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | `DevicesPage` exposes page-size selection, sets `pageSize`, resets page to `1`, and reloads devices with the new `limit` |
| Good | `RecordsPage` deletes one record, then reloads both `fetchParts({ limit: 100 })` / `fetchDevices({ limit: 100 })` and the current records query so category cards and table rows agree |
| Base | A simple list page with no derived cards still exposes page-size selection and refreshes the list after mutation |
| Bad | `PartsPage` has `pageSize = ref(10)` and sends `limit`, but the footer only shows `prev, pager, next, total` so the user cannot change it |
| Bad | A delete handler hides the row locally or refreshes only the table, leaving category entry cards with old counts and latest-upload timestamps |

### 6. Tests Required

- page/source regression test asserting every management page with server pagination includes `layout="sizes, prev, pager, next, total"`, `:page-sizes="[10, 20, 50, 100]"`, and `@size-change="handlePageSizeChange"`
- page/source or composable test asserting `handlePageSizeChange()` sets the new `pageSize`, resets `currentPage` to `1`, and calls the backend loader
- page/source or behavior test asserting record delete calls a combined resource refresh, not only the table refresh
- page behavior test for any page with category cards asserting mutation refreshes the card source data and visible table data together

Assertion points:

- the backend `limit` has a visible page-size control in the UI
- page-size changes never preserve an incompatible `skip` window
- cards and tables converge on the same backend snapshot after create/delete/update/toggle
- manual refresh uses the same broad refresh path as mutation success when derived resource cards are present

### 7. Wrong vs Correct

#### Wrong

```vue
<ElPagination
  background
  layout="prev, pager, next, total"
  :page-size="pageSize"
  :total="total"
  :current-page="currentPage"
  @current-change="handlePageChange"
/>
```

```ts
async function handleDeleteRecord(record: DetectionRecordModel): Promise<void> {
  await deleteRecord(record.id);
  await refresh();
}
```

#### Correct

```vue
<ElPagination
  background
  layout="sizes, prev, pager, next, total"
  :page-size="pageSize"
  :page-sizes="[10, 20, 50, 100]"
  :total="total"
  :current-page="currentPage"
  @size-change="handlePageSizeChange"
  @current-change="handlePageChange"
/>
```

```ts
async function handlePageSizeChange(nextPageSize: number): Promise<void> {
  pageSize.value = nextPageSize;
  currentPage.value = 1;
  await loadDevices();
}
```

```ts
async function refreshRecordsView(): Promise<void> {
  await Promise.all([loadOptions(), refresh()]);
}

async function handleDeleteRecord(record: DetectionRecordModel): Promise<void> {
  await deleteRecord(record.id);
  await refreshRecordsView();
}
```

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
  handlePageSizeChange: (pageSize: number) => Promise<void>;
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
| Records list page-size selection | `useRecordsList.handlePageSizeChange(...)` | Update `pageSize`, reset `currentPage` to `1`, and reload from the backend |
| Record detail data | `RecordDetailPage` | Detail request, reload, and display state stay local to the page |
| Manual review form state | `ManualReviewFormCard` + `RecordDetailPage` | Form fields stay local, submit action is emitted upward |
| AI review trigger | `RecordDetailPage` | Only available from record detail, not parts master pages |
| Part master data | `PartsPage` | Maintains metadata only, not review workflow |

Additional rules:

- `applyFilters()` and `resetFilters()` must reset `currentPage` to `1`
- `handlePageSizeChange()` must reset `currentPage` to `1` because the `skip` window changes when the page size changes
- records pages act as screening and navigation pages
- record detail pages act as the review workspace
- a manual review success must be followed by detail reload so that `effectiveResult` and review history stay in sync

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| Filters change but page is not reset | Query can point past the valid result window | Reset to page `1` before refresh |
| Page size changes but page is not reset | `skip` can jump into a surprising window or past the end of the result set | Set `currentPage = 1` before refreshing |
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
- composable test asserting `handlePageSizeChange()` updates `pageSize`, resets the page to `1`, and refreshes
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

## Scenario: Cookie-Based Auth Session Ownership

### 1. Scope / Trigger

- Trigger: any change touching login, register, logout, password reset, route guards, or auth runtime options
- Affected layers: backend auth cookie -> frontend auth API -> `useAuthStore` -> router guards -> public auth pages

### 2. Signatures

```ts
export function useAuthStore(): {
  currentUser: UserProfile | null;
  isReady: boolean;
  isAuthenticated: boolean;
  login: (account: string, password: string) => Promise<void>;
  register: (payload: {
    username: string;
    displayName: string;
    email: string;
    password: string;
  }) => Promise<void>;
  restoreSession: () => Promise<void>;
  logout: () => Promise<void>;
};
```

### 3. Contracts

| Concern | Owner | Contract |
|---|---|---|
| Access token / session cookie | backend + browser | Stored in `HttpOnly Cookie`; frontend must not persist it in `localStorage` |
| Current user identity | `useAuthStore` | Frontend global auth state only needs `currentUser` + readiness |
| Session restore | router guard + `useAuthStore` | First protected navigation calls `restoreSession()` once before auth branching |
| Logout | `useAuthStore` | Must clear frontend user state even if the backend logout request fails |
| Public auth capabilities | login page local state | Registration / forgot-password availability comes from runtime options, not hard-coded assumptions |

Additional rules:

- do not add a readable `token` field back into the auth store after migrating to server cookies
- do not mix auth session flags into records, statistics, or settings feature composables
- password form values may exist transiently in page-local form state, but they must not be persisted across reloads

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| Browser refreshes on a protected page | Auth store has no readable local token anymore | `restoreSession()` fetches `/auth/me` and rebuilds `currentUser` |
| `/auth/me` returns `401` during restore | Stale or missing cookie | Frontend clears `currentUser` and routes to login |
| Backend logout request fails | Browser or network glitch | Frontend still clears local user state to avoid a half-logged-out UI |
| Public login page assumes registration is enabled | Environment may disable public sign-up | Read `/auth/runtime-options` and render a disabled state instead of a fake working form |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Auth store keeps only `currentUser`, `isReady`, and async auth actions while the browser owns the cookie |
| Base | Runtime options request fails, so the login page falls back to safe defaults without crashing |
| Bad | Frontend reintroduces `localStorage` token persistence after the project has moved to `HttpOnly Cookie` auth |

### 6. Tests Required

- store test asserting login fills `currentUser` without exposing a frontend token field
- store test asserting register sets `isReady`
- store test asserting restore failure clears auth state safely
- store test asserting logout clears local state even when the request is async

### 7. Wrong vs Correct

#### Wrong

```ts
window.localStorage.setItem("auth-token", response.access_token);
token.value = response.access_token;
```

#### Correct

```ts
const response = await loginRequest({ account, password });
currentUser.value = mapUserProfileDto(response.user);
```

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

---

## Scenario: Statistics AI Workspace Message Ownership

### 1. Scope / Trigger

- Trigger: any change to `useStatisticsOverview`, the statistics AI analysis panel in `StatisticsPage.vue`, follow-up question rendering, or statistics PDF export snapshot building
- Affected layers: statistics composable state -> statistics page analysis body / follow-up conversation panels -> export payload mapping

### 2. Signatures

```ts
const aiAnalysis = ref<StatisticsAIAnalysisResponse | null>(null);
const aiMessages = ref<AIChatMessage[]>([]);
const visibleAiMessages = computed<AIChatMessage[]>(() => {
  const firstUserMessageIndex = aiMessages.value.findIndex((item) => item.role === "user");
  if (firstUserMessageIndex < 0) {
    return [];
  }

  return aiMessages.value.slice(firstUserMessageIndex);
});
```

```ts
async function runAiAnalysis(): Promise<void>;
async function submitAiQuestion(): Promise<void>;
function resolveExportConversationMessages(): AIChatMessage[];
function buildExportConversationSnapshot(): StatisticsExportConversationMessageDto[];
```

### 3. Contracts

| Concern | Owner | Contract |
|---|---|---|
| First-round batch analysis snapshot | `aiAnalysis` | Owns the standalone statistics analysis answer, provider hint, status, and generated time shown in the "本轮 AI 批次分析" block |
| Full statistics AI timeline | `aiMessages` | Keeps the full message history for the current statistics window, including the assistant placeholder created by `runAiAnalysis()` before any follow-up question exists |
| Rendered follow-up conversation | `visibleAiMessages` | Starts from the first user message only, so the standalone batch analysis text is not rendered again inside the follow-up area |
| Follow-up streaming placeholder | `visibleAiMessages` + `aiMessages` | After the first follow-up question exists, empty assistant placeholder rows must stay visible so the UI can show "思考中" / streaming states |
| Export conversation payload | `resolveExportConversationMessages()` / `buildExportConversationSnapshot()` | Exported follow-up history must start from the first user message; the standalone batch analysis answer is exported separately via cached AI analysis fields |

Additional rules:

- `runAiAnalysis()` may seed `aiMessages` with a single assistant placeholder before any user follow-up exists
- statistics follow-up UI must bind to `visibleAiMessages`, not directly to `aiMessages`
- `aiAnalysis.answer` must not be copied into `visibleAiMessages`, otherwise the first analysis body will appear twice on the page
- statistics PDF export may include both `cached_ai_answer` and `cached_ai_conversation`, but they serve different purposes and must not be merged into one display list

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| `runAiAnalysis()` creates an assistant placeholder before any user message | The follow-up panel shows the first analysis answer even though the user has not asked a follow-up yet | `visibleAiMessages` returns `[]`, and the page shows the standalone analysis block plus an empty-state follow-up panel |
| Follow-up panel renders `aiMessages` directly | First analysis text duplicates into the conversation area and the layout looks broken | Follow-up panel renders `visibleAiMessages` only |
| Export uses the full `aiMessages` array | PDF duplicates the first analysis body inside the follow-up transcript | Export conversation starts from the first user message, while cached analysis answer is passed separately |
| First follow-up is sent and the assistant placeholder is still empty | User cannot see that the follow-up request is running | Keep the assistant placeholder in `visibleAiMessages` so the UI can show the streaming state |
| Only follow-up messages exist as stable AI content during export | PDF loses all AI content because there is no final `aiAnalysis.answer` snapshot | Fallback export logic may promote the first assistant follow-up reply into the cached AI snapshot, while conversation payload still follows the first-user-message rule |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | `StatisticsPage.vue` shows `aiAnalysis.answer` in the analysis body and renders only `visibleAiMessages` inside the follow-up transcript |
| Base | The user generates a batch analysis but never asks a follow-up question, so the follow-up panel stays in a compact empty state |
| Bad | The first assistant analysis reply is inserted directly into the follow-up transcript, causing the page to show AI analysis text before any user follow-up exists |

### 6. Tests Required

- composable test asserting `visibleAiMessages` is empty after `runAiAnalysis()` seeds only the assistant placeholder
- composable test asserting `visibleAiMessages` keeps the empty assistant placeholder after the first follow-up user message is added
- composable/export test asserting `buildExportConversationSnapshot()` excludes assistant-only prelude messages and starts at the first user question
- page test asserting the statistics analysis body and the follow-up transcript render independently

Assertion points:

- first-round analysis and follow-up conversation have separate ownership
- the UI keeps follow-up streaming affordances without leaking the main analysis body into the transcript
- PDF/export payload uses separate fields for summary analysis and follow-up history

### 7. Wrong vs Correct

#### Wrong

```ts
const conversationMessages = computed(() => aiMessages.value);
```

#### Correct

```ts
const visibleAiMessages = computed<AIChatMessage[]>(() => {
  const firstUserMessageIndex = aiMessages.value.findIndex((item) => item.role === "user");
  if (firstUserMessageIndex < 0) {
    return [];
  }

  return aiMessages.value.slice(firstUserMessageIndex);
});
```

---

## Scenario: Settings Password Request Ownership

### 1. Scope / Trigger

- Trigger: any change to the account-security card in `SettingsPage.vue`, the current-user password-request flow, or the admin user-management actions that approve/reject password requests
- Affected layers: settings page local refs -> settings API service -> DTO mapper -> settings page table/card rendering

### 2. Signatures

```ts
const passwordRequestLoading = ref(false);
const passwordRequestSubmitting = ref(false);
const passwordRequestInfo = ref<UserPasswordChangeRequestInfo | null>(null);
const passwordRequestForm = ref({
  newPassword: "",
  confirmPassword: "",
});
const updatingUserIds = ref<number[]>([]);
```

```ts
async function loadCurrentUserPasswordRequestInfo(): Promise<void>;
async function handleRequestDefaultPasswordReset(): Promise<void>;
async function handleSubmitRequestedPasswordChange(): Promise<void>;
async function handleResetUserPassword(user: SystemUserListItem): Promise<void>;
async function handleApproveUserPasswordRequest(user: SystemUserListItem): Promise<void>;
async function handleRejectUserPasswordRequest(user: SystemUserListItem): Promise<void>;
```

### 3. Contracts

| Concern | Owner | Contract |
|---|---|---|
| Current user password-request snapshot | `SettingsPage.vue` local state | `passwordRequestInfo` is page-local and is refreshed from `/api/v1/settings/users/me/password-request` |
| Current user password form fields | `SettingsPage.vue` local state | `passwordRequestForm.newPassword` and `confirmPassword` stay local only and must be cleared after a successful submit |
| Current user loading/submitting flags | `SettingsPage.vue` local state | `passwordRequestLoading` and `passwordRequestSubmitting` only block the account-security card, not the whole settings page |
| Admin row action loading | `SettingsPage.vue` local state | `updatingUserIds` tracks row-level mutations by `userId` so one approve/reject/status action does not freeze the entire table |
| Auth identity | `useAuthStore` | Auth store still owns only the logged-in identity, not password-request drafts or admin row progress |
| Server-backed user table data | settings page list loader | Admin table rows may include password-request summary fields, but the mutation in-flight markers stay local to the page |
| Admin direct password reset | `SettingsPage.vue` local row action | Uses the same `updatingUserIds` guard as approve/reject/status/delete, succeeds even without a pending request, and refreshes the user table after the backend applies the reset |

Additional rules:

- do not move pending-password drafts into Pinia, `localStorage`, or URL query params
- do not reuse one page-wide boolean for every admin row mutation
- after a successful current-user submit, reload `passwordRequestInfo` from the backend instead of synthesizing status locally
- after an admin approve/reject/direct-reset action, refresh the affected user table data and, when needed, the current-user panel so both views converge on the same backend snapshot

### 4. Validation & Error Matrix

| Condition | Problem | Expected behavior |
|---|---|---|
| Current user already has a pending request | Repeated submit can overwrite the intended target password in UI memory | Keep the existing snapshot, surface the backend error, and leave the local form disabled by the pending-state guard |
| Admin row action uses a single global loading flag | One row action blocks every user-management button | Track loading by `userId` in `updatingUserIds` |
| Admin direct reset is hidden unless `passwordChangeRequestStatus === "pending"` | Admin cannot recover a member account unless the member asks first | Show direct reset as a normal admin row action, while keeping approve/reject conditional on pending requests |
| Current user password draft is stored in a global store | Sensitive text can leak across routes or survive longer than necessary | Keep the draft in page-local refs only |
| Submit succeeds but the page does not refetch the snapshot | UI can show stale status or old reviewed time | Reload the current-user request info after success |
| Page is left or session changes | Old request snapshot can belong to a different session/company | Clear page-local password-request state on teardown or auth reset |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | `SettingsPage.vue` owns the password-request card state locally, submits through the settings API, then refetches the latest request snapshot |
| Base | A non-admin user can only see their own request card; no admin row-action state exists in that view |
| Base | Admin direct reset remains visible for normal member rows even when `passwordChangeRequestStatus` is `null` |
| Bad | Direct reset is rendered inside the pending-request branch, so admins cannot reset a member until that member first submits an application |
| Bad | Requested password text is moved into a Pinia store or reused across page navigations because the feature wants "shared state" |

### 6. Tests Required

- page test asserting successful submit clears `passwordRequestForm` and refreshes `passwordRequestInfo`
- page test asserting pending request state disables the current-user submit buttons
- page test asserting `updatingUserIds` only blocks the targeted admin row while other rows remain interactive
- page test asserting current-user password-request state is not persisted in auth/global store state

Assertion points:

- sensitive draft password text does not outlive the settings page
- current-user status comes from the backend snapshot, not optimistic local fabrication
- admin row updates are scoped by `userId`

### 7. Wrong vs Correct

#### Wrong

```ts
// Sensitive draft password is promoted to global state.
export const useSettingsStore = defineStore("settings", () => {
  const requestedPassword = ref("");
  return { requestedPassword };
});
```

#### Correct

```ts
const passwordRequestForm = ref({
  newPassword: "",
  confirmPassword: "",
});

const updatingUserIds = ref<number[]>([]);
```

#### Wrong

```ts
// Direct reset is an admin recovery action, not a pending-request-only action.
if (hasPendingPasswordChangeRequest(user)) {
  renderResetPasswordButton(user);
}
```

#### Correct

```ts
renderResetPasswordButton(user);

if (hasPendingPasswordChangeRequest(user)) {
  renderApprovePasswordRequestButton(user);
  renderRejectPasswordRequestButton(user);
}
```
