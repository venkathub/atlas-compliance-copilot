package com.atlas.mcptools.audit;

import java.util.List;

/**
 * Paginated audit-read response (P5 §2.3). {@code chainVerified} is a <b>global</b> integrity flag —
 * the {@link AuditChainVerifier} recomputes the whole chain (genesis → tip), so it reflects the
 * integrity of the entire log, independent of which page is returned.
 */
public record AuditPageResponse(
        int page,
        int size,
        long total,
        boolean chainVerified,
        List<AuditRowView> rows) {
}
