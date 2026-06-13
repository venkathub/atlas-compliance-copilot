package com.atlas.ragengine.retrieval;

import com.atlas.ragengine.common.PgVector;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.RbacFilterBuilder;
import com.atlas.ragengine.security.RbacFilterBuilder.RbacPredicate;
import java.util.ArrayList;
import java.util.List;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Dense retrieval over the pgvector HNSW index (cosine). The mandatory RBAC predicate (ADR-0012) is
 * pushed into SQL so chunks above the caller's clearance are never fetched — not post-filtered.
 */
public class DenseRetriever {

    private static final ChunkRowMapper MAPPER = new ChunkRowMapper();

    private final JdbcTemplate jdbc;
    private final EmbeddingModel embeddingModel;
    private final RbacFilterBuilder rbac;

    public DenseRetriever(JdbcTemplate jdbc, EmbeddingModel embeddingModel, RbacFilterBuilder rbac) {
        this.jdbc = jdbc;
        this.embeddingModel = embeddingModel;
        this.rbac = rbac;
    }

    public List<RetrievedChunk> retrieve(String query, ClearanceLevel caller, int k) {
        String vector = PgVector.toLiteral(embeddingModel.embed(query));
        RbacPredicate rbacPredicate = rbac.predicate("clearance", caller);

        String sql = "SELECT id, document_id, content, clearance, metadata, "
                + "(1 - (embedding <=> ?::vector)) AS score "
                + "FROM atlas_chunk "
                + "WHERE " + rbacPredicate.sqlFragment() + " "
                + "ORDER BY embedding <=> ?::vector "
                + "LIMIT ?";

        List<Object> params = new ArrayList<>();
        params.add(vector);                              // score: 1 - cosine distance
        params.addAll(List.of(rbacPredicate.params()));  // RBAC visible-label array
        params.add(vector);                              // ORDER BY cosine distance
        params.add(k);
        return jdbc.query(sql, MAPPER, params.toArray());
    }
}
