import os
import subprocess
import logging
import tempfile
from pathlib import Path
from config.settings import BASE_DIR, GIT_USERNAME, GIT_TOKEN
from tools.cmd_tools import find_folder, is_safe_path, _safe_check


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
    result = find_folder(repo_name, search_root=BASE_DIR, max_results=10)
    if not result["success"]:
        return None
    for path in result["matches"]:
        if (Path(path) / ".git").exists():
            return path
    return None


def _resolve_repo(repo_path: str) -> tuple:
    p = Path(repo_path).resolve()
    if p.exists() and (p / ".git").exists():
        if is_safe_path(str(p)):
            return str(p), None
        return None, "Repo is outside the allowed directory."

    found = _find_repo(repo_path)
    if found:
        if is_safe_path(found):
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


def git_clone(url: str, dest_path: str) -> dict:
    if not url or not url.strip():
        return {"success": False, "error": "URL cannot be empty."}

    if not dest_path or not dest_path.strip():
        return {"success": False, "error": "Destination path cannot be empty."}

    dest_path = str(Path(dest_path).resolve())

    if err := _safe_check(dest_path, "git_clone"):
        return err

    if Path(dest_path).exists():
        return {"success": False, "error": f"Destination already exists: {dest_path}"}

    ok, output = _run_git_with_auth(["clone", url, dest_path], cwd=BASE_DIR)
    if not ok:
        return {"success": False, "error": output}

    logging.info(f"[Git][clone] URL: {url} | Dest: {dest_path}")
    return {"success": True, "url": url, "dest": dest_path, "output": output}


def git_init(repo_path: str) -> dict:
    if not repo_path or not repo_path.strip():
        return {"success": False, "error": "Repo path cannot be empty."}

    repo_path = str(Path(repo_path).resolve())

    if err := _safe_check(repo_path, "git_init"):
        return err

    Path(repo_path).mkdir(parents=True, exist_ok=True)

    ok, output = _run_git(["init"], repo_path)
    if not ok:
        return {"success": False, "error": output}

    logging.info(f"[Git][init] Repo: {repo_path}")
    return {"success": True, "repo": repo_path, "output": output}


def git_checkout(repo_path: str, branch: str, create: bool = False) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    if not branch or not branch.strip():
        return {"success": False, "error": "Branch name cannot be empty."}
    
    args = ["checkout"] + (["-b"] if create else []) + [branch.strip()]
    ok, output = _run_git(args, resolved)
    
    if not ok:
        return {"success": False, "error": output}
    
    action = "created and switched to" if create else "switched to"
    logging.info(f"[Git][checkout] {action} branch '{branch}' | Repo: {resolved}")
    return {"success": True, "repo": resolved, "branch": branch, "action": action, "output": output}


