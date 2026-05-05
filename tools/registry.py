from tools.cmd_tools import make_folder, find_file, read_file, list_directory, open_folder
from google.genai import types

TOOL_REGISTRY = {
    "make_folder":    make_folder,
    "find_file":      find_file,
    "read_file":      read_file,
    "list_directory": list_directory,
    "open_folder":    open_folder,
}


GEMINI_TOOL_SCHEMAS = types.Tool(
    function_declarations=[

        types.FunctionDeclaration(
            name="make_folder",
            description="Create a new folder at the given path. Creates all intermediate folders if needed.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(
                        type="STRING",
                        description="Full absolute path of the folder to create. Must be inside C:\\Users\\r4849."
                    ),
                },
                required=["path"],
            ),
        ),

        types.FunctionDeclaration(
            name="find_file",
            description="Search for a file by name inside a folder. Supports partial names and minor typos. Skips AppData, venv, and other noisy folders.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "filename": types.Schema(
                        type="STRING",
                        description="Name or partial name of the file to search for. Extension is optional."
                    ),
                    "search_root": types.Schema(
                        type="STRING",
                        description="Folder to search inside. Defaults to C:\\Users\\r4849 if not provided."
                    ),
                },
                required=["filename"],
            ),
        ),

        types.FunctionDeclaration(
            name="read_file",
            description="Read and return the text content of a file.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(
                        type="STRING",
                        description="Full absolute path to the file to read."
                    ),
                    "max_bytes": types.Schema(
                        type="INTEGER",
                        description="Maximum number of characters to read. Defaults to 10000."
                    ),
                },
                required=["path"],
            ),
        ),

        types.FunctionDeclaration(
            name="list_directory",
            description="List all files and folders inside a directory.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(
                        type="STRING",
                        description="Full absolute path of the folder to list. Defaults to C:\\Users\\r4849."
                    ),
                },
                required=[],
            ),
        ),

        types.FunctionDeclaration(
            name="open_folder",
            description="Open a folder in Windows Explorer.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(
                        type="STRING",
                        description="Full absolute path of the folder to open in Explorer."
                    ),
                },
                required=["path"],
            ),
        ),

    ]
)