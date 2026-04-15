#!/usr/bin/env python3
import shutil
import subprocess
from datetime import date
from pathlib import Path


def _format_real_or_complex(serialized, significant_digits=6):
    real = float(serialized["real"])
    imag = float(serialized["imag"])
    if abs(imag) <= 1e-12:
        return f"{real:.{significant_digits}g}"
    sign = "+" if imag >= 0.0 else "-"
    return f"{real:.{significant_digits}g} {sign} {abs(imag):.{significant_digits}g}i"


def _latex_escape_text(text):
    return str(text).replace("_", r"\_")


def _complex_from_serialized(serialized):
    return complex(float(serialized["real"]), float(serialized["imag"]))


def _operator_basis_labels(parsed_payload):
    operator_dictionary = parsed_payload.get("operator_dictionary", {})
    local_operator_basis = operator_dictionary.get("local_operator_basis", {})
    labels = local_operator_basis.get("operator_basis_labels", [])
    if labels:
        return list(labels)
    raise ValueError("parsed payload must include operator_dictionary.local_operator_basis.operator_basis_labels")


def _dense_coefficient_matrix(block, basis_labels):
    index_by_label = {label: idx for idx, label in enumerate(basis_labels)}
    size = len(basis_labels)
    matrix = [[0.0 + 0.0j for _ in range(size)] for _ in range(size)]
    for item in block.get("coefficients", []):
        row = index_by_label[item["left_label"]]
        col = index_by_label[item["right_label"]]
        matrix[row][col] = _complex_from_serialized(item["coefficient"])
    return matrix


def _serialize_complex(value):
    return {"real": float(value.real), "imag": float(value.imag)}


def _format_text_table(rows):
    widths = []
    for row in rows:
        for index, cell in enumerate(row):
            if len(widths) <= index:
                widths.append(0)
            widths[index] = max(widths[index], len(str(cell)))
    return "\n".join(
        "  ".join(str(cell).rjust(widths[index]) for index, cell in enumerate(row)) for row in rows
    )


def _matrix_rows_for_text(matrix):
    rows = [["A\\B"] + [str(index + 1) for index in range(len(matrix))]]
    for row_index, row in enumerate(matrix, start=1):
        rows.append([str(row_index)] + [_format_real_or_complex(_serialize_complex(value)) for value in row])
    return rows


def _matrix_tex(matrix):
    column_spec = "r" + "r" * len(matrix)
    lines = [rf"\resizebox{{\textwidth}}{{!}}{{\begin{{tabular}}{{{column_spec}}}", r"$A\backslash B$"]
    lines[1] += " & " + " & ".join(str(index + 1) for index in range(len(matrix))) + r" \\"
    for row_index, row in enumerate(matrix, start=1):
        values = " & ".join(rf"${_format_real_or_complex(_serialize_complex(value))}$" for value in row)
        lines.append(rf"{row_index} & {values} \\")
    lines.append(r"\end{tabular}}")
    return "\n".join(lines)


def _sorted_axis_items(mapping):
    return [(key, mapping[key]) for key in sorted(mapping)]


def _append_channel_lines(lines, title, mapping):
    lines.append(f"- {title}:")
    if not mapping:
        lines.append("  none")
        return
    for key, value in _sorted_axis_items(mapping):
        lines.append(f"  {key} = {_format_real_or_complex(value)}")


def _append_matrix_channel_lines(lines, title, mapping):
    lines.append(f"- {title}:")
    if not mapping:
        lines.append("  none")
        return
    for left_key, nested in _sorted_axis_items(mapping):
        for right_key, value in _sorted_axis_items(nested):
            lines.append(f"  ({left_key}, {right_key}) = {_format_real_or_complex(value)}")


def _append_quartic_lines(lines, mapping):
    lines.append("- quartic exchange K_{mu nu; alpha beta}:")
    if not mapping:
        lines.append("  none")
        return
    for mu in sorted(mapping):
        for nu in sorted(mapping[mu]):
            for alpha in sorted(mapping[mu][nu]):
                for beta in sorted(mapping[mu][nu][alpha]):
                    value = mapping[mu][nu][alpha][beta]
                    lines.append(
                        f"  ({mu}, {nu}; {alpha}, {beta}) = {_format_real_or_complex(value)}"
                    )


