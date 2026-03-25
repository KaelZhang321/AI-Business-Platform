# AI Gateway Docker Deployment Implementation Plan

Date: 2026-03-25

Related design:
- [`2026-03-25-ai-gateway-docker-deployment-design.md`](/Users/smart/PycharmProjects/AI-Business-Platform/docs/plans/2026-03-25-ai-gateway-docker-deployment-design.md)

## Background

This implementation plan turns the approved Docker deployment design for `ai-gateway` into an executable file-level work plan.

The deployment target is a CentOS 7 server with an older GCC toolchain. The implementation must avoid host-level Python build requirements by building and running the Python service inside Docker. The approved deployment model is:

- keep the current infrastructure Compose file focused on shared dependencies
- add a separate Compose file for `ai-gateway`
- expose `ai-gateway` directly on host port `8000`
- do not connect `ai-gateway` to the current Nginx container
- use a single `.env` source of truth
- prewarm BGE models during image build
- deliver the change as a single atomic commit

## Scope

### In Scope

- add a Dockerfile for `ai-gateway`
- add a dedicated Compose file for `ai-gateway`
- update the infrastructure Compose file only as needed for shared network support
- update the environment template for container-safe values
- document validation steps and expected operator commands

### Out Of Scope

- Nginx reverse proxy integration
- host-side startup scripts
- application business logic refactors
- autoscaling, rolling updates, or registry push workflows
- splitting environment management into multiple `.env` files

## Target Deliverables

