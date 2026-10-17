"""Form spec v1: the public document shape of a form (see docs/spec)."""

from common.form_spec.adapters import (
    SpecConversionError,
    form_to_spec,
    form_to_spec_dict,
    spec_to_form,
    spec_trust_settings,
    validation_errors,
)
from common.form_spec.models import SPEC_VERSION, FormSpec

__all__ = [
    "SPEC_VERSION",
    "FormSpec",
    "SpecConversionError",
    "form_to_spec",
    "form_to_spec_dict",
    "spec_to_form",
    "spec_trust_settings",
    "validation_errors",
]
