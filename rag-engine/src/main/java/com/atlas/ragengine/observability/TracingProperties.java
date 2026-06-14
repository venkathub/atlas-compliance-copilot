package com.atlas.ragengine.observability;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Observability tracing config (ADR-0030 / D-P2-10). Bound from {@code atlas.trace.*}.
 *
 * <p><b>Compliance default is OFF:</b> traces carry only ids/clearance/model/token/latency. Setting
 * {@code atlas.trace.content=full} (env {@code ATLAS_TRACE_CONTENT=full}) enables redaction-filtered
 * prompt/response capture for local debugging — it must never be enabled on a shared/prod stack.
 */
@ConfigurationProperties(prefix = "atlas.trace")
public class TracingProperties {

    /** Content-capture mode. {@code off} (default) | {@code full} (dev-only, redacted). */
    private String content = "off";

    /** Extra exact strings to redact when content capture is on (e.g. known PII tokens). */
    private List<String> piiDenylist = List.of();

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public List<String> getPiiDenylist() {
        return piiDenylist;
    }

    public void setPiiDenylist(List<String> piiDenylist) {
        this.piiDenylist = piiDenylist == null ? List.of() : List.copyOf(piiDenylist);
    }

    public ContentMode mode() {
        return ContentMode.fromValue(content);
    }

    /** Defaults used by the no-op tracer and unit tests (content OFF, empty deny-list). */
    public static TracingProperties defaults() {
        return new TracingProperties();
    }
}
