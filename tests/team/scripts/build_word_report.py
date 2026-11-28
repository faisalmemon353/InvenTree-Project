"""Build the final Word (.docx) report: Times New Roman, black & white, page border, page numbers."""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.section import WD_SECTION  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches, Pt, RGBColor  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "tests" / "team" / "docs"
EVID = ROOT / "tests" / "team" / "evidence"
SCRATCH = ROOT / "tests" / "team" / "scripts" / "_word_assets"
OUT = ROOT.parent / "Project_24I-3032_24I-3011_24I-3004_C.docx"
FONT = "Times New Roman"
BLACK = RGBColor(0, 0, 0)

FIGURES = {
    "03_": ("step1", "Step 1"),
    "04_": ("step2", "Step 2"),
    "05_": ("step3", "Step 3"),
    "06_": ("step4", "Step 4"),
    "07_": ("step5", "Step 5"),
}
CAPTIONS = {
    "step1_ss1": "Git branches and baseline tag",
    "step1_ss2": "Hand-calculated CFG complexity verification",
    "step1_ss3": "Seed and reset scripts",
    "step1_ss4": "SonarQube dashboard for the order module",
    "step2_ss1": "Unit tests with 100% statement and branch coverage",
    "step2_ss2": "Mutation analysis results",
    "step2_ss3": "Blocked pull request (CI quality gate failing)",
    "step2_ss4": "Documented fix pull request (red to green)",
    "step3_ss1": "OpenAPI test data generator and Viva constraint diff",
    "step3_ss2": "API and integration tests passing",
    "step3_ss3_terminal": "Git log showing Hassan Zahid commits",
    "step3_ss3_github": "GitHub commit history on dev",
    "step4_ss1": "Playwright end-to-end tests passing",
    "step4_ss2": "Lighthouse, axe-core, ZAP, pip-audit and RBAC audit summary",
    "step4_ss3": "GitHub commit history including Salman Ahmad",
    "step5_ss1": "Grafana k6 load test benchmark summary",
    "step5_ss2": "Controlled failure and recovery test passing",
}


# ---------------------------------------------------------------- helpers
def set_font(run, size=12, bold=None, italic=None, name=FONT):
    run.font.name = name
    r = run._element.get_or_add_rPr()
    rf = r.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        r.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), name)
    run.font.size = Pt(size)
    run.font.color.rgb = BLACK
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def style_font(style, size, bold=False, italic=False):
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = italic
    style.font.color.rgb = BLACK
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), FONT)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if rf.get(qn(a)) is not None:
            del rf.attrib[qn(a)]


def add_field(par, instr, size=12):
    run = par.add_run()
    set_font(run, size)
    for t, txt in (("begin", None), (None, instr), ("separate", None), (None, "1"), ("end", None)):
        if t:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), t)
            if t == "begin":
                fc.set(qn("w:dirty"), "true")
            run._element.append(fc)
        elif txt == instr:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = f" {instr} "
            run._element.append(it)
        else:
            tx = OxmlElement("w:t")
            tx.text = txt
            run._element.append(tx)


