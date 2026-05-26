"""Tests: idempotency hash previene evaluaciones duplicadas en ventana 30s."""

import hashlib
import json

import pytest

from services.evaluation_service import compute_idempotency_hash


def test_same_payload_same_hash():
    """Mismo user_id + payload → mismo hash."""
    from uuid import UUID

    uid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    payload = {"name": "Test", "product_name": "Widget", "cost_purchase": 100}
    h1 = compute_idempotency_hash(uid, payload)
    h2 = compute_idempotency_hash(uid, payload)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_different_user_different_hash():
    """Distinto user_id → distinto hash aunque payload sea igual."""
    from uuid import UUID

    uid1 = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    uid2 = UUID("11111111-2222-3333-4444-555555555555")
    payload = {"name": "Test", "product_name": "Widget", "cost_purchase": 100}
    assert compute_idempotency_hash(uid1, payload) != compute_idempotency_hash(uid2, payload)


def test_different_payload_different_hash():
    """Distinto payload → distinto hash."""
    from uuid import UUID

    uid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    p1 = {"name": "Test A", "product_name": "Widget"}
    p2 = {"name": "Test B", "product_name": "Widget"}
    assert compute_idempotency_hash(uid, p1) != compute_idempotency_hash(uid, p2)
