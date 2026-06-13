package com.atlas.ragengine.ingest;

import java.util.HashMap;
import java.util.Map;

/**
 * Minimal YAML front-matter reader for our flat {@code key: value} blocks delimited by {@code ---}.
 * Avoids pulling a full YAML dependency for the simple authored-overlay schema.
 */
final class FrontMatter {

    private final Map<String, String> values;
    private final String body;

    private FrontMatter(Map<String, String> values, String body) {
        this.values = values;
        this.body = body;
    }

    String value(String key) {
        return values.get(key);
    }

    String body() {
        return body;
    }

    static FrontMatter parse(String raw) {
        String normalized = raw.replace("\r\n", "\n");
        if (!normalized.startsWith("---")) {
            return new FrontMatter(Map.of(), normalized);
        }
        int end = normalized.indexOf("\n---", 3);
        if (end < 0) {
            return new FrontMatter(Map.of(), normalized);
        }
        String block = normalized.substring(3, end);
        String body = normalized.substring(normalized.indexOf('\n', end + 1) + 1).strip();
        Map<String, String> values = new HashMap<>();
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
            if ("null".equals(value)) {
                value = null;
            }
            values.put(key, value);
        }
        return new FrontMatter(values, body);
    }
}
