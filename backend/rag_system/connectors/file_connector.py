"""
File Connector — reads data from files on the local filesystem.

Supports CSV, TXT, and JSON files. Scans configured directories,
indexes available files, and retrieves relevant content based on
search terms from the RAG orchestrator.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

import pandas as pd

from backend.rag_system.connectors.base_connector import BaseConnector
from backend.config.settings import Config
from backend.rag_system.time_period_parser import extract_time_keywords

logger = logging.getLogger(__name__)

# Supported file extensions and their handlers
SUPPORTED_EXTENSIONS = {".csv", ".txt", ".json", ".tsv", ".docx"}

# Maximum file size to read (10 MB safety limit)
MAX_FILE_SIZE = 10 * 1024 * 1024


class FileConnector(BaseConnector):
    """
    Reads and parses files from configured directories.

    Capabilities:
    - Indexes all supported files in configured directories at startup
    - Matches files to search terms by filename and content keywords
    - Parses CSV → DataFrame, JSON → DataFrame, TXT → single-column DataFrame
    - Adds source file attribution to results

    The file connector is useful for supplementing database data with
    local reports, reference documents, and exported datasets.
    """

    def __init__(self, search_directories: Optional[List[str]] = None):
        """
        Args:
            search_directories: List of directory paths to index for files.
                Defaults to the project's generated_reports/ and config/ dirs.
        """
        self.directories = search_directories or self._default_directories()
        self.file_index: List[Dict[str, str]] = []
        self._index_files()

    def _default_directories(self) -> List[str]:
        """Default directories to search for data files."""
        return [
            Config.REPORTS_DIR,
            Config.DATA_INGEST_DIR,
            os.path.join(Config.PROJECT_ROOT, "config"),
        ]

    def connect(self) -> bool:
        """Verify at least one search directory exists."""
        for d in self.directories:
            if os.path.isdir(d):
                return True
        logger.warning("No valid file directories configured.")
        return False

    @property
    def source_type(self) -> str:
        return "file"

    def get_metadata(self) -> Dict[str, Any]:
        """Return indexed file information."""
        return {
            "source_type": "file_system",
            "directories": self.directories,
            "indexed_files": len(self.file_index),
            "files": [
                {"name": f["name"], "type": f["extension"], "path": f["path"]}
                for f in self.file_index
            ],
        }

    def _index_files(self):
        """Scan directories and build an index of available files."""
        self.file_index = []
        for directory in self.directories:
            if not os.path.isdir(directory):
                continue
            for root, _dirs, files in os.walk(directory):
                for filename in files:
                    ext = Path(filename).suffix.lower()
                    if ext not in SUPPORTED_EXTENSIONS:
                        continue

                    filepath = os.path.join(root, filename)
                    file_size = os.path.getsize(filepath)

                    if file_size > MAX_FILE_SIZE:
                        logger.warning(f"Skipping large file: {filepath} ({file_size} bytes)")
                        continue

                    self.file_index.append({
                        "name": filename,
                        "path": filepath,
                        "extension": ext,
                        "size": file_size,
                        "directory": root,
                    })

        logger.info(f"File connector indexed {len(self.file_index)} files from {len(self.directories)} directories.")

    def retrieve(self, requirements: Dict[str, Any]) -> pd.DataFrame:
        """
        Retrieve data from files matching the requirements.

        Args:
            requirements: {
                "search_term": "Q1 transactions report",
                "file_types": [".csv", ".json"],
                "directory": "/path/to/specific/dir",  # optional
                "filename": "specific_file.csv",  # optional, exact match
                "time_range": {"start": "2025-07-01", "end": "2025-09-30"},  # optional
            }

        Returns:
            DataFrame combining data from all matching files.
        """
        search_term = requirements.get("search_term", "")
        file_types = requirements.get("file_types", list(SUPPORTED_EXTENSIONS))
        target_dir = requirements.get("directory")
        filename = requirements.get("filename")
        time_range = requirements.get("time_range", {})

        matching_files = self._find_matching_files(search_term, file_types, target_dir, filename)

        if not matching_files:
            logger.info(f"No files matched search: '{search_term}'")
            return pd.DataFrame()

        # Read and combine results from all matching files
        all_frames = []
        for file_info in matching_files:
            try:
                df = self._read_file(file_info)
                if not df.empty:
                    df["_source_file"] = file_info["name"]
                    all_frames.append(df)
            except Exception as e:
                logger.warning(f"Failed to read {file_info['path']}: {e}")

        if not all_frames:
            return pd.DataFrame()

        # Combine frames
        try:
            result = pd.concat(all_frames, ignore_index=True)
        except Exception:
            result = all_frames[0]

        # Apply time filtering if a time_range was provided
        if time_range and not result.empty:
            result = self._apply_time_filter(result, time_range)

        return result

    def _find_matching_files(
        self,
        search_term: str,
        file_types: List[str],
        target_dir: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> List[Dict]:
        """Find files matching the search criteria."""
        # Exact filename match
        if filename:
            return [f for f in self.file_index if f["name"].lower() == filename.lower()]

        search_words = set(search_term.lower().split()) if search_term else set()
        matches = []

        for file_info in self.file_index:
            # Filter by extension
            if file_info["extension"] not in file_types:
                continue

            # Filter by directory
            if target_dir and not file_info["path"].startswith(target_dir):
                continue

            # Score by keyword match in filename
            if search_words:
                file_words = set(file_info["name"].lower().replace("_", " ").replace("-", " ").split())
                overlap = len(search_words & file_words)
                if overlap > 0:
                    file_info["relevance"] = overlap / len(search_words)
                    matches.append(file_info)
            else:
                file_info["relevance"] = 0
                matches.append(file_info)

        # Sort by relevance (most relevant first)
        matches.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return matches[:5]  # Return top 5 matches

    def _read_file(self, file_info: Dict) -> pd.DataFrame:
        """Read and parse a file based on its extension."""
        ext = file_info["extension"]
        path = file_info["path"]

        if ext == ".csv":
            return self._read_csv(path)
        elif ext == ".tsv":
            return self._read_csv(path, sep="\t")
        elif ext == ".json":
            return self._read_json(path)
        elif ext == ".txt":
            return self._read_text(path)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return pd.DataFrame()

    def _read_csv(self, path: str, sep: str = ",") -> pd.DataFrame:
        """Parse a CSV file into a DataFrame."""
        try:
            return pd.read_csv(path, sep=sep)
        except Exception as e:
            logger.error(f"CSV parse error for {path}: {e}")
            return pd.DataFrame()

    def _read_json(self, path: str) -> pd.DataFrame:
        """Parse a JSON file into a DataFrame."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle different JSON structures
            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                # If it has a "data" or "records" key, use that
                for key in ("data", "records", "rows", "results"):
                    if key in data and isinstance(data[key], list):
                        return pd.DataFrame(data[key])
                # Otherwise try to normalize the dict
                return pd.json_normalize(data)
            else:
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"JSON parse error for {path}: {e}")
            return pd.DataFrame()

    def _read_text(self, path: str) -> pd.DataFrame:
        """Read a text file into a single-column DataFrame."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return pd.DataFrame({"content": [content], "source_file": [os.path.basename(path)]})
        except Exception as e:
            logger.error(f"Text read error for {path}: {e}")
            return pd.DataFrame()

    def add_directory(self, directory: str):
        """Add a new directory to scan and re-index."""
        if directory not in self.directories:
            self.directories.append(directory)
            self._index_files()

    def refresh_index(self):
        """Re-scan all directories and rebuild the file index."""
        self._index_files()

    def _apply_time_filter(self, df: pd.DataFrame, time_range: Dict[str, str]) -> pd.DataFrame:
        """
        Filter a DataFrame by time range using auto-detected date columns.

        Looks for columns containing date-like data and filters rows that
        fall within the specified start/end range.
        """
        start = time_range.get("start")
        end = time_range.get("end")
        if not start and not end:
            return df

        # Find date columns
        date_col = None
        for col in df.columns:
            if col.startswith("_"):  # Skip internal columns
                continue
            if any(kw in col.lower() for kw in ["date", "time", "timestamp", "created", "event", "issued"]):
                try:
                    parsed = pd.to_datetime(df[col], errors="coerce")
                    if parsed.notna().sum() > len(df) * 0.5:  # At least 50% parseable
                        date_col = col
                        break
                except Exception:
                    continue

        if not date_col:
            logger.info("No date column found in file data for time filtering.")
            return df

        try:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            original_len = len(df)

            if start:
                df = df[df[date_col] >= pd.to_datetime(start)]
            if end:
                df = df[df[date_col] <= pd.to_datetime(end)]

            logger.info(f"File time filter: {original_len} -> {len(df)} rows (column: {date_col})")
            return df
        except Exception as e:
            logger.warning(f"File time filtering failed: {e}")
            return df
