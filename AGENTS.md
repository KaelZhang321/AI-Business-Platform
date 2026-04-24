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
# GitNexus MCP

This project is indexed by GitNexus as **AI-Business-Platform** (5114 symbols, 14467 relationships, 300 execution flows).

## Always Start Here

1. **Read `gitnexus://repo/{name}/context`** — codebase overview + check index freshness
2. **Match your task to a skill below** and **read that skill file**
3. **Follow the skill's workflow and checklist**

> If step 1 warns the index is stale, run `npx gitnexus analyze` in the terminal first.

## Skills

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
