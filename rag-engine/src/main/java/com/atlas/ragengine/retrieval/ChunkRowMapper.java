package com.atlas.ragengine.retrieval;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;

/** Maps an {@code atlas_chunk} row (plus a computed {@code score}) to a {@link RetrievedChunk}. */
final class ChunkRowMapper implements RowMapper<RetrievedChunk> {

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    @Override
    public RetrievedChunk mapRow(ResultSet rs, int rowNum) throws SQLException {
        Map<String, Object> metadata = parseMetadata(rs.getString("metadata"));
        return new RetrievedChunk(
                rs.getObject("id", UUID.class),
                rs.getObject("document_id", UUID.class),
                rs.getString("content"),
                rs.getString("clearance"),
                metadata,
                rs.getDouble("score"));
    }

    private static Map<String, Object> parseMetadata(String json) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            return JSON.readValue(json, MAP_TYPE);
        } catch (Exception e) {
            return Map.of();
        }
    }
}
