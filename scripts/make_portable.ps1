$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$source = (Resolve-Path (Join-Path $root "dist\RuralFindMe")).Path
$versionFile = Join-Path $root "app\__init__.py"
$versionSource = Get-Content -LiteralPath $versionFile -Raw
if ($versionSource -notmatch '__version__\s*=\s*"([^"]+)"') {
    throw "No se pudo leer la versión desde app\__init__.py."
}
$version = $Matches[1]
$destination = Join-Path $root "dist\RuralFindMe-$version-Windows-portable.zip"

if (-not $source.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "La carpeta de origen quedó fuera del proyecto."
}

Compress-Archive -LiteralPath $source -DestinationPath $destination -Force
Write-Host "Paquete portable listo en: $destination"
