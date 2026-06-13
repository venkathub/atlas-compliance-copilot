package com.atlas.ragengine.guardrail;

import com.atlas.ragengine.retrieval.RetrievedChunk;
import java.util.List;

/**
 * Outcome of running the {@link InjectionGuardrail} over a retrieved candidate set.
 *
 * @param safe               chunks that passed the scanner (allowed into the prompt)
 * @param quarantined        chunks flagged as likely prompt-injection (kept OUT of the prompt)
 * @param spotlightedContext the safe chunks wrapped in spotlighting delimiters, ready to drop into
 *                           the grounded prompt as data (not instructions)
 */
public record GuardrailResult(
        List<RetrievedChunk> safe,
        List<QuarantinedChunk> quarantined,
        String spotlightedContext) {

    /** A quarantined chunk plus the phrases that tripped the scanner (for the trace/observability). */
    public record QuarantinedChunk(RetrievedChunk chunk, List<String> matchedPhrases) {
    }

    public boolean anyQuarantined() {
        return !quarantined.isEmpty();
    }
}
