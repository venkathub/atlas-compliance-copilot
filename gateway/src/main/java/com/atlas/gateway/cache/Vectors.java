package com.atlas.gateway.cache;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/** Vector helpers for the semantic cache: FLOAT32 little-endian encoding (RediSearch) + cosine similarity. */
public final class Vectors {

    private Vectors() {
    }

    /** Encode a float vector as little-endian FLOAT32 bytes (the layout RediSearch expects). */
    public static byte[] toBytes(float[] vec) {
        ByteBuffer buf = ByteBuffer.allocate(vec.length * Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        for (float v : vec) {
            buf.putFloat(v);
        }
        return buf.array();
    }

    /** Cosine similarity in [-1, 1]; 0 if either vector is zero-length or null. */
    public static double cosineSimilarity(float[] a, float[] b) {
        if (a == null || b == null || a.length != b.length || a.length == 0) {
            return 0.0;
        }
        double dot = 0, na = 0, nb = 0;
        for (int i = 0; i < a.length; i++) {
            dot += (double) a[i] * b[i];
            na += (double) a[i] * a[i];
            nb += (double) b[i] * b[i];
        }
        if (na == 0 || nb == 0) {
            return 0.0;
        }
        return dot / (Math.sqrt(na) * Math.sqrt(nb));
    }
}
