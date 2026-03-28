"""
Carbon credit eligibility assessment.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class EligibilityCriterion:
    """Holds the result of a single eligibility check."""

    name: str
    passed: bool
    value: Any
    threshold: Any
    message: str


class EligibilityChecker:
    """Run eligibility checks and aggregate a final pass/fail status."""

    def __init__(self, config: Dict):
        """
        Args:
            config: Eligibility section from config.yaml, e.g.
                    {ndwi_threshold, min_ndvi, min_area_ha, min_coverage_percent}
        """
        self.config = config
        self.criteria: Dict[str, EligibilityCriterion] = {}
        self.status = "PENDING"

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_data_quality(
        self,
        coverage_percent: float,
        min_coverage: Optional[float] = None,
    ) -> bool:
        """Pass if valid-pixel coverage meets the minimum threshold."""
        if min_coverage is None:
            min_coverage = float(self.config.get("min_coverage_percent", 80))

        passed = coverage_percent >= min_coverage
        self.criteria["data_quality"] = EligibilityCriterion(
            name="Data Quality",
            passed=passed,
            value=coverage_percent,
            threshold=min_coverage,
            message=(
                f"Good data coverage ({coverage_percent:.1f}%)"
                if passed
                else f"Insufficient coverage ({coverage_percent:.1f}% < {min_coverage}%)"
            ),
        )
        logger.info(f"Data quality check: {'PASSED' if passed else 'FAILED'}")
        return passed

    def check_hydrological_condition(
        self,
        ndwi_mean: float,
        threshold: Optional[float] = None,
    ) -> bool:
        """Pass if mean NDWI is above the minimum water-availability threshold."""
        if threshold is None:
            threshold = float(self.config.get("ndwi_threshold", -0.4))

        passed = ndwi_mean >= threshold
        self.criteria["hydrology"] = EligibilityCriterion(
            name="Hydrological Condition",
            passed=passed,
            value=ndwi_mean,
            threshold=threshold,
            message=(
                f"Adequate water availability (NDWI: {ndwi_mean:.3f})"
                if passed
                else f"Insufficient water (NDWI: {ndwi_mean:.3f} < {threshold})"
            ),
        )
        logger.info(f"Hydrology check: {'PASSED' if passed else 'FAILED'}")
        return passed

    def check_minimum_biomass(
        self,
        ndvi_mean: float,
        min_ndvi: Optional[float] = None,
    ) -> bool:
        """Pass if mean NDVI indicates sufficient vegetation cover."""
        if min_ndvi is None:
            min_ndvi = float(self.config.get("min_ndvi", 0.3))

        passed = ndvi_mean >= min_ndvi
        self.criteria["biomass"] = EligibilityCriterion(
            name="Minimum Biomass",
            passed=passed,
            value=ndvi_mean,
            threshold=min_ndvi,
            message=(
                f"Sufficient vegetation (NDVI: {ndvi_mean:.3f})"
                if passed
                else f"Insufficient vegetation (NDVI: {ndvi_mean:.3f} < {min_ndvi})"
            ),
        )
        logger.info(f"Biomass check: {'PASSED' if passed else 'FAILED'}")
        return passed

    def check_minimum_area(
        self,
        area_ha: float,
        min_area: Optional[float] = None,
    ) -> bool:
        """Pass if the project area meets the minimum size requirement."""
        if min_area is None:
            min_area = float(self.config.get("min_area_ha", 1.0))

        passed = area_ha >= min_area
        self.criteria["area"] = EligibilityCriterion(
            name="Minimum Area",
            passed=passed,
            value=area_ha,
            threshold=min_area,
            message=(
                f"Area adequate ({area_ha:.2f} ha)"
                if passed
                else f"Area too small ({area_ha:.2f} ha < {min_area} ha)"
            ),
        )
        logger.info(f"Area check: {'PASSED' if passed else 'FAILED'}")
        return passed

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def get_final_status(self) -> str:
        """
        Compute and store the overall eligibility status.

        Returns:
            "ELIGIBLE" if every check passed, otherwise
            "INELIGIBLE (Failed: <check names>)"
        """
        if not self.criteria:
            self.status = "NO CHECKS PERFORMED"
            return self.status

        failed = [c.name for c in self.criteria.values() if not c.passed]
        self.status = (
            "ELIGIBLE" if not failed else f"INELIGIBLE (Failed: {', '.join(failed)})"
        )
        logger.info(f"Final eligibility status: {self.status}")
        return self.status

    def to_dict(self) -> Dict:
        """Serialise all criteria and the final status to a plain dict."""
        return {
            "status": self.status,
            "criteria": {
                key: {
                    "name": c.name,
                    "passed": c.passed,
                    "value": c.value,
                    "threshold": c.threshold,
                    "message": c.message,
                }
                for key, c in self.criteria.items()
            },
            "passed_count": sum(1 for c in self.criteria.values() if c.passed),
            "total_count": len(self.criteria),
        }
