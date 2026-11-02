$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$taskRoot=Split-Path -Parent $PSScriptRoot
$target=Join-Path $taskRoot 'build/icon.ico'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
$bitmap=New-Object Drawing.Bitmap 256,256
$graphics=[Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode=[Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([Drawing.Color]::FromArgb(29,31,40))
$brush=New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(190,184,255))
$points=[Drawing.PointF[]]@((New-Object Drawing.PointF 128,40),(New-Object Drawing.PointF 151,105),(New-Object Drawing.PointF 216,128),(New-Object Drawing.PointF 151,151),(New-Object Drawing.PointF 128,216),(New-Object Drawing.PointF 105,151),(New-Object Drawing.PointF 40,128),(New-Object Drawing.PointF 105,105))
$graphics.FillPolygon($brush,$points)
$memory=New-Object IO.MemoryStream
$bitmap.Save($memory,[Drawing.Imaging.ImageFormat]::Png)
$data=$memory.ToArray()
$stream=[IO.File]::Create($target)
$writer=New-Object IO.BinaryWriter $stream
$writer.Write([UInt16]0);$writer.Write([UInt16]1);$writer.Write([UInt16]1)
$writer.Write([byte]0);$writer.Write([byte]0);$writer.Write([byte]0);$writer.Write([byte]0)
$writer.Write([UInt16]1);$writer.Write([UInt16]32);$writer.Write([UInt32]$data.Length);$writer.Write([UInt32]22);$writer.Write($data)
$writer.Dispose();$memory.Dispose();$brush.Dispose();$graphics.Dispose();$bitmap.Dispose()