def _append_additional_channel_lines(lines, kk, residual_terms):
    lines.append("- Additional channels:")
    for channel_name in ("one_body_spin_orbital", "crossed_spin_orbital", "three_body"):
        items = kk["additional_channels"].get(channel_name, [])
        if items:
            lines.append(f"  {channel_name}:")
            for item in items:
                lines.append(
                    f"    {_format_real_or_complex(item['coefficient'])} * {item['latex_label']}"
                )
    if residual_terms:
        lines.append("  residual_terms:")
        for item in residual_terms:
            lines.append(
                f"    {_format_real_or_complex(item['coefficient'])} * {item['latex_label']} "
                f"[{item['residual_reason']}]"
            )


def render_pseudospin_orbital_human_text(grouped_payload):
    lines = ["Pseudo-Spin-Orbital Human-Friendly Report", "=========================================", ""]
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
            kk = bond.get("kugel_khomskii")
            if kk:
                lines.append("- Kugel-Khomskii decomposition:")
                lines.append(f"  c(R) = {_format_real_or_complex(kk['constant'])}")
                _append_channel_lines(lines, "h^S symmetric", kk["spin_fields"]["symmetric"])
                _append_channel_lines(lines, "h^T symmetric", kk["orbital_fields"]["symmetric"])
                _append_matrix_channel_lines(lines, "J^S", kk["spin_exchange"])
                _append_matrix_channel_lines(lines, "J^T", kk["orbital_exchange"])
                _append_quartic_lines(lines, kk["quartic_exchange"])
                _append_additional_channel_lines(lines, kk, bond.get("residual_terms", []))
            else:
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


def _latex_channel_item_list(mapping):
    if not mapping:
        return r"\varnothing"
    parts = []
    for key, value in _sorted_axis_items(mapping):
        parts.append(rf"{key}: {_format_real_or_complex(value)}")
    return r",\; ".join(parts)


def _latex_pair_list(mapping):
    if not mapping:
        return r"\varnothing"
    parts = []
    for left_key, nested in _sorted_axis_items(mapping):
        for right_key, value in _sorted_axis_items(nested):
            parts.append(rf"({left_key},{right_key}): {_format_real_or_complex(value)}")
    return r",\; ".join(parts)


def _latex_quartic_list(mapping):
    if not mapping:
        return r"\varnothing"
    parts = []
    for mu in sorted(mapping):
        for nu in sorted(mapping[mu]):
            for alpha in sorted(mapping[mu][nu]):
                for beta in sorted(mapping[mu][nu][alpha]):
                    value = mapping[mu][nu][alpha][beta]
                    parts.append(rf"({mu},{nu};{alpha},{beta}): {_format_real_or_complex(value)}")
    return r",\; ".join(parts)


