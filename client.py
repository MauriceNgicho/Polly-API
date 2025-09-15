import requests
from typing import Any, Dict, Optional


def register_user(
    username: str,
    password: str,
    *,
    base_url: str = "http://localhost:8000",
    timeout_seconds: float = 10.0,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """
    Register a new user against the Polly-API /register endpoint.

    Parameters:
        username: The username to register.
        password: The password to register.
        base_url: The API base URL. Defaults to "http://localhost:8000" as per the OpenAPI spec.
        timeout_seconds: The network timeout in seconds for the HTTP request.
        session: Optional requests.Session to reuse connections. If not provided, a one-off request is made.

    Returns:
        A dictionary containing the created user payload as returned by the API (UserOut schema).

    Raises:
        ValueError: If the server responds with a client error indicating a bad request (e.g., username already registered).
        requests.HTTPError: For non-successful responses where appropriate.
        requests.RequestException: For network-related errors.
    """

    if not username:
        raise ValueError("username must be a non-empty string")
    if not password:
        raise ValueError("password must be a non-empty string")

    url = f"{base_url.rstrip('/')}/register"
    payload: Dict[str, Any] = {"username": username, "password": password}

    http = session or requests

    try:
        response = http.post(url, json=payload, timeout=timeout_seconds)
    except requests.RequestException as request_error:
        # Surface network-level errors (DNS, connection, timeouts, etc.)
        raise request_error

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as json_error:
            raise requests.HTTPError(
                f"Expected JSON response from {url}, but failed to parse.",
                response=response,
            ) from json_error

    if response.status_code == 400:
        # Spec indicates 400 when username already registered or bad input
        # Try to extract message from JSON if present; otherwise use text
        error_message: str
        try:
            error_json = response.json()
            error_message = error_json.get("detail") or error_json.get("message") or response.text
        except ValueError:
            error_message = response.text
        raise ValueError(f"Registration failed (400): {error_message}")

    # Raise for other unexpected status codes
    try:
        response.raise_for_status()
    except requests.HTTPError as http_error:
        raise http_error

    # In case raise_for_status did not raise (unlikely), return parsed JSON if any
    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "content": response.text}


def get_polls(
    skip: int = 0,
    limit: int = 10,
    *,
    base_url: str = "http://localhost:8000",
    timeout_seconds: float = 10.0,
    session: Optional[requests.Session] = None,
) -> list[Dict[str, Any]]:
    """
    Fetch a paginated list of polls from /polls following the PollOut[] schema.

    Parameters:
        skip: Number of items to skip.
        limit: Maximum number of items to return.
        base_url: The API base URL. Defaults to "http://localhost:8000".
        timeout_seconds: The network timeout in seconds for the HTTP request.
        session: Optional requests.Session to reuse connections.

    Returns:
        A list of polls, each following the PollOut schema.

    Raises:
        requests.HTTPError: If the server returns a non-2xx response.
        requests.RequestException: For network-related errors.
        ValueError: If the response body is not a JSON array.
    """

    if skip < 0:
        raise ValueError("skip must be a non-negative integer")
    if limit <= 0:
        raise ValueError("limit must be a positive integer")

    url = f"{base_url.rstrip('/')}/polls"
    params = {"skip": skip, "limit": limit}

    http = session or requests

    try:
        response = http.get(url, params=params, timeout=timeout_seconds)
    except requests.RequestException as request_error:
        raise request_error

    if response.status_code == 200:
        try:
            data = response.json()
        except ValueError as json_error:
            raise requests.HTTPError(
                f"Expected JSON array from {response.url}, but failed to parse.",
                response=response,
            ) from json_error

        if not isinstance(data, list):
            raise ValueError("Expected response to be a JSON array of polls")
        return data

    # For any non-200, raise with context
    response.raise_for_status()
    # Defensive: if raise_for_status did not raise (unlikely), try to return parsed JSON
    try:
        parsed = response.json()
    except ValueError:
        parsed = {"status_code": response.status_code, "content": response.text}
    return parsed  # type: ignore[return-value]


