"""Policy evaluator: requester + dataset + purpose -> allow/deny.

Pure functions with no I/O so every rule can be unit tested in isolation.
Contract checking is done by the caller because it needs the contract store.
"""
from dataclasses import dataclass
from typing import Optional

from .models import Dataset, Participant


@dataclass
class PolicyResult:
    allowed: bool
    reason: str
    needs_contract: bool = False


def evaluate(requester: Optional[Participant], dataset: Dataset, purpose: str) -> PolicyResult:
    """Evaluate the dataset usage policy, ignoring the contract requirement.

    `needs_contract` tells the caller that an allowed request must still be
    backed by an active data-sharing agreement.
    """
    policy = dataset.policy

    if policy.type == "denied":
        if requester and requester.id == dataset.provider_id:
            return PolicyResult(True, "owner access: provider keeps sovereignty over its own data")
        return PolicyResult(False, "policy 'denied': dataset is not shared outside the provider")

    if requester and requester.id == dataset.provider_id:
        return PolicyResult(True, "owner access: provider keeps sovereignty over its own data")

    if policy.type == "public":
        return PolicyResult(True, "policy 'public': open dataset")

    if requester is None:
        return PolicyResult(False, "requester is not a registered participant of the data space")

    if requester.membership != "member":
        return PolicyResult(False, f"policy '{policy.type}': requester has '{requester.membership}' membership, member required")

    if policy.type == "role_based" and not set(requester.roles) & set(policy.allowed_roles):
        return PolicyResult(False, f"policy 'role_based': none of the requester roles {requester.roles} is allowed")

    if policy.type == "purpose_limited" and not policy.allowed_purposes:
        return PolicyResult(False, "policy 'purpose_limited' defines no allowed purpose")

    # allowed_roles / allowed_purposes act as extra constraints on any policy type
    if policy.allowed_roles and not set(requester.roles) & set(policy.allowed_roles):
        return PolicyResult(False, f"requester roles {requester.roles} not in allowed roles")

    if policy.allowed_purposes and purpose not in policy.allowed_purposes:
        return PolicyResult(False, f"purpose '{purpose}' is not an allowed purpose for this dataset")

    return PolicyResult(True, f"policy '{policy.type}' satisfied", needs_contract=policy.requires_contract)
