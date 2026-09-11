#!/usr/bin/env python3
"""Safe archiver utility for legacy Knowledge files.

Default mode is DRY-RUN (no files are moved or deleted).
To actually perform the move: python scripts/archive_knowledge_legacy.py --execute
"""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "Knowledge"
ARCHIVE_DIR = ROOT / "Knowledge_archive_legacy"

# The 16 candidate files identified in implementation_plan.md
CANDIDATE_FILES = [
    # Monoliti clima superati (477 MB)
    "climatizzatori_compatibilita_master.json",
    "ac_outdoor_combinations.json",
    "climatizzatori_combinazioni_provenance.json",
    # Fogli Excel manuali non usati dal codice (20 MB)
    "CODICI_PT_FINALE.xlsx",
    "VERIFICA_CLIMA_backup_original.xlsx",
    "VERIFICA_CLIMA_arricchito.xlsx",
    "VERIFICA_CLIMA.xlsx",
    "Tutto.xlsx",
    "Caldaie_Condensazione_COMPILATO_ACCESSORI_DEFANGATORE_10016877.xlsx",
    # Documenti duplicati (0.03 MB)
    "SEARCH_ENGINE_AND_VALIDATION.md",
    "AGENTS.md",
    # File intermedi storici (1.37 MB)
    "catalog_pdf_extracted_specs.json",
    "catalog_extracted_family_candidates.json",
    "catalog_raw_page_structure.json",
    "all_catalog_families_raw.json",
    "catalog_pages_full_scan.txt",
]


def main():
    parser = argparse.ArgumentParser(description="Archive legacy Knowledge files safely.")
    parser.add_argument("--execute", action="store_true", help="Perform the actual move (default is dry-run)")
    args = parser.parse_args()

    print("=== KNOWLEDGE LEGACY ARCHIVER ===")
    print(f"Mode: {'EXECUTION (MOVING FILES)' if args.execute else 'DRY-RUN (NO FILES TOUCHED)'}")
    print(f"Source directory:  {KNOWLEDGE_DIR}")
    print(f"Archive directory: {ARCHIVE_DIR}\n")

    found_files = []
    total_bytes = 0

    for name in CANDIDATE_FILES:
        file_path = KNOWLEDGE_DIR / name
        if file_path.exists():
            size = file_path.stat().st_size
            found_files.append((file_path, size))
            total_bytes += size
            print(f"  [FOUND] {name:45} ({round(size / (1024*1024), 2):7.2f} MB)")
        else:
            print(f"  [MISSING/ALREADY ARCHIVED] {name}")

    print(f"\nTotal candidate files found: {len(found_files)} / {len(CANDIDATE_FILES)}")
    print(f"Total space to reclaim:      {round(total_bytes / (1024*1024), 2)} MB ({round(total_bytes / (1024*1024*1024), 2)} GB)\n")

    if not args.execute:
        print("[INFO] DRY-RUN COMPLETE. 0 files were moved or deleted.")
        print("[INFO] To execute the actual move, run: python scripts/archive_knowledge_legacy.py --execute")
        return 0

    # If execute is requested:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    moved_count = 0
    for file_path, size in found_files:
        dest_path = ARCHIVE_DIR / file_path.name
        print(f"Moving {file_path.name} -> {dest_path}...")
        shutil.move(str(file_path), str(dest_path))
        moved_count += 1

    print(f"\n[SUCCESS] Successfully moved {moved_count} files to {ARCHIVE_DIR}.")
    print("[SUCCESS] Knowledge directory cleaned. Space reclaimed in Knowledge: "
          f"{round(total_bytes / (1024*1024), 2)} MB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
