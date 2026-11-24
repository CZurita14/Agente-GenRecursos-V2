# Regla de entrada para que SOLO la PC del Monitor de Agentes (172.18.3.16) llegue al adaptador /v1
# del Generador (172.18.3.25:8766). Ejecutar en PowerShell COMO ADMINISTRADOR:
#   powershell -File infra/habilitar-firewall-monitor.ps1
# Si la institución administra el firewall, pedir a Sistemas: origen 172.18.3.16, destino 172.18.3.25, TCP 8766.
param([string]$Generador = "172.18.3.25", [int]$Puerto = 8766, [string]$Monitor = "172.18.3.16")
$nombre = "Monitor UTI - Generador $Puerto"
if (Get-NetFirewallRule -DisplayName $nombre -ErrorAction SilentlyContinue) { Write-Host "La regla '$nombre' ya existe."; exit 0 }
New-NetFirewallRule -DisplayName $nombre -Direction Inbound -Action Allow -Protocol TCP `
  -LocalAddress $Generador -LocalPort $Puerto -RemoteAddress $Monitor -Profile Any | Out-Null
Write-Host "Regla creada: $nombre (origen $Monitor -> $Generador`:$Puerto)."
