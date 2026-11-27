# Helper script to run SonarQube Community Edition in Docker and execute SonarScanner on InvenTree
# Usage: .\tests\team\scripts\start_sonarqube.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Step 1: Checking / Starting SonarQube Container ===" -ForegroundColor Cyan
$existing = docker ps -a --filter "name=^/sonarqube$" --format "{{.Names}}"
if ($existing) {
    docker start sonarqube | Out-Null
    Write-Host "Started existing 'sonarqube' container on http://localhost:9000" -ForegroundColor Green
} else {
    $sqeExisting = docker ps -a --filter "name=sqe-sonarqube" --format "{{.Names}}"
    if (-not $sqeExisting) {
        docker run -d --name sqe-sonarqube -p 9000:9000 sonarqube:community
        Write-Host "Started new 'sqe-sonarqube' container on http://localhost:9000" -ForegroundColor Green
    } else {
        docker start sqe-sonarqube | Out-Null
        Write-Host "Started existing 'sqe-sonarqube' container on http://localhost:9000" -ForegroundColor Green
    }
}

Write-Host "Waiting for SonarQube server to report status UP at http://localhost:9000/api/system/status ..." -ForegroundColor Yellow
$maxAttempts = 45
for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:9000/api/system/status" -TimeoutSec 3
        if ($resp.status -eq "UP") {
            Write-Host "SonarQube is UP and ready!" -ForegroundColor Green
            break
        }
        Write-Host "  [$i/$maxAttempts] Status: $($resp.status) - waiting 4s..."
    } catch {
        Write-Host "  [$i/$maxAttempts] SonarQube booting - waiting 4s..."
    }
    Start-Sleep -Seconds 4
}

Write-Host "`nTo run the SonarScanner CLI against this repository once logged in (default admin / admin):" -ForegroundColor Cyan
Write-Host 'docker run --rm --network host -v "${PWD}:/usr/src" sonarsource/sonar-scanner-cli -Dsonar.host.url=http://localhost:9000 -Dsonar.token=<YOUR_SONAR_TOKEN>' -ForegroundColor White
