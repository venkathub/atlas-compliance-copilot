package com.atlas.ragengine.api;

import com.atlas.ragengine.qa.QueryService;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.ClearanceResolver;
import jakarta.servlet.http.HttpServletRequest;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
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

    public QueryController(QueryService queryService, ClearanceResolver clearanceResolver) {
        this.queryService = queryService;
        this.clearanceResolver = clearanceResolver;
    }

    @PostMapping("/query")
    public ResponseEntity<QueryResponse> query(@RequestBody QueryRequest request, HttpServletRequest http) {
        if (request == null || request.query() == null || request.query().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "query is required");
        }
        ClearanceLevel caller = clearanceResolver.resolve(HttpRequestHeaders.of(http));
        String requestId = UUID.randomUUID().toString();
        log.info("Query [{}] at clearance '{}': {}", requestId, caller.label(), request.query());
        QueryService.QaResult result =
                queryService.answer(request.query(), caller, request.topKOrDefault(), requestId);
        return ResponseEntity.ok(QueryResponse.from(result));
    }
}
