package com.atlas.mcptools.audit;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

/**
 * Read-only ("SELECT-only") paginated reader over {@code agent.tool_audit} for the admin audit view
 * (P5 Task 5). Introduces <b>no write path</b> — the append-only, hash-chained log stays owned by
 * {@link AuditService}. Only non-sensitive columns are projected: the {@code args_digest} and the
 * hash-chain columns ({@code prev_hash}/{@code row_hash}) are deliberately NOT surfaced (LLM02 —
 * the UI shows refs/digests, never raw PII).
 *
 * <p>Filters ({@code caller}, {@code run_id}) are both indexed; pagination is offset-based on the
 * monotonic {@code seq} identity, newest first.
 */
@Repository
public class AuditQueryDao {

    private static final RowMapper<AuditRowView> MAPPER = (rs, n) -> new AuditRowView(
            rs.getLong("seq"),
            rs.getObject("ts", OffsetDateTime.class).toInstant(),
            rs.getString("run_id"),
            rs.getString("tool"),
            rs.getString("phase"),
            rs.getString("caller"),
            rs.getString("clearance"),
            rs.getString("result_ref"));

    private final JdbcTemplate jdbc;

    public AuditQueryDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** Total rows matching the (optional) caller/runId filters. */
    public long count(String caller, String runId) {
        StringBuilder sql = new StringBuilder("SELECT count(*) FROM agent.tool_audit");
        List<Object> args = new ArrayList<>();
        appendFilters(sql, args, caller, runId);
        Long total = jdbc.queryForObject(sql.toString(), Long.class, args.toArray());
        return total == null ? 0L : total;
    }

    /** One page of rows, newest first (by {@code seq}), exposing only non-sensitive columns. */
    public List<AuditRowView> page(String caller, String runId, int limit, int offset) {
        StringBuilder sql = new StringBuilder(
                "SELECT seq, ts, run_id, tool, phase, caller, clearance, result_ref "
                        + "FROM agent.tool_audit");
        List<Object> args = new ArrayList<>();
        appendFilters(sql, args, caller, runId);
        sql.append(" ORDER BY seq DESC LIMIT ? OFFSET ?");
        args.add(limit);
        args.add(offset);
        return jdbc.query(sql.toString(), MAPPER, args.toArray());
    }

    private static void appendFilters(StringBuilder sql, List<Object> args, String caller, String runId) {
        List<String> clauses = new ArrayList<>();
        if (caller != null && !caller.isBlank()) {
            clauses.add("caller = ?");
            args.add(caller);
        }
        if (runId != null && !runId.isBlank()) {
            clauses.add("run_id = ?");
            args.add(runId);
        }
        if (!clauses.isEmpty()) {
            sql.append(" WHERE ").append(String.join(" AND ", clauses));
        }
    }
}