def git_merge(repo_path: str, branch: str) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    if not branch or not branch.strip():
        return {"success": False, "error": "Branch name cannot be empty."}
    
    ok, output = _run_git(["merge", branch.strip()], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    logging.info(f"[Git][merge] Merged branch '{branch}' into current branch | Repo: {resolved}")
    return {"success": True, "repo": resolved, "merged_branch": branch, "output": output}


def git_reset(repo_path: str, mode: str = "soft", steps: int = 1) -> dict:
    """Undo the last N commits. mode='soft' keeps changes staged, 'hard' discards them."""
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    if mode not in {'soft', 'hard'}:
        return {"success": False, "error": "Invalid reset mode. Use 'soft' or 'hard'."}
    
    steps = max(1, steps)
    ref = f"HEAD~{steps}"

    ok, output = _run_git(["reset", ref, f"--{mode}"], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    logging.info(f"[Git][reset] Mode: {mode} | Steps: {steps} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "mode": mode, "ref": ref, "steps": steps, "output": output}


def git_restore(repo_path: str, files: list, staged: bool = False) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err: 
        return {"success": False, "error": err}
    
    if not files:
        return {"success": False, "error": "No files specified for restore."}
    
    args = ["restore"] + (["--staged"] if staged else []) + files
    ok, output = _run_git(args, resolved)
    if not ok:
        return {"success": False, "error": output}
    
    action = "Unstaged" if staged else "Restored"
    logging.info(f"[Git][restore] Files : {files} | Staged : {staged} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "files": files, "action": action, "output": output}


def git_stash(repo_path: str, pop: bool = False) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    args = ["stash"] + (["pop"] if pop else [])
    ok, output = _run_git(args, resolved)
    if not ok:
        return {"success": False, "error": output}
    
    action = "Popped" if pop else "Stashed"
    logging.info(f"[Git][stash] Action: {action} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "action": action, "output": output}


def git_commit_amend(repo_path: str, message: str) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    if not message or not message.strip():
        return {"success": False, "error": "Commit message cannot be empty."}
    
    ok, output = _run_git(["commit", "--amend", "-m", message.strip()], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    logging.info(f"[Git][commit_amend] Repo: {resolved}")
    return {"success": True, "repo": resolved, "output": output}


def git_fetch(repo_path: str, remote: str = "origin") -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    ok, output = _run_git_with_auth(["fetch", remote], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    logging.info(f"[Git][fetch] Remote: {remote} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "remote": remote, "output": output or "(already up to date)"}


def git_remote_list(repo_path: str) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    ok, output = _run_git(["remote", "-v"], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    remotes = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            name, url = parts[0], parts[1]
            remotes[name] = url

    logging.info(f"[Git][remote_list] Count: {len(remotes)} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "remotes": remotes}


def git_remote_add(repo_path: str, name: str, url: str) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    if not name or not name.strip():
        return {"success": False, "error": "Remote name cannot be empty."}
    if not url or not url.strip():
        return {"success": False, "error": "Remote URL cannot be empty."}
    
    ok, output = _run_git(["remote", "add", name.strip(), url.strip()], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    logging.info(f"[Git][remote_add] Name: {name} | URL: {url} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "name": name.strip(), "url": url.strip(), "output": output}


def git_cherry_pick(repo_path: str, commit_hash: str) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    if not commit_hash or not commit_hash.strip():
        return {"success": False, "error": "Commit hash cannot be empty."}
    
    ok, output = _run_git(["cherry-pick", commit_hash.strip()], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    logging.info(f"[Git][cherry_pick] Hash: {commit_hash} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "commit_hash": commit_hash.strip(), "output": output}


def git_show(repo_path: str, commit_hash: str) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    if not commit_hash or not commit_hash.strip():
        return {"success": False, "error": "Commit hash cannot be empty."}
    
    ok, output = _run_git(["show", commit_hash.strip()], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    truncated = False
    if len(output) > 8000:
        output, truncated = output[:8000], True

    logging.info(f"[Git][show] Hash: {commit_hash} | Truncated: {truncated} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "commit_hash": commit_hash.strip(), "output": output, "truncated": truncated}


def git_stash_list(repo_path: str) -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
        
    ok, output = _run_git(["stash", "list"], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    stashes = []
    for line in output.splitlines():
        parts = line.split(":", 2)
        if len(parts) >= 3:
            stashes.append({
                "id": parts[0].strip(),
                "branch": parts[1].strip(),
                "message": parts[2].strip(),
            })
        elif line.strip():
            stashes.append({"id": line.strip(), "branch": "", "message": ""})

    logging.info(f"[Git][stash_list] Count: {len(stashes)} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "stashes": stashes}


def git_stash_drop(repo_path: str, ref: str = "stash@{0}") -> dict:
    resolved, err = _resolve_repo(repo_path)
    if err:
        return {"success": False, "error": err}
    
    ok, output = _run_git(["stash", "drop", ref.strip()], resolved)
    if not ok:
        return {"success": False, "error": output}
    
    logging.info(f"[Git][stash_drop] Ref: {ref} | Repo: {resolved}")
    return {"success": True, "repo": resolved, "dropped": ref.strip(), "output": output}
