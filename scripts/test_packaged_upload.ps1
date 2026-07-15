param(
    [Parameter(Mandatory = $true)][string]$AssignedPdf,
    [Parameter(Mandatory = $true)][string]$VacantPdf,
    [Parameter(Mandatory = $true)][string]$WithoutPositionPdf
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Threading;

public static class RuralFindMeMouse {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr handle, int command);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint x, uint y, uint data, UIntPtr extra);

    public static void Click(IntPtr handle, int x, int y) {
        ShowWindow(handle, 9);
        BringWindowToTop(handle);
        SetForegroundWindow(handle);
        Thread.Sleep(500);
        SetCursorPos(x, y);
        Thread.Sleep(200);
        mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
        Thread.Sleep(80);
        mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
    }
}
'@

function Get-AppWindow([int]$ProcessId) {
    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty,
        $ProcessId
    )
    return [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
        [System.Windows.Automation.TreeScope]::Children,
        $condition
    )
}

function Find-Control($Root, $ControlType, [string]$NamePart) {
    if ($null -eq $Root) { return $null }
    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        $ControlType
    )
    $items = $Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        $condition
    )
    for ($index = 0; $index -lt $items.Count; $index++) {
        $item = $items.Item($index)
        if ($item.Current.Name -like "*$NamePart*") { return $item }
    }
    return $null
}

function Wait-Control([int]$ProcessId, $ControlType, [string]$NamePart) {
    for ($attempt = 0; $attempt -lt 80; $attempt++) {
        $window = Get-AppWindow $ProcessId
        $control = Find-Control $window $ControlType $NamePart
        if ($null -ne $control) { return @($window, $control) }
        Start-Sleep -Milliseconds 250
    }
    throw "No apareció el control esperado: $NamePart"
}

function Click-Control($Window, $Control) {
    $rectangle = $Control.Current.BoundingRectangle
    [RuralFindMeMouse]::Click(
        [IntPtr]$Window.Current.NativeWindowHandle,
        [int]($rectangle.Left + ($rectangle.Width / 2)),
        [int]($rectangle.Top + ($rectangle.Height / 2))
    )
}

function Activate-Control($Window, $Control) {
    try {
        [RuralFindMeMouse]::SetForegroundWindow(
            [IntPtr]$Window.Current.NativeWindowHandle
        ) | Out-Null
        $Control.SetFocus()
        Start-Sleep -Milliseconds 250
        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    }
    catch {
        Click-Control $Window $Control
    }
}

function Get-WindowText([int]$ProcessId) {
    $window = Get-AppWindow $ProcessId
    if ($null -eq $window) { return "" }
    $items = $window.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    $parts = @()
    for ($index = 0; $index -lt $items.Count; $index++) {
        $name = $items.Item($index).Current.Name
        if ($name) { $parts += $name }
    }
    return $parts -join " | "
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$packageRoot = (Resolve-Path (Join-Path $root "dist\RuralFindMe")).Path
$executable = Join-Path $packageRoot "RuralFindMe.exe"
$main = $null

try {
    $main = Start-Process -FilePath $executable -PassThru
    $pair = Wait-Control $main.Id ([System.Windows.Automation.ControlType]::Button) "Consultar mi resultado"
    Activate-Control $pair[0] $pair[1]

    $pair = Wait-Control $main.Id ([System.Windows.Automation.ControlType]::Button) "Seleccionar los tres PDF"
    Activate-Control $pair[0] $pair[1]

    $helper = $null
    for ($attempt = 0; $attempt -lt 80; $attempt++) {
        $helper = Get-CimInstance Win32_Process | Where-Object {
            $_.ParentProcessId -eq $main.Id -and $_.CommandLine -like "*--file-picker-helper*"
        } | Select-Object -First 1
        if ($null -ne $helper) { break }
        Start-Sleep -Milliseconds 250
    }
    if ($null -eq $helper) { throw "No se inició el selector aislado." }

    $helperId = [int]$helper.ProcessId
    $fileNamePair = Wait-Control $helperId ([System.Windows.Automation.ControlType]::Edit) "File name:"
    $fileName = $fileNamePair[1]
    $quotedPaths = @($AssignedPdf, $VacantPdf, $WithoutPositionPdf) |
        ForEach-Object { '"{0}"' -f (Resolve-Path -LiteralPath $_).Path }
    $value = $fileName.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $value.SetValue($quotedPaths -join " ")

    $open = Find-Control $fileNamePair[0] ([System.Windows.Automation.ControlType]::Button) "Open"
    $invoke = $open.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $invoke.Invoke()

    $expectedNames = @($AssignedPdf, $VacantPdf, $WithoutPositionPdf) |
        ForEach-Object { Split-Path -Leaf $_ }
    $windowText = ""
    for ($attempt = 0; $attempt -lt 80; $attempt++) {
        $windowText = Get-WindowText $main.Id
        if (@($expectedNames | Where-Object { $windowText -notlike "*$_*" }).Count -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 500
    }

    $main.Refresh()
    $loaded = @($expectedNames | Where-Object { $windowText -notlike "*$_*" }).Count -eq 0
    $roundDetected = $windowText -like "*16/04/2026*"
    $advanced = $false
    if ($loaded) {
        $validatePair = Wait-Control $main.Id ([System.Windows.Automation.ControlType]::Button) "Validar la ronda y continuar"
        Activate-Control $validatePair[0] $validatePair[1]
        $identificationPair = Wait-Control $main.Id ([System.Windows.Automation.ControlType]::Text) "Su identificación"
        $advanced = $null -ne $identificationPair[1]
    }
    [pscustomobject]@{
        MainAlive = -not $main.HasExited
        HelperClosed = $null -eq (Get-Process -Id $helperId -ErrorAction SilentlyContinue)
        AllThreeLoaded = $loaded
        RoundDetected = $roundDetected
        ValidationAdvanced = $advanced
    } | Format-List

    if ($main.HasExited -or -not $loaded -or -not $advanced) {
        throw "La prueba empaquetada de carga no terminó correctamente."
    }
}
finally {
    Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and
        $_.ExecutablePath.StartsWith($packageRoot, [System.StringComparison]::OrdinalIgnoreCase)
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
