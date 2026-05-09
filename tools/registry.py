from tools.cmd_tools import make_folder, find_file, find_folder, read_file, list_directory, open_folder

TOOL_REGISTRY = {
    "make_folder":    make_folder,
    "find_file":      find_file,
    "find_folder":    find_folder,
    "read_file":      read_file,
    "list_directory": list_directory,
    "open_folder":    open_folder,
}

TOOL_SCHEMAS = [
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
]