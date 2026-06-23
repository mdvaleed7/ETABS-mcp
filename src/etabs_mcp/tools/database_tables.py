"""
Database Tables tools — powerful API for reading/writing all ETABS tables.

Tools:
  - etabs_get_available_tables
  - etabs_get_table_data
  - etabs_set_table_data
  - etabs_apply_table_edits
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from etabs_mcp.etabs_connection import get_connection
from etabs_mcp.helpers import check_ret, error_response, success_response, to_python_list


def register(mcp: FastMCP) -> None:
    """Register database table tools on the MCP server."""

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_available_tables() -> str:
        """Get a list of all available database tables in the ETABS model.

        Returns:
            JSON array of table names. Use these names in get_table_data.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.DatabaseTables.GetAllTables(0, [], [], [])
            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response("Failed to get available tables.")

            num = ret[1]
            table_names = to_python_list(ret[3])
            
            # Optionally we could return ret[2] which are the table keys, but names are usually more readable.
            # Some functions need the table key. We'll return both.
            table_keys = to_python_list(ret[2])
            
            tables = []
            for i in range(num):
                tables.append({"name": table_names[i], "key": table_keys[i]})

            return success_response(tables, message=f"Found {num} tables.")
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    def etabs_get_table_data(
        table_key: str,
        group_name: str = "",
    ) -> str:
        """Get the contents of a specific database table.

        Args:
            table_key: The internal key of the table (from get_available_tables).
            group_name: Optional group name to filter results (default "" means all).

        Returns:
            JSON object containing table fields and row data.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            # GetTableForDisplayArray signature:
            # TableKey, FieldKeyList, GroupName, TableVersion, FieldsKeysIncluded, NumberRecords, TableData
            ret = sm.DatabaseTables.GetTableForDisplayArray(
                table_key, [], group_name, 0, [], 0, []
            )
            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response(f"Failed to get data for table '{table_key}'.")

            fields = to_python_list(ret[4])
            num_records = ret[5]
            data = to_python_list(ret[6])
            
            num_fields = len(fields)
            if num_fields == 0 or num_records == 0:
                return success_response({"fields": [], "rows": []}, message="Table is empty.")

            rows = []
            for i in range(num_records):
                row = {}
                for j in range(num_fields):
                    idx = i * num_fields + j
                    row[fields[j]] = data[idx] if idx < len(data) else None
                rows.append(row)

            return success_response(
                {"table_key": table_key, "fields": fields, "rows": rows},
                message=f"Retrieved {num_records} rows from '{table_key}'.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_set_table_data(
        table_key: str,
        fields: list[str],
        data_rows: list[list[str]],
    ) -> str:
        """Set data in a specific database table (for interactive editing).

        Note: You must call etabs_apply_table_edits after setting data for it to take effect.

        Args:
            table_key: The internal key of the table.
            fields: List of field keys (column names).
            data_rows: List of rows, where each row is a list of string values corresponding to the fields.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            # Flatten data_rows into a 1D array as expected by ETABS
            flat_data = []
            for row in data_rows:
                if len(row) != len(fields):
                    return error_response("All rows must have the same number of elements as 'fields'.")
                flat_data.extend(row)

            table_version = 0
            ret = sm.DatabaseTables.SetTableForEditingArray(
                table_key, table_version, fields, len(data_rows), flat_data
            )
            if isinstance(ret, tuple):
                check_ret(ret[0], "DatabaseTables.SetTableForEditingArray")
            else:
                check_ret(ret, "DatabaseTables.SetTableForEditingArray")

            return success_response(
                {"table_key": table_key, "rows_added": len(data_rows)},
                message="Table edits staged. Call etabs_apply_table_edits to apply.",
            )
        except Exception as exc:
            return error_response(str(exc))

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
    )
    def etabs_apply_table_edits() -> str:
        """Apply all pending database table edits to the model.

        Returns:
            Confirmation.
        """
        try:
            conn = get_connection()
            conn.ensure_connected()
            sm = conn.sap_model

            ret = sm.DatabaseTables.ApplyEditedTables(False, 0, 0, 0, "")
            if not isinstance(ret, tuple) or ret[0] != 0:
                return error_response("Failed to apply table edits.")

            num_fatal = ret[1]
            num_error = ret[2]
            num_warn = ret[3]
            num_info = ret[4]
            import_log = ret[5]

            msg = "Table edits applied."
            if num_fatal > 0 or num_error > 0:
                msg = f"Table edits applied with {num_error} errors and {num_fatal} fatal errors."
                
            return success_response(
                {
                    "fatal_errors": num_fatal,
                    "errors": num_error,
                    "warnings": num_warn,
                    "info_messages": num_info,
                    "log_file": import_log,
                },
                message=msg,
            )
        except Exception as exc:
            return error_response(str(exc))
