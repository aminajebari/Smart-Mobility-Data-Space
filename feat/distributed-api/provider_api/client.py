"""Inter-service client helper: lets one provider request authorized data from another.

The partner endpoint is discovered through the Data Space catalogue
(`access_url` published by each provider), with an optional static fallback.
"""
from typing import Optional

import httpx

from .dataspace_client import DataSpaceClient


class PartnerRequestError(Exception):
    def __init__(self, status_code: int, detail):
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class ProviderClient:
    def __init__(self, api_key: str, data_space: DataSpaceClient, partner_urls: Optional[dict[str, str]] = None,
                 http: Optional[httpx.Client] = None, timeout: float = 5.0):
        self.api_key = api_key
        self.data_space = data_space
        self.partner_urls = partner_urls or {}
        self.http = http or httpx.Client(timeout=timeout)

    def resolve(self, dataset_id: str) -> str:
        provider_id = dataset_id.split(".", 1)[0]
        entry = self.data_space.dataset(dataset_id)
        if entry and entry.get("access_url"):
            return entry["access_url"].rstrip("/")
        if provider_id in self.partner_urls:
            return self.partner_urls[provider_id].rstrip("/")
        raise PartnerRequestError(404, f"no endpoint known for {dataset_id} (not published in the catalogue)")

    def get_data(self, dataset_id: str, purpose: str, limit: int = 50, **filters) -> dict:
        url = self.resolve(dataset_id)
        params = {"dataset_id": dataset_id, "purpose": purpose, "limit": limit,
                  **{k: v for k, v in filters.items() if v is not None}}
        try:
            response = self.http.get(f"{url}/data", params=params, headers={"X-API-Key": self.api_key})
        except httpx.HTTPError as exc:
            raise PartnerRequestError(502, f"partner unreachable: {exc}") from exc
        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise PartnerRequestError(response.status_code, detail)
        return response.json()
