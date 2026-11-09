import { useCallback, useEffect, useState } from 'react';
import { accesoPrueba, salir as cerrarSesion, verificarCodigo, yo } from '../api/cliente';
import type { Usuario } from '../api/tipos';

/** Sesión del docente. La fuente de verdad es la cookie HttpOnly: aquí solo se refleja `yo()`. */
export function useSesion() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let vigente = true;
    yo().then(u => { if (vigente) setUsuario(u); })
      .catch(() => { if (vigente) setUsuario(null); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, []);

  const ingresar = useCallback(async (correo: string, codigo: string) => {
    await verificarCodigo(correo, codigo);
    setUsuario(await yo());
  }, []);

  const ingresarPrueba = useCallback(async (correo?: string) => {
    await accesoPrueba(correo);
    setUsuario(await yo());
  }, []);

  const salir = useCallback(async () => {
    try {
      await cerrarSesion();
    } finally {
      setUsuario(null); // Aunque la red falle, la interfaz no sigue mostrando la sesión.
    }
  }, []);

  /** Un 401 en cualquier vista: la sesión venció en el servidor. */
  const expirar = useCallback(() => setUsuario(null), []);

  return { usuario, cargando, ingresar, ingresarPrueba, salir, expirar };
}
