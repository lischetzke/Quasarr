import os
import re

# Updated Regex: Excludes 'values' AND 'update'
PATTERN = re.compile(r"\bshared_state\.(?!(values|update)\b)")

# List of functions still in shared_state.py that are valid to call
VALID_SHARED_STATE_FUNCTIONS = {
    "set_state",
    "set_connection_info",
    "set_files",
    "generate_api_key",
    "extract_valid_hostname",
    "connect_to_jd",
    "set_device",
    "set_device_from_config",
    "check_device",
    "connect_device",
    "get_device",
    "get_devices",
    "set_device_settings",
    "update_jdownloader",
    "start_downloads",
    "get_db",
}

# Folders to ignore
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "build",
    "dist",
}

# File extensions to check
VALID_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".java",
    ".c",
    ".cpp",
    ".rb",
    ".go",
    ".rs",
}


def search_directory(start_path="."):
    print(f"Searching for matches of: {PATTERN.pattern}")
    print(
        "Excluding: shared_state.values, shared_state.update and valid shared_state functions"
    )
    print("-" * 60)

    matches_found = 0

    for root, dirs, files in os.walk(start_path):
        # Modify dirs in-place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            if VALID_EXTENSIONS and not file.lower().endswith(tuple(VALID_EXTENSIONS)):
                continue

            file_path = os.path.join(root, file)

            # Skip shared_state.py itself as it defines these functions
            if file == "shared_state.py":
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        # Search for the pattern
                        for match in PATTERN.finditer(line):
                            # Extract the function name being called
                            # The pattern matches 'shared_state.' and then looks ahead
                            # We need to find what follows 'shared_state.'
                            start = match.start()
                            remaining = line[start + len("shared_state.") :]
                            func_match = re.match(r"^(\w+)", remaining)

                            if func_match:
                                func_name = func_match.group(1)
                                if func_name in VALID_SHARED_STATE_FUNCTIONS:
                                    continue

                            clean_line = line.strip()
                            # simple highlight logic for the console
                            highlighted = clean_line.replace(
                                "shared_state.", "\033[91mshared_state.\033[0m"
                            )

                            print(
                                f"\033[96m{file_path}\033[0m : \033[93mLine {i}\033[0m"
                            )
                            print(f"  └── {highlighted}")
                            matches_found += 1
            except Exception:
                continue

    print("-" * 60)
    print(f"Search complete. Total matches found: {matches_found}")


if __name__ == "__main__":
    search_directory()
