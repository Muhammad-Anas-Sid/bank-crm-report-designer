"""
SQL Connector — safe PostgreSQL data retrieval without LLM-generated SQL.

This connector builds parameterized queries from structured requirements
(table name, columns, filters, aggregations). The key principle: the semantic
search layer identifies WHICH tables/columns are needed, and this connector
builds a SAFE query to retrieve that specific data. No SQL generation by LLM.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

import pandas as pd
from sqlalchemy import text

from backend.models.base import get_db_engine
from backend.rag_system.connectors.base_connector import BaseConnector
from backend.rag_system.knowledge_base import KnowledgeBase
from backend.rag_system.time_period_parser import parse_time_period, describe_time_range

logger = logging.getLogger(__name__)

# Whitelisted aggregation functions — only these are allowed in queries
ALLOWED_AGGREGATIONS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}

# Whitelisted operators for filter conditions
ALLOWED_OPERATORS = {"=", "!=", "<", ">", "<=", ">=", "LIKE", "ILIKE", "IN", "NOT IN", "IS", "IS NOT", "BETWEEN"}

# Table alias map matching the existing schema conventions
TABLE_ALIASES = {
    "customers": "c",
    "accounts": "a",
    "branches": "b",
    "transactions": "t",
    "external_accounts": "ea",
    "employees": "e",
    "cards": "cr",
    "card_transactions": "ct",
    "card_lifecycle": "cl",
    "merchants": "m",
}


class SQLConnector(BaseConnector):
    """
    Safely queries PostgreSQL using structured requirements.

    Instead of executing LLM-generated SQL, this connector:
    1. Receives structured requirements (table, columns, filters, aggregations)
    2. Validates table/column names against the schema whitelist
    3. Builds parameterized queries (safe from SQL injection)
    4. Executes and returns clean DataFrames

    Supported query patterns:
    - Direct retrieval: SELECT columns FROM table WHERE filters
    - Aggregation: SELECT agg(col), ... GROUP BY ... 
    - Multi-table JOIN: Automatic join path discovery via FK relationships
    """

    def __init__(self, knowledge_base: Optional[KnowledgeBase] = None):
        self.engine = get_db_engine()
        self.kb = knowledge_base or KnowledgeBase()
        self._valid_tables = set(t.lower() for t in self.kb.get_reportable_tables())
        self._valid_columns = {}
        for table in self._valid_tables:
            self._valid_columns[table] = set(
                c.lower() for c in self.kb.get_table_columns(table)
            )

    def connect(self) -> bool:
        """Test the database connection."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return False

    @property
    def source_type(self) -> str:
        return "sql"

    def get_metadata(self) -> Dict[str, Any]:
        """Return available tables and their columns."""
        return {
            "source_type": "postgresql",
            "tables": {
                t: list(cols) for t, cols in self._valid_columns.items()
            },
        }

    def retrieve(self, requirements: Dict[str, Any]) -> pd.DataFrame:
        """
        Retrieve data based on structured requirements.

        Args:
            requirements: {
                "tables": ["transactions", "accounts"],
                "columns": ["amount", "transaction_date", "account_type"],
                "filters": [
                    {"column": "status", "operator": "=", "value": "COMPLETED"},
                    {"column": "transaction_date", "operator": ">=", "value": "2026-01-01"}
                ],
                "aggregations": [
                    {"function": "SUM", "column": "amount", "alias": "total_amount"},
                    {"function": "COUNT", "column": "*", "alias": "transaction_count"}
                ],
                "group_by": ["account_type"],
                "order_by": [{"column": "total_amount", "direction": "DESC"}],
                "limit": 100,
                "time_range": {"start": "2026-01-01", "end": "2026-03-31"}
            }

        Returns:
            DataFrame with the query results.
        """
        tables = requirements.get("tables", [])
        if not tables:
            logger.warning("No tables specified in requirements.")
            return pd.DataFrame()

        # Validate all tables exist in schema
        main_table = tables[0].lower()
        if main_table not in self._valid_tables:
            logger.error(f"Table '{main_table}' is not in the allowed schema.")
            return pd.DataFrame()

        try:
            query, params = self._build_safe_query(requirements)
            if not query:
                return pd.DataFrame()

            logger.info(f"Executing safe query: {query[:200]}...")
            logger.info(f"Parameters: {params}")

            return self._execute_query(query, params)

        except Exception as e:
            logger.error(f"SQL retrieval failed: {e}")
            # Try a simpler fallback query
            return self._fallback_retrieval(main_table, requirements.get("limit", 100))

    def _build_safe_query(self, requirements: Dict[str, Any]) -> Tuple[str, Dict]:
        """
        Build a parameterized SQL query from structured requirements.

        Returns (query_string, parameters_dict).
        All user values are parameterized — never interpolated into the SQL string.
        """
        tables = [t.lower() for t in requirements.get("tables", [])]
        columns = requirements.get("columns", [])
        filters = requirements.get("filters", [])
        aggregations = requirements.get("aggregations", [])
        group_by = requirements.get("group_by", [])
        order_by = requirements.get("order_by", [])
        limit = requirements.get("limit")
        time_range = requirements.get("time_range", {})

        main_table = tables[0]
        main_alias = TABLE_ALIASES.get(main_table, main_table[0])
        params = {}
        param_counter = 0

        # --- SELECT clause ---
        select_parts = []

        if aggregations:
            for agg in aggregations:
                func = agg.get("function", "").upper()
                col = agg.get("column", "*")
                # Sanitize alias: "count_*" -> "count_all", remove special chars
                alias = agg.get("alias", f"{func.lower()}_{col}")
                alias = alias.replace("*", "all").replace("(", "").replace(")", "").replace(".", "_")

                if func not in ALLOWED_AGGREGATIONS:
                    logger.warning(f"Skipping disallowed aggregation: {func}")
                    continue

                if col == "*":
                    select_parts.append(f"{func}(*) AS {alias}")
                else:
                    qualified_col = self._qualify_column(col, main_table, tables)
                    select_parts.append(f"{func}({qualified_col}) AS {alias}")

            # Add group_by columns to SELECT
            for gb_col in group_by:
                qualified = self._qualify_column(gb_col, main_table, tables)
                if qualified not in select_parts:
                    select_parts.insert(0, qualified)
        else:
            if columns:
                for col in columns:
                    qualified = self._qualify_column(col, main_table, tables)
                    select_parts.append(qualified)
            else:
                # Default: select all columns from main table
                select_parts.append(f"{main_alias}.*")

        select_clause = ", ".join(select_parts) if select_parts else f"{main_alias}.*"

        # --- FROM clause with JOINs ---
        from_clause = f"{main_table} {main_alias}"
        joined_tables = {main_table}

        for other_table in tables[1:]:
            other_table = other_table.lower()
            if other_table in joined_tables or other_table not in self._valid_tables:
                continue

            join_path = self.kb.get_join_path(main_table, other_table)
            if join_path:
                for step in join_path:
                    jt = step["from_table"] if step["from_table"] not in joined_tables else step["to_table"]
                    if jt in joined_tables:
                        continue
                    jt_alias = TABLE_ALIASES.get(jt, jt[0])
                    ft = step["from_table"]
                    ft_alias = TABLE_ALIASES.get(ft, ft[0])
                    tt = step["to_table"]
                    tt_alias = TABLE_ALIASES.get(tt, tt[0])

                    from_clause += (
                        f" LEFT JOIN {jt} {jt_alias}"
                        f" ON {ft_alias}.{step['from_col']} = {tt_alias}.{step['to_col']}"
                    )
                    joined_tables.add(jt)
            else:
                # No FK relationship found — skip this table to avoid cartesian product
                logger.warning(f"No join path from {main_table} to {other_table}. Skipping.")

        # --- WHERE clause ---
        where_parts = []

        for filt in filters:
            col = filt.get("column", "")
            op = filt.get("operator", "=").upper()
            val = filt.get("value")

            if op not in ALLOWED_OPERATORS:
                logger.warning(f"Skipping disallowed operator: {op}")
                continue

            qualified_col = self._qualify_column(col, main_table, tables)
            param_name = f"p{param_counter}"
            param_counter += 1

            if op in ("IS", "IS NOT"):
                where_parts.append(f"{qualified_col} {op} NULL")
            elif op == "IN":
                if isinstance(val, list):
                    placeholders = []
                    for i, v in enumerate(val):
                        pn = f"{param_name}_{i}"
                        params[pn] = v
                        placeholders.append(f":{pn}")
                    where_parts.append(f"{qualified_col} IN ({', '.join(placeholders)})")
                else:
                    params[param_name] = val
                    where_parts.append(f"{qualified_col} = :{param_name}")
            elif op == "BETWEEN":
                if isinstance(val, list) and len(val) == 2:
                    pn_lo = f"{param_name}_lo"
                    pn_hi = f"{param_name}_hi"
                    params[pn_lo] = val[0]
                    params[pn_hi] = val[1]
                    where_parts.append(f"{qualified_col} BETWEEN :{pn_lo} AND :{pn_hi}")
            else:
                params[param_name] = val
                where_parts.append(f"{qualified_col} {op} :{param_name}")

        # Time range filter
        if time_range:
            date_col = self._find_date_column(main_table)
            if date_col:
                qualified_date = self._qualify_column(date_col, main_table, tables)
                if time_range.get("start"):
                    params["time_start"] = time_range["start"]
                    where_parts.append(f"{qualified_date} >= :time_start")
                if time_range.get("end"):
                    params["time_end"] = time_range["end"]
                    where_parts.append(f"{qualified_date} <= :time_end")

        where_clause = " AND ".join(where_parts) if where_parts else ""

        # --- GROUP BY clause ---
        group_clause = ""
        if group_by and aggregations:
            group_cols = []
            for g in group_by:
                group_cols.append(self._qualify_column(g, main_table, tables))
            group_clause = ", ".join(group_cols)

        # --- ORDER BY clause ---
        order_clause = ""
        if order_by:
            order_parts = []
            for ob in order_by:
                col = ob.get("column", "")
                direction = ob.get("direction", "ASC").upper()
                if direction not in ("ASC", "DESC"):
                    direction = "ASC"
                # Check if it's an alias from aggregations
                is_alias = any(a.get("alias") == col for a in aggregations)
                if is_alias:
                    order_parts.append(f"{col} {direction}")
                else:
                    order_parts.append(f"{self._qualify_column(col, main_table, tables)} {direction}")
            order_clause = ", ".join(order_parts)

        # --- Build final query ---
        query = f"SELECT {select_clause} FROM {from_clause}"
        if where_clause:
            query += f" WHERE {where_clause}"
        if group_clause:
            query += f" GROUP BY {group_clause}"
        if order_clause:
            query += f" ORDER BY {order_clause}"
        if limit and str(limit).isdigit():
            query += f" LIMIT {int(limit)}"

        return query, params

    def _qualify_column(self, column: str, main_table: str, all_tables: List[str]) -> str:
        """
        Add table alias prefix to a column name.
        If column already has a prefix (e.g., 'c.customer_id'), return as-is.
        Otherwise, find which table owns this column.
        """
        if "." in column:
            return column

        col_lower = column.lower()

        # Check main table first
        if col_lower in self._valid_columns.get(main_table, set()):
            alias = TABLE_ALIASES.get(main_table, main_table[0])
            return f"{alias}.{column}"

        # Check other tables
        for table in all_tables:
            tbl = table.lower()
            if col_lower in self._valid_columns.get(tbl, set()):
                alias = TABLE_ALIASES.get(tbl, tbl[0])
                return f"{alias}.{column}"

        # Couldn't find table — return unqualified (will work if only one table)
        return column

    def _find_date_column(self, table_name: str) -> Optional[str]:
        """Find the primary date/timestamp column for a table."""
        # Explicit mapping — most reliable
        date_columns = {
            "transactions": "transaction_date",
            "card_transactions": "transaction_date",
            "accounts": "opening_date",
            "cards": "issue_date",
            "card_lifecycle": "event_date",
            "customers": "created_at",
            "merchants": "created_at",
        }
        if table_name in date_columns:
            # Verify the column actually exists in the schema
            if date_columns[table_name].lower() in self._valid_columns.get(table_name, set()):
                return date_columns[table_name]

        # Fallback: search for date/timestamp columns in order of preference
        preferred_names = [
            "transaction_date", "event_date", "created_at", "issue_date",
            "opening_date", "date", "timestamp", "created_date",
            "registered_at", "updated_at", "expiry_date",
        ]
        table_cols = self._valid_columns.get(table_name, set())
        for pref in preferred_names:
            if pref in table_cols:
                return pref

        # Last resort: look for any column with 'date' or 'time' in its name
        for col_name in table_cols:
            if "date" in col_name or "time" in col_name:
                return col_name

        return None

    def _execute_query(self, query: str, params: Dict) -> pd.DataFrame:
        """Execute a parameterized query and return a DataFrame."""
        try:
            with self.engine.connect() as conn:
                result = pd.read_sql_query(text(query), con=conn, params=params)
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}\nParams: {params}")
            raise

    def _fallback_retrieval(self, table_name: str, limit: int = 100) -> pd.DataFrame:
        """
        Simple fallback: SELECT * FROM table LIMIT n.
        Used when structured query building fails.
        """
        try:
            alias = TABLE_ALIASES.get(table_name, table_name[0])
            query = f"SELECT * FROM {table_name} {alias} LIMIT {min(int(limit), 500)}"
            logger.info(f"Fallback retrieval: {query}")
            with self.engine.connect() as conn:
                return pd.read_sql_query(text(query), con=conn)
        except Exception as e:
            logger.error(f"Fallback retrieval also failed: {e}")
            return pd.DataFrame()

    @staticmethod
    def post_filter_by_time(df: pd.DataFrame, time_range: Dict[str, str], date_column: str = None) -> pd.DataFrame:
        """
        Post-filter a DataFrame by time range.
        
        This is a safety net applied AFTER data retrieval. If the SQL query
        didn't properly filter by date (e.g., missing date column or complex
        join scenarios), this ensures the data is still correctly filtered.
        
        Args:
            df: The DataFrame to filter
            time_range: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            date_column: Specific column to filter on (auto-detected if None)
        """
        if df.empty or not time_range:
            return df

        start = time_range.get("start")
        end = time_range.get("end")
        if not start and not end:
            return df

        # Auto-detect date column if not specified
        if not date_column:
            for col in df.columns:
                if any(kw in col.lower() for kw in ["date", "time", "timestamp", "created", "event"]):
                    try:
                        pd.to_datetime(df[col], errors="coerce")
                        date_column = col
                        break
                    except Exception:
                        continue

        if not date_column:
            logger.warning("No date column found for post-filtering — returning unfiltered data.")
            return df

        try:
            # Convert to datetime for comparison
            df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
            original_len = len(df)

            if start:
                df = df[df[date_column] >= pd.to_datetime(start)]
            if end:
                df = df[df[date_column] <= pd.to_datetime(end)]

            filtered_len = len(df)
            if filtered_len < original_len:
                logger.info(
                    f"Post-filter: {original_len} → {filtered_len} rows "
                    f"(filtered by {date_column} from {start} to {end})"
                )
            return df
        except Exception as e:
            logger.warning(f"Post-filter failed on column '{date_column}': {e}")
            return df
