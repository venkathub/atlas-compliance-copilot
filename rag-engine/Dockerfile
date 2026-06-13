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
FROM gcr.io/distroless/java21-debian12:nonroot@sha256:7e37784d94dccbf5ccb195c73b295f5ad00cd266512dfbac12eb9c3c28f8077d

WORKDIR /app
COPY rag-engine/target/rag-engine-*-exec.jar /app/app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
