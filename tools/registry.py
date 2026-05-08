from tools.cmd_tools import make_folder, find_file, read_file, list_directory, open_folder

TOOL_REGISTRY = {
    "make_folder":    make_folder,
    "find_file":      find_file,
    "read_file":      read_file,
    "list_directory": list_directory,
    "open_folder":    open_folder,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "make_folder",
            "description": "Create a new folder at the given path. Creates all intermediate folders if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Full absolute path of the folder to create."
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
            "description": "Search for a file by name inside a folder. Supports partial names and minor typos.",
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
                        "description": "Maximum number of results to return. Default is 15. Use a lower value like 5 if the search_root is large or results may be numerous."
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read and return the text content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Full absolute path to the file to read."
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Maximum number of characters to read. Defaults to 10000."
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
            "description": "Open a folder in Windows Explorer.",
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