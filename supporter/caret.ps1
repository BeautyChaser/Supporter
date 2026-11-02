Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
try {
    $focused = [System.Windows.Automation.AutomationElement]::FocusedElement
    $pattern = $null
    $range = $null
    if ($focused.TryGetCurrentPattern([System.Windows.Automation.TextPattern2]::Pattern, [ref]$pattern)) {
        $active = $false
        $range = $pattern.GetCaretRange([ref]$active)
    } elseif ($focused.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
        $ranges = $pattern.GetSelection()
        if ($ranges.Count -gt 0) { $range = $ranges[0] }
    }
    if ($range) {
        $rects = $range.GetBoundingRectangles()
        if ($rects.Count -eq 0) {
            $range.ExpandToEnclosingUnit([System.Windows.Automation.TextUnit]::Character)
            $rects = $range.GetBoundingRectangles()
        }
        if ($rects.Count -gt 0) {
            @{x=$rects[0].Left; y=$rects[0].Bottom} | ConvertTo-Json -Compress
        }
    }
} catch { }
