$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venv = Join-Path $root ".venv-build"
$python = Join-Path $venv "Scripts\python.exe"
$frontend = Join-Path $root "frontend"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js y npm son necesarios para compilar la interfaz React."
}

Push-Location $frontend
try {
    npm ci
    npm run typecheck
    npm run build
    npm audit
    if ($LASTEXITCODE -ne 0) {
        throw "npm audit encontró vulnerabilidades o no pudo completarse."
    }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv $venv
}

& $python -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
& $python -m pytest (Join-Path $root "tests")
& $python -m PyInstaller --clean --noconfirm (Join-Path $root "build_windows.spec") --distpath (Join-Path $root "dist") --workpath (Join-Path $root "build\pyinstaller")

Write-Host "Aplicación lista en: $(Join-Path $root 'dist\RuralFindMe\RuralFindMe.exe')"
