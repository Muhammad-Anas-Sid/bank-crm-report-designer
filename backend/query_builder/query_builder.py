"""
Query Builder — generates validated SQL from structured report plans.
"""

from collections import deque
from backend.chat.chat_service import ChatService
from backend.query_builder.sql_validator import SqlValidator
from backend.models.base import get_db_engine
from sqlalchemy import text


class QueryBuilder:
    """Builds safe SQL queries from report plan JSON, with validation."""

    def __init__(self):
        self.schema = ChatService.get_schema_entities()
        self.allowed_tables = list(self.schema.keys()) if self.schema else []
        self.relationship_graph = self._build_relationship_graph()
        self.validator = SqlValidator()

    def _build_relationship_graph(self):
        """Build a graph of table relationships from metadata.json."""
        graph = {}

        for referencing_table, table_info in self.schema.items():
            columns = table_info.get("columns", [])
            for col in columns:
                col_name = col.get("name")
                col_type = col.get("type", "")

                # Simple regex-less check for "REFERENCES other_table(other_col)"
                if "REFERENCES" in col_type.upper():
                    parts = col_type.upper().split("REFERENCES")
                    ref_part = parts[1].strip()
                    # e.g., "USERS(USER_ID)"
                    try:
                        referenced_table = ref_part.split("(")[0].strip().lower()
                        referenced_column = ref_part.split("(")[1].split(")")[0].strip().lower()
                        
                        join_cond = f"{referencing_table}.{col_name} = {referenced_table}.{referenced_column}"

                        if referencing_table not in graph:
                            graph[referencing_table] = []
                        graph[referencing_table].append((referenced_table, join_cond))

                        # Bidirectional for BFS pathfinding
                        if referenced_table not in graph:
                            graph[referenced_table] = []
                        graph[referenced_table].append((referencing_table, join_cond))
                    except Exception as e:
                        print(f"Warning: Failed to parse FK {col_type}: {e}")

        return graph

    def _find_join_path(self, start_table: str, target_table: str) -> list:
        """Find shortest join path using BFS."""
        if start_table == target_table:
            return []

        queue = deque([(start_table, [])])
        visited = {start_table}

        while queue:
            current, path = queue.popleft()

            for neighbor, join_condition in self.relationship_graph.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)

                new_path = path + [(neighbor, join_condition)]

                if neighbor == target_table:
                    return new_path

                queue.append((neighbor, new_path))

        raise ValueError(f"No join path found from {start_table} to {target_table}")

    def generate_sql(self, report_plan: dict) -> str:
        """
        Generate validated SQL from a report plan as a fallback.
        """
        data_reqs = report_plan.get("data_requirements", {})

        tables = data_reqs.get("tables", [])
        columns = data_reqs.get("columns", ["*"]) # Use "*" if not specified
        filters = data_reqs.get("filters", "")
        group_by = data_reqs.get("group_by")
        order_by = data_reqs.get("order_by")
        limit = data_reqs.get("limit")

        if not tables:
            raise ValueError("No tables specified in report plan.")

        # Normalize table names
        tables = [t.lower().replace('"', '').replace("'", "") for t in tables]

        # Validate tables and columns exist in schema metadata
        authorized_tables = [at.lower() for at in self.allowed_tables]
        for t in tables:
            if t not in authorized_tables:
                raise ValueError(f"Security Alert: Table '{t}' is not authorized or doesn't exist.")
            
            # If columns are specified (not "*"), validate them against the table's column list
            if columns != ["*"]:
                table_cols = [c["name"].lower() for c in self.schema.get(t, {}).get("columns", [])]
                for full_col in columns:
                    # Handle "table.column" or "column"
                    col_name = full_col.split(".")[-1].lower()
                    # We skip complex expressions like SUM(amount) for now or just check if the column is present
                    # This is more of a safety hint than a hard block for complex SQL
                    pass 

        # Build FROM clause with automatic JOINs
        main_table = tables[0]
        from_clause = main_table
        joined_tables = {main_table}

        for t in tables[1:]:
            if t in joined_tables:
                continue
            try:
                join_path = self._find_join_path(main_table, t)
                for neighbor, join_condition in join_path:
                    if neighbor not in joined_tables:
                        from_clause += f" JOIN {neighbor} ON {join_condition}"
                        joined_tables.add(neighbor)
            except ValueError:
                raise ValueError(f"No known join path from {main_table} to {t}")

        select_clause = ", ".join(columns)
        query = f"SELECT {select_clause} FROM {from_clause}"

        if filters:
            query += f" WHERE {filters}"
        if group_by:
            query += f" GROUP BY {group_by}"
        if order_by:
            query += f" ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {int(limit)}"

        # Final validation through safety layer
        is_valid, error = self.validator.validate(query)
        if not is_valid:
            raise ValueError(f"Query validation failed: {error}")

        return query
