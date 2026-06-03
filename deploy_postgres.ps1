# deploy_postgres.ps1 - Ejecutar UNA SOLA VEZ
Set-Location 'F:\Proyecto Apuestas'
Write-Host 'Creando PostgreSQL en Fly.io...' -ForegroundColor Cyan
flyctl postgres create --name valuebet-db --region iad --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1
flyctl postgres attach valuebet-db --app valuebet-analyzer
Write-Host 'Secrets actuales:' -ForegroundColor Yellow
flyctl secrets list --app valuebet-analyzer
git add -A
git commit -m 'feat: integrar PostgreSQL persistente'
git push origin master
Write-Host 'Listo! Deploy en curso via GitHub Actions.' -ForegroundColor Green
Write-Host 'Endpoints nuevos:'
Write-Host '  GET  /api/stats'
Write-Host '  GET  /api/bets'
Write-Host '  POST /api/bets'
Write-Host '  POST /api/bets/{id}/resolve'
Write-Host '  GET  /api/alerts/history'
