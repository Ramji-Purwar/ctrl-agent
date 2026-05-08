import os
import sys
import subprocess
import logging
from pathlib import Path
from difflib import SequenceMatcher
from config.settings import BASE_DIR

EXCLUDE_DIRS = {"AppData", "venv", ".venv", "__pycache__", "node_modules", ".git", "site-packages"}

FUZZY_THRESHOLD = 0.6

def is_safe_path(path: str) -> bool:
    try:
        resolved = Path(path).resolve()
        base     = Path(BASE_DIR).resolve()
        return resolved.is_relative_to(base)
    except Exception:
        return False

def _safe_check(path: str, operation: str) -> dict | None:
    if not is_safe_path(path):
        logging.warning(f"[CMD][{operation}] Blocked unsafe path: {path}")
        return {"success": False, "error": f"Path '{path}' is outside allowed directory '{BASE_DIR}'"}
    return None

def _fuzzy_match(query: str, filename: str) -> bool:
    query_clean    = query.lower().replace(".", "")
    filename_clean = Path(filename).stem.lower()

    if query_clean in filename_clean:
        return True

    ratio = SequenceMatcher(None, query_clean, filename_clean).ratio()
    return ratio >= FUZZY_THRESHOLD

def find_file(filename: str, search_root: str = BASE_DIR, max_results: int = 15) -> dict:
    if err := _safe_check(search_root, "find_file"): return err
    try:
        matches = []
        for root, dirs, files in os.walk(search_root):

            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for f in files:
                full_path = os.path.join(root, f)
                if _fuzzy_match(filename, f) and is_safe_path(full_path):
                    matches.append(full_path)
                    if len(matches) >= max_results:
                        return {
                            "success": True,
                            "matches": matches,
                            "count": len(matches),
                            "truncated": True,
                            "note": f"Showing first {max_results} results. Narrow your search_root for more specific results."
                        }

        return {"success": True, "matches": matches, "count": len(matches), "truncated": False}
    except Exception as e:
        return {"success": False, "error": str(e)}

def make_folder(path: str) -> dict:
    if err := _safe_check(path, "make_folder"): return err
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        logging.info(f"[CMD][make_folder] Created: {path}")
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def read_file(path: str, max_bytes: int = 10_000) -> dict:
    if err := _safe_check(path, "read_file"): return err
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")[:max_bytes]
        return {"success": True, "content": content, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_directory(path: str = BASE_DIR) -> dict:
    if err := _safe_check(path, "list_directory"): return err
    try:
        items = os.listdir(path)
        return {"success": True, "items": items, "count": len(items)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def open_folder(path: str) -> dict:
    if err := _safe_check(path, "open_folder"): return err
    if sys.platform != "win32":
        return {"success": False, "error": "open_folder is only supported on Windows"}
    try:
        subprocess.run(["explorer", str(Path(path).resolve())], shell=False)
        return {"success": True, "opened": path}
    except Exception as e:
        return {"success": False, "error": str(e)}