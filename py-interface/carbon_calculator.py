"""
Carbon credit calculation with forest type stratification.
"""

import logging
from typing import Dict

import numpy as np
import rasterio
from rasterio.crs import CRS as RasterioCRS
from rasterio.mask import mask as rasterio_mask

logger = logging.getLogger(__name__)


class CarbonCalculator:
    """Calculate carbon credits from NDVI/NDWI rasters with forest type stratification."""

    def __init__(self, config: Dict):
        self.carbon_fraction = config.get("carbon_fraction", 0.48)
        self.co2_to_c_ratio = config.get("co2_to_c_ratio", 3.67)
        self.uncertainty = config.get("uncertainty", 0.15)
        self.biomass_models = config.get("biomass_models", {})

        # Sort once at init — highest priority first.
        # Both classify_forest_type and calculate_from_rasters use the same order,
        # so the index assigned per model is consistent between the two methods.
        self.priority_models = sorted(
            self.biomass_models.items(),
            key=lambda x: x[1].get("priority", 0),
            reverse=True,
        )

    def classify_forest_type(
        self,
        ndvi: np.ndarray,
        ndwi: np.ndarray,
    ) -> np.ndarray:
        """
        Classify each pixel into a forest type using NDVI/NDWI thresholds.

        Returns an int8 array where each value is the index of the matching
        model in self.priority_models, or -1 if unclassified.
        Higher-priority models are assigned first and cannot be overwritten.
        """
        forest_type = np.full(ndvi.shape, fill_value=-1, dtype=np.int8)

        for idx, (type_name, model) in enumerate(self.priority_models):
            ndvi_min = model.get("ndvi_min", -1)
            ndvi_max = model.get("ndvi_max", 1)

            # Build the pixel mask — rename to avoid shadowing rasterio_mask import
            pixel_mask = (
                (ndvi >= ndvi_min)
                & (ndvi < ndvi_max)
                & (forest_type == -1)  # never overwrite an already-classified pixel
            )

            # Additional water-index conditions for forested classes
            if type_name == "dense_forest":
                pixel_mask &= ndwi > -0.2
            elif type_name == "moderate_forest":
                pixel_mask &= ndwi > -0.3

            forest_type[pixel_mask] = idx

        return forest_type

    def calculate_pixel_area(
        self,
        transform: rasterio.Affine,
        crs: RasterioCRS,
    ) -> float:
        """
        Return the area of a single raster pixel in hectares.
        Requires a projected CRS (e.g. UTM) so that units are metres.
        """
        if crs is None or not crs.is_projected:
            raise ValueError(
                "Pixel area calculation requires a projected CRS (e.g. UTM). "
                "Reproject the raster before calling this method."
            )
        pixel_area_m2 = abs(transform.a) * abs(transform.e)
        return pixel_area_m2 / 10_000  # m² → hectares

    def calculate_uncertainty(self, total_co2e: float) -> Dict:
        """Return lower/upper uncertainty bounds around a CO₂e estimate."""
        return {
            "uncertainty_percent": float(self.uncertainty * 100),
            "lower_bound": float(total_co2e * (1 - self.uncertainty)),
            "upper_bound": float(total_co2e * (1 + self.uncertainty)),
            "confidence_interval": f"±{int(self.uncertainty * 100)}%",
        }

    def calculate_from_rasters(
        self,
        ndvi_path: str,
        ndwi_path: str,
        polygon,
    ) -> Dict:
        """
        Calculate carbon credits from UTM-projected NDVI and NDWI rasters.

        Args:
            ndvi_path: Path to the UTM-projected NDVI GeoTIFF.
            ndwi_path: Path to the UTM-projected NDWI GeoTIFF.
            polygon:   Shapely polygon used to mask the rasters (same CRS as rasters).

        Returns:
            Dict with total_area_ha, total_co2e, credits_issued,
            co2e_per_ha, breakdown per forest type, and uncertainty bounds.
        """
        logger.info("Starting carbon calculation from rasters...")

        with rasterio.open(ndvi_path) as ndvi_src, rasterio.open(ndwi_path) as ndwi_src:
            # Clip rasters to the AOI polygon
            ndvi_masked, _ = rasterio_mask(ndvi_src, [polygon], crop=True)
            ndwi_masked, _ = rasterio_mask(ndwi_src, [polygon], crop=True)

            ndvi_data = ndvi_masked[0]
            ndwi_data = ndwi_masked[0]

            # Keep only pixels that are valid in both bands
            valid = ~(np.isnan(ndvi_data) | np.isnan(ndwi_data))
            ndvi_valid = ndvi_data[valid]
            ndwi_valid = ndwi_data[valid]
            logger.info(f"Valid pixels: {len(ndvi_valid):,}")

            # Classify every valid pixel into a forest type
            forest_types = self.classify_forest_type(ndvi_valid, ndwi_valid)

            pixel_area_ha = self.calculate_pixel_area(ndvi_src.transform, ndvi_src.crs)

        # ----------------------------------------------------------------
        # Per-type carbon accounting
        # ----------------------------------------------------------------
        total_co2e = 0.0
        breakdown: Dict = {}

        for idx, (type_name, model) in enumerate(self.priority_models):
            type_mask = forest_types == idx
            count = int(np.sum(type_mask))
            if count == 0:
                continue

            ndvi_type = ndvi_valid[type_mask]

            # Biomass (t/ha) using linear model:  AGB = a * NDVI + b
            a, b = model.get("a", 0), model.get("b", 0)
            agb_array = np.maximum(0.0, a * ndvi_type + b)  # biomass ≥ 0

            # AGB → carbon → CO₂e  (all in t/ha, then scaled by pixel area)
            carbon_array = agb_array * self.carbon_fraction
            co2e_array = carbon_array * self.co2_to_c_ratio

            type_area_ha = count * pixel_area_ha
            type_total_co2e = float(np.sum(co2e_array) * pixel_area_ha)
            total_co2e += type_total_co2e

            breakdown[model["name"]] = {
                "area_ha": float(type_area_ha),
                "pixel_count": count,
                "mean_ndvi": float(np.mean(ndvi_type)),
                "mean_agb_per_ha": float(np.mean(agb_array)),
                "mean_carbon_per_ha": float(np.mean(carbon_array)),
                "mean_co2e_per_ha": float(np.mean(co2e_array)),
                "total_co2e": type_total_co2e,
            }
            logger.info(
                f"{model['name']}: {type_area_ha:.2f} ha, {type_total_co2e:.2f} t CO₂e"
            )

        total_area_ha = len(ndvi_valid) * pixel_area_ha

        results = {
            "total_area_ha": float(total_area_ha),
            "total_co2e": float(total_co2e),
            "credits_issued": int(np.floor(total_co2e)),
            "co2e_per_ha": float(total_co2e / total_area_ha)
            if total_area_ha > 0
            else 0.0,
            "breakdown": breakdown,
            "uncertainty": self.calculate_uncertainty(total_co2e),
        }

        logger.info(
            f"Total: {total_area_ha:.2f} ha, {total_co2e:.2f} t CO₂e, "
            f"{results['credits_issued']} credits"
        )
        return results
