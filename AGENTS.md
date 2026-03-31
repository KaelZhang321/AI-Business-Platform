# Repository Guidelines

## Project Structure & Module Organization
- `frontend/` – React 18 + Vite; screens in `src/pages`, shared UI `src/components`, stores `src/stores`, API clients `src/services` via alias `@/*`.
- `ai-gateway/` – FastAPI + LangChain; routers `app/api`, graphs + MCP adapters `app/services`, settings `app/core`, data models `app/models`, entry `app/main.py`.
- `business-server/` – Spring Boot 3; packages under `src/main/java/com/lzke/ai/{controller,service,mapper,adapter,config,model}` with YAML/resources in `src/main/resources`.
- `docker/` supplies the Compose stack (Postgres, Redis, Milvus, RabbitMQ, Elasticsearch, MinIO, Ollama); `docs/` stores the detailed architecture decisions.

## Build, Test & Development Commands
- Infra: inside `docker/`, copy `.env.example` to `.env`, then run `docker compose up -d` to start shared services.
- AI 网关: in `ai-gateway/`, create a Python 3.11 venv, `pip install -e .`, launch `uvicorn app.main:app --reload --port 8000`, and run `pytest` (or `pytest tests/api`) before pushing.
- 业务编排: in `business-server/`, execute `mvn spring-boot:run` for port 8080 and `mvn test` for the JUnit + MyBatis suite.
- 前端: in `frontend/`, run `npm install`, `npm run dev` (5173), and gate releases with `npm run build`, `npm run preview`, `npm run lint`.

## Coding Style & Naming Conventions
- Frontend: TypeScript `strict`, 2-space indent, PascalCase components, camelCase hooks/state, Tailwind or Ant Design tokens for styling, DTOs in `src/types`.
- AI Gateway: Python files stay `snake_case`, Ruff enforces 120-char lines, every FastAPI handler returns typed Pydantic models, run `ruff check .` + `ruff format` pre-commit.
- Business Server: namespace `com.lzke.ai`, classes UpperCamelCase, beans annotated (`@Service`, `@Component`), DTOs suffixed `Request`/`Response`, mappers suffixed `Mapper`, indent 4 spaces, avoid wildcard imports.

## Testing Guidelines
- AI Gateway: mirror the `app` layout under `ai-gateway/tests/...`, name files `test_<module>.py`, run `pytest --asyncio-mode=auto`, target ≥80% branch coverage, mock Milvus/Redis fixtures for determinism.
- Business Server: place tests in `src/test/java/com/lzke/ai/...` with `*Test` suffix, rely on SpringBootTest slices plus Testcontainers for data hits, cover mapper/service success and failure paths.
- Frontend: add Vitest + Testing Library specs under `frontend/src/__tests__` as `*.test.tsx`; until that suite lands, `npm run lint` is the minimum gating step referenced in PRs.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`type(scope): summary`) with scopes like `frontend`, `ai-gateway`, `business-server`, `docker`, `docs`; e.g., `feat(ai-gateway): add SSE streaming endpoint`.
- Keep commits atomic, describe config/schema changes in the body, and list the validation commands executed.
- PRs must state motivation, affected architecture areas, verification steps (commands + UI screenshots), linked issues, and any doc or `.env` updates.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **AI-Business-Platform** (3837 symbols, 5953 relationships, 133 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/AI-Business-Platform/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/AI-Business-Platform/context` | Codebase overview, check index freshness |
| `gitnexus://repo/AI-Business-Platform/clusters` | All functional areas |
| `gitnexus://repo/AI-Business-Platform/processes` | All execution flows |
| `gitnexus://repo/AI-Business-Platform/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
