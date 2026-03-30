"""
Knowledge Base — converts schema_metadata.json into searchable text documents.

Each table and its columns are converted into natural-language descriptions
that can be embedded and searched semantically. This provides the corpus
for the EmbeddingsManager to build its FAISS index from.
"""

import json
import logging
from typing import List, Dict, Any

from backend.config.settings import Config

logger = logging.getLogger(__name__)

# Tables that are internal to the app (auth, chat, audit) — not user-reportable data
SYSTEM_TABLES = {
    "roles", "users", "user_roles", "user_sessions",
    "audit_logs", "chat_sessions", "chat_messages",
}

# Human-readable domain mapping for banking tables
TABLE_DOMAIN_MAP = {
    "customers": "Customer Management",
    "accounts": "Account Management",
    "branches": "Branch Management",
    "transactions": "Transaction Management",
    "external_accounts": "Transaction Management",
    "employees": "Employee Management",
    "cards": "Card Management",
    "card_lifecycle": "Card Management",
    "card_transactions": "Card Management",
    "merchants": "Card Management",
}


class KnowledgeBase:
    """
    Parses schema_metadata.json into searchable document chunks.

    Each document contains a natural-language description of a table or column,
    along with metadata (table name, column name, domain, data type, relationships).
    These documents feed into the EmbeddingsManager for semantic search.
    """

    def __init__(self):
        self.schema: Dict[str, Any] = {}
        self.documents: List[Dict[str, str]] = []
        self.relationships: Dict[str, List[Dict]] = {}
        self._load_schema()
        self._build_documents()
        self._build_relationships()

    def _load_schema(self):
        """Load schema metadata from the JSON config file."""
        try:
            with open(Config.SCHEMA_METADATA_PATH, "r") as f:
                data = json.load(f)
                self.schema = data.get("tables", data)
            logger.info(f"Knowledge base loaded {len(self.schema)} tables from schema metadata.")
        except FileNotFoundError:
            logger.error(f"Schema metadata not found at {Config.SCHEMA_METADATA_PATH}")
            self.schema = {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in schema metadata: {e}")
            self.schema = {}

    def _build_documents(self):
        """
        Convert each table and column into a searchable text document.

        Document structure:
        {
            "text": "Natural language description for embedding",
            "table": "table_name",
            "column": "column_name" or None (for table-level docs),
            "domain": "Customer Management",
            "data_type": "VARCHAR(100)" or None,
            "doc_type": "table" | "column"
        }
        """
        self.documents = []

        for table_name, table_info in self.schema.items():
            # Skip system/internal tables — users shouldn't query these
            if table_name.lower() in SYSTEM_TABLES:
                continue

            domain = TABLE_DOMAIN_MAP.get(table_name.lower(), "General")
            columns = table_info.get("columns", [])
            fk_list = table_info.get("foreign_keys", [])

            # --- Table-level document ---
            col_names = [c["name"] for c in columns if isinstance(c, dict)]
            table_text = (
                f"Table '{table_name}' in the {domain} domain. "
                f"Contains columns: {', '.join(col_names)}. "
                f"Has {len(columns)} columns and {len(fk_list)} foreign key relationships."
            )
            self.documents.append({
                "text": table_text,
                "table": table_name,
                "column": None,
                "domain": domain,
                "data_type": None,
                "doc_type": "table",
            })

            # --- Column-level documents ---
            for col in columns:
                if not isinstance(col, dict):
                    continue
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                nullable = col.get("nullable", True)

                # Build a rich description for semantic search
                col_text = (
                    f"Column '{col_name}' in table '{table_name}' ({domain} domain). "
                    f"Data type: {col_type}. "
                    f"{'Required' if not nullable else 'Optional'} field."
                )

                # Add relationship context if this is a FK
                if "REFERENCES" in col_type.upper():
                    col_text += f" This is a foreign key linking to another table."

                self.documents.append({
                    "text": col_text,
                    "table": table_name,
                    "column": col_name,
                    "domain": domain,
                    "data_type": col_type,
                    "doc_type": "column",
                })

        logger.info(f"Knowledge base built {len(self.documents)} searchable documents.")

    def _build_relationships(self):
        """
        Parse foreign key relationships from schema metadata.

        Builds a graph: { table_name: [{ "column": col, "ref_table": tbl, "ref_column": col }] }
        Used by the SQL connector to build safe JOINs.
        """
        self.relationships = {}

        for table_name, table_info in self.schema.items():
            if table_name.lower() in SYSTEM_TABLES:
                continue

            columns = table_info.get("columns", [])
            for col in columns:
                if not isinstance(col, dict):
                    continue

                col_type = col.get("type", "")
                if "REFERENCES" not in col_type.upper():
                    continue

                try:
                    ref_part = col_type.upper().split("REFERENCES")[1].strip()
                    ref_table = ref_part.split("(")[0].strip().lower()
                    ref_column = ref_part.split("(")[1].split(")")[0].strip().lower()

                    if table_name not in self.relationships:
                        self.relationships[table_name] = []
                    self.relationships[table_name].append({
                        "column": col["name"],
                        "ref_table": ref_table,
                        "ref_column": ref_column,
                    })
                except (IndexError, KeyError) as e:
                    logger.warning(f"Could not parse FK for {table_name}.{col.get('name')}: {e}")

        logger.info(f"Knowledge base mapped {sum(len(v) for v in self.relationships.values())} relationships.")

    def get_documents(self) -> List[Dict[str, str]]:
        """Return all searchable documents."""
        return self.documents

    def get_table_columns(self, table_name: str) -> List[str]:
        """Get column names for a specific table."""
        table_info = self.schema.get(table_name, {})
        columns = table_info.get("columns", [])
        return [c["name"] for c in columns if isinstance(c, dict)]

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get full info for a specific table."""
        return self.schema.get(table_name, {})

    def get_relationships_for(self, table_name: str) -> List[Dict]:
        """Get FK relationships originating from a table."""
        return self.relationships.get(table_name, [])

    def get_join_path(self, table_a: str, table_b: str) -> List[Dict]:
        """
        Find how to JOIN table_a to table_b using FK relationships.
        Returns a list of join steps: [{ "from_table", "from_col", "to_table", "to_col" }]
        """
        # Direct relationship: table_a has FK to table_b
        for rel in self.relationships.get(table_a, []):
            if rel["ref_table"] == table_b.lower():
                return [{
                    "from_table": table_a,
                    "from_col": rel["column"],
                    "to_table": rel["ref_table"],
                    "to_col": rel["ref_column"],
                }]

        # Reverse: table_b has FK to table_a
        for rel in self.relationships.get(table_b, []):
            if rel["ref_table"] == table_a.lower():
                return [{
                    "from_table": table_b,
                    "from_col": rel["column"],
                    "to_table": rel["ref_table"],
                    "to_col": rel["ref_column"],
                }]

        # Two-hop: table_a → intermediate → table_b
        for mid_table, mid_rels in self.relationships.items():
            for rel_a in mid_rels:
                if rel_a["ref_table"] == table_a.lower():
                    for rel_b in self.relationships.get(mid_table, []):
                        if rel_b["ref_table"] == table_b.lower():
                            return [
                                {
                                    "from_table": mid_table,
                                    "from_col": rel_a["column"],
                                    "to_table": table_a,
                                    "to_col": rel_a["ref_column"],
                                },
                                {
                                    "from_table": mid_table,
                                    "from_col": rel_b["column"],
                                    "to_table": table_b,
                                    "to_col": rel_b["ref_column"],
                                },
                            ]

        return []  # No path found

    def get_reportable_tables(self) -> List[str]:
        """Return only user-facing, reportable table names (excludes system tables)."""
        return [t for t in self.schema.keys() if t.lower() not in SYSTEM_TABLES]

    def get_domain_for_table(self, table_name: str) -> str:
        """Return the domain category for a table."""
        return TABLE_DOMAIN_MAP.get(table_name.lower(), "General")
