"""Tarifas de DeepSeek (https://api-docs.deepseek.com/quick_start/pricing, revisada el 2026-11-24)."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.llm.precios import costo, es_pico

LUNES = datetime(2026, 11, 23, tzinfo=timezone.utc)  # lunes


@pytest.mark.parametrize("hora,minuto,pico", [
    (0, 59, False), (1, 0, True), (3, 59, True), (4, 0, False), (5, 30, False),
    (6, 0, True), (9, 59, True), (10, 0, False), (15, 0, False), (23, 0, False)])
def test_horario_pico_entre_semana_en_utc(hora, minuto, pico):
    assert es_pico(LUNES.replace(hour=hora, minute=minuto)) is pico


def test_fin_de_semana_nunca_es_pico():
    assert not es_pico(datetime(2026, 11, 28, 2, 0, tzinfo=timezone.utc))  # sábado
    assert not es_pico(datetime(2026, 11, 29, 7, 0, tzinfo=timezone.utc))  # domingo


def test_hora_local_se_convierte_a_utc():
    from datetime import timedelta
    ecuador = timezone(timedelta(hours=-5))
    assert es_pico(datetime(2026, 11, 23, 21, 0, tzinfo=ecuador))  # 02:00 UTC del martes
    assert not es_pico(datetime(2026, 11, 23, 10, 0, tzinfo=ecuador))  # 15:00 UTC


def test_tarifas_v4_pro_pico_y_fuera_de_pico():
    pico, valle = LUNES.replace(hour=2), LUNES.replace(hour=15)
    m = 1_000_000
    assert costo("deepseek-v4-pro", m, 0, 0, pico) == Decimal("0.044")
    assert costo("deepseek-v4-pro", 0, m, 0, pico) == Decimal("1.32")
    assert costo("deepseek-v4-pro", 0, 0, m, pico) == Decimal("3.96")
    assert costo("deepseek-v4-pro", m, m, m, valle) == Decimal("0.022") + Decimal("0.66") + Decimal("1.98")


def test_tarifas_flash_y_nombres_antiguos():
    valle = LUNES.replace(hour=15)
    m = 1_000_000
    for nombre in ("deepseek-flash", "deepseek-v4-flash"):
        assert costo(nombre, m, m, m, valle) == Decimal("0.003") + Decimal("0.15") + Decimal("0.6")


def test_cuestionario_tipico_sin_cache_en_pico():
    assert costo("deepseek-v4-pro", 0, 77_000, 41_000, LUNES.replace(hour=2)) == Decimal("0.264")


def test_modelo_sin_tarifa():
    assert costo("qwen3-8b-awq", 0, 1000, 1000, LUNES) is None
