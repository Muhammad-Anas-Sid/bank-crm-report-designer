"""
SQL Validator — safety layer for SQL query validation.
LLM Suggests → Query Builder Enforces → SQL Executes
"""

import re
from backend.chat.chat_service import ChatService


# Dangerous SQL keywords that must be blocked
FORBIDDEN_KEYWORDS = {
    "DROP", "ALTER", "TRUNCATE", "DELETE", "INSERT", "UPDATE",
    "EXECUTE", "GRANT", "REVOKE", "CREATE", "REPLACE",
}

# Dangerous patterns
FORBIDDEN_PATTERNS = [
    r";\s*",          # Multiple statements
    r"--",            # SQL comments
    r"/\*",           # Block comments
    r"xp_",           # SQL Server extended procedures
    r"EXEC\s",        # Execute
    r"INTO\s+OUTFILE", # File write
    r"LOAD_FILE",     # File read
]


class SqlValidator:
    """Validates SQL queries against schema metadata and security rules."""

    def __init__(self):
        self.schema = ChatService.get_schema_entities()
        self.allowed_tables = set(t.lower() for t in self.schema.keys()) if self.schema else set()
        self._load_allowed_columns()

    def _load_allowed_columns(self):
        """Build a mapping of table → allowed column names from schema metadata."""
        self.allowed_columns = {}
        for table_name, table_info in self.schema.items():
            col_names = set()
            # New format is {"columns": [{"name": "...", ...}, ...]}
            columns = table_info.get("columns", [])
            for col_def in columns:
                if isinstance(col_def, dict) and "name" in col_def:
                    col_names.add(col_def["name"].lower())
                elif isinstance(col_def, str):
                    # Fallback for old string format "col_name (TYPE)"
                    col_name = col_def.split("(")[0].strip().lower()
                    col_names.add(col_name)
            self.allowed_columns[table_name.lower()] = col_names

    def validate(self, sql_query: str) -> tuple:
        """
        Validate a SQL query.
        Returns (is_valid: bool, error_message: str or None)
        """
        if not sql_query or not sql_query.strip():
            return False, "Empty SQL query."

        sql_upper = sql_query.strip().upper()

        # 1. Must be SELECT only (READ ONLY enforcement)
        if not sql_upper.startswith("SELECT"):
            return False, "Only SELECT queries are allowed (READ ONLY)."

        # 2. Block forbidden keywords
        for kw in FORBIDDEN_KEYWORDS:
            # Use word boundary matching to avoid false positives
            pattern = rf"\b{kw}\b"
            if re.search(pattern, sql_upper):
                return False, f"Security Alert: Forbidden keyword '{kw}' detected."

        # 3. Block forbidden patterns
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, sql_query, re.IGNORECASE):
                return False, f"Security Alert: Forbidden pattern detected in query."

        # 4. Validate table existence
        referenced_tables = self._extract_table_names(sql_query)
        for table in referenced_tables:
            if table.lower() not in self.allowed_tables:
                return False, f"Security Alert: Table '{table}' does not exist in schema."

        # 5. Validate column existence (best-effort)
        column_refs = self._extract_column_references(sql_query)
        for table, column in column_refs:
            table_lower = table.lower()
            if table_lower in self.allowed_columns:
                if column.lower() not in self.allowed_columns[table_lower]:
                    return False, f"Security Alert: Column '{column}' does not exist in table '{table}'."

        return True, None

    def _extract_table_names(self, sql_query: str) -> list:
        """Extract table names from FROM and JOIN clauses."""
        matches = re.findall(
            r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)",
            sql_query, flags=re.IGNORECASE,
        )
        return list(set(matches))

    def _extract_column_references(self, sql_query: str) -> list:
        """Extract table.column references from the query."""
        matches = re.findall(
            r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
            sql_query,
        )
        return [(t, c) for t, c in matches if t.lower() in self.allowed_tables]