def para_border(par, side="bottom", sz=8):
    ppr = par._p.get_or_add_pPr()
    pb = OxmlElement("w:pBdr")
    el = OxmlElement(f"w:{side}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(sz))
    el.set(qn("w:space"), "4")
    el.set(qn("w:color"), "000000")
    pb.append(el)
    ppr.append(pb)


def clean_math(text: str) -> str:
    def conv(m):
        s = m.group(1)
        s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
        s = re.sub(r"\\mathbf\{([^}]*)\}", r"\1", s)
        s = re.sub(r"\\frac\{([^}]*)\}\{([^}]*)\}", r"(\1 / \2)", s)
        s = re.sub(r"_\{([^}]*)\}", r"_\1", s)
        s = re.sub(r"\^\{([^}]*)\}", r"^\1", s)
        rep = {
            r"\land": " ∧ ",
            r"\lor": " ∨ ",
            r"\neg": "¬",
            r"\le": "≤",
            r"\ge": "≥",
            r"\neq": "≠",
            r"\ne": "≠",
            r"\times": "×",
            r"\rightarrow": "→",
            r"\leftarrow": "←",
            r"\to": "→",
            r"\approx": "≈",
            r"\cdot": "·",
            r"\quad": "  ",
            r"\%": "%",
            r"\;": " ",
            r"\,": " ",
            r"\sum": "Σ",
            r"\ll": "<<",
            r"\pm": "±",
            r"\delta": "δ",
            r"\sigma": "σ",
            r"\min": "min",
            r"\max": "max",
            r"\dots": "...",
            r"\ldots": "...",
        }
        for k in sorted(rep, key=len, reverse=True):
            s = s.replace(k, rep[k])
        # Convert simple single-digit subscripts like C_1 -> C1 or p_95 -> p95
        s = re.sub(r"\b([A-Za-z])_([A-Za-z0-9]+)\b", r"\1\2", s)
        s = s.replace("{", "").replace("}", "").replace("\\", "")
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

    text = re.sub(r"\$\$(.+?)\$\$", lambda m: conv(m), text)
    text = re.sub(r"\$([^$\n]+?)\$", lambda m: conv(m), text)
    return text


INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)")


def _emit_runs(par, seg: str, size=12, bold=False, italic=False):
    for tok in INLINE.split(seg):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            _emit_runs(par, tok[2:-2], size=size, bold=True, italic=italic)
        elif tok.startswith("`") and tok.endswith("`") and len(tok) > 2:
            inner = tok[1:-1].replace("`", "")
            r = par.add_run(inner)
            set_font(r, size, bold=bold, italic=italic)
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            _emit_runs(par, tok[1:-1], size=size, bold=bold, italic=True)
        else:
            clean_tok = tok.replace("`", "")
            r = par.add_run(clean_tok)
            set_font(r, size, bold=bold, italic=italic)


def add_inline(par, text, size=12, bold=False):
    text = clean_math(text)
    text = re.sub(r"\[([^\]]+)\]\((?:file|http)[^)]*\)", r"\1", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"<br\s*/?>", "<br/>", text)
    parts = text.split("<br/>")
    for pi, seg in enumerate(parts):
        if pi:
            par.add_run().add_break()
        _emit_runs(par, seg, size=size, bold=bold)


# ------------------------------------------------------------ chart assets
DIAGRAM_OVERRIDE = EVID / "diagrams"


def diagram(name: str) -> Path:
    cand = DIAGRAM_OVERRIDE / f"{name}.png"
    return cand if cand.exists() else SCRATCH / f"{name}.png"


