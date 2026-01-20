"""Common utility functions for file operations and parsing.

This module provides reusable helper functions for file reading, parsing,
and error handling that can be used across different tool modules.
"""

from __future__ import annotations

import json
import logging
import tomllib
import xml.etree.ElementTree as ET
import yaml
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# FILE EXISTENCE AND READING
# ============================================================================


def check_file_exists(repo_path: str, filename: str) -> tuple[bool, Path]:
    """Check if a file exists in the repository root.

    Args:
        repo_path: Absolute path to repository root
        filename: Name of file to check

    Returns:
        Tuple of (exists: bool, path: Path)

    Example:
        >>> exists, path = check_file_exists("/repo", "config.json")
        >>> if exists:
        ...     print(f"Found at {path}")
    """
    file_path = Path(repo_path) / filename
    return file_path.exists(), file_path


def read_file(file_path: str | Path, encoding: str = "utf-8") -> str | None:
    """Read a text file and return its contents.

    Args:
        file_path: Path to the file
        encoding: File encoding (default: utf-8)

    Returns:
        File contents as string, or None if reading failed

    Example:
        >>> content = read_file("/path/to/file.txt")
        >>> if content:
        ...     print(content)
    """
    try:
        path = Path(file_path)
        return path.read_text(encoding=encoding)
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return None


def read_file_bytes(file_path: str | Path) -> bytes | None:
    """Read a binary file and return its contents.

    Args:
        file_path: Path to the file

    Returns:
        File contents as bytes, or None if reading failed

    Example:
        >>> content = read_file_bytes("/path/to/file.bin")
        >>> if content:
        ...     print(f"Read {len(content)} bytes")
    """
    try:
        path = Path(file_path)
        return path.read_bytes()
    except Exception as e:
        logger.error(f"Error reading binary file {file_path}: {str(e)}")
        return None


def write_file(file_path: str | Path, content: str, encoding: str = "utf-8") -> bool:
    """Write content to a text file.

    Args:
        file_path: Path to the file
        content: Content to write
        encoding: File encoding (default: utf-8)

    Returns:
        True if write succeeded, False otherwise

    Example:
        >>> success = write_file("/path/to/file.txt", "Hello World")
        >>> if success:
        ...     print("File written successfully")
    """
    try:
        path = Path(file_path)
        path.write_text(content, encoding=encoding)
        return True
    except Exception as e:
        logger.error(f"Error writing file {file_path}: {str(e)}")
        return False


def write_file_bytes(file_path: str | Path, content: bytes) -> bool:
    """Write content to a binary file.

    Args:
        file_path: Path to the file
        content: Binary content to write

    Returns:
        True if write succeeded, False otherwise

    Example:
        >>> success = write_file_bytes("/path/to/file.bin", b"data")
        >>> if success:
        ...     print("Binary file written successfully")
    """
    try:
        path = Path(file_path)
        path.write_bytes(content)
        return True
    except Exception as e:
        logger.error(f"Error writing binary file {file_path}: {str(e)}")
        return False


# ============================================================================
# JSON PARSING
# ============================================================================


def parse_json_file(file_path: str | Path) -> dict | None:
    """Parse a JSON file with error handling.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data as dict, or None if parsing failed

    Example:
        >>> data = parse_json_file("/path/to/config.json")
        >>> if data:
        ...     print(data["version"])
    """
    try:
        with open(file_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON file {file_path}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error reading JSON file {file_path}: {str(e)}")
        return None


def parse_json_string(json_string: str) -> dict | list | None:
    """Parse a JSON string with error handling.

    Args:
        json_string: JSON string to parse

    Returns:
        Parsed JSON data, or None if parsing failed

    Example:
        >>> data = parse_json_string('{"key": "value"}')
        >>> if data:
        ...     print(data["key"])
    """
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON string: {str(e)}")
        return None


def write_json_file(file_path: str | Path, data: dict | list, indent: int = 2) -> bool:
    """Write data to a JSON file with pretty formatting.

    Args:
        file_path: Path to JSON file
        data: Data to write (dict or list)
        indent: Indentation level (default: 2)

    Returns:
        True if write succeeded, False otherwise

    Example:
        >>> data = {"name": "project", "version": "1.0"}
        >>> success = write_json_file("/path/to/config.json", data)
    """
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=indent)
        return True
    except Exception as e:
        logger.error(f"Error writing JSON file {file_path}: {str(e)}")
        return False


