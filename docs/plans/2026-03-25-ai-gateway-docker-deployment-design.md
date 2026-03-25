# AI Gateway Docker Deployment Design

Date: 2026-03-25

## Background

The deployment target is a CentOS 7 server with an older GCC toolchain. To avoid host-level Python build and runtime compatibility issues, the `ai-gateway` service will be deployed with Docker and built on the server. The selected Python base image is the Alibaba Cloud Linux 3 Python image family.

The current [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml) is an infrastructure-only stack. It should remain responsible for shared dependencies such as PostgreSQL, Redis, Milvus, Elasticsearch, Ollama, Neo4j, and ClickHouse.

## Goals

- Add a Docker Compose deployment scheme for `ai-gateway`.
- Keep infrastructure orchestration and application deployment separated.
- Build the Python image on the server with `docker compose build`.
- Expose the Python backend directly on host port `8000`.
- Do not connect the Python backend to the existing Nginx container for now.
- Include production-oriented basics such as image source acceleration, health checks, model prewarming, and `.env`-based configuration.

## Non-Goals

- No host-side startup script in this phase.
- No Nginx reverse proxy integration for `ai-gateway`.
- No split environment files such as `.env.docker` or local overlay files.
- No redesign of application startup logic beyond what is needed for container deployment.

## Chosen Approach

The approved approach is to keep the current infrastructure Compose file unchanged in responsibility and add a separate Compose file for the Python application layer.

Recommended file layout:

- [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml): infrastructure services only
- [`docker/docker-compose.ai-gateway.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.ai-gateway.yml): `ai-gateway` service only
- [`ai-gateway/Dockerfile`](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/Dockerfile): multi-stage image build
- Optional container helper files under [`ai-gateway/docker`](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/docker): only if needed for image/runtime support
- Shared environment file: [`docker/.env`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/.env)

## Why This Approach

### Option A: Append `ai-gateway` to the existing infrastructure Compose file

This is the simplest to start with, but it mixes infrastructure lifecycle and application lifecycle in one file. That increases operational coupling and makes later application-only updates noisier and riskier.

### Option B: Add a dedicated Compose file for `ai-gateway`

This preserves the current infrastructure boundary while allowing the Python application to evolve independently. It aligns with the current repository structure and gives a clear deployment flow: start infra first, then build and start the application.

### Option C: Build a fully separate independent stack

This isolates the application too aggressively and duplicates network and configuration concerns already present in the repository. It adds maintenance cost without solving a real problem in the current deployment model.

Option B was selected because it gives the cleanest operational boundary with the smallest long-term maintenance cost.

## Container Topology

`ai-gateway` runs as an application container on the same Docker network as the infrastructure containers.

- `ai-gateway` publishes `8000:8000`
- Existing infrastructure services remain in the infrastructure Compose stack
- `ai-gateway` communicates with infra by service name on the shared Docker network
- Existing Nginx remains unchanged and does not proxy to `ai-gateway`

This avoids `host.docker.internal` assumptions and keeps service-to-service traffic inside the Docker network. That is more stable on CentOS 7 than relying on host loopback or desktop-oriented networking behavior.

## Build Strategy

The image will be built on the deployment server through Docker Compose using the Alibaba Cloud Linux 3 Python base image with a fixed Python 3.11 tag.

The Dockerfile should use a multi-stage build:

1. Builder stage
   - install system build dependencies
   - configure package mirrors for reliable dependency installation
   - install Python dependencies
   - prewarm model assets
2. Runtime stage
   - copy only the required runtime dependencies and application files
   - keep the runtime image smaller and simpler
   - start the application with `uvicorn app.main:app --host 0.0.0.0 --port 8000`

This design isolates the legacy CentOS 7 host from Python package compilation concerns and keeps runtime behavior deterministic.

## Model Prewarming

The application uses `BAAI/bge-m3` and `BAAI/bge-reranker-large` through `FlagEmbedding` in [`ai-gateway/app/services/rag_service.py`](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/services/rag_service.py).

The approved strategy is to prewarm these models during image build rather than downloading them on first container start.

Design requirements:

- set stable cache directories such as `HF_HOME`, `TRANSFORMERS_CACHE`, and `XDG_CACHE_HOME`
- trigger model download during image build
- keep the runtime container from depending on first-start internet access

Trade-off:

- image size increases
- startup stability improves
- first deployment time shifts from runtime to build time

This trade-off is acceptable because the deployment goal prioritizes predictable startup on a constrained server environment.

## Configuration Strategy

Environment management uses a single `.env` file.

- Compose reads [`docker/.env`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/.env)
- the `ai-gateway` container also receives environment values from the same `.env`
- no extra `.env.docker` or environment overlays are introduced

The current application defaults in [`ai-gateway/app/core/config.py`](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/core/config.py) are local-development oriented and use `localhost`. For container deployment, the `.env` file must override those values with Docker service names.

Required overrides include:

- `database_url` -> `postgres`
- `redis_url` -> `redis`
- `milvus_host=milvus`
- `elasticsearch_url=http://elasticsearch:9200`
- `ollama_base_url=http://ollama:11434`
- `neo4j_uri=neo4j://neo4j:7687`
- `clickhouse_url` -> container-accessible ClickHouse endpoint
- any credentials already managed by the infrastructure stack

## Network Design

The infrastructure stack and the `ai-gateway` stack must share an explicit Docker network rather than relying on an implicit generated network name.

Recommended design:

- define a named network in the infrastructure Compose file
- attach infrastructure services to that network
- reference the same network from `docker-compose.ai-gateway.yml` as an external network

This prevents accidental breakage if the project directory name changes or if the application stack is launched from a different working context.

## Health Check Strategy

Two layers of health checks are required.

### Container-Level Health Check

The `ai-gateway` service in Compose should probe `http://localhost:8000/health`.

This health check determines whether the process is alive and serving HTTP inside the container.

### Application-Level Health Check

The existing `/health` endpoint in [`ai-gateway/app/main.py`](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/app/main.py) already reports dependency status for Milvus, Elasticsearch, and Ollama. This should remain the primary application health signal.

Recommended policy:

- allow the process to start even if some downstream services are not fully ready
- report degraded state through `/health`
- use logs and health status for diagnosis rather than hard failing immediately on partial dependency unavailability

This is more stable for layered deployments where infrastructure containers may come up at slightly different speeds.

## Logging

For this phase, logging should stay simple:

- use container stdout and stderr
- inspect logs via `docker logs`
- avoid adding a dedicated host-side log script or a file-based logging subsystem unless a concrete operational need appears later

This keeps the design focused and matches the current requirement to avoid extra startup tooling.

## Deployment Flow

The expected deployment flow is:

1. Start infrastructure:
   - `docker compose -f docker/docker-compose.yml up -d`
2. Build and start the Python backend:
   - `docker compose -f docker/docker-compose.ai-gateway.yml up -d --build`
3. Verify health:
   - `curl http://<host>:8000/health`

This preserves a clean separation between infra bootstrap and application rollout.

## Expected Deliverables

The implementation phase should produce:

- [`ai-gateway/Dockerfile`](/Users/smart/PycharmProjects/AI-Business-Platform/ai-gateway/Dockerfile)
- [`docker/docker-compose.ai-gateway.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.ai-gateway.yml)
- updates to [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml) only if required for shared named network support
- environment variable template updates in [`docker/.env.example`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/.env.example) if that file exists, otherwise add an example file
- minimal deployment documentation and verification notes

## Risks And Mitigations

### Large Image Size

Prewarming BGE models increases image size.

Mitigation:

- use multi-stage builds
- keep runtime image clean
- accept larger image size in exchange for predictable startup

### Native Dependency Build Failures

Some Python packages may require compilation in the builder stage.

Mitigation:

- keep compilation inside the Alibaba Cloud Linux container
- install required build dependencies only in the builder stage
- avoid host Python build involvement entirely

### Service Name Drift

If `.env` keeps `localhost` defaults, the container will fail to reach infrastructure dependencies.

Mitigation:

- explicitly document container-safe environment values
- verify dependency endpoints through `/health`

### Network Coupling Bugs

If the application stack does not join the correct Docker network, name-based access to infra services will fail.

Mitigation:

- define an explicit named shared network
- avoid implicit Compose network naming

## Testing And Verification

Implementation should verify at least:

- Docker image builds successfully on the target server
- `ai-gateway` starts and binds to host port `8000`
- `/health` returns a valid response
- the container can resolve and connect to PostgreSQL, Redis, Milvus, Elasticsearch, Ollama, Neo4j, and ClickHouse through Docker service names
- model prewarming prevents first-request model download delays

## Out Of Scope For This Design

The following are intentionally deferred:

- Nginx access integration
- host-side deployment scripts
- advanced rolling update strategy
- external registry push and pull workflow
- autoscaling or multi-instance orchestration
