"""
Data quality assessment utilities
"""

import logging
from typing import Dict, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class DataQualityAssessor:
    """Assess quality of satellite imagery data"""

    def __init__(self, min_coverage: float = 80.0):
        """
        Initialize quality assessor

        Args:
            min_coverage: Minimum acceptable coverage percentage
        """
        self.min_coverage = min_coverage

    def assess(self, data: np.ndarray, data_name: str = "data") -> Dict:
        """
        Assess data quality by checking for NaN values and coverage

        Args:
            data: Numpy array to assess
            data_name: Name of the data for logging

        Returns:
            Dictionary with quality metrics
        """
        total_pixels = data.size
        valid_pixels = np.count_nonzero(~np.isnan(data))
        invalid_pixels = total_pixels - valid_pixels
        coverage_percent = (valid_pixels / total_pixels) * 100

        quality = {
            "total_pixels": int(total_pixels),
            "valid_pixels": int(valid_pixels),
            "invalid_pixels": int(invalid_pixels),
            "coverage_percent": float(coverage_percent),
            "passed": bool(coverage_percent >= self.min_coverage),
            "data_name": data_name,
        }

        if quality["passed"]:
            logger.info(
                f"{data_name} quality: {coverage_percent:.1f}% coverage "
                f"({valid_pixels:,} valid pixels) - PASSED"
            )
        else:
            logger.warning(
                f"{data_name} quality: {coverage_percent:.1f}% coverage "
                f"({valid_pixels:,} valid pixels) - FAILED (minimum: {self.min_coverage}%)"
            )

        return quality

    def assess_multiple(self, *datasets: Tuple[np.ndarray, str]) -> Dict:
        """
        Assess multiple datasets

        Args:
            *datasets: Tuples of (array, name)

        Returns:
            Dictionary with quality metrics for each dataset
        """
        results = {}
        all_passed = True

        for data, name in datasets:
            quality = self.assess(data, name)
            results[name] = quality
            all_passed = all_passed and quality["passed"]

        results["overall_passed"] = all_passed

        return results


def calculate_statistics(data: np.ndarray, mask_nans: bool = True) -> Dict:
    """
    Calculate comprehensive statistics for an array

    Args:
        data: Input array
        mask_nans: Whether to ignore NaN values

    Returns:
        Dictionary with statistical metrics
    """
    clean_data = data[~np.isnan(data)]

    if len(clean_data) == 0:
        logger.warning("No valid data for statistics calculation")
        return {
            "count": 0,
            "mean": np.nan,
            "std": np.nan,
            "min": np.nan,
            "max": np.nan,
            "median": np.nan,
            "q25": np.nan,
            "q75": np.nan,
        }

    stats = {
        "count": int(len(clean_data)),
        "mean": float(np.mean(clean_data)),
        "std": float(np.std(clean_data)),
        "min": float(np.min(clean_data)),
        "max": float(np.max(clean_data)),
        "median": float(np.median(clean_data)),
        "q25": float(np.percentile(clean_data, 25)),
        "q75": float(np.percentile(clean_data, 75)),
    }

    return stats
