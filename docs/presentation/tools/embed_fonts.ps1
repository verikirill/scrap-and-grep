# Opens the PPTX in PowerPoint, embeds the Inter faces from fonts/ and saves it, so the deck
# looks the same on a computer without Inter. With -Png it also exports every slide as PNG
# for a look at what PowerPoint itself draws.
#
#   powershell -File docs/presentation/tools/embed_fonts.ps1 -In raw.pptx -Out scrapgrep.pptx [-Png dir]
#
# The faces are added for this Windows session only (AddFontResource), nothing is installed.
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [string]$Png = ''
)
$ErrorActionPreference = 'Stop'
$fonts = Join-Path $PSScriptRoot '..\fonts'

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class Fonts {
  [DllImport("gdi32.dll", CharSet = CharSet.Unicode)] public static extern int AddFontResource(string file);
  [DllImport("gdi32.dll", CharSet = CharSet.Unicode)] public static extern bool RemoveFontResource(string file);
  [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr w, IntPtr l, uint flags, uint timeout, out IntPtr result);
}
'@
$files = Get-ChildItem $fonts -Filter *.ttf | ForEach-Object { $_.FullName }
foreach ($f in $files) { [void][Fonts]::AddFontResource($f) }
$r = [IntPtr]::Zero
[void][Fonts]::SendMessageTimeout([IntPtr]0xffff, 0x001D, [IntPtr]::Zero, [IntPtr]::Zero, 2, 2000, [ref]$r)

$app = New-Object -ComObject PowerPoint.Application
try {
  $deck = $app.Presentations.Open((Resolve-Path $In).Path, $true, $false, $false)
  if ($Png) {
    New-Item -ItemType Directory -Force $Png | Out-Null
    foreach ($slide in $deck.Slides) {
      $name = Join-Path (Resolve-Path $Png).Path ('p{0:D2}.png' -f $slide.SlideIndex)
      $slide.Export($name, 'PNG', 1920, 1080)
    }
  }
  # ppSaveAsOpenXMLPresentation = 24; EmbedTrueTypeFonts = msoTrue (-1).
  $target = [System.IO.Path]::GetFullPath($Out)
  $deck.SaveAs($target, 24, -1)
  $deck.Close()
} finally {
  $app.Quit()
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
  foreach ($f in $files) { [void][Fonts]::RemoveFontResource($f) }
}
Write-Output "saved $Out"