def vote_on_poll(
    poll_id: int,
    option_id: int,
    token: str,
    *,
    base_url: str = "http://localhost:8000",
    timeout_seconds: float = 10.0,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """
    Cast a vote on a poll using /polls/{poll_id}/vote with bearer authentication.

    Parameters:
        poll_id: The target poll ID.
        option_id: The option to vote for.
        token: The JWT access token value (without the "Bearer " prefix).
        base_url: The API base URL. Defaults to "http://localhost:8000".
        timeout_seconds: The network timeout in seconds for the HTTP request.
        session: Optional requests.Session to reuse connections.

    Returns:
        A dictionary following the VoteOut schema on success (200).

    Raises:
        PermissionError: If unauthorized (401).
        FileNotFoundError: If the poll or option is not found (404).
        requests.HTTPError: For other non-success responses.
        requests.RequestException: For network-related errors.
    """

    if poll_id <= 0:
        raise ValueError("poll_id must be a positive integer")
    if option_id <= 0:
        raise ValueError("option_id must be a positive integer")
    if not token:
        raise ValueError("token must be a non-empty string")

    url = f"{base_url.rstrip('/')}/polls/{poll_id}/vote"
    payload: Dict[str, Any] = {"option_id": option_id}
    headers = {"Authorization": f"Bearer {token}"}

    http = session or requests

    try:
        response = http.post(url, json=payload, headers=headers, timeout=timeout_seconds)
    except requests.RequestException as request_error:
        raise request_error

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as json_error:
            raise requests.HTTPError(
                f"Expected JSON VoteOut from {response.url}, but failed to parse.",
                response=response,
            ) from json_error

    if response.status_code == 401:
        raise PermissionError("Unauthorized: missing or invalid token")

    if response.status_code == 404:
        # Try to surface API-provided details
        detail = None
        try:
            err_json = response.json()
            detail = err_json.get("detail") or err_json.get("message")
        except ValueError:
            pass
        message = f"Not found: {detail}" if detail else "Not found: poll or option"
        raise FileNotFoundError(message)

    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "content": response.text}


def get_poll_results(
    poll_id: int,
    *,
    base_url: str = "http://localhost:8000",
    timeout_seconds: float = 10.0,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    """
    Retrieve results for a specific poll from /polls/{poll_id}/results.

    Parameters:
        poll_id: The target poll ID.
        base_url: The API base URL. Defaults to "http://localhost:8000".
        timeout_seconds: The network timeout in seconds for the HTTP request.
        session: Optional requests.Session to reuse connections.

    Returns:
        A dictionary following the PollResults schema on success (200).

    Raises:
        FileNotFoundError: If the poll is not found (404).
        requests.HTTPError: For other non-success responses.
        requests.RequestException: For network-related errors.
    """

    if poll_id <= 0:
        raise ValueError("poll_id must be a positive integer")

    url = f"{base_url.rstrip('/')}/polls/{poll_id}/results"

    http = session or requests

    try:
        response = http.get(url, timeout=timeout_seconds)
    except requests.RequestException as request_error:
        raise request_error

    if response.status_code == 200:
        try:
            data = response.json()
        except ValueError as json_error:
            raise requests.HTTPError(
                f"Expected JSON PollResults from {response.url}, but failed to parse.",
                response=response,
            ) from json_error
        if not isinstance(data, dict):
            raise ValueError("Expected response to be a JSON object for poll results")
        return data

    if response.status_code == 404:
        detail = None
        try:
            err_json = response.json()
            detail = err_json.get("detail") or err_json.get("message")
        except ValueError:
            pass
        message = f"Poll not found: {detail}" if detail else "Poll not found"
        raise FileNotFoundError(message)

    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "content": response.text} 