# Deployment Guidelines

> Production server connection and update contract for this project.

---

## Overview

The current production deployment is a single Ubuntu host reached through a local SSH alias.

The most important rule is:

> use the SSH alias and the fixed server paths, not ad-hoc raw host strings or guessed directories

This avoids accidental deployment to the wrong machine and keeps update steps repeatable.

---

## Scenario: Production Server Connection and Update Flow

### 1. Scope / Trigger

- Trigger: any production deployment, hotfix upload, backend restart, frontend static asset update, or production verification step
- Affected layers: local shell -> SSH alias -> remote filesystem -> backend process -> Nginx static serving

### 2. Signatures

```powershell
ssh yunfuwu-prod
scp <local-file> yunfuwu-prod:<remote-path>
scp -r frontend/dist/* yunfuwu-prod:/opt/yunduan/frontend/dist/
ssh yunfuwu-prod 'cd /opt/yunduan/backend && python3 -m py_compile <files>'
ssh yunfuwu-prod 'curl -s http://127.0.0.1:8000/health'
```

```bash
# Remote backend start command
cd /opt/yunduan/backend
nohup /opt/yunduan/backend/.venv/bin/uvicorn src.app:app --host 127.0.0.1 --port 8000 > /opt/yunduan/backend/uvicorn.log 2>&1 < /dev/null &
```

### 3. Contracts

| Item | Contract |
|---|---|
| SSH alias | Production server alias is `yunfuwu-prod` |
| Backend root | `/opt/yunduan/backend` |
| Frontend root | `/opt/yunduan/frontend` |
| Frontend static output | `/opt/yunduan/frontend/dist` |
| Backend bind address | `127.0.0.1:8000` |
| Backend health check | `GET /health` on `http://127.0.0.1:8000/health` |
| Backend log file | `/opt/yunduan/backend/uvicorn.log` |
| Nginx role | Serves frontend static assets and proxies API requests to `127.0.0.1:8000` |
| Deployment backups | Store timestamped backups under `/opt/yunduan/deploy_backups/` for backend files, and `dist_backup_<timestamp>` for frontend static assets |
| Live frontend verification | After a frontend upload, validate either `/opt/yunduan/frontend/dist/index.html` or `curl -s http://127.0.0.1/` on the server to confirm the currently served entry HTML |

Additional rules:

- do not depend on the raw public IP in routine deployment commands; use `yunfuwu-prod`
- do not overwrite production files without a backup when changing backend source or frontend `dist`
- backend updates are not complete until `curl http://127.0.0.1:8000/health` returns `{"status":"ok"}`
- frontend updates are not complete until the new bundle reference is visible in `/opt/yunduan/frontend/dist/index.html`
- do not assume every asset hash changes on each frontend build; confirm the entry HTML now points at the expected new bundle(s)

### 4. Validation & Error Matrix

| Condition | Problem | Expected handling |
|---|---|---|
| SSH alias does not resolve | Local machine is missing the expected SSH config | Fix local `~/.ssh/config` entry for `yunfuwu-prod` before any deployment |
| Backend files uploaded but process not restarted | Old code keeps serving traffic | Restart `uvicorn` and verify `/health` |
| Backend restart hangs or fails | Production may be partially updated | Read `/opt/yunduan/backend/uvicorn.log` and verify running `uvicorn` process before asking for browser validation |
| Frontend files uploaded but browser still shows old UI | Static cache or incomplete upload | Verify `dist/index.html` points to the new bundle and hard-refresh the browser |
| Changed backend files contain syntax errors | Service fails after restart | Run `python3 -m py_compile` on the uploaded files before or immediately after restart |
| Deployment touches the wrong directory | Files appear uploaded but product does not change | Recheck the fixed paths under `/opt/yunduan/backend` and `/opt/yunduan/frontend/dist` |
| `dist/index.html` looks updated but the live page still appears stale | The operator only checked the filesystem, not what Nginx is actually serving | Run `curl -s http://127.0.0.1/` on the server and compare the served bundle reference with the file on disk |
| CSS hash did not change after a frontend-only tweak | Operator assumes the deployment failed because not every asset name rotated | Trust the entry HTML bundle references, not the expectation that both JS and CSS hashes must always change |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Use `ssh yunfuwu-prod`, back up the target, upload the changed files, run `py_compile`, restart `uvicorn`, and verify `/health` plus the new frontend bundle |
| Base | Frontend-only update: back up `/opt/yunduan/frontend/dist`, upload new `dist/*`, verify `index.html`, then hard-refresh the browser |
| Bad | Upload files directly to a guessed path with the raw IP, skip backups, skip restart, and assume the change is live without checking `/health` or logs |

