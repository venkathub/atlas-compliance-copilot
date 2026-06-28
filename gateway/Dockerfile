# syntax=docker/dockerfile:1
#
# Atlas gateway runtime image (P3, ADR-0033 — Spring Cloud Gateway WebMVC).
#
# Distroless + nonroot + no shell -> minimal attack surface. The Spring Boot fat jar is
# architecture-independent, so this image is multi-arch (amd64 + arm64) by layering the jar
# onto the multi-arch distroless base — NO QEMU emulation (there are no RUN steps). Same
# pattern as rag-engine, so the image runs on the Oracle Ampere A1 (arm64) prod target.
#
# Base pinned by digest (OWASP LLM03 supply-chain). Build context = repo root; build the jar
# first:  mvn -pl gateway -am package
# The runnable Spring Boot jar is the classified `-exec` artifact (the plain jar is a thin
# library jar; see gateway/pom.xml spring-boot-maven-plugin classifier).

# ── probe stage: compile the health probe ONCE (portable bytecode; native build arch) ──
# `--platform=$BUILDPLATFORM` keeps javac running on the native build arch (no QEMU); the
# resulting .class is architecture-independent and copied into both arch runtime images.
FROM --platform=$BUILDPLATFORM eclipse-temurin:21-jdk AS healthprobe
COPY infra/docker/HealthCheck.java /HealthCheck.java
RUN javac -d /probe /HealthCheck.java

FROM gcr.io/distroless/java21-debian12:nonroot@sha256:7e37784d94dccbf5ccb195c73b295f5ad00cd266512dfbac12eb9c3c28f8077d

WORKDIR /app
COPY gateway/target/gateway-*-exec.jar /app/app.jar
# Distroless has no shell/curl, so the HEALTHCHECK uses the JRE + the portable probe class.
COPY --from=healthprobe /probe/HealthCheck.class /app/HealthCheck.class
# Run as the distroless non-root user (uid 65532). The :nonroot base already drops root; this
# makes it explicit (defense against a base change + satisfies Trivy DS-0002 static check).
USER 65532:65532
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD ["java", "-cp", "/app", "HealthCheck", "http://127.0.0.1:8080/actuator/health"]
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
