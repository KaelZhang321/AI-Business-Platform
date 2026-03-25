# Business Server Docker Deployment Design

Date: 2026-03-25

## Background

The `business-server` module is the business orchestration layer of the platform. It is a Spring Boot 3.3.6 service running on Java 17 and currently defaults to port `8080`.

The current repository already separates infrastructure deployment into [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml). That file should remain infrastructure-only and continue to manage shared components such as PostgreSQL, Redis, RabbitMQ, MinIO, ClickHouse, and Nacos.

The deployment target remains a CentOS 7 server. To avoid depending on host-level Java and Maven installation, the service should be built and run entirely inside Docker.

## Goals

- Add a Docker deployment scheme for `business-server`
- Keep infrastructure orchestration and application deployment separated
- Build the Java service on the server through Docker Compose
- Expose `business-server` directly on host port `8080`
- Do not connect the service to the existing Nginx container for now
- Include `.env`-based configuration, health checks, and Maven/source acceleration in the deployment design

## Non-Goals

- No Nginx reverse proxy integration in this phase
- No host-side startup scripts
- No separate environment files such as `.env.docker`
- No CI/CD registry workflow design
- No rolling update or multi-instance orchestration design

## Chosen Approach

The approved direction is to mirror the deployment pattern already used for `ai-gateway`:

- keep [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml) focused on infrastructure
- add a dedicated [`docker/docker-compose.business-server.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.business-server.yml) for the Java application
- add a module-local [`business-server/Dockerfile`](/Users/smart/PycharmProjects/AI-Business-Platform/business-server/Dockerfile)
- keep environment management unified through [`docker/.env`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/.env)

## Why This Approach

### Option A: Add `business-server` directly into the infrastructure Compose file

This reduces file count, but it couples infrastructure lifecycle with Java application lifecycle. That makes application-only updates noisier and increases the chance of unintended infra churn.

### Option B: Add a dedicated `docker-compose.business-server.yml`

This keeps responsibilities clear and matches the approved deployment pattern already used for `ai-gateway`. Infrastructure, Python gateway, and Java orchestration can evolve independently while still sharing the same Docker network and environment source.

### Option C: Merge `business-server` and `ai-gateway` into one application-layer Compose

This reduces one file, but it unnecessarily couples Python and Java build/release behavior. A failure in one application stack would block independent deployment of the other.

Option B is selected because it gives the cleanest operational boundary with the least long-term maintenance cost.

## File Layout

Recommended deployment file layout:

- [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml): infrastructure only
- [`docker/docker-compose.business-server.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.business-server.yml): `business-server` only
- [`business-server/Dockerfile`](/Users/smart/PycharmProjects/AI-Business-Platform/business-server/Dockerfile): multi-stage Java image build
- [`docker/.env`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/.env): shared configuration source

## Container Topology

`business-server` runs as an application container on the same shared Docker network as the infrastructure services.

- `business-server` publishes `8080:8080`
- infrastructure services remain managed by the infrastructure Compose file
- `business-server` accesses PostgreSQL, Redis, RabbitMQ, MinIO, ClickHouse, and optionally Nacos through Docker service names
- existing Nginx remains unchanged and does not proxy to `business-server`

This avoids container-local `localhost` mistakes and keeps service-to-service traffic within the Docker network.

## Build Strategy

The service should be built on the target server through Docker Compose. "On-server build" means the Maven packaging process runs inside Docker during image build rather than on the host machine.

Recommended image structure:

1. Build stage
   - use Java 17 + Maven image
   - configure Maven source acceleration
   - download dependencies
   - run `mvn clean package -DskipTests`
   - produce a Spring Boot runnable jar
2. Runtime stage
   - use Java 17 runtime image
   - copy the built jar into the runtime image
   - start with `java -jar`

Recommended runtime entrypoint:

```text
java -jar /app/app.jar
```

This design avoids host-level Java and Maven installation requirements and keeps the runtime image smaller and cleaner than a single-stage Maven image.

## Source Acceleration

The deployment design should include source acceleration because the build will happen directly on the server.

Recommended acceleration scope:

- Maven repository mirror, ideally using a stable mirror such as Alibaba Cloud Maven mirror
- system package source adjustments only if the chosen base image requires extra package installation

This is not an optimization detail; it directly affects whether on-server builds remain reliable and repeatable.

## Configuration Strategy

The service already uses Spring Boot configuration files, but the current dev defaults rely heavily on `localhost`.

Relevant files today:

