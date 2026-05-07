<?php
/**
 * OpenAPI Client Example (PHP)
 *
 * Requirements: PHP 7.4+
 *
 * Usage:
 * 1. Set your AppId and Secret
 * 2. Call request methods to make API calls
 */

class OpenApiClient
{
    private string $gatewayUrl;
    private string $appId;
    private string $secret;
    private $ch;

    public function __construct(
        string $gatewayUrl = "http://localhost:8080/openapi",
        string $appId = "partner-a",
        string $secret = "partner-a-secret-key-change-in-production"
    ) {
        $this->gatewayUrl = rtrim($gatewayUrl, '/');
        $this->appId = $appId;
        $this->secret = $secret;
        $this->ch = curl_init();
    }

    public function __destruct()
    {
        if (is_resource($this->ch)) {
            curl_close($this->ch);
        }
    }

    /**
     * Send a GET request
     */
    public function get(string $path, ?array $params = null): string
    {
        return $this->request('GET', $path, $params);
    }

    /**
     * Send a POST request
     */
    public function post(string $path, ?array $data = null): string
    {
        return $this->request('POST', $path, null, $data);
    }

    /**
     * Execute the request with HMAC signature
     */
    public function request(
        string $method,
        string $path,
        ?array $params = null,
        ?array $data = null
    ): string {
        // 1. Generate timestamp (milliseconds)
        $timestamp = (string)(int)(microtime(true) * 1000);

        // 2. Build sign path (include gateway prefix for signature)
        $gatewayPrefix = '/openapi';
        $signPath = $gatewayPrefix . $path;

        // 3. Build query string
        $queryString = '';
        if ($params !== null && count($params) > 0) {
            ksort($params);
            $queryString = http_build_query($params);
        }

        // 4. Build request body
        $body = '';
        $bodyJson = null;
        if ($data !== null && count($data) > 0) {
            $bodyJson = json_encode($data, JSON_UNESCAPED_UNICODE);
            $body = $bodyJson;
        }

        // 5. Calculate signature (use signPath for signature)
        $signContent = $timestamp . $method . $signPath . $queryString . $body;
        $sign = $this->hmacSha256($this->secret, $signContent);

        // 5. Build full URL
        $url = $this->gatewayUrl . $path;
        if ($queryString !== '') {
            $url .= '?' . $queryString;
        }

        // 6. Build headers
        $headers = [
            "X-App-Id: {$this->appId}",
            "X-Timestamp: {$timestamp}",
            "X-Sign: {$sign}",
        ];

        if ($bodyJson !== null) {
            $headers[] = "Content-Type: application/json";
        }

        // 7. Send request
        curl_reset($this->ch);
        curl_setopt($this->ch, CURLOPT_URL, $url);
        curl_setopt($this->ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($this->ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($this->ch, CURLOPT_TIMEOUT, 30);

        if ($method === 'POST') {
            curl_setopt($this->ch, CURLOPT_POST, true);
            if ($bodyJson !== null) {
                curl_setopt($this->ch, CURLOPT_POSTFIELDS, $bodyJson);
            }
        }

        $response = curl_exec($this->ch);
        $httpCode = curl_getinfo($this->ch, CURLINFO_HTTP_CODE);

        if ($response === false) {
            throw new RuntimeException('Request failed: ' . curl_error($this->ch));
        }

        if ($httpCode >= 400) {
            throw new RuntimeException("HTTP error: {$httpCode}");
        }

        return $response;
    }

    /**
     * Calculate HMAC-SHA256 signature
     */
    private function hmacSha256(string $secret, string $data): string
    {
        return base64_encode(
            hash_hmac('sha256', $data, $secret, true)
        );
    }
}

// ==================== Usage Examples ====================

// Example 1: GET request
echo "=== GET Request Example ===\n";
$client = new OpenApiClient();
$result = $client->get('/fund/selector/list');
echo $result . "\n";

// Example 2: GET request with query parameters
echo "\n=== GET with Parameters Example ===\n";
$result = $client->get('/fund/selector/list', ['category' => '混合型', 'page' => 1]);
echo $result . "\n";

// Example 3: POST request
echo "\n=== POST Request Example ===\n";
$result = $client->post('/fund/add', ['name' => 'Test Fund', 'category' => '混合型']);
echo $result . "\n";
