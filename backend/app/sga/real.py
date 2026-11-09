"""Adaptador del SGA real: pendiente de TI (bloqueo B-SGA1)."""
from app.sga.proveedor import SGANoDisponible


def crear_proveedor_real(config):
    raise SGANoDisponible("adaptador real pendiente de TI")
