package com.atlas.ragengine.common;

/** Helpers for the pgvector text I/O format. */
public final class PgVector {

    private PgVector() {
    }

    /** Format a float[] as the pgvector text literal {@code [v1,v2,...]} for {@code ?::vector} binds. */
    public static String toLiteral(float[] embedding) {
        StringBuilder sb = new StringBuilder(embedding.length * 8).append('[');
        for (int i = 0; i < embedding.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(embedding[i]);
        }
        return sb.append(']').toString();
    }
}
