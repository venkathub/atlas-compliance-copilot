# syntax=docker/dockerfile:1
#
# Atlas mcp-tools runtime image (P4, ADR-0043 — Spring AI MCP server, Streamable HTTP on WebMVC).
#
# Distroless + nonroot + no shell -> minimal attack surface. The Spring Boot fat jar is
# architecture-independent, so this image is multi-arch (amd64 + arm64) by layering the jar
# onto the multi-arch distroless base — NO QEMU emulation (there are no RUN steps). Same
# pattern as gateway/rag-engine, so the image runs on the Oracle Ampere A1 (arm64) prod target.
#
# Base pinned by digest (OWASP LLM03 / ASI04 supply-chain). Build context = repo root; build the jar
# first:  mvn -pl mcp-tools -am package
# The runnable Spring Boot jar is the classified `-exec` artifact (the plain jar is a thin
# library jar; see mcp-tools/pom.xml spring-boot-maven-plugin classifier).
FROM gcr.io/distroless/java21-debian12:nonroot@sha256:7e37784d94dccbf5ccb195c73b295f5ad00cd266512dfbac12eb9c3c28f8077d

WORKDIR /app
COPY mcp-tools/target/mcp-tools-*-exec.jar /app/app.jar
EXPOSE 8082
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
