"""Persistent FastMCP application context for one Mechanical session manager."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP

from ansys_mechanical_mcp.core.tool_result import ToolResult
from ansys_mechanical_mcp.products.mechanical.selection import (
    capture_current_selection,
    selection_error_result,
)
from ansys_mechanical_mcp.products.mechanical.session import (
    MechanicalDependencyError,
    MechanicalInsecureTransportOptInRequired,
    MechanicalSessionConfigurationError,
    MechanicalSessionConnectError,
    MechanicalSessionError,
    MechanicalSessionManager,
    MechanicalSessionStartError,
    MechanicalTransportCompatibilityError,
    MechanicalTransportConfigurationError,
    MechanicalTransportPreflightError,
)
from ansys_mechanical_mcp.products.mechanical.tools import inspect_mechanical_model
from ansys_mechanical_mcp.products.mechanical.transport import is_loopback_host
from ansys_mechanical_mcp.workflows.cad_import import CadImportConfig, CadImportWorkflow


@dataclass(slots=True)
class MechanicalApplicationContext:
    """Lifespan-owned access to one lazy, serialized Mechanical session."""

    session_manager: MechanicalSessionManager
    cad_import_workflow: CadImportWorkflow
    _operation_lock: RLock = field(default_factory=RLock, repr=False)

    @property
    def session_context(self) -> dict[str, Any]:
        """Return JSON-compatible configured session and ownership facts."""
        return self.session_manager.session_context

    def inspect_model(self) -> ToolResult:
        """Inspect through the persistent session, connecting lazily if needed."""
        with self._operation_lock:
            try:
                session = self.session_manager.start_or_connect()
            except MechanicalSessionError as exc:
                return _session_error_result(exc, self.session_context)
            result = inspect_mechanical_model(session)
            return _with_session_context(result, self.session_context)

    def capture_selection(self) -> ToolResult:
        """Capture current GUI selection without silently launching a new session."""
        with self._operation_lock:
            config = self.session_manager.config
            session_context = self.session_context

            if config.mode is None:
                return selection_error_result(
                    error="MECHANICAL_SESSION_CONFIGURATION_REQUIRED",
                    message=(
                        "Mechanical session mode is not configured. Explicitly choose "
                        "'start' or 'connect' before using a Mechanical tool."
                    ),
                    session_context=session_context,
                )

            if config.interactive is not True:
                return selection_error_result(
                    error="MECHANICAL_SELECTION_INTERACTIVE_SESSION_REQUIRED",
                    message=(
                        "Current selection capture requires a GUI-capable Mechanical session. "
                        "Launch with batch=False or explicitly declare a connected GUI session."
                    ),
                    session_context=session_context,
                    details={"configured_batch": config.effective_batch},
                )

            if config.mode == "start" and self.session_manager.session is None:
                return selection_error_result(
                    error="MECHANICAL_SELECTION_SESSION_NOT_READY",
                    message=(
                        "Selection capture will not start a new empty Mechanical instance. "
                        "Establish the configured GUI session first, then select entities and "
                        "retry."
                    ),
                    session_context=session_context,
                )

            try:
                session = self.session_manager.start_or_connect()
            except MechanicalSessionError as exc:
                code, _ = _session_error(exc)
                return selection_error_result(
                    error=code,
                    message=str(exc),
                    session_context=self.session_context,
                )
            return capture_current_selection(
                session,
                session_context=self.session_context,
            )

    def intake_local_cad(self, input_path: str) -> ToolResult:
        """Inspect one configured local CAD input without touching Mechanical."""
        with self._operation_lock:
            return self.cad_import_workflow.intake(input_path)

    def preview_geometry_import(self, input_path: str, output_project: str) -> ToolResult:
        """Inspect Mechanical and retain a deterministic import plan."""
        with self._operation_lock:
            preflight_error = self.cad_import_workflow.validate_preview_request(
                input_path=input_path,
                output_project=output_project,
            )
            if preflight_error is not None:
                return preflight_error
            session_or_error = self._local_import_session()
            if isinstance(session_or_error, ToolResult):
                return session_or_error
            result = self.cad_import_workflow.preview(
                session_or_error,
                input_path=input_path,
                output_project=output_project,
            )
            return _with_session_context(result, self.session_context)

    def apply_geometry_import(self, plan_id: str) -> ToolResult:
        """Apply one exact retained import plan without automatic retry."""
        with self._operation_lock:
            confirmation_error = self.cad_import_workflow.validate_confirmation(plan_id)
            if confirmation_error is not None:
                return confirmation_error
            session_or_error = self._local_import_session()
            if isinstance(session_or_error, ToolResult):
                return session_or_error
            result = self.cad_import_workflow.apply(session_or_error, plan_id=plan_id)
            return _with_session_context(result, self.session_context)

    def inspect_imported_geometry(self) -> ToolResult:
        """Inspect native geometry through the configured local Mechanical session."""
        with self._operation_lock:
            session_or_error = self._local_import_session()
            if isinstance(session_or_error, ToolResult):
                return session_or_error
            result = self.cad_import_workflow.inspect(session_or_error)
            return _with_session_context(result, self.session_context)

    def _local_import_session(self) -> Any | ToolResult:
        config = self.session_manager.config
        if config.mode == "connect" and not is_loopback_host(config.host or "127.0.0.1"):
            return ToolResult(
                success=False,
                message=(
                    "Stage-1 CAD import accepts only a Mechanical process on the same machine "
                    "as the configured local filesystem roots."
                ),
                data={"session_context": self.session_context},
                error="CAD_IMPORT_LOCAL_SESSION_REQUIRED",
            )
        try:
            return self.session_manager.start_or_connect()
        except MechanicalSessionError as exc:
            return _session_error_result(exc, self.session_context)

    def close(self) -> None:
        """Run the manager's idempotent cleanup under the operation lock."""
        with self._operation_lock:
            self.session_manager.close()


