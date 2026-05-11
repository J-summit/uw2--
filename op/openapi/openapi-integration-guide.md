# OpenAPI Integration Guide

## Overview

This document describes how to integrate with external-facing API endpoints using HMAC-SHA256 signature verification for secure authentication.

## Base URLs

| Environment | URL |
|-------------|-----|
| Testing | `http://gateway-test.tongyu.tech/openapi` |
| Production | `http://gateway.tongyu.tech/openapi` |

## Available Services

| Service | Path | Description |
|---------|------|-------------|
| Fund Service | `/openapi/fund/**` | Fund queries, filtering, etc. |
| Common Service | `/openapi/comm/**` | General business endpoints |
| Auth Service | `/openapi/auth/**` | Authentication endpoints |

## Signature Algorithm

### Signature Content

The signature content is constructed by concatenating the following fields in order:

```
signContent = timestamp + method + path + queryString + body
```

| Field | Description | Example |
|-------|-------------|---------|
| timestamp | Request timestamp (milliseconds) | `1744705238000` |
| method | HTTP method | `GET`, `POST` |
| path | Request path (without domain) | `/openapi/fund/selector/list` |
| queryString | Query string (without `?`) | `category=Mixed&page=1` |
| body | Request body (empty string if none) | `{"name":"Test"}` |

### Signature Calculation

```java
// Java example
String signContent = timestamp + method + path + queryString + body;
String sign = Base64.encode(HmacSHA256(secret, signContent));
```

### Signature Verification

```
sign = Base64(HMAC-SHA256(secret, signContent))
```

## Required Headers

| Header | Required | Description |
|--------|----------|-------------|
| X-App-Id | Yes | Assigned application identifier |
| X-Timestamp | Yes | Request timestamp (milliseconds) |
| X-Sign | Yes | HMAC-SHA256 signature |
| Content-Type | Yes (POST) | `application/json` |

## Error Codes

| Error Code | Description |
|------------|-------------|
| `openapi.missing.params` | Missing required parameters |
| `openapi.unknown.app` | Unknown AppId |
| `openapi.invalid.timestamp` | Invalid timestamp format |
| `openapi.timestamp.expired` | Request expired (valid within 5 minutes) |
| `openapi.sign.verify.fail` | Signature verification failed |

## Security Recommendations

1. **Key Security**: Keep AppId and Secret confidential; never hardcode them in client code
2. **Time Synchronization**: Ensure server time is within 5 minutes of standard time
3. **Log Protection**: Avoid printing signature content in production logs

## Integration Steps

1. Contact administrator to obtain `AppId` and `Secret`
2. Implement signature logic according to this guide
3. Perform integration testing in the test environment
4. Switch to production environment after verification

## Example Code

Sample code in various languages:

- [Java](./examples/java/OpenApiClient.java)
- [Python](./examples/python/openapi_client.py)
- [PHP](./examples/php/OpenApiClient.php)
- [C#](./examples/csharp/OpenApiClient.cs)
