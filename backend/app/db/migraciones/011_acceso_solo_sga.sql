-- V2: se entra solo por el SGA y el acceso a cada asignatura lo define el SGA.
-- Las sesiones abiertas con el código por correo de V1 se cierran: el próximo ingreso pasa por el SGA.
DELETE FROM auth_sesion;
-- Los accesos compartidos de V1 dejan de valer. La tabla y sus roles se conservan para los
-- accesos que un administrador escriba directamente en la base de datos.
DELETE FROM asignatura_acceso;
