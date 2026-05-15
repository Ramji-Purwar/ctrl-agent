import os
import subprocess
import logging
import tempfile
from pathlib import Path
from config.settings import BASE_DIR, GIT_USERNAME, GIT_TOKEN

def _is_safe_repo(repo_path: str) -> bool:
    try:
        resolved = Path(repo_path).resolve()
        base     = Path(BASE_DIR).resolve()
        resolved.relative_to(base)
        return True
    except ValueError:
        return False
    except Exception:
        return False


def _run_git(args: list, cwd: str) -> tuple:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip() or result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Git command timed out after 30s."
    except FileNotFoundError:
        return False, "Git is not installed or not on PATH."
    except Exception as e:
        return False, str(e)


def _run_git_with_auth(args: list, cwd: str) -> tuple:
    if not GIT_USERNAME or not GIT_TOKEN:
        return _run_git(args, cwd)

    askpass_content = (
        "@echo off\n"
        "echo %1 | find /i \"Username\" >nul\n"
        "if not errorlevel 1 (\n"
        f"    echo {GIT_USERNAME}\n"
        "    exit /b\n"
        ")\n"
        f"echo {GIT_TOKEN}\n"
        "exit /b\n"
    )

    tmp_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".bat", delete=False, encoding="utf-8"
        )
        tmp.write(askpass_content)
        tmp.flush()
        tmp.close()
        tmp_path = tmp.name

        env = os.environ.copy()
        env["GIT_ASKPASS"]         = tmp_path
        env["GIT_TERMINAL_PROMPT"] = "0"

        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
            env=env,
        )

        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            raw_err  = result.stderr.strip() or result.stdout.strip()
            safe_err = raw_err.replace(GIT_TOKEN, "***").replace(GIT_USERNAME, "***")
            return False, safe_err

    except subprocess.TimeoutExpired:
        return False, "Git command timed out after 30s."
    except Exception as e:
        safe_msg = str(e).replace(GIT_TOKEN or "", "***").replace(GIT_USERNAME or "", "***")
        return False, safe_msg
    finally:
        if tmp_path and Path(tmp_path).exists():
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _find_repo(repo_name: str) -> str | None:
    base = Path(BASE_DIR).resolve()
    name = repo_name.lower()

    EXCLUDE = {
        "AppData", "venv", ".venv", "__pycache__", "node_modules",
        ".git", "site-packages", ".cache",
    }

    def _walk(root: Path, depth: int):
        if depth > 4:
            return
        try:
            for child in root.iterdir():
                if not child.is_dir() or child.name in EXCLUDE:
                    continue
                if child.name.lower() == name and (child / ".git").exists():
                    yield child
                else:
                    yield from _walk(child, depth + 1)
        except PermissionError:
            pass

    for match in _walk(base, 0):
        return str(match)
    return None


def _resolve_repo(repo_path: str) -> tuple:
    p = Path(repo_path).resolve()
    if p.exists() and (p / ".git").exists():
        if _is_safe_repo(str(p)):
            return str(p), None
        return None, "Repo is outside the allowed directory."

    found = _find_repo(repo_path)
    if found:
        if _is_safe_repo(found):
            return found, None
        return None, "Repo is outside the allowed directory."

    return None, f"No git repository found for '{repo_path}' inside BASE_DIR."



def git_status(repo_path: str) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    ok, branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], resolved)
    if not ok:
        branch = "unknown"

    ok, output = _run_git(["status", "--porcelain"], resolved)
    if not ok:
        return {"success": False, "error": output}

    staged, unstaged, untracked = [], [], []
    for line in output.splitlines():
        if len(line) < 2:
            continue
        x, y, filename = line[0], line[1], line[3:]
        if x not in (" ", "?"):
            staged.append(filename)
        if y != " " and y != "?":
            unstaged.append(filename)
        if line[:2] == "??":
            untracked.append(filename)

    logging.info(f"[Git][status] Branch: {branch} | Repo: {resolved}")
    return {
        "success":   True,
        "repo":      resolved,
        "branch":    branch,
        "staged":    staged,
        "unstaged":  unstaged,
        "untracked": untracked,
        "clean":     not (staged or unstaged or untracked),
    }