- [`business-server/src/main/resources/application.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/business-server/src/main/resources/application.yml)
- [`business-server/src/main/resources/application-dev.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/business-server/src/main/resources/application-dev.yml)
- [`business-server/src/main/resources/bootstrap.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/business-server/src/main/resources/bootstrap.yml)

For container deployment, the Docker design should rely on environment-variable overrides injected from `.env`, not on a separate Docker-specific application profile file.

Recommended `.env` coverage:

- `SPRING_DATASOURCE_URL`
- `SPRING_DATASOURCE_USERNAME`
- `SPRING_DATASOURCE_PASSWORD`
- `SPRING_DATA_REDIS_HOST`
- `SPRING_DATA_REDIS_PORT`
- `SPRING_DATA_REDIS_PASSWORD`
- `SPRING_RABBITMQ_HOST`
- `SPRING_RABBITMQ_PORT`
- `SPRING_RABBITMQ_USERNAME`
- `SPRING_RABBITMQ_PASSWORD`
- `APP_MINIO_ENDPOINT`
- `APP_MINIO_ACCESS_KEY`
- `APP_MINIO_SECRET_KEY`
- `APP_CLICKHOUSE_URL`
- `APP_CLICKHOUSE_USERNAME`
- `APP_CLICKHOUSE_PASSWORD`
- `NACOS_SERVER_ADDR`
- `NACOS_ENABLED`

Container-safe example targets:

- PostgreSQL -> `postgres`
- Redis -> `redis`
- RabbitMQ -> `rabbitmq`
- MinIO -> `minio`
- ClickHouse -> `clickhouse`
- Nacos -> `nacos`

## Network Design

`business-server` should join the same explicit shared network already used by infrastructure services and `ai-gateway`.

Recommended design:

- infrastructure Compose defines the named network
- application Compose references it as an external network

This avoids dependence on implicitly generated Compose network names and keeps deployment behavior stable if directory names or execution contexts change.

## Health Check Strategy

The service already includes Spring Boot Actuator dependencies in [`business-server/pom.xml`](/Users/smart/PycharmProjects/AI-Business-Platform/business-server/pom.xml), and the application config exposes health-related actuator endpoints.

Recommended health check path:

```text
/actuator/health
```

Two layers should exist:

1. Container-level health check in Compose
   - probe `http://localhost:8080/actuator/health`
2. Application-level health reporting
   - rely on Spring Boot Actuator as the deployment health surface

Recommended policy:

- allow the process to start normally
- let Actuator report service health
- avoid introducing a more complex readiness/liveness split in the first deployment design

This keeps the design operationally simple while still giving a standard health signal.

## Deployment Flow

Recommended deployment sequence:

1. Start infrastructure

```bash
docker compose -f docker/docker-compose.yml up -d
```

2. Build and start `business-server`

```bash
docker compose -f docker/docker-compose.business-server.yml up -d --build
```

3. Verify service health

```bash
curl http://localhost:8080/actuator/health
```

4. Inspect logs if needed

```bash
docker logs -f ai-platform-business-server
```

## Expected Deliverables

The implementation phase should eventually produce:

- [`business-server/Dockerfile`](/Users/smart/PycharmProjects/AI-Business-Platform/business-server/Dockerfile)
- [`docker/docker-compose.business-server.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.business-server.yml)
- minimal updates to [`docker/docker-compose.yml`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/docker-compose.yml) if shared network support needs adjustment
- `business-server` related additions to [`docker/.env.example`](/Users/smart/PycharmProjects/AI-Business-Platform/docker/.env.example)
- minimal deployment notes

## Risks And Mitigations

### Localhost Configuration Drift

Risk:
- `application-dev.yml` currently points to `localhost` for multiple dependencies, which will fail inside the container

Mitigation:
- override all container-relevant endpoints through environment variables injected from `.env`

### Build Instability On Server

Risk:
- on-server Maven builds may be slow or flaky if repository access is unstable

Mitigation:
- configure Maven mirror acceleration
- prefer predictable multi-stage build flow

### Network Attachment Failure

Risk:
- if `business-server` does not join the correct shared Docker network, all service-name-based connectivity breaks

Mitigation:
- use an explicit named shared network
- avoid implicit Compose defaults

### Health Signal Ambiguity

Risk:
- a running process may be mistaken for a healthy service if no standard probe exists

Mitigation:
- use `/actuator/health` as the standard deployment probe

## Out Of Scope For This Design

The following are intentionally deferred:

- Nginx reverse-proxy integration
- host-side deployment scripts
- advanced JVM tuning policy
- CI/CD image publishing workflow
- multi-instance deployment and traffic switching
