"""Ayuda de pruebas: crea la asignatura de un docente sin pasar por el SGA ni por la API."""
from app.silabo.integridad import cargar_silabo


def subir(app, correo, datos):
    """Guarda el sílabo (dict del contrato) con el servicio de la app; devuelve id, menú y clases_cambiadas."""
    return app.state.asignaturas.guardar(correo, cargar_silabo(datos))