def git_log(repo_path: str, limit: int = 10) -> dict:

    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    limit = max(1, min(limit, 50))
    fmt   = "%H|%an|%ar|%s"
    ok, output = _run_git(
        ["log", f"--pretty=format:{fmt}", f"-{limit}"],
        resolved
    )
    if not ok:
        return {"success": False, "error": output}

    commits = []
    for line in output.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "hash":    parts[0][:8],
                "author":  parts[1],
                "date":    parts[2],
                "message": parts[3],
            })

    logging.info(f"[Git][log] Commits: {len(commits)} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "commits": commits}


def git_diff(repo_path: str, staged: bool = False) -> dict:

    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    args = ["diff"] + (["--staged"] if staged else [])
    ok, output = _run_git(args, resolved)
    if not ok:
        return {"success": False, "error": output}

    truncated = False
    if len(output) > 8000:
        output, truncated = output[:8000], True

    logging.info(f"[Git][diff] Staged: {staged} | Truncated: {truncated} | Repo: {resolved}")
    return {
        "success":   True,
        "repo":      resolved,
        "staged":    staged,
        "diff":      output or "(no changes)",
        "truncated": truncated,
    }


def git_add(repo_path: str, files: list = None) -> dict:

    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    args = ["add"] + (files if files else ["-A"])
    ok, output = _run_git(args, resolved)
    if not ok:
        return {"success": False, "error": output}

    logging.info(f"[Git][add] Files: {files or 'all'} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "staged": files or "all"}


def git_commit(repo_path: str, message: str) -> dict:

    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    if not message or not message.strip():
        return {"success": False, "error": "Commit message cannot be empty."}

    ok, output = _run_git(["commit", "-m", message.strip()], resolved)
    if not ok:
        return {"success": False, "error": output}

    logging.info(f"[Git][commit] Repo: {resolved}")
    return {"success": True, "repo": resolved, "output": output}


def git_push_dry_run(repo_path: str, remote: str = "origin", branch: str = "") -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    if not branch:
        ok, branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], resolved)
        if not ok:
            return {"success": False, "error": f"Could not determine branch: {branch}"}

    ok, output = _run_git_with_auth(["push", "--dry-run", remote, branch], resolved)

    logging.info(f"[Git][push_dry_run] Remote: {remote} | Branch: {branch} | Repo: {resolved}")
    return {
        "success": True,
        "repo":    resolved,
        "remote":  remote,
        "branch":  branch,
        "preview": output or "(nothing to push)",
        "note":    "Dry run — nothing was pushed.",
    }


def git_push(repo_path: str, remote: str = "origin", branch: str = "",
             confirmed: bool = False) -> dict:
    
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    if not branch:
        ok, branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], resolved)
        if not ok:
            branch = "current branch"

    if not confirmed:
        return {
            "success":               False,
            "error":                 "Push requires explicit confirmation.",
            "requires_confirmation": True,
            "message": (
                f"About to push '{branch}' to '{remote}'. "
                f"Reply with confirmed=True to proceed."
            ),
        }

    ok, output = _run_git_with_auth(["push", remote, branch], resolved)
    if not ok:
        return {"success": False, "error": output}

    logging.info(f"[Git][push] Remote: {remote} | Branch: {branch} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "remote": remote, "branch": branch, "output": output}


def git_pull(repo_path: str, remote: str = "origin", branch: str = "") -> dict:
    
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    if not branch:
        ok, branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], resolved)
        if not ok:
            return {"success": False, "error": f"Could not determine branch: {branch}"}

    ok, output = _run_git_with_auth(["pull", remote, branch], resolved)
    if not ok:
        return {"success": False, "error": output}

    logging.info(f"[Git][pull] Remote: {remote} | Branch: {branch} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "remote": remote, "branch": branch, "output": output}


def git_branches(repo_path: str) -> dict:
    
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}

    ok, output = _run_git(["branch"], resolved)
    if not ok:
        return {"success": False, "error": output}

    branches, current = [], ""
    for line in output.splitlines():
        name = line.strip().lstrip("* ").strip()
        if line.strip().startswith("*"):
            current = name
        branches.append(name)

    logging.info(f"[Git][branches] Count: {len(branches)} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "branches": branches, "current": current}