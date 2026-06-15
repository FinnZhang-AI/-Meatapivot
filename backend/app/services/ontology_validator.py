"""Dual-stage validator for Ontology definitions.

P0-ONT-02: Static validator (compile-time) + Runtime validator (Pydantic dynamic models).
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from pydantic import create_model, Field, ValidationError

from app.models.ontology_models import OntologyObjectType, OntologyInterface

logger = logging.getLogger(__name__)


class ValidationErrorDetail:
    """Structured validation error."""
    
    def __init__(self, error_kind: str, field: str, detail: str, object_type_id: Optional[str] = None):
        self.error_kind = error_kind
        self.field = field
        self.detail = detail
        self.object_type_id = object_type_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_kind": self.error_kind,
            "field": self.field,
            "detail": self.detail,
            "object_type_id": self.object_type_id,
        }


class StaticValidator:
    """Compile-time static validation.
    
    Validates ontology definitions without executing them:
    - Interface property completeness
    - Link type cardinality validity
    - Duplicate property names within ObjectType
    - Required field presence
    - Neo4j label validity (no spaces, starts with letter)
    """
    
    def __init__(self):
        self.errors: List[ValidationErrorDetail] = []
        self.warnings: List[str] = []
    
    def validate_object_type(self, obj_type: OntologyObjectType) -> List[ValidationErrorDetail]:
        """Validate a single ObjectType definition."""
        errors = []
        
        # Check name
        if not obj_type.name or not obj_type.name.strip():
            errors.append(ValidationErrorDetail(
                error_kind="missing_field",
                field="name",
                detail="ObjectType name is required",
                object_type_id=str(obj_type.id),
            ))
        
        # Check neo4j_label validity
        label = obj_type.neo4j_label or obj_type.name
        if label:
            if not label[0].isalpha():
                errors.append(ValidationErrorDetail(
                    error_kind="invalid_label",
                    field="neo4j_label",
                    detail=f"Neo4j label must start with a letter: '{label}'",
                    object_type_id=str(obj_type.id),
                ))
            if " " in label:
                errors.append(ValidationErrorDetail(
                    error_kind="invalid_label",
                    field="neo4j_label",
                    detail=f"Neo4j label cannot contain spaces: '{label}'",
                    object_type_id=str(obj_type.id),
                ))
        
        # Check for duplicate property names
        if obj_type.properties:
            prop_names = [p.get("name") for p in obj_type.properties if isinstance(p, dict)]
            seen = set()
            for name in prop_names:
                if name in seen:
                    errors.append(ValidationErrorDetail(
                        error_kind="duplicate_property",
                        field=f"properties.{name}",
                        detail=f"Duplicate property name: '{name}'",
                        object_type_id=str(obj_type.id),
                    ))
                seen.add(name)
        
        self.errors.extend(errors)
        return errors
    
    def validate_interface_implementation(
        self,
        obj_type: OntologyObjectType,
        interfaces: List[OntologyInterface],
    ) -> List[ValidationErrorDetail]:
        """Validate that ObjectType implements all required interface properties.
        
        P0-ONT-02: Interface missing property returns error_kind='missing_property' + detail.
        """
        errors = []
        if not obj_type.implemented_interfaces:
            return errors
        
        # Build set of interface IDs this object implements
        interface_ids = set(obj_type.implemented_interfaces)
        
        # Get all properties defined on the object type
        obj_prop_names = set()
        if obj_type.properties:
            for prop in obj_type.properties:
                if isinstance(prop, dict) and "name" in prop:
                    obj_prop_names.add(prop["name"])
        
        # Check each interface
        for interface in interfaces:
            if str(interface.id) not in interface_ids:
                continue
            
            if interface.required_properties:
                for req_prop in interface.required_properties:
                    if isinstance(req_prop, dict):
                        prop_name = req_prop.get("name")
                    else:
                        prop_name = str(req_prop)
                    
                    if prop_name and prop_name not in obj_prop_names:
                        errors.append(ValidationErrorDetail(
                            error_kind="missing_property",
                            field=f"properties.{prop_name}",
                            detail=(
                                f"ObjectType '{obj_type.name}' implements interface "
                                f"'{interface.name}' but missing required property "
                                f"'{prop_name}'"
                            ),
                            object_type_id=str(obj_type.id),
                        ))
        
        self.errors.extend(errors)
        return errors
    
    def validate_link_type(self, link_type) -> List[ValidationErrorDetail]:
        """Validate LinkType definition."""
        errors = []
        
        if not link_type.name or not link_type.name.strip():
            errors.append(ValidationErrorDetail(
                error_kind="missing_field",
                field="name",
                detail="LinkType name is required",
            ))
        
        valid_cardinalities = {"ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_ONE", "MANY_TO_MANY"}
        if link_type.cardinality not in valid_cardinalities:
            errors.append(ValidationErrorDetail(
                error_kind="invalid_value",
                field="cardinality",
                detail=f"Invalid cardinality: '{link_type.cardinality}'. Must be one of: {valid_cardinalities}",
            ))
        
        self.errors.extend(errors)
        return errors
    
    def validate_all(
        self,
        object_types: List[OntologyObjectType],
        link_types: List[Any],
        interfaces: List[OntologyInterface],
    ) -> List[ValidationErrorDetail]:
        """Run all static validations."""
        # Validate object types
        for obj_type in object_types:
            self.validate_object_type(obj_type)
            self.validate_interface_implementation(obj_type, interfaces)
        
        # Validate link types
        for link_type in link_types:
            self.validate_link_type(link_type)
        
        return self.errors


class RuntimeValidator:
    """Runtime validation using dynamically generated Pydantic models.
    
    Creates Pydantic models from ObjectType property definitions and validates
    instance data at runtime.
    """
    
    def __init__(self):
        self._model_cache: Dict[str, Any] = {}
    
    def _get_python_type(self, prop_def: Dict[str, Any]) -> type:
        """Map ontology type to Python type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": bool,
            "datetime": str,  # Store as ISO string
            "uuid": str,
            "json": dict,
            "text": str,
            "enum": str,
        }
        base_type = prop_def.get("base_type", "string")
        return type_mapping.get(base_type, str)
    
    def create_validator(self, obj_type: OntologyObjectType) -> Any:
        """Create a Pydantic model for validating ObjectType instances.
        
        Returns cached model if available.
        """
        cache_key = f"{obj_type.tenant_id}:{obj_type.id}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        fields = {}
        if obj_type.properties:
            for prop in obj_type.properties:
                if not isinstance(prop, dict):
                    continue
                name = prop.get("name")
                if not name:
                    continue
                
                python_type = self._get_python_type(prop)
                is_required = prop.get("required", False)
                default = ... if is_required else prop.get("default", None)
                
                # Add field constraints
                field_kwargs = {}
                if "max_length" in prop:
                    field_kwargs["max_length"] = prop["max_length"]
                if "min_length" in prop:
                    field_kwargs["min_length"] = prop["min_length"]
                if "ge" in prop:
                    field_kwargs["ge"] = prop["ge"]
                if "le" in prop:
                    field_kwargs["le"] = prop["le"]
                
                fields[name] = (Optional[python_type] if not is_required else python_type, Field(default, **field_kwargs))
        
        model_name = f"OntologyValidator_{obj_type.name}_{str(obj_type.id)[:8]}"
        model = create_model(model_name, **fields)
        
        self._model_cache[cache_key] = model
        return model
    
    def validate_instance(
        self,
        obj_type: OntologyObjectType,
        data: Dict[str, Any],
    ) -> Tuple[bool, Optional[List[str]]]:
        """Validate instance data against ObjectType definition.
        
        Returns: (is_valid, list_of_errors)
        """
        try:
            model = self.create_validator(obj_type)
            model(**data)
            return True, None
        except ValidationError as e:
            errors = []
            for err in e.errors():
                field = ".".join(str(x) for x in err["loc"])
                errors.append(f"{field}: {err['msg']}")
            return False, errors
        except Exception as e:
            logger.error(f"Runtime validation error: {e}")
            return False, [str(e)]
    
    def invalidate_cache(self, tenant_id: UUID, obj_type_id: UUID) -> None:
        """Remove cached validator for an object type."""
        cache_key = f"{tenant_id}:{obj_type_id}"
        self._model_cache.pop(cache_key, None)
    
    def clear_cache(self) -> None:
        """Clear all cached validators."""
        self._model_cache.clear()
