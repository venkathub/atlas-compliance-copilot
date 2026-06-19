package com.atlas.gateway.query;

import com.atlas.gateway.resilience.DownstreamUnavailableException;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** Maps gateway resource-control failures to typed HTTP responses (ADR-0039, LLM10). */
@RestControllerAdvice
public class GatewayExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GatewayExceptionHandler.class);

    /** Circuit-breaker open / downstream failure → {@code 503} + {@code Retry-After} (honest UX). */
    @ExceptionHandler(DownstreamUnavailableException.class)
    ResponseEntity<Map<String, Object>> handleDownstreamUnavailable(DownstreamUnavailableException e) {
        log.warn("Downstream unavailable → 503", e.getCause() != null ? e.getCause() : e);
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .header(HttpHeaders.RETRY_AFTER, Long.toString(e.retryAfterSeconds()))
                .body(Map.of("error", "service_unavailable",
                        "reason", "the answering service is temporarily unavailable",
                        "retryAfterSeconds", e.retryAfterSeconds()));
    }
}
