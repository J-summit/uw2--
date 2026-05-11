package com.example.openapi;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import java.util.TreeMap;

/**
 * OpenAPI Client Example (Java)
 *
 * Usage:
 * 1. Set your AppId and Secret
 * 2. Call request methods to make API calls
 */
public class OpenApiClient {

    private static final String GATEWAY_URL = "http://localhost:8080/openapi";
    private static final String APP_ID = "partner-a";
    private static final String SECRET = "partner-a-secret-key-change-in-production";

    private final HttpClient httpClient;

    public OpenApiClient() {
        this.httpClient = HttpClient.newHttpClient();
    }

    /**
     * Send a GET request
     */
    public String get(String path) throws IOException, InterruptedException {
        return doRequest("GET", path, "", "");
    }

    /**
     * Send a GET request with query parameters (Map will be URL encoded)
     */
    public String get(String path, Map<String, String> params) throws IOException, InterruptedException {
        String queryString = buildQueryString(params);
        return doRequest("GET", path, queryString, "");
    }

    /**
     * Build URL-encoded query string from Map
     */
    private String buildQueryString(Map<String, String> params) {
        if (params == null || params.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        // Sort by key for consistent ordering
        new TreeMap<>(params).forEach((key, value) -> {
            if (value != null) {
                if (sb.length() > 0) {
                    sb.append("&");
                }
                try {
                    sb.append(URLEncoder.encode(key, StandardCharsets.UTF_8));
                    sb.append("=");
                    sb.append(URLEncoder.encode(value, StandardCharsets.UTF_8));
                } catch (IOException e) {
                    throw new RuntimeException("Failed to encode query string", e);
                }
            }
        });
        return sb.toString();
    }

    /**
     * Send a POST request
     */
    public String post(String path, String body) throws IOException, InterruptedException {
        return doRequest("POST", path, "", body);
    }

    /**
     * Execute the request
     */
    public String doRequest(String method, String path, String queryString, String body)
            throws IOException, InterruptedException {

        // 1. Generate timestamp
        String timestamp = String.valueOf(System.currentTimeMillis());

        // 2. Build sign path (include gateway prefix for signature)
        String gatewayPrefix = "/openapi";  // Extract from GATEWAY_URL if needed
        String signPath = gatewayPrefix + path;

        // 3. Build full URL
        String fullUrl = GATEWAY_URL + path;
        if (queryString != null && !queryString.isEmpty()) {
            fullUrl += "?" + queryString;
        }

        // 4. Calculate signature (use signPath for signature)
        String signContent = timestamp + method + signPath + (queryString != null ? queryString : "") + body;
        String sign = hmacSha256(SECRET, signContent);

        // 4. Build request
        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                .uri(URI.create(fullUrl))
                .header("X-App-Id", APP_ID)
                .header("X-Timestamp", timestamp)
                .header("X-Sign", sign);

        if ("POST".equals(method)) {
            requestBuilder
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body));
        } else {
            requestBuilder.GET();
        }

        // 5. Send request
        HttpResponse<String> response = httpClient.send(
                requestBuilder.build(),
                HttpResponse.BodyHandlers.ofString()
        );

        return response.body();
    }

    /**
     * Calculate HMAC-SHA256 signature
     */
    private String hmacSha256(String secret, String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            SecretKeySpec keySpec = new SecretKeySpec(
                    secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
            mac.init(keySpec);
            byte[] rawHmac = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
            return Base64.getEncoder().encodeToString(rawHmac);
        } catch (Exception e) {
            throw new RuntimeException("Failed to calculate signature", e);
        }
    }

    // ==================== Usage Examples ====================

    public static void main(String[] args) throws Exception {
        OpenApiClient client = new OpenApiClient();

        // Example 1: GET request
        System.out.println("=== GET Request Example ===");
        String result1 = client.get("/fund/selector/list");
        System.out.println(result1);

        // Example 2: GET request with query parameters (using Map for proper URL encoding)
        System.out.println("\n=== GET with Parameters Example ===");
        Map<String, String> params = new HashMap<>();
        params.put("category", "Mixed");
        params.put("page", "1");
        String result2 = client.get("/fund/selector/list", params);
        System.out.println(result2);

        // Example 3: POST request
        System.out.println("\n=== POST Request Example ===");
        String requestBody = "{\"name\":\"Test Fund\",\"category\":\"Mixed\"}";
        String result3 = client.post("/fund/add", requestBody);
        System.out.println(result3);
    }
}
