package com.atlas.ragengine.corpus;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/**
 * Pure-unit fixture-integrity guard (no Docker, no Spring context) for the P1 corpus + fixtures
 * (D1/D2/D3/D4/D7). Catches fixture rot — bad clearance labels, dangling doc-id references,
 * empty corpus files — before the heavier Testcontainers ITs (tasks 3/5/6) consume them.
 */
class FixtureCatalogTest {

    private static final Set<String> CLEARANCES = Set.of("public", "analyst", "compliance", "restricted");
    private final ObjectMapper json = new ObjectMapper();
    private final PathMatchingResourcePatternResolver resolver = new PathMatchingResourcePatternResolver();

    // ---- D1: Layer-1 FinanceBench manifest + snippet files -----------------

    @Test
    void layer1ManifestResolvesToNonEmptySnippetFiles() throws IOException {
        JsonNode manifest = json.readTree(resource("classpath:corpus/layer1/manifest.json").getInputStream());
        assertThat(manifest.get("source_layer").asInt()).isEqualTo(1);
        JsonNode docs = manifest.get("documents");
        assertThat(docs).isNotNull();
        assertThat(docs.size()).isBetween(10, 15); // ADR-0017: ~10-15 docs

        Set<String> files = new HashSet<>();
        for (JsonNode doc : docs) {
            String file = doc.get("file").asText();
            assertThat(files.add(file)).as("duplicate file " + file).isTrue();
            assertThat(doc.get("clearance").asText()).isIn(CLEARANCES);
            assertThat(doc.get("source_uri").asText()).isNotBlank();
            Resource snippet = resource("classpath:corpus/layer1/" + file);
            assertThat(snippet.exists()).as("missing snippet " + file).isTrue();
            String content = new String(snippet.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            assertThat(content.strip()).as("empty snippet " + file).isNotEmpty();
        }
    }

    // ---- D2: Layer-2 authored overlay --------------------------------------

    @Test
    void layer2OverlayCoversAllClearanceLevels() throws IOException {
        Resource[] docs = resolver.getResources("classpath:corpus/layer2/*.md");
        assertThat(docs.length).isBetween(10, 20); // ADR-0004: ~10-20 narrative docs

        Map<String, String> clearanceById = new HashMap<>();
        for (Resource doc : docs) {
            Map<String, String> fm = frontMatter(doc);
            assertThat(fm.get("doc_id")).as("doc_id in " + doc.getFilename()).isNotBlank();
            assertThat(fm.get("title")).as("title in " + doc.getFilename()).isNotBlank();
            assertThat(fm.get("source_layer")).isEqualTo("2");
            assertThat(fm.get("clearance")).as("clearance in " + doc.getFilename()).isIn(CLEARANCES);
            clearanceById.put(fm.get("doc_id"), fm.get("clearance"));
        }
        // every clearance level represented (the RBAC gradient)
        assertThat(new HashSet<>(clearanceById.values())).containsExactlyInAnyOrderElementsOf(CLEARANCES);
        // the forcing-story account doc exists at compliance, the SAR draft at restricted
        assertThat(clearanceById).containsEntry("l2-northwind-aml-exceptions-2026q2", "compliance");
        assertThat(clearanceById).containsEntry("l2-northwind-sar-draft", "restricted");
    }

    // ---- D3: dev user -> clearance shim ------------------------------------

    @Test
    void devClearanceMapIsValid() throws IOException {
        JsonNode map = json.readTree(resource("classpath:dev/clearance-users.json").getInputStream());
        assertThat(map.get("default_clearance").asText()).isIn(CLEARANCES);
        JsonNode users = map.get("users");
        assertThat(users.size()).isGreaterThanOrEqualTo(4);
        users.forEach(u -> assertThat(u.get("clearance").asText()).isIn(CLEARANCES));
        assertThat(users.get("priya").get("clearance").asText()).isEqualTo("compliance");
        assertThat(users.get("bsa-admin").get("clearance").asText()).isEqualTo("restricted");
    }

    // ---- D4: negative-access golden set ------------------------------------

    @Test
    void negativeAccessCasesAreWellFormedAndReferenceRealDocs() throws IOException {
        Set<String> layer2Ids = layer2DocIds();
        JsonNode root = json.readTree(resource("classpath:fixtures/negative_access.json").getInputStream());
        JsonNode cases = root.get("cases");
        assertThat(cases.size()).isGreaterThanOrEqualTo(5);

        Set<String> ids = new HashSet<>();
        for (JsonNode c : cases) {
            assertThat(ids.add(c.get("id").asText())).as("duplicate case id").isTrue();
            assertThat(c.get("clearance").asText()).isIn(CLEARANCES);
            assertThat(c.get("query").asText()).isNotBlank();
            for (JsonNode fc : c.get("forbiddenClearances")) {
                assertThat(fc.asText()).isIn(CLEARANCES);
            }
            for (JsonNode id : c.get("forbiddenDocIds")) {
                assertThat(layer2Ids).as("forbidden doc id " + id.asText()).contains(id.asText());
            }
            for (JsonNode id : c.get("allowedDocIds")) {
                assertThat(layer2Ids).as("allowed doc id " + id.asText()).contains(id.asText());
            }
        }
    }

    // ---- D7: poisoned-doc fixtures -----------------------------------------

    @Test
    void poisonedFixturesAndExpectationsAlign() throws IOException {
        Resource[] poison = resolver.getResources("classpath:fixtures/poisoned/poison-*.md");
        assertThat(poison.length).isGreaterThanOrEqualTo(4);

        Map<String, Boolean> poisonFlagById = new HashMap<>();
        for (Resource doc : poison) {
            Map<String, String> fm = frontMatter(doc);
            assertThat(fm.get("clearance")).isIn(CLEARANCES);
            assertThat(fm.get("poison_class")).isNotBlank();
            poisonFlagById.put(fm.get("doc_id"), Boolean.parseBoolean(fm.get("poison")));
        }
        // at least one true-poison doc and exactly one benign control
        assertThat(poisonFlagById.values()).contains(true, false);

        JsonNode exp = json.readTree(resource("classpath:fixtures/poisoned/expectations.json").getInputStream());
        for (JsonNode d : exp.get("docs")) {
            String id = d.get("doc_id").asText();
            assertThat(poisonFlagById).as("expectations references unknown poison doc " + id).containsKey(id);
            // a doc the heuristic must quarantine is a true-poison doc; benign control must not
            assertThat(d.get("mustQuarantine").asBoolean()).isEqualTo(poisonFlagById.get(id));
        }
        assertThat(exp.get("injectionPhrases").size()).isGreaterThan(0);
        assertThat(exp.get("answerMustNotContain").size()).isGreaterThan(0);
    }

    // ---- helpers -----------------------------------------------------------

    private Resource resource(String location) {
        return resolver.getResource(location);
    }

    private Set<String> layer2DocIds() throws IOException {
        Set<String> ids = new HashSet<>();
        for (Resource doc : resolver.getResources("classpath:corpus/layer2/*.md")) {
            ids.add(frontMatter(doc).get("doc_id"));
        }
        return ids;
    }

    /** Minimal YAML front-matter reader for our flat `key: value` blocks delimited by `---`. */
    private Map<String, String> frontMatter(Resource md) throws IOException {
        String text = new String(md.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        assertThat(text).as("front-matter delimiter in " + md.getFilename()).startsWith("---");
        int end = text.indexOf("\n---", 3);
        assertThat(end).as("closing front-matter delimiter in " + md.getFilename()).isGreaterThan(0);
        String block = text.substring(3, end);
        Map<String, String> fm = new HashMap<>();
        for (String line : block.split("\n")) {
            int colon = line.indexOf(':');
            if (colon <= 0) {
                continue;
            }
            String key = line.substring(0, colon).trim();
            String value = line.substring(colon + 1).trim();
            if (value.length() >= 2 && value.startsWith("\"") && value.endsWith("\"")) {
                value = value.substring(1, value.length() - 1);
            }
            fm.put(key, value);
        }
        return fm;
    }
}
