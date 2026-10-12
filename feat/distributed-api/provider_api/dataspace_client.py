"""Client for the Data Space governance service (Module 3)."""
from typing import Optional

import httpx


class DataSpaceUnavailable(Exception):
    pass


class DataSpaceClient:
    def __init__(self, base_url: str, service_token: str = "", http: Optional[httpx.Client] = None, timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-Service-Token": service_token} if service_token else {}
        # `http` can be injected (e.g. a TestClient wrapping the governance app in tests)
        self.http = http or httpx.Client(timeout=timeout)

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            return self.http.request(method, f"{self.base_url}{path}", headers=self.headers, **kwargs)
        except httpx.HTTPError as exc:
            raise DataSpaceUnavailable(str(exc)) from exc

    def authorize(self, requester_id: str, dataset_id: str, purpose: str, via: str) -> dict:
        response = self._request("POST", "/authorize", json={
            "requester_id": requester_id, "dataset_id": dataset_id, "purpose": purpose, "via": via})
        if response.status_code != 200:
            raise DataSpaceUnavailable(f"authorize returned {response.status_code}: {response.text}")
        return response.json()

    def publish(self, dataset_id: str, provider_id: str, access_url: str, record_count: Optional[int],
                last_published: Optional[str]) -> bool:
        response = self._request("POST", f"/catalogue/{dataset_id}/publish", json={
            "provider_id": provider_id, "access_url": access_url,
            "record_count": record_count, "last_published": last_published})
        return response.status_code == 200

    def negotiate_contract(self, requester_id: str, dataset_id: str, purpose: str) -> httpx.Response:
        return self._request("POST", "/contracts", json={
            "requester_id": requester_id, "dataset_id": dataset_id, "purpose": purpose})

    def catalogue(self, **params) -> list[dict]:
        response = self._request("GET", "/catalogue", params={k: v for k, v in params.items() if v is not None})
        response.raise_for_status()
        return response.json()

    def dataset(self, dataset_id: str) -> Optional[dict]:
        response = self._request("GET", f"/catalogue/{dataset_id}")
        return response.json() if response.status_code == 200 else None
