package com.atlas.ragengine.api;

import com.atlas.ragengine.qa.QueryService;
import com.atlas.ragengine.qa.ModelTierResolver;
import com.atlas.ragengine.observability.RequestIdFilter;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.ClearanceResolver;
import jakarta.servlet.http.HttpServletRequest;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

/** {@code POST /v1/query} — permission-aware grounded QA with inline citations. */
@RestController
@RequestMapping("/v1")
public class QueryController {

    private static final Logger log = LoggerFactory.getLogger(QueryController.class);

    private final QueryService queryService;
    private final ClearanceResolver clearanceResolver;
    private final ModelTierResolver modelTierResolver;

    public QueryController(QueryService queryService, ClearanceResolver clearanceResolver,
            ModelTierResolver modelTierResolver) {
        this.queryService = queryService;
        this.clearanceResolver = clearanceResolver;
        this.modelTierResolver = modelTierResolver;
    }

    @PostMapping("/query")
    public ResponseEntity<QueryResponse> query(@RequestBody QueryRequest request, HttpServletRequest http) {
        if (request == null || request.query() == null || request.query().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "query is required");
        }
        ClearanceLevel caller = resolveClearance(http);
        // P3 model router (ADR-0035): the Gateway selects a tier; map it to a per-request model override
        // (tier1-small/absent → default ChatModel). Plus the LLM10 max-output-token cap (ADR-0038).
        String modelOverride = modelTierResolver.resolveModel(http.getHeader(ModelTierResolver.HEADER))
                .orElse(null);
        Integer maxOutputTokens = parseMaxOutputTokens(http.getHeader("X-Atlas-Max-Output-Tokens"));
        // Reuse the gateway-propagated correlation id (RequestIdFilter put it in the MDC) as the trace
        // id so the rag-engine span stitches to the gateway request; mint one only on direct access.
        String requestId = MDC.get(RequestIdFilter.MDC_KEY);
        if (requestId == null || requestId.isBlank()) {
            requestId = UUID.randomUUID().toString();
        }
        log.info("Query [{}] at clearance '{}' (model={}): {}",
                requestId, caller.label(), modelOverride == null ? "default" : modelOverride, request.query());
        QueryService.QaResult result = queryService.answer(
                request.query(), caller, request.topKOrDefault(), requestId, modelOverride, maxOutputTokens);
        return ResponseEntity.ok(QueryResponse.from(result, request.includeContextsOrDefault()));
    }

    private static Integer parseMaxOutputTokens(String header) {
        if (header == null || header.isBlank()) {
            return null;
        }
        try {
            int v = Integer.parseInt(header.strip());
            return v > 0 ? v : null;
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /**
     * Prefer the Gateway-asserted, verified clearance (ADR-0034): on the Gateway-fronted path the
     * {@link DownstreamClearanceFilter} has already verified the internal assertion and stashed the
     * clearance, so the client {@code X-Atlas-Clearance} shim is ignored. Only when no verified
     * assertion is present (direct/test access) do we fall back to the P1 {@link ClearanceResolver}.
     */
    private ClearanceLevel resolveClearance(HttpServletRequest http) {
        Object verified = http.getAttribute(DownstreamClearanceFilter.ATTRIBUTE);
        if (verified instanceof ClearanceLevel level) {
            return level;
        }
        return clearanceResolver.resolve(HttpRequestHeaders.of(http));
    }
}
