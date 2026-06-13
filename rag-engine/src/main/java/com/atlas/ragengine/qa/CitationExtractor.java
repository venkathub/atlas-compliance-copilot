package com.atlas.ragengine.qa;

import com.atlas.ragengine.retrieval.RetrievedChunk;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.RbacFilterBuilder;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Maps the inline {@code [n]} markers in a generated answer to chunk-level {@link Citation}s
 * (ADR-0018). Only sources actually cited appear; out-of-range markers are ignored; duplicates
 * collapse. Defense in depth (ADR-0012): every citation is re-checked against the caller's clearance
 * and dropped (with a SECURITY log) if it would exceed it — so a retrieval bug can never surface a
 * cited above-clearance source.
 */
public class CitationExtractor {

    private static final Logger log = LoggerFactory.getLogger(CitationExtractor.class);
    private static final Pattern MARKER = Pattern.compile("\\[(\\d{1,3})]");
    private static final int SNIPPET_LEN = 240;

    private final RbacFilterBuilder rbac;

    public CitationExtractor(RbacFilterBuilder rbac) {
        this.rbac = rbac;
    }

    /**
     * @param answer  the model's answer text containing {@code [n]} markers
     * @param sources the numbered sources presented to the model ({@code [1]} == sources.get(0))
     * @param caller  the caller's clearance (for the defense-in-depth re-check)
     */
    public List<Citation> extract(String answer, List<RetrievedChunk> sources, ClearanceLevel caller) {
        Set<Integer> markers = new LinkedHashSet<>();
        Matcher m = MARKER.matcher(answer == null ? "" : answer);
        while (m.find()) {
            markers.add(Integer.parseInt(m.group(1)));
        }

        List<Citation> citations = new ArrayList<>();
        for (int marker : markers) {
            int idx = marker - 1; // markers are 1-based
            if (idx < 0 || idx >= sources.size()) {
                continue; // hallucinated / out-of-range marker
            }
            RetrievedChunk chunk = sources.get(idx);
            if (!rbac.isVisible(caller, chunk.clearance())) {
                log.error("SECURITY: dropped citation [{}] — chunk {} clearance '{}' exceeds caller '{}'",
                        marker, chunk.id(), chunk.clearance(), caller.label());
                continue;
            }
            citations.add(new Citation(marker, chunk.id(), chunk.documentId(), chunk.docId(),
                    chunk.title(), chunk.sourceUri(), chunk.clearance(), chunk.score(), snippet(chunk)));
        }
        return citations;
    }

    private static String snippet(RetrievedChunk chunk) {
        String text = chunk.content() == null ? "" : chunk.content().strip().replaceAll("\\s+", " ");
        return text.length() <= SNIPPET_LEN ? text : text.substring(0, SNIPPET_LEN) + "…";
    }
}
