Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$envFile = Join-Path $repoRoot ".env"
$redisContainer = "rag-redis"

function Get-EnvValue {
    param(
        [string]$Name,
        [string]$Default = ""
    )

    if (-not (Test-Path $envFile)) {
        return $Default
    }

    foreach ($line in Get-Content $envFile -Encoding utf8) {
        if ($line -match "^\s*$Name=(.*)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $Default
}

function Convert-ToWslPath {
    param([string]$WindowsPath)

    $fullPath = [System.IO.Path]::GetFullPath($WindowsPath)
    $drive = $fullPath.Substring(0, 1).ToLowerInvariant()
    $tail = $fullPath.Substring(2).Replace("\", "/")
    return "/mnt/$drive$tail"
}

function Wait-Command {
    param(
        [scriptblock]$Condition,
        [string]$Description,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            if (& $Condition) {
                Write-Host "[OK] $Description"
                return
            }
        } catch {
        }
        Start-Sleep -Seconds 2
    }

    throw "Timeout while waiting for: $Description"
}

function Test-DockerDesktopReady {
    & docker info --format "{{.ServerVersion}}" *> $null
    return $LASTEXITCODE -eq 0
}

function Test-PortOpen {
    param(
        [string]$TargetHost,
        [int]$Port
    )

    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $iar = $client.BeginConnect($TargetHost, $Port, $null, $null)
        $success = $iar.AsyncWaitHandle.WaitOne(1500, $false)
        if (-not $success) {
            $client.Close()
            return $false
        }
        $client.EndConnect($iar)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Ensure-DockerDesktop {
    if (Test-DockerDesktopReady) {
        Write-Host "[OK] Docker daemon is ready"
        return
    }

    Write-Host "[INFO] Starting Docker Desktop..."
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    Wait-Command -Description "Docker daemon ready" -TimeoutSeconds 120 -Condition {
        Test-DockerDesktopReady
    }
}

function Invoke-WslDocker {
    param(
        [string]$Command,
        [switch]$IgnoreErrors
    )

    $wrapped = "docker context use default >/dev/null 2>&1 || true; $Command"
    $output = & wsl -e sh -lc $wrapped 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0 -and -not $IgnoreErrors) {
        $details = ($output | Out-String).Trim()
        if (-not $details) {
            $details = "Unknown WSL/Docker error."
        }
        throw "WSL Docker command failed. Details: $details"
    }

    return ($output | Out-String)
}

$pythonExe = Get-EnvValue -Name "PYTHON_EXE" -Default "D:\Anaconda\envs\RAG\python.exe"
$appPort = [int](Get-EnvValue -Name "APP_PORT" -Default "8001")
$embeddingPort = [int](Get-EnvValue -Name "LOCAL_EMBEDDING_SERVICE_PORT" -Default "8002")
$wslRepoRoot = Convert-ToWslPath -WindowsPath $repoRoot
$redisReady = Test-PortOpen -TargetHost "127.0.0.1" -Port 6379
$milvusReady = Test-PortOpen -TargetHost "127.0.0.1" -Port 19530

Write-Host "[INFO] Repo root: $repoRoot"
Write-Host "[INFO] Python: $pythonExe"
Write-Host "[INFO] App port: $appPort"
Write-Host "[INFO] Local embedding port: $embeddingPort"

if (-not ($redisReady -and $milvusReady)) {
    Ensure-DockerDesktop
}

if ($redisReady) {
    Write-Host "[INFO] Redis port 6379 is already reachable"
} else {
    Write-Host "[INFO] Starting Redis container in WSL if needed..."
    $redisExists = (Invoke-WslDocker "docker ps -a --format '{{.Names}}' | grep '^$redisContainer$' || true" -IgnoreErrors).Trim()
    if ($redisExists) {
        Invoke-WslDocker "docker start $redisContainer >/dev/null || true" | Out-Null
    } else {
        Invoke-WslDocker "docker run -d --name $redisContainer --restart unless-stopped -p 6379:6379 redis:7-alpine" | Out-Null
    }
    $redisReady = $true
}

if ($milvusReady) {
    Write-Host "[INFO] Milvus port 19530 is already reachable"
} else {
    Write-Host "[INFO] Starting Milvus stack..."
    Invoke-WslDocker "cd '$wslRepoRoot' && docker compose -f docker-compose.milvus.yml up -d" | Out-Null
    $milvusReady = $true
}

Wait-Command -Description "Redis port 6379 reachable" -TimeoutSeconds 60 -Condition {
    Test-PortOpen -TargetHost "127.0.0.1" -Port 6379
}

Wait-Command -Description "Milvus port 19530 reachable" -TimeoutSeconds 120 -Condition {
    Test-PortOpen -TargetHost "127.0.0.1" -Port 19530
}

if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found: $pythonExe"
}

if (-not (Test-PortOpen -TargetHost "127.0.0.1" -Port $embeddingPort)) {
    Write-Host "[INFO] Starting local embedding service on port $embeddingPort..."
    Start-Process -FilePath $pythonExe -ArgumentList "local_embedding_service.py" -WorkingDirectory $repoRoot -WindowStyle Hidden
} else {
    Write-Host "[INFO] Local embedding port $embeddingPort is already listening, skipping restart"
}

Wait-Command -Description "Local embedding health endpoint ready" -TimeoutSeconds 60 -Condition {
    $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$embeddingPort/health" -TimeoutSec 3
    return $response.StatusCode -eq 200
}

if (-not (Test-PortOpen -TargetHost "127.0.0.1" -Port $appPort)) {
    Write-Host "[INFO] Starting app on port $appPort..."
    Start-Process -FilePath $pythonExe -ArgumentList "main.py" -WorkingDirectory $repoRoot -WindowStyle Hidden
} else {
    Write-Host "[INFO] App port $appPort is already listening, skipping restart"
}

Wait-Command -Description "App health endpoint ready" -TimeoutSeconds 60 -Condition {
    $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$appPort/health" -TimeoutSec 3
    return $response.StatusCode -eq 200
}

$health = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$appPort/health").Content
$embeddingHealth = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$embeddingPort/health").Content
Write-Host "[INFO] Embedding Health: $embeddingHealth"
Write-Host "[INFO] Health: $health"
Write-Host "[DONE] Workspace: http://127.0.0.1:$appPort/workspace"
