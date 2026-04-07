#!/usr/bin/env python3
import subprocess
from pathlib import Path


def render_pseudospin_orbital_text(grouped_payload):
    lines = ["Pseudo-Spin-Orbital Bond Report", "==============================", ""]
    for shell in grouped_payload.get("distance_shells", []):
        lines.append(f"Distance shell {shell['shell_index']}")
        lines.append(f"- distance = {shell['distance']}")
        lines.append(f"- bond_count = {shell['bond_count']}")
        lines.append(f"- R_vectors = {shell['R_vectors']}")
        lines.append("")
        for bond in grouped_payload.get("bonds", []):
            if round(bond["distance"], 10) != round(shell["distance"], 10):
                continue
            lines.append(f"Bond R = {bond['R']}")
            lines.append(f"- matrix_shape = {bond['matrix_shape']}")
            lines.append("- grouped terms:")
            for item in bond.get("grouped_terms", []):
                lines.append(
                    f"  - family={item['family']} body_order={item['body_order']} "
                    f"coeff={item['coefficient']} label={item['latex_label']}"
                )
            lines.append("- Residual terms")
            for item in bond.get("residual_terms", []):
                lines.append(
                    f"  - reason={item['residual_reason']} body_order={item['body_order']} "
                    f"coeff={item['coefficient']} label={item['latex_label']}"
                )
            lines.append("")
    return "\n".join(lines)


def render_pseudospin_orbital_tex(grouped_payload):
    lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath}",
        r"\usepackage{longtable}",
        r"\begin{document}",
        r"\section*{Pseudo-Spin-Orbital Bond Report}",
    ]
    for shell in grouped_payload.get("distance_shells", []):
        lines.append(rf"\section{{Distance shell {shell['shell_index']}}}")
        lines.append(rf"Distance: ${shell['distance']}$\\")
        lines.append(rf"Bond count: {shell['bond_count']}\\")
        lines.append(rf"$R$ vectors: {shell['R_vectors']}\\")
        for bond in grouped_payload.get("bonds", []):
            if round(bond["distance"], 10) != round(shell["distance"], 10):
                continue
            lines.append(rf"\subsection{{Bond $R=({bond['R'][0]},{bond['R'][1]},{bond['R'][2]})$}}")
            lines.append(rf"Matrix shape: {bond['matrix_shape']}\\")
            lines.append(r"\paragraph{Grouped terms}")
            lines.append(r"\begin{itemize}")
            for item in bond.get("grouped_terms", []):
                lines.append(
                    rf"\item {item['family']} (body order {item['body_order']}): "
                    rf"${item['latex_label']}$, coefficient = ${item['coefficient']['real']}$"
                )
            lines.append(r"\end{itemize}")
            lines.append(r"\paragraph{Residual terms}")
            lines.append(r"\begin{itemize}")
            for item in bond.get("residual_terms", []):
                lines.append(
                    rf"\item {item['residual_reason']} (body order {item['body_order']}): "
                    rf"${item['latex_label']}$, coefficient = ${item['coefficient']['real']}$"
                )
            lines.append(r"\end{itemize}")
    lines.append(r"\end{document}")
    return "\n".join(lines)


def write_pseudospin_orbital_report(grouped_payload, output_dir, compile_pdf=True):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    text = render_pseudospin_orbital_text(grouped_payload)
    tex = render_pseudospin_orbital_tex(grouped_payload)

    txt_path = output_dir / "report.txt"
    tex_path = output_dir / "report.tex"
    txt_path.write_text(text, encoding="utf-8")
    tex_path.write_text(tex, encoding="utf-8")

    manifest = {
        "report": {
            "txt_path": str(txt_path),
            "tex_path": str(tex_path),
            "pdf_path": None,
        }
    }

    if compile_pdf:
        pdf_path = output_dir / "report.pdf"
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", str(tex_path.name)],
            cwd=output_dir,
            check=False,
            capture_output=True,
            text=True,
        )
        manifest["report"]["pdf_path"] = str(pdf_path)

    return manifest
