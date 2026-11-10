Oráculo de equivalencia: huellas generadas con el código de la V1 (commit 011bd68) a partir de
`tests/fixtures/silabo_datos.json`. Se regenera con `generar_oraculo.py` (ver su docstring); no se edita a mano.

- `huellas()` en `generar_oraculo.py` y en `tests/test_equivalencia_v1.py` debe mantenerse **idéntica** en los dos archivos: el oráculo y la prueba tienen que calcular lo mismo. Si se cambia una, se cambia la otra y se regenera el oráculo con el código de V1.
- Las 23 pasadas de la V1 que partían de PDF reales **no se pueden reproducir en la V2**: los PDF reales no se versionan y la entrada por PDF ya no existe. La cobertura de equivalencia es `silabo_datos.json` (59 huellas) más los 3 sílabos del SGA simulado (`tests/fixtures/sga/`), que no cambian al quitar los campos privados.