### 6. Tests Required

- local command verification that `ssh yunfuwu-prod` reaches the correct host
- remote verification that `ps -ef | grep uvicorn` shows the expected backend process
- remote verification that `curl -s http://127.0.0.1:8000/health` returns success
- remote verification that `/opt/yunduan/frontend/dist/index.html` references the latest built bundle after frontend deployment
- remote verification that `curl -s http://127.0.0.1/` returns entry HTML referencing the same active frontend bundle when a UI fix is being validated live

Assertion points:

- the deployment command path always uses `yunfuwu-prod`
- uploaded backend files are placed under `/opt/yunduan/backend`
- uploaded frontend assets are placed under `/opt/yunduan/frontend/dist`
- production verification uses remote logs and health checks, not guesswork
- frontend verification checks the served entry HTML, not only the local `dist` directory contents

### 7. Wrong vs Correct

#### Wrong

```powershell
scp backend/src/services/record_service.py ubuntu@<server-ip>:/home/ubuntu/
```

```powershell
ssh yunfuwu-prod "cd /opt/yunduan/backend && cp new_file.py src/services/ && exit"
# No backup, no syntax check, no restart, no health check.
```

#### Correct

```powershell
scp backend/src/services/record_service.py yunfuwu-prod:/opt/yunduan/backend/src/services/record_service.py
ssh yunfuwu-prod 'cd /opt/yunduan/backend && python3 -m py_compile src/services/record_service.py'
ssh yunfuwu-prod 'curl -s http://127.0.0.1:8000/health'
```

```powershell
scp -r frontend/dist/* yunfuwu-prod:/opt/yunduan/frontend/dist/
ssh yunfuwu-prod 'sed -n "1,20p" /opt/yunduan/frontend/dist/index.html'
```

---

## Scenario: PowerShell-Driven Production Deployment and PDF Benchmark Flow

### 1. Scope / Trigger

- Trigger: a Windows PowerShell operator deploys backend hotfixes, uploads multiple changed files, restarts the backend, or benchmarks statistics PDF export on the production host
- Affected layers: local PowerShell quoting -> SSH/SCP transport -> remote bash execution -> backend file layout -> PDF benchmark interpretation

### 2. Signatures

```powershell
ssh yunfuwu-prod 'ts=$(date +%Y%m%d_%H%M%S); echo $ts'
scp backend/src/services/statistics_export_service.py yunfuwu-prod:/opt/yunduan/backend/src/services/statistics_export_service.py
scp backend/src/services/statistics_lightweight_pdf_renderer.py yunfuwu-prod:/opt/yunduan/backend/src/services/statistics_lightweight_pdf_renderer.py
scp backend/src/schemas/statistics.py yunfuwu-prod:/opt/yunduan/backend/src/schemas/statistics.py
scp backend/tests/test_statistics_export_service.py yunfuwu-prod:/opt/yunduan/backend/tests/test_statistics_export_service.py
scp -r frontend/dist/* yunfuwu-prod:/opt/yunduan/frontend/dist/
```

