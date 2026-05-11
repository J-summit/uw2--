using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;

namespace OpenApiClient;

/// <summary>
/// OpenAPI Client Example (.NET)
/// </summary>
public class OpenApiClient : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _gatewayUrl;
    private readonly string _appId;
    private readonly string _secret;

    public OpenApiClient(
        string gatewayUrl = "http://localhost:8080/openapi",
        string appId = "partner-a",
        string secret = "partner-a-secret-key-change-in-production")
    {
        _gatewayUrl = gatewayUrl.TrimEnd('/');
        _appId = appId;
        _secret = secret;
        _httpClient = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
    }

    public void Dispose()
    {
        _httpClient?.Dispose();
    }

    /// <summary>
    /// Send a GET request
    /// </summary>
    public async Task<string> GetAsync(string path, Dictionary<string, string>? queryParams = null)
    {
        var url = BuildUrl(path, queryParams);
        return await SendAsync("GET", url);
    }

    /// <summary>
    /// Send a POST request with JSON body
    /// </summary>
    public async Task<string> PostAsync<T>(string path, T data) where T : class
    {
        var url = BuildUrl(path);
        return await SendAsync("POST", url, data);
    }

    private string BuildUrl(string path, Dictionary<string, string>? queryParams = null)
    {
        var url = $"{_gatewayUrl}{path}";
        if (queryParams != null && queryParams.Count > 0)
        {
            var queryString = string.Join("&",
                queryParams.OrderBy(kv => kv.Key)
                    .Select(kv => $"{Uri.EscapeDataString(kv.Key)}={Uri.EscapeDataString(kv.Value)}"));
            url += "?" + queryString;
        }
        return url;
    }

    private async Task<string> SendAsync<T>(string method, string url, T? data = null) where T : class
    {
        // 1. Generate timestamp (milliseconds since Unix epoch)
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString();

        // 2. Build request
        using var request = new HttpRequestMessage(new HttpMethod(method), url);
        request.Headers.Add("X-App-Id", _appId);
        request.Headers.Add("X-Timestamp", timestamp);

        if (data != null)
        {
            request.Content = JsonContent.Create(data, options: new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            });

            // 3. Calculate signature (includes body)
            var body = await request.Content.ReadAsStringAsync();
            var signContent = $"{timestamp}{method}{pathFromUrl(url)}{queryFromUrl(url)}{body}";
            request.Headers.Remove("X-Timestamp");
            request.Headers.Add("X-Timestamp", timestamp);
            request.Headers.Add("X-Sign", HmacSha256(_secret, signContent));
        }
        else
        {
            // 3. Calculate signature (no body)
            var signContent = $"{timestamp}{method}{pathFromUrl(url)}{queryFromUrl(url)}";
            request.Headers.Add("X-Sign", HmacSha256(_secret, signContent));
        }

        // 4. Send request
        var response = await _httpClient.SendAsync(request);
        var responseBody = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
        {
            throw new HttpRequestException($"HTTP {(int)response.StatusCode}: {responseBody}");
        }

        return responseBody;
    }

    private static string pathFromUrl(string url)
    {
        var uri = new Uri(url);
        return uri.AbsolutePath;
    }

    private static string queryFromUrl(string url)
    {
        var uri = new Uri(url);
        return uri.Query.TrimStart('?');
    }

    /// <summary>
    /// Calculate HMAC-SHA256 signature
    /// </summary>
    private static string HmacSha256(string secret, string data)
    {
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
        var hash = hmac.ComputeHash(Encoding.UTF8.GetBytes(data));
        return Convert.ToBase64String(hash);
    }
}

// ==================== Usage Examples ====================

public class Program
{
    public static async Task Main()
    {
        await using var client = new OpenApiClient();

        // Example 1: GET request
        Console.WriteLine("=== GET Request Example ===");
        var result1 = await client.GetAsync("/fund/selector/list");
        Console.WriteLine(result1);

        // Example 2: GET request with query parameters
        Console.WriteLine("\n=== GET with Parameters Example ===");
        var queryParams = new Dictionary<string, string>
        {
            { "category", "Mixed" },
            { "page", "1" }
        };
        var result2 = await client.GetAsync("/fund/selector/list", queryParams);
        Console.WriteLine(result2);

        // Example 3: POST request
        Console.WriteLine("\n=== POST Request Example ===");
        var requestData = new { name = "Test Fund", category = "Mixed" };
        var result3 = await client.PostAsync("/fund/add", requestData);
        Console.WriteLine(result3);
    }
}
