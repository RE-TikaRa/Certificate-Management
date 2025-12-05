"""
Audit logging system for tracking user operations and changes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any


class OperationType(str, Enum):
    """Types of operations that are audited."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    IMPORT = "import"
    EXPORT = "export"
    BACKUP = "backup"
    RESTORE = "restore"
    SEARCH = "search"


class EntityType(str, Enum):
    """Types of entities that are audited."""

    AWARD = "award"
    MEMBER = "member"
    TAG = "tag"
    ATTACHMENT = "attachment"
    BACKUP = "backup"
    SETTINGS = "settings"


class AuditLogger:
    """
    Centralized audit logging for user operations.
    Provides structured logging of all significant user actions.
    """

    def __init__(self, logger_name: str = "audit"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

    def log_operation(
        self,
        operation: OperationType | str,
        entity: EntityType | str,
        entity_id: int | str,
        details: dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """
        Log a single entity operation.

        Args:
            operation: Type of operation (create, update, delete, etc.)
            entity: Type of entity (award, member, etc.)
            entity_id: ID of the entity
            details: Additional details about the operation
            success: Whether operation succeeded
            error: Error message if failed
        """
        details = details or {}
        timestamp = datetime.now().isoformat()

        op_str = operation.value if isinstance(operation, OperationType) else operation
        entity_str = entity.value if isinstance(entity, EntityType) else entity
        message = f"AUDIT: {op_str} {entity_str}#{entity_id}"

        if success:
            self.logger.info(
                f"{message} | time={timestamp} | details={details}",
            )
        else:
            self.logger.error(
                f"{message} | time={timestamp} | error={error} | details={details}",
            )

    def log_bulk_operation(
        self,
        operation: OperationType | str,
        entity: EntityType | str,
        count: int,
        details: dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """
        Log a bulk operation affecting multiple entities.

        Args:
            operation: Type of operation
            entity: Type of entity
            count: Number of entities affected
            details: Additional details
            success: Whether operation succeeded
            error: Error message if failed
        """
        details = details or {}
        timestamp = datetime.now().isoformat()

        op_str = operation.value if isinstance(operation, OperationType) else operation
        entity_str = entity.value if isinstance(entity, EntityType) else entity
        message = f"AUDIT_BULK: {op_str} ×{count} {entity_str}s"

        if success:
            self.logger.warning(
                f"{message} | time={timestamp} | details={details}",
            )
        else:
            self.logger.error(
                f"{message} | time={timestamp} | error={error} | details={details}",
            )

    def log_import(
        self,
        file_path: str,
        total: int,
        success_count: int,
        failed_count: int,
        errors: list[str] | None = None,
    ) -> None:
        """
        Log an import operation.

        Args:
            file_path: Path to imported file
            total: Total records in file
            success_count: Number of successfully imported records
            failed_count: Number of failed records
            errors: List of error messages
        """
        errors = errors or []
        timestamp = datetime.now().isoformat()

        self.logger.warning(
            f"AUDIT_IMPORT: {file_path} | time={timestamp} | "
            f"total={total} | success={success_count} | failed={failed_count} | "
            f"errors={len(errors)} | details={errors[:5]}",  # Log first 5 errors
        )

    def log_export(
        self,
        file_path: str,
        entity: EntityType | str,
        record_count: int,
        size_mb: float,
    ) -> None:
        """
        Log an export operation.

        Args:
            file_path: Path to exported file
            entity: Type of entity exported
            record_count: Number of records exported
            size_mb: Size of exported file in MB
        """
        timestamp = datetime.now().isoformat()

        self.logger.info(
            f"AUDIT_EXPORT: {file_path} | time={timestamp} | "
            f"entity={entity.value if isinstance(entity, EntityType) else entity} | "
            f"records={record_count} | size={size_mb:.2f}MB",
        )

    def log_backup(
        self,
        backup_path: str,
        size_mb: float,
        include_attachments: bool,
        include_logs: bool,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """
        Log a backup operation.

        Args:
            backup_path: Path to backup file
            size_mb: Size of backup file in MB
            include_attachments: Whether attachments were included
            include_logs: Whether logs were included
            success: Whether backup succeeded
            error: Error message if failed
        """
        timestamp = datetime.now().isoformat()
        status = "success" if success else "failed"

        self.logger.warning(
            f"AUDIT_BACKUP: {backup_path} | time={timestamp} | "
            f"status={status} | size={size_mb:.2f}MB | "
            f"attachments={include_attachments} | logs={include_logs} | "
            f"error={error or 'none'}",
        )

    def log_data_modification(
        self,
        operation: str,
        entity: str,
        count: int,
        details: str = "",
    ) -> None:
        """
        Log significant data modifications (bulk updates, batch deletes, etc.).

        Args:
            operation: Description of operation
            entity: Entity type
            count: Number of records affected
            details: Additional details
        """
        timestamp = datetime.now().isoformat()

        self.logger.warning(
            f"AUDIT_DATA_CHANGE: {operation} | time={timestamp} | "
            f"entity={entity} | affected={count} | details={details}",
        )

    def log_performance_issue(
        self,
        operation: str,
        duration_ms: float,
        threshold_ms: float = 1000,
    ) -> None:
        """
        Log slow operations that exceed performance threshold.

        Args:
            operation: Description of operation
            duration_ms: Actual duration in milliseconds
            threshold_ms: Performance threshold in milliseconds
        """
        if duration_ms > threshold_ms:
            self.logger.warning(
                f"AUDIT_SLOW: {operation} | duration={duration_ms:.2f}ms | threshold={threshold_ms}ms",
            )

    def log_error_recovery(
        self,
        error_type: str,
        operation: str,
        recovery_action: str,
        success: bool = True,
    ) -> None:
        """
        Log error recovery and mitigation actions.

        Args:
            error_type: Type of error that occurred
            operation: Operation that failed
            recovery_action: Action taken to recover
            success: Whether recovery succeeded
        """
        timestamp = datetime.now().isoformat()
        status = "recovered" if success else "recovery_failed"

        self.logger.error(
            f"AUDIT_ERROR_RECOVERY: {error_type} | time={timestamp} | "
            f"operation={operation} | recovery={recovery_action} | status={status}",
        )


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
