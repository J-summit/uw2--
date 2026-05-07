"""
OpenAPI Client Example (Python)

Requirements:
    pip install requests

Usage:
    client = OpenApiClient(app_id="partner-a", secret="your-secret")
    result = client.get("/fund/selector/list")
    result = client.post("/fund/add", {"name": "Test Fund"})
"""

import base64
import hashlib
import hmac
import time
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    raise ImportError("Please install requests: pip install requests")


class OpenApiClient:
    """OpenAPI Client for external system integration"""

    def __init__(
        self,
        gateway_url: str = "http://localhost:8080/openapi",
        app_id: str = "partner-a",
        secret: str = "partner-a-secret-key-change-in-production"
    ):
        """
        Initialize the OpenAPI client

        Args:
            gateway_url: API gateway base URL
            app_id: Application ID assigned by the API provider
            secret: Secret key for HMAC signature
        """
        self.gateway_url = gateway_url.rstrip("/")
        self.app_id = app_id
        self.secret = secret
        self.session = requests.Session()

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Send a GET request

        Args:
            path: Request path (e.g., /fund/selector/list)
            params: Query parameters dictionary

        Returns:
            Response body as string
        """
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Send a POST request

        Args:
            path: Request path
            data: Form data dictionary
            json: JSON data dictionary

        Returns:
            Response body as string
        """
        return self._request("POST", path, data=data, json=json)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None
    ) -> str:
        """Execute the HTTP request with HMAC signature"""

        # 1. Generate timestamp (milliseconds)
        timestamp = str(int(time.time() * 1000))

        # 2. Build URL (use path as-is for URL construction)
        url = f"{self.gateway_url}{path}"

        # 3. Build sign path (use full path including gateway prefix for signature)
        # Extract the gateway prefix (e.g., /openapi from http://localhost:8080/openapi)
        from urllib.parse import urlparse
        gateway_prefix = urlparse(self.gateway_url).path  # e.g., /openapi
        sign_path = gateway_prefix + path  # e.g., /openapi/fund/add

        # 3. Build query string (must use URL encoding to match server-side calculation)
        import urllib.parse
        query_string = ""
        if params:
            # Filter None values, keep original order, then URL encode
            filtered_params = [(k, v) for k, v in params.items() if v is not None]
            query_string = urllib.parse.urlencode(filtered_params)

        # 4. Build request body
        body = ""
        body_json = None
        if json is not None:
            import json as json_lib
            body_json = json_lib.dumps(json, ensure_ascii=False)
            body = body_json
        elif data:
            # URL encode form data
            filtered_data = [(k, v) for k, v in data.items() if v is not None]
            body = urllib.parse.urlencode(filtered_data)

        # 5. Calculate signature (use full path including gateway prefix)
        sign_content = f"{timestamp}{method}{sign_path}{query_string}{body}"
        sign = self._hmac_sha256(self.secret, sign_content)

        # 6. Build headers
        headers = {
            "X-App-Id": self.app_id,
            "X-Timestamp": timestamp,
            "X-Sign": sign,
        }

        if json is not None:
            headers["Content-Type"] = "application/json"

        # 7. Send request
        if method == "GET":
            response = self.session.get(url, params=params, headers=headers)
        elif method == "POST":
            if json is not None:
                # Use data= with manually encoded JSON to ensure consistency with signature
                response = self.session.post(url, data=body_json.encode('utf-8'), headers=headers)
            else:
                response = self.session.post(url, data=data, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        return response.text

    @staticmethod
    def _hmac_sha256(secret: str, data: str) -> str:
        """
        Calculate HMAC-SHA256 signature

        Args:
            secret: Secret key
            data: Data to sign

        Returns:
            Base64 encoded signature
        """
        mac = hmac.new(
            secret.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode("utf-8")


# ==================== Usage Examples ====================

if __name__ == "__main__":
    client = OpenApiClient()

    # Example 1: GET request
    print("=== GET Request Example ===")
    result = client.get("/fund/selector/list")
    print(result)

    # Example 2: GET request with query parameters
    print("\n=== GET with Parameters Example ===")
    result = client.get("/fund/selector/list", params={"pageSize": "5", "page": 1})
    print(result)

