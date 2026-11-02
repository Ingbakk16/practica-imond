"""Refresh a published semantic model after a validated warehouse build.

Uses GitHub OIDC federation with Entra; no stored client secret is needed.
Only a completed refresh with the submitted request ID counts as success.
"""

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import UUID


class RefreshError(RuntimeError):
    pass


def request_json(url, *, token=None, data=None, form=False):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        body = (urlencode(data) if form else json.dumps(data)).encode()
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=60) as response:
            content = response.read()
            return response.status, response.headers, json.loads(content) if content else {}
    except HTTPError as error:
        # Do not emit response bodies, tokens, assertions or credential URLs.
        raise RefreshError(f"HTTP {error.code} from {urlsplit(url).hostname}; request not retried") from None
    except (URLError, TimeoutError):
        raise RefreshError("Network request failed; request not retried. Check Power BI history before rerunning.") from None


def configuration(env):
    values = {}
    for name in ("POWERBI_TENANT_ID", "POWERBI_CLIENT_ID", "POWERBI_WORKSPACE_ID", "POWERBI_DATASET_ID"):
        try:
            values[name] = str(UUID(env.get(name, "")))
        except ValueError:
            raise RefreshError(f"Set {name} to a valid UUID in GitHub environment bigquery") from None
    for name in ("ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN"):
        if not env.get(name):
            raise RefreshError(f"Missing {name}; run in GitHub Actions with id-token: write")
    return values


def access_token(config, env):
    parts = urlsplit(env["ACTIONS_ID_TOKEN_REQUEST_URL"])
    if parts.scheme != "https" or not (parts.hostname or "").endswith(".actions.githubusercontent.com"):
        raise RefreshError("Unexpected GitHub OIDC endpoint")
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "audience"]
    query.append(("audience", "api://AzureADTokenExchange"))
    url = urlunsplit(parts._replace(query=urlencode(query)))
    _, _, assertion = request_json(url, token=env["ACTIONS_ID_TOKEN_REQUEST_TOKEN"])
    _, _, result = request_json(
        f'https://login.microsoftonline.com/{config["POWERBI_TENANT_ID"]}/oauth2/v2.0/token',
        form=True,
        data={
            "client_id": config["POWERBI_CLIENT_ID"],
            "scope": "https://analysis.windows.net/powerbi/api/.default",
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion["value"],
        },
    )
    return result["access_token"]


def refresh(config, token, *, timeout=1800, interval=20, clock=time.monotonic, sleep=time.sleep):
    endpoint = (
        "https://api.powerbi.com/v1.0/myorg/groups/"
        f'{config["POWERBI_WORKSPACE_ID"]}/datasets/{config["POWERBI_DATASET_ID"]}/refreshes'
    )
    # One POST only: retrying an ambiguous timeout can submit a second refresh.
    status, headers, _ = request_json(endpoint, token=token, data={})
    if status != 202:
        raise RefreshError(f"Expected refresh acceptance (202), received {status}")
    candidate = headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
    candidate = candidate or headers.get("x-ms-request-id", "")
    try:
        request_id = str(UUID(candidate))
    except ValueError:
        raise RefreshError("Refresh accepted without a request ID; inspect history before rerunning") from None
    print(f"Power BI accepted refresh {request_id}; waiting for completion.", flush=True)
    deadline = clock() + timeout
    while clock() < deadline:
        _, _, history = request_json(endpoint + "?$top=60", token=token)
        entry = next((item for item in history.get("value", [])
                      if str(item.get("requestId", "")).lower() == request_id), None)
        if entry:
            state = entry.get("status")
            if state == "Completed":
                print(f"Power BI refresh {request_id}: Completed", flush=True)
                return request_id
            if state not in ("Unknown", "NotStarted", "InProgress"):
                raise RefreshError(f"Power BI refresh {request_id}: {state}; inspect refresh history")
        sleep(min(interval, max(0, deadline - clock())))
    raise RefreshError(f"Timed out waiting for Power BI refresh {request_id}; it may still be running")


def main():
    try:
        config = configuration(os.environ)
        refresh(config, access_token(config, os.environ))
    except (RefreshError, KeyError, json.JSONDecodeError) as error:
        message = str(error) if isinstance(error, RefreshError) else "Unexpected API response; inspect service configuration"
        print(f"Power BI update failed: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
