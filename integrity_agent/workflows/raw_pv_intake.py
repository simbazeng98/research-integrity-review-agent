from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from integrity_agent.core.path_display import display_path
import re

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="Scan and intake raw measurements package for PV analysis.")
    parser.add_argument("package_dir", help="Path to raw measurements package directory.")
    parser.add_argument("-o", "--output-dir", default="outputs/raw_pv", help="Directory to write output manifest.")
    return parser.parse_args(args)

def guess_device_id_from_filename(filename: str) -> str | None:
    stem = Path(filename).stem
    parts = re.split(r"[-_]", stem)
    for part in parts:
        if "dev" in part.lower():
            return part
    return parts[0] if parts else stem

def run_raw_pv_intake(package_dir: str, output_dir: str = "outputs/raw_pv") -> tuple[str, str]:
    pack_path = Path(package_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    manifest_file = out_path / "raw_pv_manifest.jsonl"
    summary_file = out_path / "raw_pv_intake_summary.md"

    manifest_items = []
    warnings_list = []

    subfolders = {
        "jv": "jv_curve",
        "eqe": "eqe_spectrum",
        "excel": "excel_workbook",
        "reported": "reported_metrics",
        "reference": "reference_spectrum"
    }

    # Scan the package directory
    item_counter = 1
    
    # Check if package_dir exists
    if not pack_path.exists():
        msg = f"Package directory '{package_dir}' does not exist."
        warnings_list.append(msg)
        # Write empty manifest and summary
        manifest_file.write_text("", encoding="utf-8")
        summary_file.write_text(f"# Raw PV Intake Summary\n\n**Warning**: {msg}\n", encoding="utf-8")
        return str(manifest_file), str(summary_file)

    # We will search both directly in subfolders and recursively
    for folder_name, input_type in subfolders.items():
        folder_path = pack_path / folder_name
        if not folder_path.exists():
            warnings_list.append(f"Directory '{folder_name}' not found under '{package_dir}'.")
            continue

        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(pack_path)
                
                # Guess device ID
                dev_guess = guess_device_id_from_filename(file)
                
                # File warnings
                file_warnings = []
                # Check for xlsm under excel
                if input_type == "excel_workbook" and file_path.suffix.lower() == ".xlsm":
                    file_warnings.append("Macro-enabled workbook (.xlsm) is not supported for formula audit safety.")

                item = {
                    "item_id": f"raw-item-{item_counter:03d}",
                    "source_file": file,
                    "relative_path": str(rel_path).replace("\\", "/"),
                    "input_type": input_type,
                    "device_id_guess": dev_guess,
                    "warnings": file_warnings
                }
                manifest_items.append(item)
                item_counter += 1

    # Also scan root folder for any unknown files
    for root, _, files in os.walk(pack_path):
        for file in files:
            file_path = Path(root) / file
            # Check if this file is already in manifest by relative path
            rel_path = file_path.relative_to(pack_path)
            rel_str = str(rel_path).replace("\\", "/")
            
            # Skip if it is inside one of the subfolders
            parts = rel_path.parts
            if parts and parts[0] in subfolders:
                continue
                
            # It's an unknown file
            item = {
                "item_id": f"raw-item-{item_counter:03d}",
                "source_file": file,
                "relative_path": rel_str,
                "input_type": "unknown",
                "device_id_guess": guess_device_id_from_filename(file),
                "warnings": ["unknown input directory or format"]
            }
            manifest_items.append(item)
            item_counter += 1

    # Write manifest JSONL
    with manifest_file.open("w", encoding="utf-8") as f:
        for item in manifest_items:
            f.write(json.dumps(item) + "\n")

    # Generate summary MD
    summary_lines = [
        "# Raw PV Intake Summary",
        "",
        f"- **Package Source**: `{package_dir}`",
        f"- **Total items discovered**: {len(manifest_items)}",
    ]
    
    # Counts by type
    counts = {}
    for item in manifest_items:
        t = item["input_type"]
        counts[t] = counts.get(t, 0) + 1
        
    for k, v in counts.items():
        summary_lines.append(f"  - `{k}`: {v} files")
        
    if warnings_list:
        summary_lines.append("")
        summary_lines.append("## Intake Warnings")
        for w in warnings_list:
            summary_lines.append(f"- {w}")

    summary_file.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    
    print(f"Wrote raw PV manifest: {display_path(manifest_file)}")
    print(f"Wrote raw PV intake summary: {display_path(summary_file)}")
    
    return str(manifest_file), str(summary_file)

def main(args=None):
    parsed = parse_args(args)
    run_raw_pv_intake(parsed.package_dir, parsed.output_dir)

if __name__ == "__main__":
    main()
