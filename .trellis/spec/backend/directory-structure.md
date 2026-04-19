# Directory Structure

> How cloud backend code should be organized in this project.

---

## Overview

Current repository evidence shows a planned cloud backend based on `FastAPI`, `SQLAlchemy`, `MySQL`, and object storage. There is no executable backend package yet, so this file defines the bootstrap directory contract for the first implementation.

Evidence in the repository:

- `工业缺陷检测系统完整方案.md` contains a `FastAPI` example with `database`, `models`, and `schemas` imports.
- `STM32MP157DAA1工业缺陷检测系统综合方案.md` defines the cloud stack as `FastAPI + MySQL + COS + Docker Compose`.

---

## Directory Layout

```text
backend/
├── src/
│   ├── app.py
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── records.py
│   │       ├── devices.py
│   │       └── parts.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── errors.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   ├── integrations/
│   │   ├── cos_client.py
│   │   └── ai_review_client.py
│   └── tasks/
├── tests/
├── alembic/
└── pyproject.toml
```

This layout is preferred over a single `main.py` with routes, database access, storage code, and AI calls mixed together.

---

## Module Organization

| Area | Responsibility |
|---|---|
| `api/routes/` | HTTP endpoints only; parse requests, call services, shape responses |
| `api/deps.py` | Shared FastAPI dependencies such as DB session, auth context, pagination |
| `services/` | Business workflows: record creation, upload orchestration, AI review, manual review |
| `repositories/` | Database read/write logic for a single aggregate or table group |
| `db/models/` | SQLAlchemy ORM models only |
| `schemas/` | Request/response DTOs and validation models |
| `integrations/` | COS, AI API, queue, cache, or other external clients |
| `core/` | Config, cross-cutting errors, security, logging bootstrap |

### Feature Rule

Use vertical features with shared infrastructure:

- `records` owns detection record APIs, service logic, repository logic, and schemas.
- `parts` owns part type metadata and sample image metadata.
- `devices` owns device registration, status sync, and firmware metadata.

Do not place business logic in `api/routes/`.

---

## Naming Conventions

| Item | Convention |
|---|---|
| Folders | `snake_case` |
| Python files | `snake_case.py` |
| Route modules | plural resource names such as `records.py`, `devices.py` |
| Service modules | workflow-oriented names such as `record_service.py`, `review_service.py` |
| Repository modules | entity-oriented names such as `record_repository.py` |
| Config modules | short cross-cutting names such as `config.py`, `security.py`, `logging.py` |

---

## Forbidden Patterns

| Pattern | Why it is forbidden |
|---|---|
| Keeping all backend code in `main.py` | Hard to test, extend, and review |
| Mixing device-side logic into cloud backend modules | The cloud backend manages records and review, not conveyor control |
| Writing uploads directly to ad-hoc root folders in production code | Object storage is already part of the chosen architecture |
| Reusing Markdown prototype snippets as production file structure | Planning examples are evidence, not final implementation layout |

---

## Examples

| Repository evidence | What it shows |
|---|---|
| `工业缺陷检测系统完整方案.md` | Imports split into `database`, `models`, and `schemas`, which supports separate layers |
| `工业缺陷检测系统完整方案.md` | Routes grouped by `/api/records/` and related actions, which suggests feature-based route modules |
| `STM32MP157DAA1工业缺陷检测系统综合方案.md` | Cloud stack explicitly separates backend, frontend, storage, and deployment concerns |
