// Atlas container health probe for the distroless Java services (P6 Task 2).
//
// The runtime images are `gcr.io/distroless/java21-debian12:nonroot` — no shell, no curl,
// no wget — so a `HEALTHCHECK CMD curl ...` cannot work. This 30-line probe uses only
// java.base (java.net.http), is compiled ONCE to architecture-independent bytecode in a
// `--platform=$BUILDPLATFORM` builder stage, and is copied into both the amd64 and arm64
// runtime images (no QEMU for the runtime layers — the distroless "no RUN steps" property
// is preserved). It exits 0 on a 2xx from the Spring Actuator health endpoint, else 1.
//
// Usage (in the Dockerfile HEALTHCHECK):
//   java -cp /app HealthCheck http://127.0.0.1:<port>/actuator/health
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

public final class HealthCheck {
    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("usage: HealthCheck <url>");
            System.exit(2);
        }
        try {
            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(3))
                    .build();
            HttpRequest request = HttpRequest.newBuilder(URI.create(args[0]))
                    .timeout(Duration.ofSeconds(4))
                    .GET()
                    .build();
            HttpResponse<Void> response = client.send(request, HttpResponse.BodyHandlers.discarding());
            int status = response.statusCode();
            System.exit(status >= 200 && status < 300 ? 0 : 1);
        } catch (Exception e) {
            System.exit(1);
        }
    }
}
