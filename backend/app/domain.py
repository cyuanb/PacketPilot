"""Compatibility imports for the pure review API. Implementations live in app.review."""

from .review.aggregation import assess_results as assess_results
from .review.aggregation import overall as overall
from .review.aggregation import requirements_fingerprint as requirements_fingerprint
from .review.aggregation import review_result as review_result
from .review.checks import check_one as check_one
from .review.checks import run_checks as run_checks
from .review.common import norm as norm
from .review.conditions import condition_value as condition_value
from .review.evidence import excerpts as excerpts
from .review.evidence import verify_evidence as verify_evidence
from .review.fields import field_coverage as field_coverage
from .review.fields import is_placeholder as is_placeholder
from .review.matching import MATERIAL_PROFILES as MATERIAL_PROFILES
from .review.matching import candidates as candidates
from .review.matching import material_identity as material_identity
from .review.version import REVIEW_ENGINE_VERSION as REVIEW_ENGINE_VERSION
