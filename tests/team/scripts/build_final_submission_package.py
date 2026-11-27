"""
SE3002 Software Quality Engineering — Section C
Final Submission Package Builder:
  1. Compiles all 7 project reports (Sections 1-7) and all Step 1-5 evidence screenshots
     into a self-contained HTML master report and renders it via headless Microsoft Edge
     to `d:\SQE Project\Project_24I-3032_24I-3011_24I-3004_C.pdf`.
  2. Packages the full Git repository (including `.git`, all branches, source code, tests,
     reports, and evidence) into `d:\SQE Project\Project_24I-3032_24I-3011_24I-3004_C.zip`
     (excluding transient `.venv` and `node_modules` build caches so the archive is clean and portable).
"""

from __future__ import annotations

import base64
import mimetypes
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import markdown

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT.parent  # d:\SQE Project
PDF_PATH = OUT_DIR / "Project_24I-3032_24I-3011_24I-3004_C.pdf"
ZIP_PATH = OUT_DIR / "Project_24I-3032_24I-3011_24I-3004_C.zip"
DOCS_DIR = REPO_ROOT / "tests" / "team" / "docs"
EVIDENCE_DIR = REPO_ROOT / "tests" / "team" / "evidence"
MASTER_HTML_PATH = DOCS_DIR / "Master_Final_Report_Section_C.html"


def image_to_data_uri(img_path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(img_path))
    mime = mime or "image/jpeg"
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_master_html() -> Path:
    doc_files = sorted(DOCS_DIR.glob("0*_*.md"))

    sections_html = []
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists"]
    )

    for doc_file in doc_files:
        md.reset()
        raw_text = doc_file.read_text(encoding="utf-8")
        rendered = md.convert(raw_text)
        sections_html.append(
            f'<section class="report-chapter" id="{doc_file.stem}">\n{rendered}\n</section>'
        )

    # Embed all Step 1..4 screenshots in an Evidence Appendix
    evidence_cards = []
    for step_dir in sorted(EVIDENCE_DIR.glob("step*")):
        if not step_dir.is_dir():
            continue
        for img in sorted(step_dir.iterdir()):
            if img.suffix.lower() in (".png", ".jpg", ".jpeg"):
                data_uri = image_to_data_uri(img)
                evidence_cards.append(
                    f"""
                    <div class="evidence-item">
                      <h4>{step_dir.name.upper()} — {img.name}</h4>
                      <img src="{data_uri}" alt="{img.name}" />
                    </div>
                    """
                )

    cover_html = """
    <div class="cover-page">
      <div class="cover-header">FAST National University of Computer and Emerging Sciences (NUCES), Islamabad</div>
      <h1>SE3002 — Software Quality Engineering<br/>Final Project Report (Fall 2026)</h1>
      <h2>End-to-End Quality Evaluation & Verification of InvenTree Open-Source MIS<br/>(Purchasing & Stock Receipt Subsystem)</h2>
      <table class="cover-table">
        <thead>
          <tr>
            <th>Member Name</th>
            <th>Roll Number</th>
            <th>Section</th>
            <th>GitHub Username</th>
            <th>Primary Individual Area & Shared Contributions</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Faisal</strong></td>
            <td><code>24I-3032</code></td>
            <td>Section C</td>
            <td><code>faisalmemon353</code></td>
            <td>Area 1: Static Analysis (SonarQube &amp; CFG V(G)=14), White-Box Unit Tests (100% Stmt/Branch), MCC/MC/DC, Custom Mutation Operators (92% raw / 100% non-equiv), GitHub Actions CI Quality Gate (Blocked PR #1 &amp; Fix PR #2) + Shared Management</td>
          </tr>
          <tr>
            <td><strong>Hassan Zahid</strong></td>
            <td><code>24I-3011</code></td>
            <td>Section C</td>
            <td><code>Hassan-Zahid110</code></td>
            <td>Area 2: OpenAPI 3.0 Specification, Automated EP (82 partitions) &amp; 3-Point BVA (117 values) Test Data Generator, 2-Constraint Viva Diff Demonstration, and 33 API &amp; Cross-Workflow Integration Tests (PR #3) + Shared Management</td>
          </tr>
          <tr>
            <td><strong>Salman Ahmed</strong></td>
            <td><code>24I-3004</code></td>
            <td>Section C</td>
            <td><code>Salman-ahmed-2</code></td>
            <td>Area 3: 6 Use Cases (UC-01..UC-06), Playwright E2E Automation, Keyboard Navigation, Lighthouse (68&rarr;100) &amp; axe-core (6&rarr;0) Fix, RBAC Matrix, OWASP ZAP, pip-audit, 4&times;60s Grafana k6 Load Testing, and Failure &amp; Recovery Test (PR #4 &amp; Step 5) + Shared Management</td>
          </tr>
        </tbody>
      </table>
      <div class="cover-meta">
        <p><strong>System Under Test (SUT):</strong> InvenTree (<code>https://github.com/inventree/InvenTree</code>) | <strong>License:</strong> MIT</p>
        <p><strong>Baseline Commit Hash:</strong> <code>b686d7cb64e0b09644d9e9afb0ce4997dfde0c1d</code> (Tag: <code>upstream-b686d7cb64e0b09644d9e9afb0ce4997dfde0c1d</code>)</p>
        <p><strong>Team Repository:</strong> <code>https://github.com/faisalmemon353/InvenTree-Project</code></p>
        <p><strong>Submission Files:</strong> <code>Project_24I-3032_24I-3011_24I-3004_C.pdf</code> &amp; <code>Project_24I-3032_24I-3011_24I-3004_C.zip</code></p>
      </div>
    </div>
    """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Project_24I-3032_24I-3011_24I-3004_C — SE3002 SQE Final Report</title>
  <style>
    @page {{
      size: A4;
      margin: 14mm 14mm 16mm 14mm;
    }}
    body {{
      font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #0f172a;
      line-height: 1.48;
      font-size: 10.2pt;
      margin: 0;
      padding: 0;
    }}
    .cover-page {{
      page-break-after: always;
      padding: 24px 12px;
      border: 2px solid #1e3a8a;
      border-radius: 10px;
      background: #f8fafc;
    }}
    .cover-header {{
      font-size: 11pt;
      font-weight: 700;
      color: #1e3a8a;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 12px;
    }}
    .cover-page h1 {{
      font-size: 20pt;
      color: #0f172a;
      margin: 8px 0 10px 0;
      border-bottom: 3px solid #1d4ed8;
      padding-bottom: 10px;
    }}
    .cover-page h2 {{
      font-size: 13pt;
      color: #334155;
      margin: 0 0 18px 0;
    }}
    .cover-table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 18px;
      font-size: 9.5pt;
    }}
    .cover-table th, .cover-table td {{
      border: 1px solid #94a3b8;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    .cover-table th {{
      background: #1e3a8a;
      color: #ffffff;
    }}
    .cover-meta p {{
      margin: 6px 0;
      font-size: 9.8pt;
    }}
    .report-chapter {{
      page-break-before: always;
    }}
    h1 {{
      font-size: 16pt;
      color: #1e3a8a;
      border-bottom: 2px solid #1e3a8a;
      padding-bottom: 4px;
      margin-top: 16px;
    }}
    h2 {{
      font-size: 13pt;
      color: #0f172a;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 3px;
      margin-top: 14px;
    }}
    h3 {{
      font-size: 11pt;
      color: #1e293b;
      margin-top: 12px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0 14px 0;
      font-size: 8.8pt;
      page-break-inside: auto;
    }}
    tr {{
      page-break-inside: avoid;
      page-break-after: auto;
    }}
    th, td {{
      border: 1px solid #cbd5e1;
      padding: 5px 7px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
    }}
    th {{
      background: #f1f5f9;
      font-weight: 700;
      color: #0f172a;
    }}
    pre, code {{
      font-family: Consolas, 'Courier New', monospace;
      font-size: 8.6pt;
    }}
    pre {{
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 8px 10px;
      overflow-x: auto;
      white-space: pre-wrap;
      word-wrap: break-word;
    }}
    code {{
      background: #f1f5f9;
      padding: 1px 4px;
      border-radius: 3px;
    }}
    blockquote {{
      border-left: 4px solid #1d4ed8;
      background: #eff6ff;
      margin: 10px 0;
      padding: 8px 12px;
    }}
    .evidence-item {{
      page-break-inside: avoid;
      margin-bottom: 18px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 10px;
      background: #ffffff;
    }}
    .evidence-item h4 {{
      margin: 0 0 8px 0;
      color: #1e3a8a;
      font-size: 10pt;
    }}
    .evidence-item img {{
      max-width: 100%;
      height: auto;
      border: 1px solid #94a3b8;
    }}
  </style>