- [`ai-gateway/Dockerfile`](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/Dockerfile)
- [`docker/docker-compose.ai-gateway.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.ai-gateway.yml)
- updates to [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml)
- updates to [`docker/.env.example`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/.env.example)
- this implementation plan document

## Execution Strategy

The implementation should follow the approved "minimum runnable path first" strategy:

1. establish shared network support
2. define the application Compose file
3. implement the Docker build chain
4. add model prewarming and cache controls
5. align environment template values with container networking
6. validate with static checks and minimum runtime checks

Although the execution order is phased, all resulting code changes are intended to be merged as one atomic commit.

## File-Level Task List

### 1. Update `docker/docker-compose.yml`

Purpose:
- add an explicit named Docker network that can be shared by the infrastructure stack and the `ai-gateway` application stack

Expected changes:
- declare a top-level named network
- attach required infrastructure services to that network if needed by the chosen Compose structure
- avoid mixing `ai-gateway` service definitions into this file

Completion criteria:
- `docker compose -f docker/docker-compose.yml config` succeeds
- the file still represents an infrastructure-only stack
- the network can be referenced externally by the application Compose file

### 2. Add `docker/docker-compose.ai-gateway.yml`

Purpose:
- define the runtime contract for the Python application container

Expected changes:
- add `ai-gateway` service definition
- include `build` context pointing to `ai-gateway`
- expose `8000:8000`
- load environment from the shared `.env`
- join the shared external Docker network
- add `restart` policy
- add container health check against `http://localhost:8000/health`

Recommended service fields:
- `build`
- `image`
- `container_name`
- `ports`
- `env_file`
- `environment`
- `healthcheck`
- `restart`
- `networks`

Completion criteria:
- `docker compose -f docker/docker-compose.ai-gateway.yml config` succeeds
- the service can theoretically start independently once the infra network exists

### 3. Add `ai-gateway/Dockerfile`

Purpose:
- make the Python service buildable on the target server without relying on host Python or host GCC

Expected changes:
- use Alibaba Cloud Linux 3 Python 3.11 base image with a fixed tag
- implement multi-stage build
- install system dependencies required by Python packages
- configure package mirrors for more reliable builds
- install Python dependencies from `pyproject.toml`
- copy application source code
- define runtime startup command using `uvicorn`

Completion criteria:
- the Dockerfile expresses a full build path for the service
- the runtime stage does not depend on host Python
- the container entry point is consistent with the approved deployment design

### 4. Extend `ai-gateway/Dockerfile` for model prewarming

Purpose:
- prevent first-start model downloads for `BAAI/bge-m3` and `BAAI/bge-reranker-large`

Expected changes:
- set stable cache-related environment variables such as `HF_HOME`, `TRANSFORMERS_CACHE`, and `XDG_CACHE_HOME`
- trigger model asset download during image build
- ensure runtime uses the same cache locations

Completion criteria:
- build-time behavior includes model preparation
- runtime startup should not depend on initial live model fetches
- the chosen cache path strategy is explicit and documented

### 5. Update `docker/.env.example`

Purpose:
- make container deployment values discoverable and reduce hidden localhost assumptions

Expected changes:
- add or update `ai-gateway`-related environment variables
- document container-safe endpoints using Docker service names
- keep example values aligned with the infrastructure stack

Required template coverage:
- database connection settings
- Redis connection settings
- Milvus host and port
- Elasticsearch URL
- Ollama base URL and model
- Neo4j connection settings
- ClickHouse connection settings
- optional observability or external API keys already supported by the application

Completion criteria:
- operators can prepare a `.env` file without reverse-engineering the application code
- container-facing values are clearly different from local `localhost` development defaults

### 6. Write deployment verification notes

Purpose:
- define the minimum acceptance path for the deployment deliverable

Expected changes:
- document static validation commands
- document runtime startup commands
- document health-check commands
- document what counts as success versus acceptable degraded state

Completion criteria:
- a developer can follow the notes and verify the deployment without extra tribal knowledge

## Validation Commands

The implementation should be checked with the following commands.

### Static validation

Infrastructure Compose:

```bash
docker compose -f docker/docker-compose.yml config
```

Application Compose:

```bash
docker compose -f docker/docker-compose.ai-gateway.yml config
```

### Build validation

```bash
docker compose -f docker/docker-compose.ai-gateway.yml build
```

If model prewarming behavior needs to be verified more strictly:

```bash
docker compose -f docker/docker-compose.ai-gateway.yml build --no-cache
```

### Runtime validation

Start infrastructure:

```bash
docker compose -f docker/docker-compose.yml up -d
```

Build and start application:

```bash
docker compose -f docker/docker-compose.ai-gateway.yml up -d --build
```

Check health:

```bash
curl http://localhost:8000/health
```

Inspect logs if needed:

```bash
docker logs ai-platform-ai-gateway
```

## Acceptance Criteria

The implementation is complete only when all of the following are true:

- both Compose files pass `docker compose config`
- `ai-gateway` can be built through its Compose file
- the service is exposed on host port `8000`
- the service joins the intended shared Docker network
- `.env.example` is sufficient to prepare a container deployment `.env`
- `/health` returns a valid application response after startup
- first-start model download behavior is removed or materially reduced by build-time prewarming

## Risk Priorities

### Priority 1: Shared network wiring

Risk:
- `ai-gateway` cannot resolve infrastructure service names

Mitigation:
- define an explicit named shared network
- validate both Compose files before runtime testing

### Priority 2: Docker build compatibility

Risk:
- system dependencies or Python packages fail under the chosen base image

Mitigation:
- keep build dependencies inside the builder stage
- avoid any host-level Python compilation assumptions

### Priority 3: Model prewarming stability

Risk:
- build-time model warmup causes long builds or unstable image assembly

Mitigation:
- use explicit cache directories
- if direct library warmup proves unstable, fall back to deterministic asset fetch into the same cache path

### Priority 4: Configuration drift

Risk:
- `.env` values keep `localhost` semantics and break container-to-container access

Mitigation:
- document container-safe hostnames in `.env.example`
- verify with `/health` and runtime logs

## Fallback Decisions

If implementation hits friction, use the following fallback order:

1. keep the shared network change minimal rather than refactoring the infrastructure Compose structure
2. prefer a simpler but correct Dockerfile over early optimization
3. if multi-stage build path becomes temporarily blocked, get a working build path first and then re-tighten image structure before finalizing
4. accept `/health = degraded` when downstream dependencies are not fully ready, but do not accept container startup failure or unreachable port `8000`

## Single-Commit Strategy

The implementation will be delivered as one atomic commit after all file updates and validations are complete.

Recommended commit message:

```text
feat(ai-gateway): add docker compose deployment for centos7
```

This keeps the repository history focused on the final deployment capability rather than intermediate scaffolding states.

## Suggested Execution Checklist

- [ ] Update shared network definition in [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml)
- [ ] Add [`docker/docker-compose.ai-gateway.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.ai-gateway.yml)
- [ ] Add multi-stage [`ai-gateway/Dockerfile`](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/Dockerfile)
- [ ] Add model prewarming and cache environment settings
- [ ] Update [`docker/.env.example`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/.env.example)
- [ ] Run Compose static validation
- [ ] Run image build validation
- [ ] Run minimum runtime verification
- [ ] Commit all deployment changes as one atomic commit
