package com.atlas.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Atlas API Gateway — the single front door in front of {@code rag-engine} (P3, ADR-0033).
 *
 * <p>P3 task 1 stands up the module skeleton only: a Spring Cloud Gateway (WebMVC) application
 * exposing actuator health + Prometheus metrics. Auth (simulated IdP), the cost-aware router,
 * the clearance-safe semantic cache, rate limiting, budget caps, the circuit breaker, PII egress
 * redaction, output sanitization, and cost metering are layered on in subsequent P3 tasks.
 */
@SpringBootApplication
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }
}
