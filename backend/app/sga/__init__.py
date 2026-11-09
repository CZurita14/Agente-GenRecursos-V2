"""Acceso al SGA: interfaz, traductor al contrato y proveedores (simulado y real)."""
from app.sga.proveedor import (CredencialesInvalidas, IdentidadSGA, MateriaSGA, ProveedorSGA,
                               SGAError, SGANoDisponible, SilaboNoDisponible, separar_codigo)
from app.sga.traductor import a_contrato


def crear_proveedor(config) -> ProveedorSGA:
    """Proveedor según `config.sga_proveedor`."""
    if config.sga_proveedor == "simulado":
        from app.sga.simulado import ProveedorSimulado
        if config.sga_simulado_dir is None:
            raise SGANoDisponible("SGA_SIMULADO_DIR es obligatorio con el proveedor simulado")
        return ProveedorSimulado(config.sga_simulado_dir)
    from app.sga.real import crear_proveedor_real
    return crear_proveedor_real(config)


__all__ = ["CredencialesInvalidas", "IdentidadSGA", "MateriaSGA", "ProveedorSGA", "SGAError",
           "SGANoDisponible", "SilaboNoDisponible", "a_contrato", "crear_proveedor",
           "separar_codigo"]