</head>
<body>
  {cover_html}
  {"".join(sections_html)}
  <section class="report-chapter" id="evidence-appendix">
    <h1>Appendix A: Execution Screenshots &amp; Verification Evidence (Steps 1 – 5)</h1>
    <p>All execution screenshots captured on the live InvenTree repository, SonarQube dashboard, GitHub Actions CI Quality Gate Pull Requests, Playwright E2E runner, Lighthouse/axe-core/ZAP/pip-audit suite, and multi-member Git history are embedded below.</p>
    {"".join(evidence_cards)}
  </section>
</body>
</html>
"""
    MASTER_HTML_PATH.write_text(html_content, encoding="utf-8")
    return MASTER_HTML_PATH


def render_pdf_via_edge(html_path: Path, pdf_path: Path) -> None:
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    edge_exe = next((p for p in edge_candidates if os.path.exists(p)), "msedge")
    file_url = html_path.resolve().as_uri()

    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        file_url,
    ]
    print(f"Rendering PDF via Microsoft Edge: {pdf_path} ...")
    subprocess.run(cmd, check=True)
    print(f"Created PDF: {pdf_path} ({pdf_path.stat().st_size / 1024:.1f} KB)")


def build_repository_zip(zip_path: Path) -> None:
    excluded_top_dirs = {
        ".venv",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
    }
    print(f"Creating full repository ZIP archive (including .git): {zip_path} ...")
    if zip_path.exists():
        zip_path.unlink()

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(REPO_ROOT):
            rel_root = Path(root).relative_to(REPO_ROOT)
            # Prune excluded directories in-place
            dirs[:] = [
                d
                for d in dirs
                if d not in excluded_top_dirs
                and not (rel_root == Path("tests/team/e2e") and d == "node_modules")
            ]
            for file in files:
                if file.endswith(".pyc"):
                    continue
                abs_file = Path(root) / file
                arcname = str(Path("InvenTree") / abs_file.relative_to(REPO_ROOT))
                zf.write(abs_file, arcname=arcname)
                file_count += 1

    print(
        f"Created ZIP: {zip_path} ({file_count} files, {zip_path.stat().st_size / (1024 * 1024):.2f} MB)"
    )


def main() -> None:
    html_path = build_master_html()
    render_pdf_via_edge(html_path, PDF_PATH)
    build_repository_zip(ZIP_PATH)


if __name__ == "__main__":
    main()
