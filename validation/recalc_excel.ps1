# Open excel_check.xlsx in Microsoft Excel, recalculate all formulas, and save,
# so the computed values are stored in the file for compare.py to read.
param([string]$Path = (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "excel_check.xlsx"))
$Path = (Resolve-Path $Path).Path
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Open($Path)
    $xl.CalculateFull()
    $wb.RemovePersonalInformation = $true   # do not write the Office user name into the file
    $wb.Save()
    $wb.Close($false)
    Write-Output "Recalculated: $Path"
} finally {
    $xl.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
