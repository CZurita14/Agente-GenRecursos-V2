# Cambia la clave del panel de consumo. La clave se escribe oculta y nunca se guarda: en el .env
# solo queda su huella (CONSUMO_CLAVE_HASH). Después hay que reiniciar el backend.
# Uso (desde la carpeta del proyecto):  powershell -File infra/cambiar-clave-consumo.ps1
param([string]$Python = "C:\Users\Chris\Desktop\CIA\Agente-GeneradorRecursos\.venv\Scripts\python.exe")
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$envArchivo = Join-Path $raiz ".env"

$uno = Read-Host "Nueva clave del panel" -AsSecureString
$dos = Read-Host "Repite la clave" -AsSecureString
$texto = { param($s) [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)) }
$clave = & $texto $uno
if ($clave -ne (& $texto $dos)) { throw "Las claves no coinciden." }
if ($clave.Length -lt 8) { throw "Usa al menos 8 caracteres." }

Set-Location (Join-Path $raiz "backend")
$hash = $clave | & $Python -m app.operacion hash-clave
$clave = $null
if (-not $hash) { throw "No se pudo calcular la huella." }

$lineas = Get-Content $envArchivo -Encoding UTF8 | Where-Object { $_ -notmatch '^CONSUMO_CLAVE_HASH=' }
# Sin BOM: el .env lo leen Python y los scripts de arranque.
[IO.File]::WriteAllLines($envArchivo, [string[]]($lineas + "CONSUMO_CLAVE_HASH=$($hash.Trim())"), (New-Object Text.UTF8Encoding($false)))
Write-Host "Clave del panel cambiada. Reinicia el backend para que la use."
