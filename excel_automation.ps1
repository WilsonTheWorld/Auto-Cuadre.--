param(
    [Parameter(Mandatory = $true)][ValidateSet('initialize', 'read', 'update', 'statistics')][string]$Action,
    [string]$WorkbookPath,
    [Parameter(Mandatory = $true)][string]$PayloadBase64
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$payloadText = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($PayloadBase64))
$payload = $payloadText | ConvertFrom-Json
$excel = $null
$book = $null
$sheet = $null
$result = $null

function Get-QuadreSnapshot($activeSheet) {
    $available = @()
    $receipts = @()
    for ($row = 24; $row -le 39; $row++) {
        $existing = $activeSheet.Cells.Item($row, 2).Value2
        if ($null -eq $existing -or [string]::IsNullOrWhiteSpace([string]$existing)) {
            $available += $row
        }
        else {
            $receipts += [ordered]@{
                row = $row
                beneficiary = [string]$existing
                receipt = [string]$activeSheet.Cells.Item($row, 3).Value2
                value = $activeSheet.Cells.Item($row, 4).Value2
            }
        }
    }
    return [ordered]@{
        monthly = $activeSheet.Range('E11').Value2
        other = $activeSheet.Range('E14').Value2
        transfers = $activeSheet.Range('D41').Value2
        cash = $activeSheet.Range('E47').Value2
        balance = $activeSheet.Range('E45').Value2
        difference = $activeSheet.Range('E49').Value2
        availableReceiptRows = $available
        receipts = @($receipts)
    }
}

try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    if ($Action -ne 'statistics') {
        if ([string]::IsNullOrWhiteSpace($WorkbookPath)) {
            throw 'No se indicó el archivo de cuadre.'
        }
        $book = $excel.Workbooks.Open($WorkbookPath, 0, $false)
        $sheet = $book.Worksheets.Item(1)
    }

    if ($Action -eq 'statistics') {
        $records = @()
        if ($null -ne $payload.records) { $records = @($payload.records) }
        $history = @()
        foreach ($record in $records) {
            $statBook = $null
            $statSheet = $null
            try {
                $statBook = $excel.Workbooks.Open([string]$record.path, 0, $true)
                $statSheet = $statBook.Worksheets.Item(1)
                $history += [ordered]@{
                    date = [string]$record.date
                    balance = $statSheet.Range('E45').Value2
                    cash = $statSheet.Range('E47').Value2
                    difference = $statSheet.Range('E49').Value2
                }
            }
            finally {
                if ($null -ne $statBook) { $statBook.Close($false) }
                if ($null -ne $statSheet) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($statSheet) }
                if ($null -ne $statBook) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($statBook) }
            }
        }
        $result = [ordered]@{ records = @($history) }
    }
    elseif ($Action -eq 'initialize') {
        $format = 'dd/mm/yyyy'
        if (-not [string]::IsNullOrWhiteSpace([string]$payload.dateFormat)) { $format = [string]$payload.dateFormat }
        $dateCell = $sheet.Range('A5')
        # Primero el formato y después la fecha (número de Excel): no depende del idioma de Windows.
        $dateCell.NumberFormat = $format
        $dateCell.Value2 = [double]$payload.serial
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($dateCell)
        $excel.CalculateFull()
        $book.Save()
    }
    elseif ($Action -eq 'read') {
        $result = Get-QuadreSnapshot $sheet
    }
    else {
        $updates = @()
        $newReceipts = @()
        if ($null -ne $payload.updates) { $updates = @($payload.updates) }
        if ($null -ne $payload.newReceipts) { $newReceipts = @($payload.newReceipts) }
        foreach ($change in $updates) {
            $row = [int]$change.row
            if ($row -lt 24 -or $row -gt 39) {
                throw "La fila de recibo $row está fuera del rango permitido."
            }
            $sheet.Cells.Item($row, 2).Value2 = [string]$change.beneficiary
            $sheet.Cells.Item($row, 3).Value2 = [string]$change.receipt
            $sheet.Cells.Item($row, 4).Value2 = [double]$change.value
        }
        $available = @()
        for ($row = 24; $row -le 39; $row++) {
            $existing = $sheet.Cells.Item($row, 2).Value2
            if ($null -eq $existing -or [string]::IsNullOrWhiteSpace([string]$existing)) {
                $available += $row
            }
        }
        if ($newReceipts.Count -gt $available.Count) {
            throw "Solo quedan $($available.Count) fila(s) disponibles para recibos en el cuadre de hoy."
        }
        $sheet.Range('E11').Value2 = [double]$payload.monthly
        $sheet.Range('E14').Value2 = [double]$payload.other
        $sheet.Range('D41').Value2 = [double]$payload.transfers
        $sheet.Range('E47').Value2 = [double]$payload.cash
        for ($index = 0; $index -lt $newReceipts.Count; $index++) {
            $row = $available[$index]
            $receipt = $newReceipts[$index]
            $sheet.Cells.Item($row, 2).Value2 = [string]$receipt.beneficiary
            $sheet.Cells.Item($row, 3).Value2 = [string]$receipt.receipt
            $sheet.Cells.Item($row, 4).Value2 = [double]$receipt.value
        }
        $excel.CalculateFull()
        $book.Save()
        $result = Get-QuadreSnapshot $sheet
    }
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
finally {
    if ($null -ne $book) { $book.Close($false) }
    if ($null -ne $excel) { $excel.Quit() }
    if ($null -ne $sheet) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($sheet) }
    if ($null -ne $book) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($book) }
    if ($null -ne $excel) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
}

if ($Action -in @('read', 'update', 'statistics')) {
    $result | ConvertTo-Json -Compress -Depth 4
}
