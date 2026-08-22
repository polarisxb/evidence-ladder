<!-- PR 标题请用 Conventional Commits 风格，例如 feat(scope): ... / fix: ... / chore: ... -->

## Summary / 概述

<!-- 改了什么、为什么改（高信噪比，别复述 diff）。 -->

## Changes / 主要改动

-

## Verification / 验证

<!-- 本地怎么验的；CI 会自动跑 backend pytest + ruff + frontend vitest/build。 -->

- [ ] `cd backend && pytest app/tests tests` 通过
- [ ] `cd backend && ruff check app tests conftest.py` 通过
- [ ] `cd frontend && npm run test` 通过
- [ ] `cd frontend && npm run build` 通过

## Out of scope / 不在本次范围

<!-- 故意没做的事，避免 reviewer 误以为遗漏。 -->
