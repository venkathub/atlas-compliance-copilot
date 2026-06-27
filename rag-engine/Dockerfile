# syntax=docker/dockerfile:1
#
# Atlas rag-engine runtime image.
#
# Distroless + nonroot + no shell  -> minimal attack surface.
# The Spring Boot fat jar is architecture-independent, so this image is multi-arch
# (amd64 + arm64) simply by layering the jar onto the multi-arch distroless base —
# NO QEMU emulation needed (there are no RUN steps). This is what lets the same image
# run on the Oracle Ampere A1 (arm64) prod target.
#
# Base pinned by digest (OWASP LLM03 supply-chain). Build context = repo root; the jar
# must be built first:  mvn -pl rag-engine -am package
# The runnable Spring Boot jar is the classified `-exec` artifact (the plain jar is a thin
# library jar; see rag-engine/pom.xml spring-boot-maven-plugin classifier).

# ── probe stage: compile the health probe ONCE (portable bytecode; native build arch) ──
# `--platform=$BUILDPLATFORM` keeps javac on the native build arch (no QEMU); the resulting
# .class is architecture-independent and copied into both arch runtime images.
FROM --platform=$BUILDPLATFORM eclipse-temurin:21-jdk AS healthprobe
COPY infra/docker/HealthCheck.java /HealthCheck.java
RUN javac -d /probe /HealthCheck.java

FROM gcr.io/distroless/java21-debian12:nonroot@sha256:7e37784d94dccbf5ccb195c73b295f5ad00cd266512dfbac12eb9c3c28f8077d

WORKDIR /app
COPY rag-engine/target/rag-engine-*-exec.jar /app/app.jar
# Distroless has no shell/curl, so the HEALTHCHECK uses the JRE + the portable probe class.
COPY --from=healthprobe /probe/HealthCheck.class /app/HealthCheck.class
# P1 runs with the local profile so the dev clearance shim (ADR-0016) is wired. The P3 IdP
# supersedes it; this is a demo/dev default and must not be treated as production authz.
# In production (behind the gateway's signed HMAC clearance assertion) this is overridden
# to a non-local profile via the box .env (see infra/docker-compose.prod.yml).
ENV SPRING_PROFILES_ACTIVE=local
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD ["java", "-cp", "/app", "HealthCheck", "http://127.0.0.1:8081/actuator/health"]
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
