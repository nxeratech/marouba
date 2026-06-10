param(
    [string]$Path,
    [int]$X = 0,
    [int]$Y = 0,
    [int]$Width = 0,
    [int]$Height = 0
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime

[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] > $null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] > $null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] > $null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq "AsTask" -and
        $_.IsGenericMethodDefinition -and
        $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } |
    Select-Object -First 1)
if ($null -eq $asTaskGeneric) {
    throw "Could not locate WindowsRuntime AsTask(IAsyncOperation<T>) overload"
}

function Await-WinRt($operation, [type]$resultType) {
    $task = $asTaskGeneric.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait()
    $task.Result
}

$temp = $null
$bitmap = $null
$graphics = $null

try {
    if ([string]::IsNullOrWhiteSpace($Path)) {
        if ($Width -le 0 -or $Height -le 0) {
            throw "Width and Height are required when Path is not supplied"
        }
        $temp = Join-Path $env:TEMP ("marouba-ocr-{0}.png" -f ([guid]::NewGuid().ToString("N")))
        $bitmap = New-Object System.Drawing.Bitmap($Width, $Height)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.CopyFromScreen($X, $Y, 0, 0, $bitmap.Size)
        $bitmap.Save($temp, [System.Drawing.Imaging.ImageFormat]::Png)
        $Path = $temp
    }

    $file = Await-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
    $stream = Await-WinRt ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
    $decoder = Await-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $softwareBitmap = Await-WinRt ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        throw "Windows OCR engine is unavailable"
    }
    $result = Await-WinRt ($engine.RecognizeAsync($softwareBitmap)) ([Windows.Media.Ocr.OcrResult])

    $words = @()
    foreach ($line in $result.Lines) {
        foreach ($word in $line.Words) {
            $rect = $word.BoundingRect
            $words += [pscustomobject]@{
                text = $word.Text
                left = $X + [int][math]::Round($rect.X)
                top = $Y + [int][math]::Round($rect.Y)
                width = [int][math]::Round($rect.Width)
                height = [int][math]::Round($rect.Height)
            }
        }
    }
    $words | ConvertTo-Json -Compress
}
finally {
    if ($graphics) { $graphics.Dispose() }
    if ($bitmap) { $bitmap.Dispose() }
    if ($temp) {
        Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
    }
}
