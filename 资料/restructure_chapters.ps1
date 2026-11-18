# 目录重构：每章一个目录（正文 + 音频 + 封面），保留卷层级
# 章节\卷X_卷名\第NNN章_章名\
#   ├─ 第NNN章_章名.md
#   ├─ 第NNN章_章名.mp3 / .lrc（若有）
#   └─ 封面\（若有）
$ErrorActionPreference = 'Stop'
$root = 'e:\OneDrive\Create\松风巷的女儿'
$dest = "$root\章节"
New-Item $dest -ItemType Directory -Force | Out-Null

# 1) 正文按卷/章归位
Get-ChildItem "$root\正文" -Recurse -Filter '第*章_*.md' | ForEach-Object {
    $vol = Split-Path (Split-Path $_.FullName -Parent) -Leaf
    $chdir = Join-Path "$dest\$vol" $_.BaseName
    New-Item $chdir -ItemType Directory -Force | Out-Null
    Move-Item $_.FullName $chdir -Force
}
if (Test-Path "$root\正文\尾声.md") { Move-Item "$root\正文\尾声.md" "$dest\" -Force }

# 2) 音频按章名归位
Get-ChildItem "$root\音频" -Recurse -Include *.mp3,*.lrc -File | ForEach-Object {
    $chdir = Get-ChildItem $dest -Recurse -Directory -Filter $_.BaseName | Select-Object -First 1
    if ($chdir) { Move-Item $_.FullName $chdir.FullName -Force }
    else { Write-Output "!! 音频无对应章节目录: $($_.Name)" }
}

# 3) 章节封面归位（书封 封面_定稿.png 保留原处）
$coverRoot = "$root\封面"
if (Test-Path $coverRoot) {
    Get-ChildItem $coverRoot -File -Include *.png -Recurse | ForEach-Object {
        $name = $_.Name
        $chnum = $null
        if ($name -match '^第(\d{3})章') { $chnum = $Matches[1] }
        elseif ($name -match '^cover_(\d{3})_') { $chnum = $Matches[1] }
        if ($chnum) {
            $chdir = Get-ChildItem $dest -Recurse -Directory -Filter "第$chnum`章_*" | Select-Object -First 1
            if ($chdir) {
                $cdir = Join-Path $chdir.FullName '封面'
                New-Item $cdir -ItemType Directory -Force | Out-Null
                Move-Item $_.FullName $cdir -Force
            } else { Write-Output "!! 封面无对应章节目录: $name" }
        }
    }
    # 封面\章节\第NNN章\ 候选图
    if (Test-Path "$coverRoot\章节") {
        Get-ChildItem "$coverRoot\章节" -Directory | ForEach-Object {
            $num = $_.Name -replace '^第(\d{3})章$','$1'
            $chdir = Get-ChildItem $dest -Recurse -Directory -Filter "第$num`章_*" | Select-Object -First 1
            if ($chdir) {
                $cdir = Join-Path $chdir.FullName '封面'
                New-Item $cdir -ItemType Directory -Force | Out-Null
                Get-ChildItem $_.FullName -File | Move-Item -Destination $cdir -Force
            } else { Write-Output "!! 候选封面无对应章节目录: $($_.Name)" }
        }
    }
}

# 4) 清理空目录
foreach ($d in "$root\正文", "$root\音频") {
    if (Test-Path $d) {
        $left = Get-ChildItem $d -Recurse -File
        if (-not $left) { Remove-Item $d -Recurse -Force }
        else { Write-Output "!! $d 仍有文件："; $left | ForEach-Object { $_.FullName } }
    }
}
Write-Output '--- 完成 ---'