def render_pseudospin_orbital_human_tex(grouped_payload):
    lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath}",
        r"\usepackage{amssymb}",
        r"\usepackage{longtable}",
        r"\begin{document}",
        r"\section*{Pseudo-Spin-Orbital Human-Friendly Report}",
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
            kk = bond.get("kugel_khomskii")
            if kk:
                lines.append(r"\paragraph{Kugel-Khomskii decomposition}")
                lines.append(r"\begin{align}")
                lines.append(
                    r"H_{ij}(R)"
                    r"&="
                    rf"{_format_real_or_complex(kk['constant'])}"
                    r"+\sum_\mu h_\mu^S(R) \left( S_i^\mu + S_j^\mu \right)"
                    r"+\sum_\alpha h_\alpha^T(R) \left( T_i^\alpha + T_j^\alpha \right)"
                    r"\nonumber\\"
                )
                lines.append(
                    r"&+"
                    r"\sum_{\mu\nu} J_{\mu\nu}^S(R)\, S_i^\mu S_j^\nu"
                    r"+\sum_{\alpha\beta} J_{\alpha\beta}^T(R)\, T_i^\alpha T_j^\beta"
                    r"\nonumber\\"
                )
                lines.append(
                    r"&+"
                    r"\sum_{\mu\nu\alpha\beta}"
                    r"K_{\mu\nu;\alpha\beta}(R)\,"
                    r"S_i^\mu S_j^\nu T_i^\alpha T_j^\beta."
                )
                lines.append(r"\end{align}")
                lines.append(r"\paragraph{Coefficient summary}")
                lines.append(rf"$h^S$: ${_latex_channel_item_list(kk['spin_fields']['symmetric'])}$\\")
                lines.append(rf"$h^T$: ${_latex_channel_item_list(kk['orbital_fields']['symmetric'])}$\\")
                lines.append(rf"$J^S$: ${_latex_pair_list(kk['spin_exchange'])}$\\")
                lines.append(rf"$J^T$: ${_latex_pair_list(kk['orbital_exchange'])}$\\")
                lines.append(rf"$K$: ${_latex_quartic_list(kk['quartic_exchange'])}$\\")
                lines.append(r"\paragraph{Additional channels}")
                for channel_name in ("one_body_spin_orbital", "crossed_spin_orbital", "three_body"):
                    items = kk["additional_channels"].get(channel_name, [])
                    if not items:
                        continue
                    lines.append(rf"\textbf{{{_latex_escape_text(channel_name)}}}:\\")
                    lines.append(r"\begin{itemize}")
                    for item in items:
                        lines.append(
                            rf"\item ${item['latex_label']}$ with coefficient ${_format_real_or_complex(item['coefficient'])}$"
                        )
                    lines.append(r"\end{itemize}")
                if bond.get("residual_terms"):
                    lines.append(r"\paragraph{Residual terms}")
                    lines.append(r"\begin{itemize}")
                    for item in bond.get("residual_terms", []):
                        lines.append(
                            rf"\item {_latex_escape_text(item['residual_reason'])}: "
                            rf"${item['latex_label']}$, coefficient = ${_format_real_or_complex(item['coefficient'])}$"
                        )
                    lines.append(r"\end{itemize}")
            else:
                lines.append(r"\paragraph{Grouped terms}")
                lines.append(r"\begin{itemize}")
                for item in bond.get("grouped_terms", []):
                    lines.append(
                        rf"\item {_latex_escape_text(item['family'])} (body order {item['body_order']}): "
                        rf"${item['latex_label']}$, coefficient = ${_format_real_or_complex(item['coefficient'])}$"
                    )
                lines.append(r"\end{itemize}")
                lines.append(r"\paragraph{Residual terms}")
                lines.append(r"\begin{itemize}")
                for item in bond.get("residual_terms", []):
                    lines.append(
                        rf"\item {_latex_escape_text(item['residual_reason'])} (body order {item['body_order']}): "
                        rf"${item['latex_label']}$, coefficient = ${_format_real_or_complex(item['coefficient'])}$"
                    )
                lines.append(r"\end{itemize}")
    lines.append(r"\end{document}")
    return "\n".join(lines)


def render_pseudospin_orbital_full_text(parsed_payload):
    basis_labels = _operator_basis_labels(parsed_payload)
    inferred = parsed_payload.get("inferred", {})
    lines = ["Full coefficient report", "======================", ""]
    lines.append(f"local_dimension = {inferred['local_dimension']}")
    if "orbital_count" in inferred:
        lines.append(f"orbital_count = {inferred['orbital_count']}")
    if "multiplet_dimension" in inferred:
        lines.append(f"multiplet_dimension = {inferred['multiplet_dimension']}")
    lines.append("")
    lines.append("Basis index map")
    for index, label in enumerate(basis_labels, start=1):
        lines.append(f"{index:>2}  {label}")
    lines.append("")
    for block in parsed_payload.get("bond_blocks", []):
        matrix = _dense_coefficient_matrix(block, basis_labels)
        lines.append(f"Bond R = {block['R']}")
        lines.append(f"- matrix_shape = {block['matrix_shape']}")
        lines.append("Coefficient matrix C_AB(R)")
        lines.append(_format_text_table(_matrix_rows_for_text(matrix)))
        lines.append("")
    return "\n".join(lines)


