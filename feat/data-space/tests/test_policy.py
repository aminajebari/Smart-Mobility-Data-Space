import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from dataspace.models import Dataset, Participant, Policy
from dataspace.policy import evaluate

MEMBER = Participant(id="city", name="City", membership="member", roles=["public_authority"])
GUEST = Participant(id="startup", name="Startup", membership="guest", roles=["commercial"])
OWNER = Participant(id="prov", name="Provider", type="provider", membership="member", roles=["provider"])


def dataset(**policy) -> Dataset:
    return Dataset(id="prov.ds", provider_id="prov", title="ds", policy=Policy(**policy))


def test_public_allows_anyone_even_unregistered():
    assert evaluate(None, dataset(type="public"), "research").allowed
    assert evaluate(GUEST, dataset(type="public"), "commercial").allowed


def test_denied_blocks_everyone_but_owner():
    assert not evaluate(MEMBER, dataset(type="denied"), "research").allowed
    assert evaluate(OWNER, dataset(type="denied"), "monitoring").allowed


def test_partner_only_requires_member():
    assert evaluate(MEMBER, dataset(type="partner_only"), "research").allowed
    assert not evaluate(GUEST, dataset(type="partner_only"), "research").allowed
    assert not evaluate(None, dataset(type="partner_only"), "research").allowed


def test_role_based():
    ds = dataset(type="role_based", allowed_roles=["public_authority"])
    assert evaluate(MEMBER, ds, "monitoring").allowed
    other = MEMBER.model_copy(update={"roles": ["analytics"]})
    assert not evaluate(other, ds, "monitoring").allowed


def test_purpose_limited():
    ds = dataset(type="purpose_limited", allowed_purposes=["research"])
    assert evaluate(MEMBER, ds, "research").allowed
    result = evaluate(MEMBER, ds, "commercial")
    assert not result.allowed and "purpose" in result.reason


def test_contract_requirement_is_reported_not_enforced_by_evaluator():
    ds = dataset(type="partner_only", requires_contract=True)
    result = evaluate(MEMBER, ds, "research")
    assert result.allowed and result.needs_contract
    # the owner never needs a contract with itself
    assert not evaluate(OWNER, ds, "research").needs_contract
