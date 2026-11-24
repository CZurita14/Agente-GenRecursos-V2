# Inicia el adaptador del Monitor de Agentes UTI: solo la API UTI v1 (/v1) del Generador de Recursos.
# Uso (desde la carpeta del proyecto):  powershell -File infra/iniciar-monitor.ps1
# Mantener esta ventana abierta durante las pruebas; Ctrl+C lo detiene.
#
# El resto de la API del Generador sigue en 127.0.0.1; aquí solo se publica /v1 en la IP institucional.
# Token: MONITOR_TOKEN_HASH del .env (SHA-256). Si la variable MONITOR_TOKEN está definida en esta
# sesión, se usa su hash en su lugar (el token nunca se escribe en disco ni se imprime).
param(
    [string]$Direccion = "172.18.3.25",
    [int]$Puerto = 8766,
    [string]$BaseDatos = "genrecursos_v2",
    [string]$AgenteId = "generador-recursos-uti",
    [string]$Python = "C:\Users\Chris\Desktop\CIA\Agente-GeneradorRecursos\.venv\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$envArchivo = Join-Path $raiz ".env"

if (-not (Test-Path $Python)) { throw "No se encuentra Python en $Python (parámetro -Python)." }
if (-not (Test-Path $envArchivo)) { throw "Falta el archivo .env en $raiz." }

# La dirección debe ser de este equipo; si no, el monitor no podrá conectarse.
$propias = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
if ($Direccion -ne "0.0.0.0" -and $propias -notcontains $Direccion) {
    throw "La dirección $Direccion no pertenece a este equipo. Direcciones disponibles: $($propias -join ', ')"
}
if (Get-NetTCPConnection -LocalPort $Puerto -State Listen -ErrorAction SilentlyContinue) {
    $ocupado = Get-NetTCPConnection -LocalPort $Puerto -State Listen | Select-Object -First 1
    throw "El puerto $Puerto ya está en uso (proceso $($ocupado.OwningProcess)). Deténgalo antes de iniciar el adaptador."
}

# Base de datos del Generador V2 (misma URL del .env, con la base indicada).
$linea = Select-String -Path $envArchivo -Pattern '^DATABASE_URL=' | Select-Object -First 1
if (-not $linea) { throw "El .env no tiene DATABASE_URL." }
$url = $linea.Line.Substring("DATABASE_URL=".Length).Trim()
$env:DATABASE_URL = ($url -replace '/[^/]*$', "/$BaseDatos")
$env:ENTORNO = "desarrollo"
$env:MONITOR_AGENT_ID = $AgenteId

if ($env:MONITOR_TOKEN) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($env:MONITOR_TOKEN.Trim()))
    $env:MONITOR_TOKEN_HASH = -join ($bytes | ForEach-Object { $_.ToString("x2") })
} elseif (-not (Select-String -Path $envArchivo -Pattern '^MONITOR_TOKEN_HASH=[0-9a-f]{64}' -Quiet)) {
    throw "No hay token del monitor: defina MONITOR_TOKEN en esta sesión o MONITOR_TOKEN_HASH en el .env (python -m app.operacion token-monitor <archivo>)."
}

Write-Host "Adaptador del Monitor UTI: agente $AgenteId en http://${Direccion}:$Puerto (solo /v1). Ctrl+C para detener."
Set-Location (Join-Path $raiz "backend")
& $Python -m app.monitor_servidor --host $Direccion --port $Puerto
