"""Seam 1: política de TC (ADR-005). El TC del usuario se respeta, pero se etiqueta honesto."""

from decimal import Decimal as D

import pytest

from services.evaluation_service import resolve_tc


@pytest.mark.parametrize(
    "payload, banxico, expected",
    [
        # coincide (±0.5 %) con Banxico fresco → banxico, sin flag
        (D("19.50"), (D("19.50"), "banxico"), ("banxico", [])),
        (D("19.59"), (D("19.50"), "banxico"), ("banxico", [])),  # +0.46 %
        # difiere de Banxico → lo puso el usuario
        (D("19.70"), (D("19.50"), "banxico"), ("user_provided", ["warn_fx"])),  # +1.03 %
        (D("18.00"), (D("19.50"), "banxico"), ("user_provided", ["warn_fx"])),
        # Banxico caído pero hay último valor en memoria → fallback, marcado
        (D("19.50"), (D("19.50"), "fallback"), ("fallback_db", ["warn_fx"])),
        # Banxico caído y el usuario difiere del fallback
        (D("21.00"), (D("19.50"), "fallback"), ("user_provided", ["warn_fx"])),
        # Banxico caído sin ningún valor → solo queda el del usuario
        (D("19.50"), None, ("user_provided", ["warn_fx"])),
    ],
)
def test_resolve_tc(payload, banxico, expected):
    assert resolve_tc(payload, banxico) == expected
