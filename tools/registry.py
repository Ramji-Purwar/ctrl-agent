from tools.cmd_tools import make_folder, find_file, find_folder, read_file, list_directory, open_folder
from tools.git_tools import (
    git_status, git_log, git_diff, git_add,
    git_commit, git_push_dry_run, git_push,
    git_pull, git_branches, git_clone, git_init,
)

TOOL_REGISTRY = {
    # File system
    "make_folder":    make_folder,
    "find_file":      find_file,
    "find_folder":    find_folder,
    "read_file":      read_file,
    "list_directory": list_directory,
    "open_folder":    open_folder,
    # Git
    "git_status":       git_status,
    "git_log":          git_log,
    "git_diff":         git_diff,
    "git_add":          git_add,
    "git_commit":       git_commit,
    "git_push_dry_run": git_push_dry_run,
    "git_push":         git_push,
    "git_pull":         git_pull,
    "git_branches":     git_branches,
    "git_clone":        git_clone,
    "git_init":         git_init,
}

TOOL_SCHEMAS = [
    # -----------------------------------------------------------------------
    # File system tools (unchanged)
    # -----------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "make_folder",
            "description": (
                "Create a new folder inside an existing parent folder. "
                "IMPORTANT: If the user says 'make folder X inside Y', you MUST first call "
                "find_folder to locate Y and get its full path. Never guess a parent path. "
                "Only call make_folder once you have the verified full path of the parent. "
                "Never place another tool call inside this tool's arguments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Full absolute path of the folder to create, including its parent."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": (
                "Search for a file by name and return its location(s) only. "
                "Returns file paths — does NOT read or show file contents. "
                "Use this when the user asks where a file is, or needs its path. "
                "Do NOT call read_file after this unless the user explicitly asks to read or open the file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name or partial name of the file to search for."
                    },
                    "search_root": {
                        "type": "string",
                        "description": "Folder to search inside. Defaults to BASE_DIR if not provided."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return. Default 15."
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_folder",
            "description": (
                "Search for a folder by name and return its full path(s). "
                "Use this BEFORE open_folder or make_folder whenever the user gives a folder name "
                "but not a full path. Supports partial names and fuzzy matching. "
                "Always search broadly — use BASE_DIR as search_root unless user specifies a location."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "foldername": {
                        "type": "string",
                        "description": "Name or partial name of the folder to find."
                    },
                    "search_root": {
                        "type": "string",
                        "description": "Root folder to search inside. Defaults to BASE_DIR."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return. Default 10."
                    }
                },
                "required": ["foldername"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read and return the text content of a file. "
                "Only call this when the user explicitly asks to read, view, show, or print a file's contents. "
                "Do NOT call this automatically after find_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Full absolute path to the file."
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Max characters to read. Defaults to 10000."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List all files and folders inside a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Full absolute path of the folder to list."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_folder",
            "description": (
                "Open a folder in Windows Explorer. "
                "IMPORTANT: You must have a verified full path before calling this. "
                "If the user gives only a folder name (not a full path), call find_folder first "
                "to get the real path, then call open_folder with that path. "
                "Never place another tool call inside this tool's arguments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Full absolute path of the folder to open."
                    }
                },
                "required": ["path"]
            }
        }
    },

    # -----------------------------------------------------------------------
    # Git tools
    # -----------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": (
                "Show the current status of a git repository: branch name, staged files, "
                "unstaged changes, and untracked files. "
                "Use this first when the user asks about a repo's state or before any commit/push."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": (
                            "Full path to the repo, or just the repo folder name. "
                            "If only a name is given, the tool will search for it inside BASE_DIR."
                        )
                    }
                },
                "required": ["repo_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Return the recent commit history of a repo (hash, author, date, message).",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Full path or name of the repo."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of commits to return. Default 10, max 50."
                    }
                },
                "required": ["repo_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": (
                "Show file changes in a repo. "
                "By default shows unstaged changes. Set staged=true to see staged (indexed) changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Full path or name of the repo."
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "If true, shows staged changes. If false (default), shows unstaged changes."
                    }
                },
                "required": ["repo_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": (
                "Stage files for commit. "
                "If no files are specified, stages all changes (equivalent to git add -A). "
                "Call git_status first to see what will be staged."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Full path or name of the repo."
                    },
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to stage. Omit to stage everything."
                    }
                },
                "required": ["repo_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": (
                "Commit staged changes with a message. "
                "IMPORTANT: Always call git_status first to confirm there are staged changes. "
                "Never commit without the user providing or approving the commit message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Full path or name of the repo."
                    },
                    "message": {
                        "type": "string",
                        "description": "Commit message. Must not be empty."
                    }
                },
                "required": ["repo_path", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_push_dry_run",
            "description": (
                "Simulate a push to show what would be sent — does NOT actually push anything. "
                "Always call this before git_push so the user can see what will happen. "
                "Safe to call at any time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Full path or name of the repo."
                    },
                    "remote": {
                        "type": "string",
                        "description": "Remote name. Defaults to 'origin'."
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch to push. Defaults to current branch."
                    }
                },
                "required": ["repo_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": (
                "Push commits to a remote repository. "
                "IMPORTANT RULES: "
                "1. Always call git_push_dry_run first and show the user the preview. "
                "2. Only call git_push with confirmed=true after the user explicitly says to proceed. "
                "3. Never push without user confirmation — confirmed=false will always be rejected."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Full path or name of the repo."
                    },
                    "remote": {
                        "type": "string",
                        "description": "Remote name. Defaults to 'origin'."
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch to push. Defaults to current branch."
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": (
                            "Must be true for the push to execute. "
                            "Only set true after the user has explicitly confirmed they want to push."
                        )
                    }
                },
                "required": ["repo_path", "confirmed"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_pull",
            "description": "Pull latest changes from a remote branch into the local repo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Full path or name of the repo."
                    },
                    "remote": {
                        "type": "string",
                        "description": "Remote name. Defaults to 'origin'."
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch to pull. Defaults to current branch."
                    }
                },
                "required": ["repo_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_branches",
            "description": "List all local branches in a repo and show which one is currently checked out.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Full path or name of the repo."
                    }
                },
                "required": ["repo_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_clone",
            "description": "Clone a remote git repository to a specified local path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the remote git repository to clone."
                    },
                    "dest_path": {
                        "type": "string",
                        "description": "Local path where the repository should be cloned."
                    }
                },
                "required": ["url", "dest_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_init",
            "description": "Initialize a new git repository in the specified local path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Local path where the new git repository should be initialized."
                    }
                },
                "required": ["repo_path"]
            }
        }
    }
]