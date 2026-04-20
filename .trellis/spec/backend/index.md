# Backend Development Guidelines

> Bootstrap backend conventions for the cloud service in this project.

---

## Overview

The repository is still in a bootstrap stage. There is no runnable backend package yet.
Current backend guidance is derived from:

- `工业缺陷检测系统完整方案.md`: proposed `FastAPI + SQLAlchemy + MySQL` service and sample API snippet
- `STM32MP157DAA1工业缺陷检测系统综合方案.md`: confirmed cloud stack (`FastAPI + MySQL + COS + Docker Compose`)
- `AGENTS.md`: project-scoped instructions that apply to all generated code

These files define the initial backend contract that future code must follow.

---

## Pre-Development Checklist

Read these files before changing backend code:

- [Directory Structure](./directory-structure.md): always
- [Quality Guidelines](./quality-guidelines.md): always
- [Error Handling](./error-handling.md): when touching API handlers or integrations
- [Logging Guidelines](./logging-guidelines.md): when adding observability or background tasks
- [Database Guidelines](./database-guidelines.md): when touching models, queries, or migrations
- [Deployment Guidelines](./deployment-guidelines.md): when touching production update flow, server paths, restart procedure, or runtime deployment assumptions

If a change also affects frontend payloads or storage contracts, read:

- `../guides/cross-layer-thinking-guide.md`
- `../guides/code-reuse-thinking-guide.md`

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Bootstrap filled |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | Bootstrap filled |
| [Error Handling](./error-handling.md) | Error types, handling strategies | Bootstrap filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Bootstrap filled |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | Bootstrap filled |
| [Deployment Guidelines](./deployment-guidelines.md) | Production server alias, paths, update steps, restart and verification contract | Bootstrap filled |

---

## Notes About Evidence

- Backend examples currently come from Markdown planning documents because no backend package has been created yet.
- Once real backend files exist, update these guidelines to replace planning references with production code references.
- Do not treat prototype snippets in Markdown as permission to keep production backend code in a single file.

---

**Language**: All documentation in this directory should remain in **English**.
