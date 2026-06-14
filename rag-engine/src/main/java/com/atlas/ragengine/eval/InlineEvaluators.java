package com.atlas.ragengine.eval;

import com.atlas.ragengine.retrieval.RetrievedChunk;
import io.micrometer.observation.Observation;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.evaluation.FactCheckingEvaluator;
import org.springframework.ai.chat.evaluation.RelevancyEvaluator;
import org.springframework.ai.document.Document;
import org.springframework.ai.evaluation.EvaluationRequest;
import org.springframework.ai.evaluation.EvaluationResponse;

/**
 * Spring AI in-pipeline evaluators (ADR-0026 / D-P2-6): {@link RelevancyEvaluator} (is the answer
 * relevant to the question + context?) and {@link FactCheckingEvaluator} (is the answer grounded in
 * the retrieved context?) run **inline as a cheap pre-filter** and **annotate the trace** with
 * pass/score — they are NOT the merge gate (the Python RAGAS run is the authority).
 *
 * <p>Each evaluator is an extra LLM call, so this is **OFF by default** (cost discipline) and
 * **fail-soft**: any evaluator error is logged and the request proceeds unaffected. The annotations
 * land on the current {@code atlas.query} span (no separate trace).
 */
public class InlineEvaluators {

    private static final Logger log = LoggerFactory.getLogger(InlineEvaluators.class);

    private final boolean enabled;
    private final RelevancyEvaluator relevancy;
    private final FactCheckingEvaluator factChecking;

    public InlineEvaluators(boolean enabled, ChatClient.Builder chatClientBuilder) {
        this.enabled = enabled;
        this.relevancy = enabled ? new RelevancyEvaluator(chatClientBuilder) : null;
        this.factChecking = enabled ? new FactCheckingEvaluator(chatClientBuilder) : null;
    }

    /** No-op evaluators for tests / when inline evaluation is disabled. */
    public static InlineEvaluators disabled() {
        return new InlineEvaluators(false, null);
    }

    public boolean enabled() {
        return enabled;
    }

    /** Run the inline evaluators and annotate {@code span} with their verdicts. Never throws. */
    public void annotate(Observation span, String query, List<RetrievedChunk> contexts, String answer) {
        if (!enabled || span == null) {
            return;
        }
        List<Document> docs = contexts.stream()
                .map(c -> Document.builder().text(c.content()).build())
                .toList();
        EvaluationRequest request = new EvaluationRequest(query, docs, answer);
        evaluate("relevancy", span, () -> relevancy.evaluate(request));
        evaluate("factcheck", span, () -> factChecking.evaluate(request));
    }

    private void evaluate(String name, Observation span, java.util.function.Supplier<EvaluationResponse> eval) {
        try {
            EvaluationResponse r = eval.get();
            span.lowCardinalityKeyValue("eval." + name + ".pass", Boolean.toString(r.isPass()));
            span.highCardinalityKeyValue("eval." + name + ".score", Float.toString(r.getScore()));
        } catch (RuntimeException e) {
            // Fail-soft: a flaky pre-filter must never break a query or the trace.
            log.warn("inline {} evaluator failed (ignored): {}", name, e.toString());
        }
    }
}