def render_pseudospin_orbital_full_tex(parsed_payload):
    basis_labels = _operator_basis_labels(parsed_payload)
    inferred = parsed_payload.get("inferred", {})
    lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath}",
        r"\usepackage{longtable}",
        r"\usepackage{graphicx}",
        r"\begin{document}",
        r"\section*{Full coefficient report}",
        rf"Local dimension: {inferred['local_dimension']}\\",
        r"\subsection*{Basis index map}",
        r"\begin{longtable}{rl}",
        r"Index & Label \\",
        r"\hline",
    ]
    if "orbital_count" in inferred:
        lines.insert(7, rf"Orbital count: {inferred['orbital_count']}\\")
    if "multiplet_dimension" in inferred:
        lines.insert(7, rf"Multiplet dimension: {inferred['multiplet_dimension']}\\")
    for index, label in enumerate(basis_labels, start=1):
        escaped_label = label.replace("_", r"\_")
        lines.append(rf"{index} & \texttt{{{escaped_label}}} \\")
    lines.append(r"\end{longtable}")

    for block in parsed_payload.get("bond_blocks", []):
        matrix = _dense_coefficient_matrix(block, basis_labels)
        lines.append(rf"\section{{Bond $R=({block['R'][0]},{block['R'][1]},{block['R'][2]})$}}")
        lines.append(rf"Matrix shape: {block['matrix_shape']}\\")
        lines.append(r"\subsection*{Coefficient matrix}")
        lines.append(_matrix_tex(matrix))
    lines.append(r"\end{document}")
    return "\n".join(lines)


def _write_single_report(prefix, text, tex, output_dir, compile_pdf):
    txt_path = output_dir / f"{prefix}.txt"
    tex_path = output_dir / f"{prefix}.tex"
    txt_path.write_text(text, encoding="utf-8")
    tex_path.write_text(tex, encoding="utf-8")

    manifest = {
        "txt_path": str(txt_path),
        "tex_path": str(tex_path),
        "pdf_path": None,
        "pdf_status": "skipped",
        "pdf_error": None,
    }

    if compile_pdf:
        pdf_path = output_dir / f"{prefix}.pdf"
        pdflatex_cmd = shutil.which("pdflatex")
        if Path("/usr/bin/pdflatex").exists():
            pdflatex_cmd = "/usr/bin/pdflatex"

        completed = subprocess.run(
            [pdflatex_cmd, "-interaction=nonstopmode", "-halt-on-error", str(tex_path.name)],
            cwd=output_dir,
            check=False,
            capture_output=True,
            text=True,
        )
        manifest["pdf_path"] = str(pdf_path)
        if completed.returncode == 0 and pdf_path.exists():
            manifest["pdf_status"] = "ok"
        else:
            manifest["pdf_status"] = "error"
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            manifest["pdf_error"] = stderr or stdout or "pdflatex failed"

    return manifest


def write_pseudospin_orbital_reports(parsed_payload, grouped_payload, output_dir, compile_pdf=True):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    human_text = render_pseudospin_orbital_human_text(grouped_payload)
    human_tex = render_pseudospin_orbital_human_tex(grouped_payload)
    full_text = render_pseudospin_orbital_full_text(parsed_payload)
    full_tex = render_pseudospin_orbital_full_tex(parsed_payload)

    return {
        "reports": {
            "human_friendly": _write_single_report(
                "human_friendly_report", human_text, human_tex, output_dir, compile_pdf
            ),
            "full_coefficients": _write_single_report(
                "full_coefficients_report", full_text, full_tex, output_dir, compile_pdf
            ),
        }
    }


def write_stage_markdown(summary, docs_dir):
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / f"{date.today().isoformat()}-pseudospin-orbital-report-phase.md"
    path.write_text(summary, encoding="utf-8")
    return path