MechanicalLifespan = Callable[
    [FastMCP[MechanicalApplicationContext]],
    AbstractAsyncContextManager[MechanicalApplicationContext],
]


def create_mechanical_lifespan(
    session_manager: MechanicalSessionManager,
    cad_import_config: CadImportConfig | None = None,
) -> MechanicalLifespan:
    """Create a FastMCP lifespan around an injected persistent manager."""

    @asynccontextmanager
    async def app_lifespan(
        _server: FastMCP[MechanicalApplicationContext],
    ) -> AsyncIterator[MechanicalApplicationContext]:
        context = MechanicalApplicationContext(
            session_manager=session_manager,
            cad_import_workflow=CadImportWorkflow(cad_import_config),
        )
        try:
            yield context
        finally:
            # PyMechanical cleanup is synchronous and may involve a remote
            # process. Keep it off the MCP event loop while still waiting for
            # the serialized, idempotent cleanup path to finish.
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(context.close)

    return app_lifespan


def _session_error_result(
    error: MechanicalSessionError,
    session_context: dict[str, Any],
) -> ToolResult:
    code, operation = _session_error(error)
    return ToolResult(
        success=False,
        message=str(error),
        data={"session_context": session_context, "operation": operation},
        error=code,
    )


def _session_error(error: MechanicalSessionError) -> tuple[str, str]:
    if isinstance(error, MechanicalSessionConfigurationError):
        return "MECHANICAL_SESSION_CONFIGURATION_REQUIRED", "configure"
    if isinstance(error, MechanicalDependencyError):
        return "MECHANICAL_DEPENDENCY_MISSING", "load_dependency"
    if isinstance(error, MechanicalInsecureTransportOptInRequired):
        return (
            "MECHANICAL_INSECURE_TRANSPORT_OPT_IN_REQUIRED",
            "acknowledge_insecure_transport",
        )
    if isinstance(error, MechanicalTransportConfigurationError):
        return "MECHANICAL_TRANSPORT_CONFIGURATION_ERROR", "configure_transport"
    if isinstance(error, MechanicalTransportPreflightError):
        return "MECHANICAL_TRANSPORT_PREFLIGHT_FAILED", "preflight_transport"
    if isinstance(error, MechanicalTransportCompatibilityError):
        return "MECHANICAL_TRANSPORT_INCOMPATIBLE", "select_transport"
    if isinstance(error, MechanicalSessionStartError):
        return "MECHANICAL_SESSION_START_FAILED", "start"
    if isinstance(error, MechanicalSessionConnectError):
        return "MECHANICAL_SESSION_CONNECT_FAILED", "connect"
    return "MECHANICAL_SESSION_UNAVAILABLE", "access"


def _with_session_context(result: ToolResult, session_context: dict[str, Any]) -> ToolResult:
    """Add current manager diagnostics without mutating a helper result."""
    return ToolResult(
        success=result.success,
        message=result.message,
        data={**result.data, "session_context": session_context},
        error=result.error,
    )
