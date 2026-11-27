#!/usr/bin/env python3
"""Automated SonarQube password setup, token generation, and scanner execution script."""

import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
SONAR_URL = 'http://localhost:9000'
ADMIN_USER = 'admin'
DEFAULT_PASS = 'admin'
NEW_PASS = 'SQESonarPass123!'

SCANNER_VERSION = '6.2.1.4610'
SCANNER_ZIP_URL = f'https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-{SCANNER_VERSION}.zip'
SCANNER_DIR = REPO_ROOT / '.venv' / f'sonar-scanner-{SCANNER_VERSION}'


def wait_for_sonarqube_up(timeout_sec: int = 180) -> None:
    """Wait until SonarQube reports status == UP."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            r = requests.get(f'{SONAR_URL}/api/system/status', timeout=5)
            status = r.json().get('status')
            print(f'  SonarQube status: {status}')
            if status == 'UP':
                return
        except Exception as exc:
            print(f'  Waiting for SonarQube... ({exc})')
        time.sleep(3)
    raise RuntimeError('SonarQube did not reach UP status within timeout')


def ensure_password_and_token() -> str:
    """Ensure admin password is set to NEW_PASS and return a fresh analysis token."""
    r = requests.post(
        f'{SONAR_URL}/api/users/change_password',
        auth=(ADMIN_USER, DEFAULT_PASS),
        data={'login': ADMIN_USER, 'previousPassword': DEFAULT_PASS, 'password': NEW_PASS},
        timeout=10,
    )
    if r.status_code in (200, 204):
        print(f"Changed SonarQube admin password to '{NEW_PASS}'")

    requests.post(
        f'{SONAR_URL}/api/user_tokens/revoke',
        auth=(ADMIN_USER, NEW_PASS),
        data={'name': 'sqe-auto-token'},
        timeout=10,
    )

    tok_resp = requests.post(
        f'{SONAR_URL}/api/user_tokens/generate',
        auth=(ADMIN_USER, NEW_PASS),
        data={'name': 'sqe-auto-token'},
        timeout=10,
    )
    tok_resp.raise_for_status()
    token = tok_resp.json()['token']
    print('Generated fresh SonarQube analysis token.')
    return token


def ensure_sonar_scanner_cli() -> Path:
    """Download the lightweight (~600 KB) pure-Java SonarScanner CLI if not already extracted."""
    bat_path = SCANNER_DIR / 'bin' / 'sonar-scanner.bat'
    if bat_path.exists():
        return bat_path

    zip_path = REPO_ROOT / '.venv' / f'sonar-scanner-cli-{SCANNER_VERSION}.zip'
    print(f'Downloading lightweight SonarScanner CLI ({SCANNER_VERSION})...')
    resp = requests.get(SCANNER_ZIP_URL, timeout=60)
    resp.raise_for_status()
    zip_path.write_bytes(resp.content)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(REPO_ROOT / '.venv')
    return bat_path


def find_java_home() -> str | None:
    """Locate JDK 17+ on Windows."""
    candidates = [
        Path(r'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'),
    ]
    for base in [Path(r'C:\Program Files\Eclipse Adoptium'), Path(r'C:\Program Files\Java'), Path(r'C:\Program Files\Microsoft')]:
        if base.exists():
            for child in sorted(base.iterdir(), reverse=True):
                if (child / 'bin' / 'java.exe').exists():
                    candidates.append(child)
    for cand in candidates:
        if (cand / 'bin' / 'java.exe').exists():
            return str(cand)
    return os.environ.get('JAVA_HOME')


def run_scanner(token: str) -> None:
    """Execute sonar-scanner.bat against the repository."""
    scanner_bat = ensure_sonar_scanner_cli()
    env = os.environ.copy()
    java_home = find_java_home()
    if java_home:
        env['JAVA_HOME'] = java_home
        env['PATH'] = str(Path(java_home) / 'bin') + os.pathsep + env.get('PATH', '')
        print(f'Using JAVA_HOME: {java_home}')

    cmd = [
        str(scanner_bat),
        f'-Dsonar.host.url={SONAR_URL}',
        f'-Dsonar.token={token}',
        '-Dsonar.projectKey=inventree-sqe-section-c',
        '-Dsonar.projectName=InvenTree SQE Project (Section C - 24I-3032, 24I-3011, 24I-3004)',
        '-Dsonar.sources=src/backend/InvenTree/order',
        '-Dsonar.exclusions=**/migrations/**,**/__pycache__/**,**/test*.py',
        '-Dsonar.python.version=3.13',
    ]
    print('Running SonarScanner CLI...')
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, check=False)
    if res.returncode != 0:
        sys.exit(res.returncode)
    print(f'\n=== SONARQUBE SCAN COMPLETE! Dashboard: {SONAR_URL}/dashboard?id=inventree-sqe-section-c ===')


if __name__ == '__main__':
    wait_for_sonarqube_up()
    token = ensure_password_and_token()
    run_scanner(token)
