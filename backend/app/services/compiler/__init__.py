"""Ontology compiler modules.

P1-01: Compiler five-module split.
- neo4j_emitter: Neo4j constraint generation
- schema_emitter: GraphQL schema generation
- incremental: DAG-based incremental compilation
- compiler: Six-stage pipeline orchestration
"""

from app.services.compiler.compiler import (
    CompilationPipeline,
    compile_ontology,
    compile_object_type,
)
from app.services.compiler.neo4j_emitter import Neo4jEmitter
from app.services.compiler.schema_emitter import SchemaEmitter
from app.services.compiler.incremental import IncrementalCompiler

__all__ = [
    "CompilationPipeline",
    "compile_ontology",
    "compile_object_type",
    "Neo4jEmitter",
    "SchemaEmitter",
    "IncrementalCompiler",
]