# ============================================================================
# TOML PARSING
# ============================================================================


def parse_toml_file(file_path: str | Path) -> dict | None:
    """Parse a TOML file with error handling.

    Args:
        file_path: Path to TOML file

    Returns:
        Parsed TOML data as dict, or None if parsing failed

    Example:
        >>> data = parse_toml_file("/path/to/pyproject.toml")
        >>> if data:
        ...     print(data["project"]["name"])
    """
    try:
        with open(file_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        logger.error(f"Error parsing TOML file {file_path}: {str(e)}")
        return None


# ============================================================================
# YAML PARSING
# ============================================================================


def parse_yaml_file(file_path: str | Path) -> dict | None:
    """Parse a YAML file with error handling.

    Args:
        file_path: Path to YAML file

    Returns:
        Parsed YAML data as dict, or None if parsing failed

    Example:
        >>> data = parse_yaml_file("/path/to/config.yml")
        >>> if data:
        ...     print(data["version"])
    """
    try:
        with open(file_path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error parsing YAML file {file_path}: {str(e)}")
        return None


def parse_yaml_string(yaml_string: str) -> dict | None:
    """Parse a YAML string with error handling.

    Args:
        yaml_string: YAML string to parse

    Returns:
        Parsed YAML data as dict, or None if parsing failed

    Example:
        >>> data = parse_yaml_string("version: 1.0\\nname: project")
        >>> if data:
        ...     print(data["name"])
    """
    try:
        return yaml.safe_load(yaml_string)
    except Exception as e:
        logger.error(f"Error parsing YAML string: {str(e)}")
        return None


def write_yaml_file(file_path: str | Path, data: dict) -> bool:
    """Write data to a YAML file.

    Args:
        file_path: Path to YAML file
        data: Data to write

    Returns:
        True if write succeeded, False otherwise

    Example:
        >>> data = {"name": "project", "version": "1.0"}
        >>> success = write_yaml_file("/path/to/config.yml", data)
    """
    try:
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
        return True
    except Exception as e:
        logger.error(f"Error writing YAML file {file_path}: {str(e)}")
        return False


# ============================================================================
# XML PARSING
# ============================================================================


def parse_xml_file(file_path: str | Path, namespace: dict | None = None) -> ET.Element | None:
    """Parse an XML file with error handling.

    Args:
        file_path: Path to XML file
        namespace: Optional XML namespace dict

    Returns:
        Parsed XML root element, or None if parsing failed

    Example:
        >>> root = parse_xml_file("/path/to/pom.xml")
        >>> if root:
        ...     print(root.tag)
    """
    try:
        tree = ET.parse(file_path)
        return tree.getroot()
    except Exception as e:
        logger.error(f"Error parsing XML file {file_path}: {str(e)}")
        return None


def parse_xml_string(xml_string: str) -> ET.Element | None:
    """Parse an XML string with error handling.

    Args:
        xml_string: XML string to parse

    Returns:
        Parsed XML root element, or None if parsing failed

    Example:
        >>> root = parse_xml_string("<root><item>value</item></root>")
        >>> if root:
        ...     print(root.tag)
    """
    try:
        return ET.fromstring(xml_string)
    except Exception as e:
        logger.error(f"Error parsing XML string: {str(e)}")
        return None


# ============================================================================
# RESPONSE HELPERS
# ============================================================================


def create_error_response(message: str, path: str = "", found: bool = True) -> str:
    """Create a standardized error response in JSON format.

    Args:
        message: Error message
        path: File path (optional)
        found: Whether the file was found but failed to parse

    Returns:
        JSON-formatted error response

    Example:
        >>> response = create_error_response("Failed to parse", "/path/to/file")
        >>> print(response)
        {"found": true, "error": "Failed to parse", "path": "/path/to/file"}
    """
    response = {"found": found, "error": message}
    if path:
        response["path"] = path
    return json.dumps(response, indent=2)


def create_not_found_response(filename: str) -> str:
    """Create a standardized not-found response in JSON format.

    Args:
        filename: Name of file that was not found

    Returns:
        JSON-formatted not-found response

    Example:
        >>> response = create_not_found_response("config.json")
        >>> print(response)
        {"found": false, "message": "config.json not found"}
    """
    return json.dumps({"found": False, "message": f"{filename} not found"}, indent=2)


def create_success_response(data: dict) -> str:
    """Create a standardized success response in JSON format.

    Args:
        data: Response data to include

    Returns:
        JSON-formatted success response

    Example:
        >>> response = create_success_response({"name": "project", "version": "1.0"})
        >>> print(response)
        {"name": "project", "version": "1.0"}
    """
    return json.dumps(data, indent=2)


# ============================================================================
# FILE OPERATIONS
# ============================================================================


def count_files_with_extension(
    repo_path: str | Path,
    extension: str,
    max_depth: int = 3,
    max_count: int = 100
) -> int:
    """Count files with a specific extension in a directory tree.

    Args:
        repo_path: Repository root path
        extension: File extension to count (e.g., ".py")
        max_depth: Maximum directory depth to search
        max_count: Maximum count before stopping (for performance)

    Returns:
        Count of files with the extension (capped at max_count)

    Example:
        >>> count = count_files_with_extension("/repo", ".py", max_depth=3)
        >>> print(f"Found {count} Python files")
    """
    count = 0
    try:
        root_path = Path(repo_path)
        for item in root_path.rglob(f"*{extension}"):
            # Calculate depth relative to repo_path
            depth = len(item.relative_to(root_path).parts)
            if depth <= max_depth and item.is_file():
                count += 1
                if count >= max_count:
                    break
    except Exception as e:
        logger.debug(f"Error counting files with extension {extension}: {str(e)}")
    return count


def list_files_in_directory(
    directory: str | Path,
    pattern: str = "*",
    recursive: bool = False
) -> list[Path]:
    """List files in a directory matching a pattern.

    Args:
        directory: Directory path
        pattern: Glob pattern to match (default: "*")
        recursive: Whether to search recursively

    Returns:
        List of matching file paths

    Example:
        >>> files = list_files_in_directory("/repo", "*.py", recursive=True)
        >>> for f in files:
        ...     print(f.name)
    """
    try:
        dir_path = Path(directory)
        if recursive:
            return [p for p in dir_path.rglob(pattern) if p.is_file()]
        else:
            return [p for p in dir_path.glob(pattern) if p.is_file()]
    except Exception as e:
        logger.error(f"Error listing files in {directory}: {str(e)}")
        return []


def get_file_size(file_path: str | Path) -> int | None:
    """Get the size of a file in bytes.

    Args:
        file_path: Path to the file

    Returns:
        File size in bytes, or None if error

    Example:
        >>> size = get_file_size("/path/to/file.txt")
        >>> if size:
        ...     print(f"File is {size} bytes")
    """
    try:
        path = Path(file_path)
        return path.stat().st_size
    except Exception as e:
        logger.error(f"Error getting file size for {file_path}: {str(e)}")
        return None


def ensure_directory_exists(directory: str | Path) -> bool:
    """Ensure a directory exists, creating it if necessary.

    Args:
        directory: Directory path

    Returns:
        True if directory exists or was created, False otherwise

    Example:
        >>> if ensure_directory_exists("/path/to/dir"):
        ...     print("Directory ready")
    """
    try:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory}: {str(e)}")
        return False
