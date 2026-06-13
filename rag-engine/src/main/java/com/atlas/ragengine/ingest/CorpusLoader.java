package com.atlas.ragengine.ingest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/**
 * Reads the two-layer corpus into {@link SourceDocument}s:
 * <ul>
 *   <li><b>Layer 1 (D1)</b> — the FinanceBench manifest + committed evidence snippet files.</li>
 *   <li><b>Layer 2 (D2)</b> — the authored AML/compliance markdown overlay (YAML front-matter).</li>
 * </ul>
 * No DB, no model — pure resource reading, so it is unit-testable on its own.
 */
public class CorpusLoader {

    private static final ObjectMapper JSON = new ObjectMapper();

    private final IngestionProperties props;
    private final PathMatchingResourcePatternResolver resolver = new PathMatchingResourcePatternResolver();

    public CorpusLoader(IngestionProperties props) {
        this.props = props;
    }

    public List<SourceDocument> loadAll() {
        List<SourceDocument> docs = new ArrayList<>(loadLayer1());
        docs.addAll(loadLayer2());
        return docs;
    }

    /** Layer 1: manifest.json pins each snippet file + its clearance/provenance. */
    public List<SourceDocument> loadLayer1() {
        Resource manifestRes = resolver.getResource(props.layer1Manifest());
        String baseLocation = props.layer1Manifest().replaceFirst("manifest\\.json$", "");
        List<SourceDocument> out = new ArrayList<>();
        try {
            JsonNode manifest = JSON.readTree(manifestRes.getInputStream());
            for (JsonNode doc : manifest.get("documents")) {
                String file = doc.get("file").asText();
                String origin = baseLocation + file;
                String content = read(resolver.getResource(origin));
                Map<String, Object> meta = new HashMap<>();
                meta.put("company", text(doc, "company"));
                meta.put("docName", text(doc, "doc_name"));
                meta.put("docType", text(doc, "doc_type"));
                meta.put("section", text(doc, "section"));
                meta.put("gicsSector", text(doc, "gics_sector"));
                meta.put("financebenchId", text(doc, "financebench_id"));
                if (doc.hasNonNull("doc_period")) {
                    meta.put("docPeriod", doc.get("doc_period").asInt());
                }
                String title = text(doc, "doc_name") + " — " + text(doc, "section");
                out.add(new SourceDocument(
                        text(doc, "financebench_id"), title, text(doc, "clearance"),
                        text(doc, "source_uri"), 1, origin, content, meta));
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to load Layer-1 manifest " + props.layer1Manifest(), e);
        }
        return out;
    }

    /** Layer 2: authored markdown with YAML front-matter. */
    public List<SourceDocument> loadLayer2() {
        List<SourceDocument> out = new ArrayList<>();
        String base = globBase(props.layer2Glob());
        try {
            Resource[] resources = resolver.getResources(props.layer2Glob());
            for (Resource res : resources) {
                String raw = read(res);
                FrontMatter fm = FrontMatter.parse(raw);
                Map<String, Object> meta = new HashMap<>();
                meta.put("account", fm.value("account"));
                meta.put("docType", fm.value("doc_type"));
                meta.put("containsPii", Boolean.parseBoolean(fm.value("contains_pii")));
                String origin = base + res.getFilename();
                out.add(new SourceDocument(
                        fm.value("doc_id"), fm.value("title"), fm.value("clearance"),
                        fm.value("source_uri"), 2, origin, fm.body(), meta));
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to load Layer-2 overlay " + props.layer2Glob(), e);
        }
        return out;
    }

    /** The fixed prefix of a resource glob, up to (and including) the last '/' before the wildcard. */
    private static String globBase(String glob) {
        int star = glob.indexOf('*');
        String prefix = star >= 0 ? glob.substring(0, star) : glob;
        int slash = prefix.lastIndexOf('/');
        return slash >= 0 ? prefix.substring(0, slash + 1) : prefix;
    }

    private static String read(Resource res) throws IOException {
        return new String(res.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
    }

    private static String text(JsonNode node, String field) {
        JsonNode v = node.get(field);
        return (v == null || v.isNull()) ? null : v.asText();
    }
}
