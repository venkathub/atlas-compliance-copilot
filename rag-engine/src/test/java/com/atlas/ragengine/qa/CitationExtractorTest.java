package com.atlas.ragengine.qa;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.retrieval.RetrievedChunk;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.RbacFilterBuilder;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CitationExtractorTest {

    private final CitationExtractor extractor = new CitationExtractor(new RbacFilterBuilder());

    @Test
    void mapsMarkersToSources() {
        List<RetrievedChunk> sources = List.of(src("public", "doc-a"), src("public", "doc-b"));
        List<Citation> citations = extractor.extract(
                "The answer is in [1] and confirmed by [2].", sources, ClearanceLevel.ANALYST);

        assertThat(citations).extracting(Citation::marker).containsExactly(1, 2);
        assertThat(citations).extracting(Citation::docId).containsExactly("doc-a", "doc-b");
        assertThat(citations.get(0).snippet()).isNotBlank();
    }

    @Test
    void onlyCitedSourcesAppear() {
        List<RetrievedChunk> sources = List.of(src("public", "doc-a"), src("public", "doc-b"));
        List<Citation> citations = extractor.extract("Only [2] is relevant.", sources, ClearanceLevel.ANALYST);
        assertThat(citations).extracting(Citation::docId).containsExactly("doc-b");
    }

    @Test
    void ignoresOutOfRangeAndDeduplicatesMarkers() {
        List<RetrievedChunk> sources = List.of(src("public", "doc-a"));
        List<Citation> citations = extractor.extract("[1] and again [1] but not [5].", sources,
                ClearanceLevel.ANALYST);
        assertThat(citations).hasSize(1);
        assertThat(citations.get(0).marker()).isEqualTo(1);
    }

    @Test
    void dropsCitationAboveCallerClearanceDefenseInDepth() {
        // a restricted source slipped into the candidate list; a compliance caller must not cite it
        List<RetrievedChunk> sources = List.of(src("compliance", "ok"), src("restricted", "leak"));
        List<Citation> citations = extractor.extract("See [1] and [2].", sources, ClearanceLevel.COMPLIANCE);
        assertThat(citations).extracting(Citation::docId).containsExactly("ok");
    }

    @Test
    void noMarkersYieldsNoCitations() {
        assertThat(extractor.extract("A plain answer with no citations.",
                List.of(src("public", "doc-a")), ClearanceLevel.PUBLIC)).isEmpty();
    }

    private static RetrievedChunk src(String clearance, String docId) {
        return new RetrievedChunk(UUID.randomUUID(), UUID.randomUUID(),
                "content for " + docId, clearance,
                Map.of("docId", docId, "title", "Title " + docId, "sourceUri", "atlas://" + docId), 0.5);
    }
}
