# Repository Guidelines

## Project Structure & Module Organization
- `frontend/` – React 18 + Vite; pages stay in `src/pages`, shared UI in `src/components`, state in `src/stores`, and API clients in `src/services` (alias `@/*`).
- `ai-gateway/` – FastAPI + LangChain; routes live in `app/api`, orchestration + MCP adapters in `app/services`, runtime settings in `app/core`, and persistence models in `app/models`; entry is `app/main.py`.
- `business-server/` – Spring Boot 3; keep packages under `src/main/java/com/lzke/ai/{controller,service,mapper,adapter,config,model}` with YAML/resources in `src/main/resources`.
- `docker/` hosts the Compose stack (Postgres, Redis, Milvus, RabbitMQ, Elasticsearch, MinIO, Ollama), while `docs/` stores architecture decisions (start with `docs/AI业务中台_整体技术架构文档.md`).

## Build, Test & Development Commands
- Infra: `cd docker && cp .env.example .env && docker compose up -d` to boot all shared dependencies.
- AI 网关: `cd ai-gateway && python -m venv .venv && source .venv/bin/activate && pip install -e . && uvicorn app.main:app --reload --port 8000`; verify with `pytest` or targeted `pytest tests/api`.
- 业务编排: `cd business-server && mvn spring-boot:run` for port 8080 and `mvn test` for JUnit + MyBatis checks.
- 前端: `cd frontend && npm install && npm run dev` for port 5173; ship with `npm run build`, `npm run preview`, and `npm run lint`.

## Coding Style & Naming Conventions
- Frontend: TypeScript `strict`, 2-space indent, PascalCase component files, camelCase hooks/state, Tailwind or Ant Design tokens for styling, DTOs centralized in `src/types`.
- AI Gateway: Python 3.11 with Ruff line length 120; keep modules snake_case, return typed Pydantic models from FastAPI handlers, and run `ruff check .` plus `ruff format` before commits.
- Business Server: package prefix `com.lzke.ai`, classes UpperCamelCase, beans annotated (`@Service`, `@Component`), DTOs suffixed `Request`/`Response`, mapper interfaces suffixed `Mapper`, 4-space indent, no wildcard imports.

## Testing Guidelines
- AI Gateway: mirror `app` under `ai-gateway/tests/...`, name files `test_<module>.py`, run `pytest --asyncio-mode=auto`, aim for ≥80% branch coverage, and mock Milvus/Redis fixtures for determinism.
- Business Server: keep tests under `src/test/java/com/lzke/ai/...` with `*Test` suffix, use SpringBootTest slices + Testcontainers when touching stores, and cover mapper/service happy + failure paths.
- Frontend: place Vitest + Testing Library specs in `frontend/src/__tests__` as `*.test.tsx`; until the suite matures, `npm run lint` is the minimum gate referenced in PRs.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`type(scope): summary`) with scopes such as `frontend`, `ai-gateway`, `business-server`, `docker`, `docs`; e.g., `feat(ai-gateway): add SSE streaming endpoint`.
- Keep commits atomic, describe config or schema changes in the body, and mention the validation commands you ran.
- PRs must explain motivation, impacted architecture pieces, verification steps (commands + screenshots for UI work), linked issues, and required doc or `.env` updates.

## Security & Configuration Tips
- Never commit `.env*`; start from the provided templates in `docker/` and `frontend/`, document any new keys in PRs, and rotate keys before sharing demos.
- Keep services behind the Compose network, reuse the documented ports (5173/8000/8080/etc.), and update `docs/` whenever auth flows or connector credentials change.
