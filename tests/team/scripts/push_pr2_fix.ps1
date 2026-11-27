# Helper script to push the fix commit to Pull Request #2 (fix/faisal-documented-pr-fix)
# Run this AFTER opening PR #2 on GitHub and letting Commit 1 fail the CI Quality Gate!
# Usage: .\tests\team\scripts\push_pr2_fix.ps1

$ErrorActionPreference = "Stop"
cd "d:\SQE Project\InvenTree"

git checkout fix/faisal-documented-pr-fix
git checkout dev -- src/backend/InvenTree/order/po_business_rules.py
git add src/backend/InvenTree/order/po_business_rules.py
git commit -m "fix(order): restore strict PLACED status precondition in evaluate_stock_receipt_decision (24I-3032)"
git push origin fix/faisal-documented-pr-fix
git checkout dev

Write-Host "`n=== Fix commit pushed to 'fix/faisal-documented-pr-fix'! ===" -ForegroundColor Green
Write-Host "Refresh Pull Request #2 on GitHub to watch the CI Quality Gate turn GREEN (Passed)!" -ForegroundColor Cyan
