package com.atlas.ragengine.api;

import com.atlas.ragengine.security.RequestHeaders;
import jakarta.servlet.http.HttpServletRequest;
import java.util.HashMap;
import java.util.Map;

/** Thin adapter: {@link HttpServletRequest} → the servlet-free {@link RequestHeaders}. */
final class HttpRequestHeaders {

    private HttpRequestHeaders() {
    }

    static RequestHeaders of(HttpServletRequest request) {
        Map<String, String> headers = new HashMap<>();
        var names = request.getHeaderNames();
        while (names.hasMoreElements()) {
            String name = names.nextElement();
            headers.put(name, request.getHeader(name));
        }
        return RequestHeaders.of(headers);
    }
}