def make_assets():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif"]
    # Pareto
    cats = ["Business Logic\n& FSM", "Security\n& RBAC", "Accessibility\n(WCAG)", "Performance\n(N+1)", "Null-Safety"]
    counts = [3, 2, 1, 1, 1]
    cum = [3, 5, 6, 7, 8]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.bar(cats, counts, color=["#2e86de", "#e67e22", "#27ae60", "#8e44ad", "#16a085"], edgecolor="black")
    ax.set_ylabel("Defect Count")
    ax.set_ylim(0, 8.5)
    ax.plot(cats, cum, color="#c0392b", marker="o", lw=2)
    for i, v in enumerate(cum):
        ax.annotate(f"{v/8*100:.1f}%", (i, v), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax.set_title("Pareto Analysis of Defects by Category")
    fig.tight_layout()
    fig.savefig(SCRATCH / "pareto.png", dpi=200)
    plt.close(fig)

    def fishbone(path, effect, causes, title):
        fig, ax = plt.subplots(figsize=(9.4, 4.8))
        ax.set_xlim(0, 11.6)
        ax.set_ylim(0, 6)
        ax.axis("off")
        ax.annotate("", xy=(8.2, 3), xytext=(0.3, 3), arrowprops=dict(arrowstyle="-|>", lw=2.5, color="#2c3e50"))
        ax.text(8.3, 3, effect, va="center", ha="left", fontsize=9, weight="bold",
                bbox=dict(boxstyle="round", fc="#f5b7b1", ec="#c0392b", lw=1.5))
        cols = ["#aed6f1", "#abebc6", "#f9e79f", "#d7bde2"]
        edges = ["#2874a6", "#1e8449", "#b7950b", "#76448a"]
        pos = [(3.0, 5.2), (6.3, 5.2), (3.0, 0.8), (6.3, 0.8)]
        for k, ((x, y), (head, body)) in enumerate(zip(pos, causes)):
            top = y > 3
            y_end = y - 0.35 if top else y + 0.35
            ax.plot([x, x + 1.4], [y_end, 3], color=edges[k], lw=2.2)
            ax.text(x, y, head, ha="center", va="center", fontsize=9, weight="bold",
                    bbox=dict(boxstyle="round", fc=cols[k], ec=edges[k], lw=1.5))
            ym = (y_end + 3) / 2
            ax.text(x + 0.5, ym, body, ha="right", va="center", fontsize=7.2,
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=edges[k], lw=0.8))
        ax.set_title(title, fontsize=11)
        fig.tight_layout()
        fig.savefig(path, dpi=200)
        plt.close(fig)

    fishbone(SCRATCH / "fish1.png", "DEF-01 (High / P1)\nUnrestricted over-receiving\ninflates StockItem.quantity", [
        ("Architecture & Design", "Validation split between UI warning\nand model layer; no\nallow_over_receive flag"),
        ("Code & Implementation", "models.py checks only quantity < 0\nbefore line.received += quantity"),
        ("Requirements & Rules", "Upstream assumes over-shipment\nis always acceptable"),
        ("Testing & Verification", "Happy-path tests lacked BVA\n(ordered + 1) and boundary mutants"),
    ], "Ishikawa (Fishbone) Diagram - DEF-01")
    fishbone(SCRATCH / "fish2.png", "DEF-03 (High / P1)\n6 axe-core WCAG 2.1 AA\nviolations; Lighthouse 68/100", [
        ("HTML Semantics", "span used instead of label-for;\nno html lang; img without alt"),
        ("CSS & Visual Design", "Status badge #b5b5b5 on #ffffff\n(2.03:1 vs required 4.5:1)"),
        ("ARIA Naming", "Icon button had no accessible name;\naria-label mismatched visible text"),
        ("QA Process", "Accessibility checks not automated\nbefore Step 4"),
    ], "Ishikawa (Fishbone) Diagram - DEF-03")



