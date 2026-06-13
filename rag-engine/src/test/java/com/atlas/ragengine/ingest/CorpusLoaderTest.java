package com.atlas.ragengine.ingest;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;

/** Unit test for {@link CorpusLoader} — reads the committed P1 corpus from the classpath. */
class CorpusLoaderTest {

    private final CorpusLoader loader = new CorpusLoader(IngestionProperties.defaults());

    @Test
    void loadsLayer1FinanceBenchSnippets() {
        List<SourceDocument> layer1 = loader.loadLayer1();
        assertThat(layer1).hasSizeBetween(10, 15);
        assertThat(layer1).allSatisfy(d -> {
            assertThat(d.sourceLayer()).isEqualTo(1);
            assertThat(d.content()).isNotBlank();
            assertThat(d.clearance()).isIn("public", "analyst");
            assertThat(d.origin()).startsWith("classpath:corpus/layer1/");
            assertThat(d.sourceUri()).isNotBlank();
        });
        // a known snippet resolves and carries its company metadata
        SourceDocument threeM = byId(layer1, "financebench_id_03029");
        assertThat(threeM.metadata()).containsEntry("company", "3M");
        assertThat(threeM.content()).contains("Purchases of property, plant and equipment");
    }

    @Test
    void loadsLayer2OverlayWithFrontMatter() {
        List<SourceDocument> layer2 = loader.loadLayer2();
        assertThat(layer2).hasSizeBetween(10, 20);
        assertThat(layer2).allSatisfy(d -> {
            assertThat(d.sourceLayer()).isEqualTo(2);
            assertThat(d.docId()).isNotBlank();
            assertThat(d.title()).isNotBlank();
            assertThat(d.content()).doesNotStartWith("---"); // front-matter stripped from body
            assertThat(d.clearance()).isIn("public", "analyst", "compliance", "restricted");
        });
        // the restricted SAR draft is loaded with the right clearance + body
        SourceDocument sar = byId(layer2, "l2-northwind-sar-draft");
        assertThat(sar.clearance()).isEqualTo("restricted");
        assertThat(sar.metadata()).containsEntry("containsPii", true);
        assertThat(sar.content()).contains("DRAFT SUSPICIOUS ACTIVITY REPORT");
    }

    @Test
    void loadAllCombinesBothLayers() {
        Map<Integer, Long> byLayer = loader.loadAll().stream()
                .collect(Collectors.groupingBy(SourceDocument::sourceLayer, Collectors.counting()));
        assertThat(byLayer.get(1)).isEqualTo(loader.loadLayer1().size());
        assertThat(byLayer.get(2)).isEqualTo(loader.loadLayer2().size());
    }

    private static SourceDocument byId(List<SourceDocument> docs, String id) {
        return docs.stream().filter(d -> id.equals(d.docId())).findFirst().orElseThrow();
    }
}
