package com.atlas.ragengine.retrieval;

import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.RbacFilterBuilder;
import com.atlas.ragengine.security.RbacFilterBuilder.RbacPredicate;
import java.util.ArrayList;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Sparse (keyword) retrieval over the Postgres full-text {@code content_tsv} GIN index. Catches rare
 * exact terms (e.g. ticker symbols, place names) that dense embeddings miss. The mandatory RBAC
 * predicate (ADR-0012) is pushed into SQL alongside the text match.
 */
public class SparseRetriever {

    private static final ChunkRowMapper MAPPER = new ChunkRowMapper();
    // Allow-list: this value is interpolated into SQL, so it must never be caller-controlled.
    private static final java.util.Set<String> ALLOWED_FNS =
            java.util.Set.of("plainto_tsquery", "websearch_to_tsquery");

    private final JdbcTemplate jdbc;
    private final RbacFilterBuilder rbac;
    private final String tsqueryFn;

    public SparseRetriever(JdbcTemplate jdbc, RbacFilterBuilder rbac) {
        this(jdbc, rbac, "plainto_tsquery");
    }

    public SparseRetriever(JdbcTemplate jdbc, RbacFilterBuilder rbac, String tsqueryFn) {
        this.jdbc = jdbc;
        this.rbac = rbac;
        if (!ALLOWED_FNS.contains(tsqueryFn)) {
            throw new IllegalArgumentException("unsupported tsquery function: " + tsqueryFn);
        }
        this.tsqueryFn = tsqueryFn;
    }

    public List<RetrievedChunk> retrieve(String query, ClearanceLevel caller, int k) {
        RbacPredicate rbacPredicate = rbac.predicate("clearance", caller);

        String sql = "SELECT id, document_id, content, clearance, metadata, "
                + "ts_rank_cd(content_tsv, " + tsqueryFn + "('english', ?)) AS score "
                + "FROM atlas_chunk "
                + "WHERE " + rbacPredicate.sqlFragment() + " "
                + "AND content_tsv @@ " + tsqueryFn + "('english', ?) "
                + "ORDER BY score DESC "
                + "LIMIT ?";

        List<Object> params = new ArrayList<>();
        params.add(query);                               // ts_rank_cd query
        params.addAll(List.of(rbacPredicate.params()));  // RBAC visible-label array
        params.add(query);                               // @@ match query
        params.add(k);
        return jdbc.query(sql, MAPPER, params.toArray());
    }
}
