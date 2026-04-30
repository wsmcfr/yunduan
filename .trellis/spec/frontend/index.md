# Frontend Development Guidelines

> Bootstrap frontend conventions for the cloud web interface in this project.

---

## Overview

The repository does not yet contain a runnable web frontend. Current frontend guidance is derived from:

- `STM32MP157DAA1工业缺陷检测系统综合方案.md`: chosen cloud frontend stack (`Vue 3 + Vite + Element Plus`)
- `工业缺陷检测系统完整方案.md`: proposed web page map and record-management flows
- `MainPagePrototype.qml`: the only real UI code in the repository, useful for naming, grouping, layout, and documentation patterns

Important distinction:

- Cloud frontend is the current priority for this repository.
- `MainPagePrototype.qml` is an embedded-device UI prototype, not the final cloud web UI.

---

## Pre-Development Checklist

Read these files before changing frontend code:

- [Directory Structure](./directory-structure.md): always
- [Component Guidelines](./component-guidelines.md): always
- [Quality Guidelines](./quality-guidelines.md): always
- [Layout Scroll Contract](./layout-scroll-contract.md): when changing shell, page roots, workspace stages, table heights, or any `height` / `overflow` CSS
- [Type Safety](./type-safety.md): when defining API models or shared types
- [State Management](./state-management.md): when state crosses pages or features
- [Hook Guidelines](./hook-guidelines.md): when adding composables or data-fetch helpers

If a change also touches API payloads or persistence, read:

- `../guides/cross-layer-thinking-guide.md`
- `../guides/code-reuse-thinking-guide.md`

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Bootstrap filled |
| [Component Guidelines](./component-guidelines.md) | Component patterns, props, composition | Bootstrap filled |
| [Hook Guidelines](./hook-guidelines.md) | Custom hooks, data fetching patterns | Bootstrap filled |
| [Layout Scroll Contract](./layout-scroll-contract.md) | Shell viewport locking and internal route scroll behavior | Active contract |
| [State Management](./state-management.md) | Local state, global state, server state | Bootstrap filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Bootstrap filled |
| [Type Safety](./type-safety.md) | Type patterns, validation | Bootstrap filled |

---

## Notes About Evidence

- There is no Vue code in the repository yet.
- `MainPagePrototype.qml` is currently the only executable UI artifact, so it is used to infer naming and composition habits.
- Planning documents define the web stack and page responsibilities, which makes them valid bootstrap evidence.

---

**Language**: All documentation in this directory should remain in **English**.