```powershell
(@'
set -euo pipefail
cd /opt/yunduan/backend
nohup /opt/yunduan/backend/.venv/bin/uvicorn src.app:app --host 127.0.0.1 --port 8000 > /opt/yunduan/backend/uvicorn.log 2>&1 < /dev/null &
'@) -replace "`r", "" | ssh yunfuwu-prod 'bash -s'
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/statistics/export-pdf \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"export_mode":"visual","include_ai_analysis":false,"include_sample_images":true,"sample_image_limit":2}'
```

### 3. Contracts

| Item | Contract |
|---|---|
| Local shell | Assume the local deployment shell is PowerShell, not bash |
| Remote command quoting | If the remote command contains `$()`, `$var`, `+%Y...`, or JSON quotes, wrap the whole SSH payload in single quotes or send a script to `bash -s` |
| Multi-line remote scripts | Normalize CRLF before piping to SSH; otherwise the remote shell can receive hidden `\r` characters and break commands such as `curl` |
| Backend file upload | When uploading a small set of backend files, target the final absolute remote file path instead of dumping files into `/opt/yunduan/backend/` and moving them later |
| Backend restart command | Use the absolute executable path `/opt/yunduan/backend/.venv/bin/uvicorn` during remote restart commands |
| Benchmark isolation | When measuring PDF renderer cost, set `include_ai_analysis=false` so AI latency does not pollute renderer timing |
| Benchmark comparison | Compare `visual` and `lightweight` exports with the same statistics window and explicit image settings |

Additional rules:

- prefer one-file-to-one-target `scp` commands for backend hotfixes
- treat a benchmark result as invalid if AI generation or unrelated uploads are running at the same time
- confirm the deployed frontend bundle by reading remote `dist/index.html`, not by trusting the local build output

Operational reference on the current production host (`2 vCPU`, measured on `2026-04-20`):

- visual PDF export with `include_ai_analysis=false`, `include_sample_images=true`, and `sample_image_limit=2` took about `18-22s` and drove CPU close to saturation
- lightweight PDF export with `include_ai_analysis=false` and `include_sample_images=false` completed in about `0.05s`
- treat these numbers as a regression baseline, not a hard SLA

### 4. Validation & Error Matrix

| Condition | Problem | Expected handling |
|---|---|---|
| PowerShell expands `$(date +%Y%m%d_%H%M%S)` locally | The remote backup timestamp command fails before SSH even reaches the server | Use single-quoted remote payloads such as `ssh yunfuwu-prod 'ts=$(date +%Y%m%d_%H%M%S); ...'` |
| Complex JSON or shell variables are embedded in a double-quoted SSH command | PowerShell and bash quoting collide | Send the script body through `bash -s` instead of stacking more escaping |
| Piped remote script keeps Windows CRLF line endings | Remote `curl` or shell commands can fail with malformed URL or syntax errors | Strip `\r` before piping the script into SSH |
| `scp` uploads several backend files to `/opt/yunduan/backend/` | Files land in the backend root instead of `src/services/`, `src/schemas/`, or `tests/` | Upload directly to the final remote file path or move the files before restart |
| Remote restart uses relative `.venv/bin/uvicorn` in a fragile shell context | `nohup` can fail to find the executable or use the wrong working directory | Restart with `/opt/yunduan/backend/.venv/bin/uvicorn` |
| PDF benchmark keeps `include_ai_analysis=true` | Measured duration reflects model latency, not PDF generation | Disable AI analysis during renderer benchmarks |
| Visual and lightweight modes use different windows or sample-image settings | Comparison is misleading | Benchmark both modes with the same date window and explicitly documented image flags |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Use exact remote target paths for backend files, strip CRLF for piped scripts, restart with absolute `uvicorn`, and benchmark both PDF modes with `include_ai_analysis=false` |
| Base | Frontend-only deployment still reads remote `index.html` afterward to verify the active bundle name |
| Bad | Use a double-quoted SSH command with `$(date ...)`, upload backend files to the project root, restart with a fragile relative command, and then compare PDF timings with AI analysis still enabled |

### 6. Tests Required

- deployment dry-run or documented command review for every changed remote file target
- remote `python3 -m py_compile` against uploaded backend files before restart
- remote `/health` check after restart
- remote `dist/index.html` inspection after frontend upload
- PDF benchmark run for both `visual` and `lightweight` modes with explicit payload snapshots

Assertion points:

- backend files are uploaded to their final module paths, not left in `/opt/yunduan/backend/`
- the restart command references `/opt/yunduan/backend/.venv/bin/uvicorn`
- benchmark payloads show `include_ai_analysis=false`
- benchmark notes record whether sample images were enabled for `visual` mode

### 7. Wrong vs Correct

#### Wrong

```powershell
ssh yunfuwu-prod "ts=$(date +%Y%m%d_%H%M%S); mkdir -p /opt/yunduan/deploy_backups/$ts"
scp backend/src/services/statistics_export_service.py backend/src/schemas/statistics.py yunfuwu-prod:/opt/yunduan/backend/
ssh yunfuwu-prod 'cd /opt/yunduan/backend && nohup .venv/bin/uvicorn src.app:app --host 127.0.0.1 --port 8000 > uvicorn.log 2>&1 < /dev/null &'
```

#### Correct

```powershell
ssh yunfuwu-prod 'ts=$(date +%Y%m%d_%H%M%S); mkdir -p /opt/yunduan/deploy_backups/$ts'
scp backend/src/services/statistics_export_service.py yunfuwu-prod:/opt/yunduan/backend/src/services/statistics_export_service.py
scp backend/src/schemas/statistics.py yunfuwu-prod:/opt/yunduan/backend/src/schemas/statistics.py
ssh yunfuwu-prod 'cd /opt/yunduan/backend && python3 -m py_compile src/services/statistics_export_service.py src/schemas/statistics.py'
```

```powershell
(@'
set -euo pipefail
cd /opt/yunduan/backend
nohup /opt/yunduan/backend/.venv/bin/uvicorn src.app:app --host 127.0.0.1 --port 8000 > /opt/yunduan/backend/uvicorn.log 2>&1 < /dev/null &
'@) -replace "`r", "" | ssh yunfuwu-prod 'bash -s'
```

---

## Scenario: Lightweight PDF Renderer Hotfix and Smoke Validation

### 1. Scope / Trigger

- Trigger: the direct-draw lightweight statistics PDF renderer changes layout, pagination, footer logic, or AI appendix page flow
- Affected layers: local unit tests -> backend source upload -> production dependency check -> backend restart -> live smoke-render verification

### 2. Signatures

```powershell
& 'D:\yunfuwu\backend\.venv\Scripts\python.exe' -m unittest tests.test_statistics_export_service
scp backend/src/services/statistics_lightweight_pdf_renderer.py yunfuwu-prod:/opt/yunduan/backend/src/services/statistics_lightweight_pdf_renderer.py
ssh yunfuwu-prod 'cd /opt/yunduan/backend && python3 -m py_compile src/services/statistics_lightweight_pdf_renderer.py'
ssh yunfuwu-prod 'cd /opt/yunduan/backend && .venv/bin/python -c "from src.services.statistics_lightweight_pdf_renderer import StatisticsLightweightPdfRenderer; StatisticsLightweightPdfRenderer()._load_reportlab(); print(\"renderer-ok\")"'
ssh yunfuwu-prod 'ss -ltnp | grep 8000 || true'
ssh yunfuwu-prod 'curl -s http://127.0.0.1:8000/health'
```

```bash
# Remote smoke-render idea:
# build a tiny fake StatisticsOverviewResponse and print
# filename / byte-size / page-count after StatisticsLightweightPdfRenderer().build_pdf(...)
```

### 3. Contracts

| Item | Contract |
|---|---|
| Local test contract | Lightweight PDF layout changes must run backend unit tests before deployment |
| Optional local dependency | Local `reportlab` is optional; pagination unit tests must still pass via fake canvas stubs |
| Production dependency | Production `.venv` must have `reportlab`; otherwise lightweight export is not deployable |
| Upload target | Renderer hotfix uploads directly to `/opt/yunduan/backend/src/services/statistics_lightweight_pdf_renderer.py` |
| Pre-restart gate | Production `py_compile` and `_load_reportlab()` import check must both pass before restart |
| Restart validation | Post-restart validation is not complete until `/health` succeeds |
| Listener validation | If restart behavior is suspicious, confirm the real port owner with `ss -ltnp`, not only `ps -ef` |
| Smoke-render contract | A smoke render should verify the renderer can generate bytes and a reasonable page count after a pagination fix |

Additional rules:

- a layout-only hotfix is not validated by syntax check alone; it still needs one renderer import check and one smoke render
- do not treat "PDF bytes returned" as enough proof when the bug class is pagination or clipping
- when AI appendix pages are involved, expect later-page counts to increase beyond the base summary pages

### 4. Validation & Error Matrix

| Condition | Problem | Expected handling |
|---|---|---|
| Local machine lacks `reportlab` | Visual render cannot be replayed locally | Run fake-canvas unit tests locally and reserve real render validation for the server |
| `py_compile` passes but `_load_reportlab()` fails | Source is syntactically valid, but runtime dependency is missing | Install or restore `reportlab` in production `.venv` before restart |
| Health check fails right after restart | Service may still be starting or may have crashed | Inspect `uvicorn.log`, then verify process/listener state before retrying |
| Multiple `uvicorn` PIDs appear after restart | `ps` output alone is ambiguous | Use `ss -ltnp | grep 8000` to see which PID actually owns the listener |
| Smoke render returns too few pages after a pagination fix | Supporting sections may still be squeezed into the first pages | Recheck explicit `showPage()` boundaries and later-page section titles |
| Smoke render succeeds but the PDF still looks crowded | Logical pagination passed, but visual hierarchy is weak | Adjust block heights, fonts, or per-page section split, then rerun smoke validation |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Run local unit tests, upload the renderer file, pass remote `py_compile`, pass `_load_reportlab()`, restart, verify `/health`, then run a smoke render and confirm page count |
| Base | For a small footer-only fix, still run local pagination tests and the remote import check before relying on manual PDF review |
| Bad | Upload the renderer, skip dependency validation, skip smoke render, and assume the layout is fixed because the endpoint still returns a PDF file |

### 6. Tests Required

- local backend unit test run for `tests.test_statistics_export_service`
- local assertion that fake-canvas tests cover summary-page and AI-page pagination behavior
- remote `py_compile` against `src/services/statistics_lightweight_pdf_renderer.py`
- remote renderer import + `_load_reportlab()` check
- remote `/health` check after restart
- remote smoke render that reports at least filename, byte size, and page count for a sample lightweight PDF

Assertion points:

- pagination tests do not depend on local `reportlab`
- production runtime can import the renderer and resolve `reportlab`
- the restarted backend is healthy on `127.0.0.1:8000`
- the smoke render proves the renderer can still produce multi-page output after the hotfix

### 7. Wrong vs Correct

#### Wrong

```powershell
scp backend/src/services/statistics_lightweight_pdf_renderer.py yunfuwu-prod:/opt/yunduan/backend/src/services/statistics_lightweight_pdf_renderer.py
ssh yunfuwu-prod 'cd /opt/yunduan/backend && python3 -m py_compile src/services/statistics_lightweight_pdf_renderer.py'
# Assume success and stop here.
```

#### Correct

```powershell
& 'D:\yunfuwu\backend\.venv\Scripts\python.exe' -m unittest tests.test_statistics_export_service
scp backend/src/services/statistics_lightweight_pdf_renderer.py yunfuwu-prod:/opt/yunduan/backend/src/services/statistics_lightweight_pdf_renderer.py
ssh yunfuwu-prod 'cd /opt/yunduan/backend && python3 -m py_compile src/services/statistics_lightweight_pdf_renderer.py'
ssh yunfuwu-prod 'cd /opt/yunduan/backend && .venv/bin/python -c "from src.services.statistics_lightweight_pdf_renderer import StatisticsLightweightPdfRenderer; StatisticsLightweightPdfRenderer()._load_reportlab(); print(\"renderer-ok\")"'
ssh yunfuwu-prod 'curl -s http://127.0.0.1:8000/health'
```

---

## Scenario: GitHub Push Secret Hygiene and Safe Defaults

### 1. Scope / Trigger

- Trigger: any `git add`, `git commit`, `git push`, GitHub sync, or “准备把当前改动发到远端仓库” 的场景
- Affected layers: local working tree -> staged diff -> tracked docs/spec -> runtime config defaults -> remote GitHub history

### 2. Signatures

```powershell
git status --short
git diff --cached --stat
git log --oneline -1
git push origin main
```

```powershell
rg -n --hidden --glob '!.git/**' --glob '!node_modules/**' --glob '!frontend/dist/**' --glob '!ziliao/**' 'AKID[0-9A-Za-z]+'
rg -n --hidden --glob '!.git/**' --glob '!node_modules/**' --glob '!frontend/dist/**' --glob '!ziliao/**' '(JWT_SECRET_KEY|SECRET_ENCRYPTION_KEY|PASSWORD_PEPPER|COS_SECRET_ID|COS_SECRET_KEY)'
rg -n --hidden --glob '!.git/**' --glob '!node_modules/**' --glob '!frontend/dist/**' --glob '!ziliao/**' '(sk-[A-Za-z0-9_-]+|-----BEGIN)'
```

```env
backend/.env                 # Must stay gitignored
backend/.env.example         # May only contain placeholders / non-secret examples
DEFAULT_ADMIN_PASSWORD=
SECRET_ENCRYPTION_KEY=replace_me
PASSWORD_PEPPER=replace_me
```

### 3. Contracts

| Item | Contract |
|---|---|
| `backend/.env` | Must remain ignored and must never be staged or committed |
| `backend/.env.example` | May document required env keys, but values must be placeholders such as `replace_me` or `change_me_*`, never production secrets |
| Docs / specs / screenshots | Must not include real passwords, real API keys, real public server IPs, or operator-only account hints |
| Source-code defaults for secrets | Secret-like config defaults must be empty or explicit placeholders, not predictable working credentials |
| Default admin bootstrap | If `DEFAULT_ADMIN_PASSWORD` is absent or blank, seed scripts must skip creating a default admin instead of silently using a baked-in password |
| Secret-handling code | It is allowed to commit password hashing, cookie session, encryption, and decryption logic; the forbidden part is committing real secret material or reversible data derived from production secrets |
| Test fixtures | Demo tokens and fake API keys may exist in tests only when they are clearly fake values such as `sk-demo-*`, never copied from production |
| Push gate | Before `git push`, the staged diff must be reviewed specifically for secrets, unsafe defaults, and docs/spec leakage |

Additional rules:

- if a spec example needs to mention credentials or a server address, use placeholders such as `<real-production-password>` or `<server-ip>`
- do not assume “already encrypted” means safe to commit; if the committed data can still expose the real runtime secret or operator identity, it must be removed
- do not keep a real admin password as a fallback default in `config.py`, seed scripts, or frontend helper text
- when a push includes auth, secret storage, COS, SMTP, or AI gateway changes, run an extra manual review of `.env.example`, spec docs, and staged tests before pushing

### 4. Validation & Error Matrix

| Condition | Problem | Expected handling |
|---|---|---|
| `git diff --cached` or `rg` finds a real password / API key / cloud secret | Sensitive material is about to enter immutable Git history | Remove it, replace with placeholders, then restage before commit |
| A spec or guideline file contains the real public server IP or real operator credential pair | Documentation leaks production access information | Replace with SSH alias or placeholder text before pushing |
| `config.py` contains a usable default admin password | Fresh deployments may expose a predictable privileged account | Replace with empty default and require env-provided password |
| Admin seed script still creates an account when password env is blank | Public deployment can accidentally boot with an unsafe fallback | Skip bootstrap and print an explicit operator message |
| Test files contain obvious demo keys such as `sk-demo-*` | These are not real secrets, but they resemble secrets syntactically | Keep only if they are clearly fake and scoped to tests |
| Code adds hashing/encryption helpers | This is security implementation, not a secret leak by itself | Allow commit as long as actual secret values stay in ignored env/config stores |

### 5. Good / Base / Bad Cases

| Case | Example |
|---|---|
| Good | Push includes auth hardening and secret-storage code, but `.env` stays ignored, `.env.example` uses placeholders, docs use `<server-ip>`, and the commit is scanned before `git push` |
| Base | Tests contain `sk-demo-codex` and similar fake tokens under `backend/tests`, while production secrets stay only in runtime env |
| Bad | A commit pushes real COS keys, a real public admin password in a spec screenshot/example, or a working default admin password baked into source defaults |

### 6. Tests Required

- staged-diff review via `git diff --cached --stat` and targeted file inspection before `git commit`
- repository secret scan using `rg` for cloud-key, JWT-secret, PEM, and API-key shaped patterns before `git push`
- backend test run after changing auth/seed/config defaults, at minimum covering auth smoke paths
- frontend build/test run if login helper copy, auth UI hints, or public-facing docs embedded in frontend code changed
- post-commit verification that `git status --short` is clean and the commit message matches the reviewed safe change set

Assertion points:

- no real runtime secret or operator credential is present in tracked files
- secret defaults in source are blank or placeholders rather than working credentials
- admin bootstrap behavior is safe when password env is missing
- committed security code does not include the actual env values that make decryption or authentication possible

### 7. Wrong vs Correct

#### Wrong

```python
default_admin_password: str = Field(default="admin123", alias="DEFAULT_ADMIN_PASSWORD")
```

```markdown
管理员账号：admin / <real-password>
服务器：119.91.xx.xx
```

#### Correct

```python
default_admin_password: str = Field(default="", alias="DEFAULT_ADMIN_PASSWORD")
```

```python
if not settings.default_admin_password.strip():
    print("未配置 DEFAULT_ADMIN_PASSWORD，跳过默认管理员初始化。")
    return
```

```markdown
管理员账号：admin / <real-production-password>
服务器：yunfuwu-prod 或 <server-ip>
```

---

## Deployment Sequence

### Backend Hotfix Sequence

1. Back up the target backend files into `/opt/yunduan/deploy_backups/<timestamp>/`
2. Upload the changed files with `scp`
3. Run `python3 -m py_compile` against the uploaded files
4. Restart the backend process in `/opt/yunduan/backend` with `/opt/yunduan/backend/.venv/bin/uvicorn`
5. Check `/opt/yunduan/backend/uvicorn.log`
6. Check `curl -s http://127.0.0.1:8000/health`

### Frontend Update Sequence

1. Build locally in `frontend/`
2. Back up the current `/opt/yunduan/frontend/dist`
3. Upload the new `dist/*`
4. Inspect `/opt/yunduan/frontend/dist/index.html`
5. Refresh the browser and confirm the new bundle is active

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Using the raw server IP as the normal deployment target | Easy to mistype and bypasses the agreed machine alias |
| Updating production without a backup | Makes rollback and root-cause comparison harder |
| Restarting backend without a health check | Can leave a broken service unnoticed |
| Declaring frontend deployment complete without checking `dist/index.html` | Browser cache and partial uploads can hide the real server state |
| Guessing production paths such as `/home/ubuntu/project` | The real deploy roots are fixed under `/opt/yunduan/` |
