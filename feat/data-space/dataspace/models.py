from typing import Literal, Optional

from pydantic import BaseModel, Field

PolicyType = Literal["public", "partner_only", "role_based", "purpose_limited", "denied"]
Decision = Literal["allow", "deny"]


class Participant(BaseModel):
    id: str
    name: str
    organization: str = ""
    type: Literal["provider", "consumer"] = "consumer"
    membership: Literal["member", "guest"] = "guest"
    roles: list[str] = Field(default_factory=list)
    country: str = ""


class Policy(BaseModel):
    type: PolicyType
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_purposes: list[str] = Field(default_factory=list)
    requires_contract: bool = False
    retention_days: Optional[int] = None
    redistribution: bool = False


class Dataset(BaseModel):
    """Gaia-X style self-description of a dataset. Metadata only, never raw records."""
    id: str
    provider_id: str
    title: str
    description: str = ""
    fields: list[str] = Field(default_factory=list)
    update_frequency: str = ""
    tags: list[str] = Field(default_factory=list)
    location: Optional[list[float]] = None
    derived_from: list[str] = Field(default_factory=list)
    policy: Policy
    access_url: Optional[str] = None
    last_published: Optional[str] = None
    record_count: Optional[int] = None


class PublishRequest(BaseModel):
    """Sent by a provider connector to refresh the live metadata of its own dataset."""
    provider_id: str
    access_url: Optional[str] = None
    record_count: Optional[int] = None
    last_published: Optional[str] = None


class AuthorizationRequest(BaseModel):
    requester_id: str
    dataset_id: str
    purpose: str
    via: str = Field("", description="Connector/service that is asking, e.g. the provider API id")


class AuthorizationDecision(BaseModel):
    decision: Decision
    reason: str
    requester_id: str
    dataset_id: str
    purpose: str
    policy_type: Optional[str] = None
    contract_id: Optional[str] = None
    audit_id: Optional[int] = None


class ContractRequest(BaseModel):
    requester_id: str
    dataset_id: str
    purpose: str
    duration_days: int = Field(30, ge=1, le=365)


class Contract(BaseModel):
    id: str
    requester_id: str
    provider_id: str
    dataset_id: str
    purpose: str
    status: Literal["active", "revoked"]
    created_at: str
    expires_at: str
    terms: dict


class AuditEntry(BaseModel):
    id: int
    timestamp: str
    requester_id: str
    provider_id: Optional[str]
    dataset_id: str
    purpose: str
    policy_type: Optional[str]
    decision: Decision
    reason: str
    contract_id: Optional[str]
    via: str