def render_cfg(body, path):
    node_re = r'(\w+)(\[".*?"\]|\{".*?"\}|\(\[".*?"\]\))?'
    edge_re = re.compile(r'^\s*' + node_re + r'\s*(?:--\s*"([^"]*)"\s*)?-->\s*' + node_re + r'\s*$')
    labels, shapes, edges = {}, {}, []
    def reg(i, br):
        if br:
            shapes[i] = "d" if br.startswith("{") else ("o" if br.startswith("([") else "b")
            labels[i] = br.strip("[]{}()").strip('"')
        labels.setdefault(i, i)
        shapes.setdefault(i, "b")
    for ln in body:
        m = edge_re.match(ln)
        if not m:
            continue
        a, abr, lab, b, bbr = m.groups()
        reg(a, abr); reg(b, bbr)
        edges.append((a, b, lab or ""))
    num = lambda x: int(re.sub(r"\D", "", x) or 0)
    order = sorted(labels, key=num)
    nn = len(order)
    pos = {}
    for k, n in enumerate(order):
        x = 1.7 if "raise" in labels[n].lower() else 5.6
        pos[n] = (x, nn - k)
    fig, ax = plt.subplots(figsize=(8.0, 11.0))
    ax.set_xlim(-0.6, 9.4); ax.set_ylim(0, nn + 1); ax.axis("off")
    for a, b, lab in edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        col = "#1e8449" if lab == "True" else ("#c0392b" if lab == "False" else "#566573")
        skip = abs(y1 - y2) > 1.5
        rad = -0.35 if (x1 == x2 and skip and lab == "False") else 0.0
        ax.annotate("", xy=(x2, y2 + 0.28), xytext=(x1, y1 - 0.28),
                    arrowprops=dict(arrowstyle="-|>", lw=1.1, color=col, shrinkA=0, shrinkB=0,
                                    connectionstyle=f"arc3,rad={rad}"))
        if lab and not (x1 == x2 and skip):
            ax.text((x1 + x2) / 2 + 0.25, (y1 + y2) / 2, lab, fontsize=7, color=col, ha="left", va="center",
                    bbox=dict(fc="white", ec="none", pad=0.2))
    for n, (x, y) in pos.items():
        txt = re.sub(r"(.{34})\s", r"\1\n", labels[n])
        style = {"d": "round,pad=0.3,rounding_size=0.4", "o": "round,pad=0.3,rounding_size=0.6", "b": "square,pad=0.3"}[shapes[n]]
        low = labels[n].lower()
        if "raise" in low:
            fc, ec = "#f5b7b1", "#c0392b"
        elif shapes[n] == "d":
            fc, ec = "#fcf3cf", "#b7950b"
        elif shapes[n] == "o":
            fc, ec = "#d5d8dc", "#2c3e50"
        elif "entry" in low:
            fc, ec = "#abebc6", "#1e8449"
        else:
            fc, ec = "#aed6f1", "#2874a6"
        ax.text(x, y, txt, ha="center", va="center", fontsize=7.4, bbox=dict(boxstyle=style, fc=fc, ec=ec, lw=1.1))
    ax.text(-0.4, nn + 0.6, "Legend:  green arrow = True branch   |   red arrow = False branch   |   grey arrow = sequential flow\n"
            "yellow = decision node   |   red box = raise ValidationError   |   grey = unified EXIT", fontsize=7.2, va="top",
            bbox=dict(boxstyle="round", fc="white", ec="#566573"))
    ax.set_title("Control Flow Graph - PurchaseOrderLineItem.clean()", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


# ----------------------------------------------------------- doc elements
def add_heading(doc, text, level):
    sizes = {1: 16, 2: 14, 3: 14, 4: 12}
    p = doc.add_heading(level=min(level, 4))
    p.paragraph_format.space_before = Pt(14 if level <= 2 else 10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    text = clean_math(text)
    text = re.sub(r"[`*]", "", text)
    r = p.add_run(text)
    set_font(r, sizes[min(level, 4)], bold=True, italic=(level == 3))
    return p


def add_table(doc, rows):
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    size = 10 if ncols <= 5 else (9 if ncols <= 8 else 8)
    t = doc.add_table(rows=len(rows), cols=ncols)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    weights = []
    for c in range(ncols):
        lens = [len(clean_math(rows[r][c])) for r in range(len(rows))]
        weights.append(max(6, min(45, sum(lens) / len(lens))))
    total = sum(weights)
    for ri, row in enumerate(rows):
        for ci, cell_text in enumerate(row):
            cell = t.cell(ri, ci)
            cell.width = Inches(6.5 * weights[ci] / total)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            add_inline(p, cell_text.strip(), size=size, bold=(ri == 0))
        if ri == 0:
            trpr = t.rows[0]._tr.get_or_add_trPr()
            h = OxmlElement("w:tblHeader")
            h.set(qn("w:val"), "true")
            trpr.append(h)
        cs = OxmlElement("w:cantSplit")
        t.rows[ri]._tr.get_or_add_trPr().append(cs)


def add_code(doc, lines):
    for idx, ln in enumerate(lines):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4 if idx == len(lines) - 1 else 0)
        p.paragraph_format.left_indent = Inches(0.2)
        r = p.add_run(ln if ln else " ")
        set_font(r, 9, name="Courier New")


def add_picture(doc, path: Path, caption: str, num: int, width=6.2):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    with Image.open(path) as im:
        w, h = im.size
        norm = SCRATCH / ("norm_" + path.stem + ".png")
        im.convert("RGB").save(norm)
    path = norm
    wi = min(width, 6.2)
    hi = wi * h / w
    if hi > 7.4:
        wi = wi * 7.4 / hi
    p.add_run().add_picture(str(path), width=Inches(wi))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run(f"Figure {num}: {caption}")
    set_font(r, 12, italic=True)


def render_markdown(doc, md_text, prefix, fig_counter):
    lines = md_text.splitlines()
    i = 0
    mermaid_no = 0
    first_h1 = True
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```"):
            lang = s[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i].rstrip())
                i += 1
            i += 1
            if lang == "mermaid":
                mermaid_no += 1
                if prefix == "07_":
                    img = {1: "pareto.png", 2: "fish1.png", 3: "fish2.png"}.get(mermaid_no)
                    cap = {1: "Pareto chart of defects by category",
                           2: "Fishbone diagram for DEF-01",
                           3: "Fishbone diagram for DEF-03"}.get(mermaid_no)
                    if img:
                        fig_counter[0] += 1
                        add_picture(doc, diagram(img[:-4]), cap, fig_counter[0], width=6.0)
                        continue
            if lang == "mermaid" and prefix == "03_":
                render_cfg(body, SCRATCH / "cfg.png")
                fig_counter[0] += 1
                add_picture(doc, diagram("cfg"), "Control Flow Graph of PurchaseOrderLineItem.clean()", fig_counter[0], width=6.2)
                continue
            add_code(doc, body)
            continue
        if re.match(r"^#{1,6}\s", s):
            level = len(s) - len(s.lstrip("#"))
            text = s[level:].strip()
            if level == 1:
                if not first_h1:
                    pass
                first_h1 = False
                doc.add_page_break()
            add_heading(doc, text, level)
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip().strip("|")
                if not re.match(r"^\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*$", row):
                    rows.append([c.strip() for c in re.split(r"(?<!\\)\|", row)])
                i += 1
            add_table(doc, rows)
            continue
        if s in ("---", "***", "___"):
            i += 1
            continue
        if not s:
            i += 1
            continue
        if s.startswith("$$") and s.endswith("$$"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline(p, s)
            i += 1
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", ln)
        if m:
            indent = len(m.group(1)) // 2
            marker = m.group(2)
            numbered = marker[0].isdigit()
            if numbered:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.35 + 0.3 * indent)
                p.paragraph_format.first_line_indent = Inches(-0.22)
                p.paragraph_format.space_after = Pt(3)
                r_num = p.add_run(f"{marker} ")
                set_font(r_num, 12, bold=True)
                add_inline(p, m.group(3))
            else:
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.left_indent = Inches(0.35 + 0.3 * indent)
                p.paragraph_format.space_after = Pt(2)
                add_inline(p, m.group(3))
            i += 1
            continue
        if s.startswith(">"):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            para_border(p, "left", 12)
            add_inline(p, re.sub(r"^>\s*(\[![A-Z]+\])?\s*", "", s))
            i += 1
            continue
        # paragraph (merge continuation lines)
        buf = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|```|\||>|[-*]\s|\d+\.\s|\$\$)", lines[i].strip()
        ):
            buf.append(lines[i].strip())
            i += 1
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(6)
        add_inline(p, " ".join(buf))


