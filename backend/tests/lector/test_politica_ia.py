"""P3b T2: §9.4 regla 2 — política de IA que excluye la IA en una evaluación."""
import pytest

from app.herramientas.politica import excluye_ia_en_evaluacion


@pytest.mark.parametrize("texto", [
    "LA EVALUACIÓN INDIVIDUAL DE RESULTADOS DE APRENDIZAJE SE DESARROLLA SIN ASISTENCIA DE IA, SALVO...",
    "El examen se rinde sin uso de la IA.",
    "La prueba final es sin apoyo de IA generativa.",
    "No se permite el uso de IA en la evaluación cognitiva.",
    "No se permite la IA durante la defensa.",
    "Queda prohibido el uso de la IA en la evaluación.",
    # Revisión P3b: otras redacciones habituales.
    "La evaluación cognitiva es sin IA.",
    "No está permitido el uso de IA durante el examen.",
    "Examen sin uso de herramientas de IA.",
    "Prohibida la IA en la defensa oral.",
    "No se permite el uso de herramientas de inteligencia artificial.",
])
def test_patrones_restrictivos(texto):
    assert excluye_ia_en_evaluacion(texto)


@pytest.mark.parametrize("texto", [
    "", "SE PERMITE EL USO DE IA PARA COMPRENDER CONCEPTOS.",
    "Se autoriza el uso de IA generativa como apoyo heurístico.",
    "Se promueve el uso de IA generativa para la exploración de alternativas.",
    "El estudiante declara el uso de IA y verifica sus resultados.",
])
def test_politicas_permisivas_sinteticas(texto):
    assert not excluye_ia_en_evaluacion(texto)


def test_politicas_reales(pdf_real):
    from app.silabo.lector import leer_silabo
    datos = leer_silabo(pdf_real("datos"))
    tic = leer_silabo(pdf_real("tic"))
    assert not any(excluye_ia_en_evaluacion(m.politica_ia) for m in datos.momentos)
    assert [m.numero for m in tic.momentos if excluye_ia_en_evaluacion(m.politica_ia)] == [4]
