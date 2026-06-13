package com.atlas.ragengine.api;

/** {@code POST /v1/query} request body. {@code topK} is optional (defaults applied downstream). */
public record QueryRequest(String query, Integer topK) {

    public int topKOrDefault() {
        return topK == null ? 0 : topK; // 0 => service uses configured default
    }
}
