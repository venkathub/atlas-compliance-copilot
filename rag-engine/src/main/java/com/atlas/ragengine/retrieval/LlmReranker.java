package com.atlas.ragengine.retrieval;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.prompt.Prompt;

/**
 * LLM-as-reranker (ADR-0027 / D-P2-7 option c): asks the served model to reorder the RRF-fused
 * candidates by relevance to the query, then truncates to {@code topK}. Drops in behind the
 * {@link Reranker} seam with no caller changes; enabled via {@code atlas.retrieval.reranker=llm} and
 * kept only if the eval A/B proves a lift.
 *
 * <p>Fail-safe: if the model's response can't be parsed into a valid ordering, it falls back to the
 * RRF order (truncated) — reranking can only reorder candidates already retrieved (and RBAC-filtered),
 * never introduce new ones, so it cannot weaken the RBAC guarantee.
 */
public class LlmReranker implements Reranker {

    private static final Logger log = LoggerFactory.getLogger(LlmReranker.class);
    private static final Pattern INT = Pattern.compile("\\d+");
    private static final int SNIPPET = 280;

    private final ChatModel chatModel;

    public LlmReranker(ChatModel chatModel) {
        this.chatModel = chatModel;
    }

    @Override
    public List<RetrievedChunk> rerank(String query, List<RetrievedChunk> fused, int topK) {
        int limit = (topK <= 0) ? fused.size() : Math.min(topK, fused.size());
        if (fused.size() <= 1) {
            return fused.subList(0, Math.min(limit, fused.size()));
        }
        try {
            String answer = chatModel.call(new Prompt(prompt(query, fused)))
                    .getResult().getOutput().getText();
            List<Integer> order = parseOrder(answer, fused.size());
            if (order.isEmpty()) {
                return fallback(fused, limit);
            }
            List<RetrievedChunk> reranked = new ArrayList<>(fused.size());
            for (int idx : order) {
                reranked.add(fused.get(idx));
            }
            return reranked.subList(0, Math.min(limit, reranked.size()));
        } catch (RuntimeException e) {
            log.warn("LLM rerank failed ({}); falling back to RRF order", e.toString());
            return fallback(fused, limit);
        }
    }

    private static List<RetrievedChunk> fallback(List<RetrievedChunk> fused, int limit) {
        return fused.subList(0, Math.min(limit, fused.size()));
    }

    private static String prompt(String query, List<RetrievedChunk> fused) {
        StringBuilder sb = new StringBuilder();
        sb.append("Rank the candidate passages by how well they help answer the question. ")
                .append("Return ONLY a JSON array of passage numbers, most relevant first, e.g. [3,1,2]. ")
                .append("Include every number exactly once.\n\nQuestion: ").append(query).append("\n\n");
        for (int i = 0; i < fused.size(); i++) {
            String content = fused.get(i).content();
            String snippet = content.length() > SNIPPET ? content.substring(0, SNIPPET) : content;
            sb.append("[").append(i + 1).append("] ").append(snippet.replace('\n', ' ')).append("\n");
        }
        return sb.toString();
    }

    /** Parse a 1-based ordering from the model output → 0-based indices; append any it omitted. */
    private static List<Integer> parseOrder(String answer, int n) {
        Set<Integer> order = new LinkedHashSet<>();
        Matcher m = INT.matcher(answer == null ? "" : answer);
        while (m.find()) {
            int v = Integer.parseInt(m.group()) - 1; // model is 1-based
            if (v >= 0 && v < n) {
                order.add(v);
            }
        }
        if (order.isEmpty()) {
            return List.of();
        }
        for (int i = 0; i < n; i++) {
            order.add(i); // de-dup set preserves earlier order; appends any missing indices
        }
        return new ArrayList<>(order);
    }
}