# ------------------------------------------------------------- main build
def build():
    make_assets()
    doc = Document()
    for name, size, bold in (("Normal", 12, False), ("List Bullet", 12, False), ("List Number", 12, False),
                             ("Heading 1", 16, True), ("Heading 2", 14, True), ("Heading 3", 14, True),
                             ("Heading 4", 12, True), ("Table Grid", 12, False)):
        try:
            style_font(doc.styles[name], size, bold)
        except KeyError:
            pass
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
    sec.left_margin = sec.right_margin = Inches(1)
    sec.top_margin = sec.bottom_margin = Inches(1)
    sec.different_first_page_header_footer = True

    # page border on every page
    sp = sec._sectPr
    pb = OxmlElement("w:pgBorders")
    pb.set(qn("w:offsetFrom"), "page")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "12")
        el.set(qn("w:space"), "24")
        el.set(qn("w:color"), "000000")
        pb.append(el)
    sp.append(pb)

    # header / footer (not on title page)
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_inline(hp, "SE3002 Software Quality Engineering - Final Project Report (Section C)", size=10)
    para_border(hp, "bottom", 6)
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("Page ")
    set_font(r, 12)
    add_field(fp, "PAGE")
    r = fp.add_run(" of ")
    set_font(r, 12)
    add_field(fp, "NUMPAGES")

    # ---- title page
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(30)
    for t in ("Final Project Report", "Software Quality Engineering", "Quality Evaluation of the InvenTree",
              "Inventory Management Information System"):
        r = p.add_run(t)
        set_font(r, 16, bold=True)
        r.add_break()
    para_border(p, "bottom", 8)
    with Image.open(ROOT / "tests" / "team" / "scripts" / "_title_ref.jpg") as ref:
        logo = ref.crop((176, 270, 548, 594))
        logo.save(SCRATCH / "logo.png")
    lp = doc.add_paragraph()
    lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lp.paragraph_format.space_before = Pt(36)
    lp.paragraph_format.space_after = Pt(36)
    lp.add_run().add_picture(str(SCRATCH / "logo.png"), width=Inches(3.4))
    t = doc.add_table(rows=2, cols=3)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, (n, rn) in enumerate((("Hassan Zahid", "24I-3011"), ("Faisal Memon", "24I-3032"),
                                 ("Salman Ahmad", "24I-3004"))):
        for rr, txt in enumerate((n, rn)):
            cell = t.cell(rr, c)
            pp = cell.paragraphs[0]
            pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pp.paragraph_format.space_after = Pt(0)
            set_font(pp.add_run(txt), 12)
    for txt in ("SE-C", "Software Quality Engineering (SE3002) - Fall 2026",
                "Submitted to: Anum Kaleem"):
        pp = doc.add_paragraph()
        pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pp.paragraph_format.space_before = Pt(14)
        set_font(pp.add_run(txt), 12)

    # ---- table of contents
    doc.add_page_break()
    add_heading(doc, "Table of Contents", 1)
    tp = doc.add_paragraph()
    add_field(tp, 'TOC \\o "1-2" \\h \\z \\u')
    note = doc.add_paragraph()
    set_font(note.add_run("(If page numbers are not shown, right-click this area and choose Update Field.)"), 12,
             italic=True)

    # ---- chapters
    fig_counter = [0]
    for md_file in sorted(DOCS.glob("0*_*.md")):
        text = md_file.read_text(encoding="utf-8")
        render_markdown(doc, text, md_file.name[:3], fig_counter)
        key = md_file.name[:3]
        # Step 1 screenshots belong to docs 01-03 -> attach after doc 03
        if key in FIGURES:
            step_dir = EVID / FIGURES[key][0]
            doc.add_page_break()
            add_heading(doc, f"Execution Screenshots - {FIGURES[key][1]}", 2)
            for img in sorted(step_dir.iterdir()):
                if img.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    cap = next((v for k, v in CAPTIONS.items() if img.name.startswith(k)), img.stem)
                    fig_counter[0] += 1
                    add_picture(doc, img, cap, fig_counter[0])

    # update fields on open (TOC / page numbers)
    settings = doc.settings.element
    uf = OxmlElement("w:updateFields")
    uf.set(qn("w:val"), "true")
    settings.append(uf)
    doc.core_properties.title = "SE3002 SQE Final Project Report"
    doc.core_properties.author = "Hassan Zahid, Faisal Memon, Salman Ahmad"
    try:
        doc.save(OUT)
        print("Saved", OUT, f"({OUT.stat().st_size/1024/1024:.2f} MB), figures:", fig_counter[0])
    except PermissionError:
        alt_out = OUT.with_name("Project_24I-3032_24I-3011_24I-3004_C_Updated.docx")
        doc.save(alt_out)
        print("Target file open in Word; saved to:", alt_out, f"({alt_out.stat().st_size/1024/1024:.2f} MB), figures:", fig_counter[0])


if __name__ == "__main__":
    build()
