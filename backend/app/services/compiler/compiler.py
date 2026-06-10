"""Ontology compiler orchestration - coordinates all compilation stages.

P1-01/P1-03/P1-07: Six-stage compilation pipeline:
  1. Load ontology definitions
  2. Build DAG and check for cycles
  3. Run static validation
  4. Generate Neo4j constraints
  5. Generate GraphQL schema
  6. Commit to database

Each stage can halt the pipeline on failure.
"""

import logging
import time
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ontology_models import (
    OntologyObjectType,
    OntologyLinkType,
    OntologyInterface,
    OntologyCompileLog,
    OntologyCurrentVersion,
    ActionExecutionLog,
)
from app.models.ontology_schemas import CompileResult, CompileError
from app.services.compiler.neo4j_emitter import Neo4jEmitter
from app.services.compiler.schema_emitter import SchemaEmitter
from app.services.compiler.incremental import IncrementalCompiler
from app.services.ontology_dag import OntologyDAG
from app.services.ontology_validator import StaticValidator, RuntimeValidator
from app.services.schema_registry import schema_registry
from app.services.ontology_service import OntologyService
from app.services.versioning import compute_next_version, build_diff_snapshot

logger = logging.getLogger(__name__)


class CompilationPipeline:
    """Six-stage compilation pipeline orchestrator."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self.errors: List[CompileError] = []
        self.warnings: List[str] = []
        self.constraints_created = 0
        self._constraints_log: List[str] = []
        self._stage = 0

    # ------------------------------------------------------------------
    # Stage 1: Load
    # ------------------------------------------------------------------

    async def _stage_load(self) -> Tuple[bool, dict]:
        """Stage 1: Load all active ontology definitions."""
        self._stage = 1
        result = await self.db.execute(
            select(OntologyObjectType).where(
                OntologyObjectType.tenant_id == self.tenant_id,
                OntologyObjectType.status == "active",
            )
        )
        object_types = list(result.scalars().all())

        result = await self.db.execute(
            select(OntologyLinkType).where(
                OntologyLinkType.tenant_id == self.tenant_id,
                OntologyLinkType.status == "active",
            )
        )
        link_types = list(result.scalars().all())

        result = await self.db.execute(
            select(OntologyInterface).where(
                OntologyInterface.tenant_id == self.tenant_id,
                OntologyInterface.status == "active",
            )
        )
        interfaces = list(result.scalars().all())

        return True, {
            "object_types": object_types,
            "link_types": link_types,
            "interfaces": interfaces,
            "counts": {
                "object_types": len(object_types),
                "link_types": len(link_types),
                "interfaces": len(interfaces),
            }
        }

    # ------------------------------------------------------------------
    # Stage 2: DAG
    # ------------------------------------------------------------------

    async def _stage_dag(self, context: dict) -> Tuple[bool, dict]:
        """Stage 2: Build DAG and detect cycles."""
        self._stage = 2
        service = OntologyService(self.db, self.tenant_id)
        dag = await service.build_dependency_dag()
        context["dag"] = dag

        cycle = dag.find_cycle()
        if cycle:
            cycle_str = " -> ".join(str(n)[:8] for n in cycle)
            self.errors.append(CompileError(
                code="CYCLE_DETECTED",
                message=f"Circular dependency detected: {cycle_str}",
            ))
            return False, {"cycle": cycle}

        sorted_nodes, _ = dag.topological_sort()
        context["sorted_nodes"] = sorted_nodes
        return True, {"sorted_count": len(sorted_nodes)}

    # ------------------------------------------------------------------
    # Stage 3: Validate
    # ------------------------------------------------------------------

    async def _stage_validate(self, context: dict) -> Tuple[bool, dict]:
        """Stage 3: Static validation."""
        self._stage = 3
        validator = StaticValidator()
        errors = validator.validate_all(
            context["object_types"],
            context["link_types"],
            context["interfaces"],
        )
        validation_errors = [
            CompileError(
                code="VALIDATION_ERROR",
                message=e.get("detail", str(e)),
                field=e.get("field", ""),
            )
            for e in errors
        ]
        if validation_errors:
            self.errors.extend(validation_errors)
            return False, {"validation_errors": len(validation_errors)}

        return True, {"validation_passed": True}

    # ------------------------------------------------------------------
    # Stage 4: Neo4j Constraints
    # ------------------------------------------------------------------

    async def _stage_neo4j(self, context: dict) -> Tuple[bool, dict]:
        """Stage 4: Generate and apply Neo4j constraints."""
        self._stage = 4
        emitter = Neo4jEmitter(self.db, self.tenant_id)
        created = 0

        for ot in context["object_types"]:
            try:
                c, _ = await emitter.emit_constraints_for_object_type(ot)
                created += c
            except Exception as e:
                self.errors.append(CompileError(
                    code="NEO4J_CONSTRAINT_FAILED",
                    message=f"Failed to create constraint for {ot.name}: {str(e)}",
                    field=str(ot.id),
                ))

        self.constraints_created = created
        self._constraints_log = emitter.get_constraints_log()
        context["constraints_created"] = created

        if self.errors:
            return False, {"constraints_created": created}

        return True, {"constraints_created": created}

    # ------------------------------------------------------------------
    # Stage 5: Schema Generation
    # ------------------------------------------------------------------

    async def _stage_schema(self, context: dict) -> Tuple[bool, dict]:
        """Stage 5: Generate GraphQL schema (async, non-blocking)."""
        self._stage = 5
        emitter = SchemaEmitter(self.db, self.tenant_id)
        try:
            schema = await emitter.generate_schema()
            context["graphql_schema"] = schema
            return True, {"schema_length": len(schema)}
        except Exception as e:
            self.warnings.append(f"Schema generation warning: {str(e)}")
            return True, {"schema_length": 0}

    # ------------------------------------------------------------------
    # Stage 6: Commit
    # ------------------------------------------------------------------

    async def _stage_commit(
        self,
        context: dict,
        executed_by: Optional[UUID] = None,
    ) -> Tuple[bool, dict]:
        """Stage 6: Commit compilation log to database.

        P0-ONT-05/P0-ONT-06/P0-ONT-07:
        - Computes next semver version from diff_snapshot
        - Records parent_version for rollback chain
        - Records neo4j_stmts for constraint rollback
        """
        self._stage = 6

        # Compute version from diff
        diff = context.get("diff_snapshot", {})
        current_version = None
        current_row = await self.db.execute(
            select(OntologyCurrentVersion).where(
                OntologyCurrentVersion.tenant_id == self.tenant_id,
            )
        )
        current_row = current_row.scalar_one_or_none()
        if current_row:
            current_version = current_row.version

        next_version, bump_type = compute_next_version(current_version, diff)
        parent_version = current_version

        compile_log = OntologyCompileLog(
            tenant_id=self.tenant_id,
            version=next_version,
            parent_version=parent_version,
            compile_type="full",
            status="running",
            diff_snapshot=diff,
            neo4j_stmts=self._constraints_log.copy(),
            executed_by=executed_by,
        )
        self.db.add(compile_log)
        await self.db.flush()

        try:
            compile_log.status = "success" if not self.errors else "failed"
            compile_log.errors = [e.model_dump() for e in self.errors]
            compile_log.warnings = self.warnings
            compile_log.neo4j_constraints_snapshot = self._constraints_log.copy()
            compile_log.duration_ms = context.get("duration_ms", 0)
            compile_log.completed_at = datetime.utcnow()

            if "sorted_nodes" in context:
                compile_log.affected_types = [str(n) for n in context["sorted_nodes"]]

            await self.db.flush()

            if not self.errors:
                if current_row:
                    current_row.version = next_version
                    current_row.log_id = compile_log.id
                else:
                    current_row = OntologyCurrentVersion(
                        tenant_id=self.tenant_id,
                        version=next_version,
                        log_id=compile_log.id,
                    )
                    self.db.add(current_row)
                await self.db.flush()

            await schema_registry.invalidate(self.tenant_id)

            return True, {"log_id": str(compile_log.id), "version": next_version, "bump_type": bump_type}

        except Exception as e:
            logger.error(f"Commit stage failed: {e}")
            return False, {"commit_error": str(e)}

    # ------------------------------------------------------------------
    # Pipeline Run
    # ------------------------------------------------------------------

    async def run_full(self, executed_by: Optional[UUID] = None) -> CompileResult:
        """Run the full six-stage compilation pipeline.

        P0-ONT-07: If any non-schema stage fails, Neo4j constraints are rolled back
        and PostgreSQL compile log is marked failed. No partial constraints remain.
        """
        start_time = int(time.time() * 1000)
        context = {}

        # Capture pre-compile snapshot for diff
        old_object_types = []
        try:
            result = await self.db.execute(
                select(OntologyObjectType).where(
                    OntologyObjectType.tenant_id == self.tenant_id,
                    OntologyObjectType.status == "active",
                )
            )
            old_object_types = [
                {
                    "id": str(ot.id),
                    "name": ot.name,
                    "display_name": ot.display_name,
                    "description": ot.description,
                    "icon": ot.icon,
                    "properties": ot.properties or [],
                    "implemented_interfaces": ot.implemented_interfaces or [],
                    "neo4j_label": ot.neo4j_label,
                    "status": ot.status,
                }
                for ot in result.scalars().all()
            ]
        except Exception as e:
            logger.warning(f"Failed to capture pre-compile snapshot: {e}")

        stages = [
            ("load", self._stage_load),
            ("dag", self._stage_dag),
            ("validate", self._stage_validate),
            ("neo4j", self._stage_neo4j),
            ("schema", self._stage_schema),
            ("commit", self._stage_commit),
        ]

        halted_stage = None
        for stage_name, stage_fn in stages:
            context["current_stage"] = stage_name
            success, stage_data = await stage_fn(context)

            if stage_name == "commit":
                # Commit stage always runs last; no break needed
                pass
            elif not success and stage_name not in ("schema",):
                halted_stage = stage_name
                break

        duration_ms = int(time.time() * 1000) - start_time
        context["duration_ms"] = duration_ms

        # Build diff snapshot post-compile
        new_object_types = []
        try:
            result = await self.db.execute(
                select(OntologyObjectType).where(
                    OntologyObjectType.tenant_id == self.tenant_id,
                    OntologyObjectType.status == "active",
                )
            )
            new_object_types = [
                {
                    "id": str(ot.id),
                    "name": ot.name,
                    "display_name": ot.display_name,
                    "description": ot.description,
                    "icon": ot.icon,
                    "properties": ot.properties or [],
                    "implemented_interfaces": ot.implemented_interfaces or [],
                    "neo4j_label": ot.neo4j_label,
                    "status": ot.status,
                }
                for ot in result.scalars().all()
            ]
        except Exception as e:
            logger.warning(f"Failed to capture post-compile snapshot: {e}")

        diff = build_diff_snapshot(old_object_types, new_object_types)
        context["diff_snapshot"] = diff

        # P0-ONT-07: Rollback Neo4j constraints if pipeline halted before commit
        if halted_stage and halted_stage != "commit":
            logger.warning(f"Pipeline halted at stage '{halted_stage}'. Rolling back Neo4j constraints.")
            emitter = Neo4jEmitter(self.db, self.tenant_id)
            await emitter.drop_constraints(self._constraints_log)
            self._constraints_log.clear()
            self.errors.append(CompileError(
                code="COMPILE_ROLLED_BACK",
                message=f"Compilation halted at '{halted_stage}'; Neo4j constraints rolled back.",
            ))

        # Re-run commit stage with final diff and duration
        if halted_stage:
            await self._stage_commit(context, executed_by)

        return CompileResult(
            status="compiled" if not self.errors else "has_errors",
            errors=self.errors,
            warnings=self.warnings,
            neo4j_constraints_created=self.constraints_created,
            duration_ms=duration_ms,
        )

    async def run_incremental(
        self,
        object_type_id: UUID,
        executed_by: Optional[UUID] = None,
    ) -> CompileResult:
        """Run incremental compilation for a single type."""
        start_time = int(time.time() * 1000)

        compiler = IncrementalCompiler(self.db, self.tenant_id)
        result = await compiler.incremental_compile(object_type_id, executed_by)

        await schema_registry.invalidate(self.tenant_id, "object_type", object_type_id)

        duration_ms = int(time.time() * 1000) - start_time

        if result["errors"]:
            errors = [
                CompileError(
                    code="INCREMENTAL_COMPILE_ERROR",
                    message=e.get("error", str(e)),
                    field=e.get("object_type_id", ""),
                )
                for e in result["errors"]
            ]
        else:
            errors = []

        return CompileResult(
            status="compiled" if not errors else "has_errors",
            errors=errors,
            warnings=[],
            neo4j_constraints_created=result["constraints_created"],
            duration_ms=duration_ms,
        )


async def compile_ontology(
    db: AsyncSession,
    tenant_id: UUID,
    executed_by: Optional[UUID] = None,
) -> CompileResult:
    """Public API to trigger full Ontology compilation."""
    pipeline = CompilationPipeline(db, tenant_id)
    return await pipeline.run_full(executed_by)


async def compile_object_type(
    db: AsyncSession,
    tenant_id: UUID,
    object_type_id: UUID,
    executed_by: Optional[UUID] = None,
) -> CompileResult:
    """Public API to trigger single Object Type compilation."""
    pipeline = CompilationPipeline(db, tenant_id)
    return await pipeline.run_incremental(object_type_id, executed_by)