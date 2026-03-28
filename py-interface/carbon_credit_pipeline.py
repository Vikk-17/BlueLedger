"""
Carbon credit calculation pipeline.
Accepts a GeoJSON geometry dict directly — no file I/O for AOI.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import geopandas as gpd
import rasterio
from carbon_calculator import CarbonCalculator
from config_loader import Config
from data_quality import DataQualityAssessor, calculate_statistics
from eligibility import EligibilityChecker
from raster_processing import determine_utm_crs, reproject_raster, save_geotiff
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from satellite_data import SatelliteDataAcquisition
from sentinelhub.constants import CRS as SentinelCRS
from sentinelhub.geometry import Geometry
from shapely.geometry import shape


def generate_text_report(results: Dict, output_path: Optional[str] = None) -> str:
    lines = [
        "CARBON CREDIT ASSESSMENT REPORT",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        f"Project Name: {results.get('project', {}).get('name', 'N/A')}",
        f"Time Period:  {results.get('project', {}).get('time_period', 'N/A')}",
        "",
        "NDVI Statistics:",
        f"  mean: {results.get('ndvi_stats', {}).get('mean', 0):.4f}",
        "",
        "NDWI Statistics:",
        f"  mean: {results.get('ndwi_stats', {}).get('mean', 0):.4f}",
        "",
        "CARBON CALCULATION",
        f"  Total Area:     {results.get('carbon', {}).get('total_area_ha', 0):.2f} hectares",
        f"  Total CO2e:     {results.get('carbon', {}).get('total_co2e', 0):.2f} tonnes",
        f"  Credits Issued: {results.get('carbon', {}).get('credits_issued', 0)}",
        "",
        "ELIGIBILITY",
        f"  Status: {results.get('eligibility', {}).get('status', 'UNKNOWN')}",
    ]
    report_text = "\n".join(lines)
    if output_path:
        with open(output_path, "w") as f:
            f.write(report_text)
    return report_text


class CarbonCreditPipeline:
    """
    Carbon credit calculation pipeline.

    Usage:
        pipeline = CarbonCreditPipeline()
        results  = pipeline.run(geometry_dict)

    geometry_dict: a GeoJSON geometry object, e.g.
        {"type": "Polygon", "coordinates": [...]}
    """

    def __init__(self, config_path: str = "config.yaml"):
        self.config = Config(config_path)
        self._setup_logging()
        self.logger = logging.getLogger(__name__)

        self.satellite_data = SatelliteDataAcquisition(
            {
                "client_id": self.config.get("sentinel_hub", "client_id"),
                "client_secret": self.config.get("sentinel_hub", "client_secret"),
                "max_retries": self.config.get("processing", "max_retries"),
                "retry_delay_seconds": self.config.get(
                    "processing", "retry_delay_seconds"
                ),
            }
        )

        self.quality_assessor = DataQualityAssessor(
            min_coverage=self.config.get("quality", "min_coverage_percent")
        )
        self.carbon_calculator = CarbonCalculator(self.config.get("carbon_model"))
        self.eligibility_checker = EligibilityChecker(self.config.get("eligibility"))

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, geometry_dict: dict, request_id: str = "") -> Dict:
        """
        Run the full pipeline for the given GeoJSON geometry dict.

        Args:
            geometry_dict: GeoJSON geometry object
                           e.g. {"type": "Polygon", "coordinates": [...]}

        Returns:
            results dict with keys: project, utm_crs, quality,
                                    ndvi_stats, ndwi_stats, carbon, eligibility
        """
        self.start_time = datetime.now()
        self.end_time = None
        self.eligibility_checker.criteria = {}
        self.eligibility_checker.status = "PENDING"
        # Fresh results for every call — no stale data from previous runs
        self.results: Dict[str, Any] = {
            "project": {
                "name": self.config.get("project", "name"),
                "time_period": self.config.get("acquisition", "time_intervals"),
            }
        }

        self.logger.info("Starting Carbon Credit Pipeline")

        try:
            # Step 1 — Parse AOI geometry from the incoming dict
            aoi_polygon = shape(geometry_dict)  # Shapely polygon for UTM / raster work
            gdf = gpd.GeoDataFrame(geometry=[aoi_polygon], crs="EPSG:4326")
            sh_geometry = Geometry(
                geometry_dict, crs=SentinelCRS.WGS84
            )  # Sentinel Hub geometry — accepts raw dict directly

            # Step 2 — Determine UTM CRS for accurate area calculation
            utm_crs = determine_utm_crs(aoi_polygon)
            aoi_utm = gdf.to_crs(utm_crs).geometry.iloc[0]
            self.results["utm_crs"] = str(utm_crs)

            # Step 3 — Download satellite data (NDVI + NDWI)
            ndvi, ndwi = self.satellite_data.get_data(
                geometry=sh_geometry,
                time_intervals=self.config.get("acquisition", "time_intervals"),
                output_size=tuple(self.config.get("acquisition", "output_size")),
            )

            # Step 4 — Assess data quality (cloud/NaN coverage)
            quality = self.quality_assessor.assess_multiple(
                (ndvi, "NDVI"), (ndwi, "NDWI")
            )
            self.results["quality"] = quality
            if not quality["overall_passed"]:
                raise ValueError("Data quality assessment failed")

            # Step 5 — Save WGS84 rasters then reproject to UTM
            output_dir = Path(self.config.get("project", "output_dir")) / (
                request_id or "default"
            )
            output_dir.mkdir(parents=True, exist_ok=True)

            ndvi_wgs84 = output_dir / "ndvi_wgs84.tif"
            ndwi_wgs84 = output_dir / "ndwi_wgs84.tif"

            bounds = sh_geometry.geometry.bounds
            h, w = ndvi.shape
            transform = from_bounds(*bounds, w, h)

            save_geotiff(str(ndvi_wgs84), ndvi, CRS.from_epsg(4326), transform)
            save_geotiff(str(ndwi_wgs84), ndwi, CRS.from_epsg(4326), transform)

            ndvi_utm = output_dir / "ndvi_utm.tif"
            ndwi_utm = output_dir / "ndwi_utm.tif"

            reproject_raster(str(ndvi_wgs84), str(ndvi_utm), utm_crs)
            reproject_raster(str(ndwi_wgs84), str(ndwi_utm), utm_crs)

            # Step 6 — Compute statistics and carbon credits
            ndvi_stats, ndwi_stats = self._calculate_statistics(
                str(ndvi_utm), str(ndwi_utm)
            )
            self.results["ndvi_stats"] = ndvi_stats
            self.results["ndwi_stats"] = ndwi_stats

            carbon = self.carbon_calculator.calculate_from_rasters(
                str(ndvi_utm), str(ndwi_utm), aoi_utm
            )
            self.results["carbon"] = carbon

            # Step 7 — Eligibility checks
            self.eligibility_checker.check_data_quality(
                quality["NDVI"]["coverage_percent"]
            )
            self.eligibility_checker.check_hydrological_condition(ndwi_stats["mean"])
            self.eligibility_checker.check_minimum_biomass(ndvi_stats["mean"])
            self.eligibility_checker.check_minimum_area(carbon["total_area_ha"])
            self.eligibility_checker.get_final_status()
            self.results["eligibility"] = self.eligibility_checker.to_dict()

            # Step 8 — Write text report
            report_path = output_dir / "carbon_credit_report.txt"
            report_text = generate_text_report(self.results, str(report_path))
            print("\n" + report_text)

            self.logger.info("Pipeline completed successfully!")
            return self.results

        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            self.results["error"] = str(e)
            raise

        finally:
            self.end_time = datetime.now()
            self._save_results()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _setup_logging(self):
        log_dir = Path(self.config.get("project", "log_dir"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"carbon_calc_{datetime.now():%Y%m%d_%H%M%S}.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        )
        logging.info(f"Logging initialized: {log_file}")

    def _calculate_statistics(self, ndvi_path: str, ndwi_path: str):
        """Read UTM rasters and return (ndvi_stats, ndwi_stats) dicts."""
        with rasterio.open(ndvi_path) as ndvi_src, rasterio.open(ndwi_path) as ndwi_src:
            return (
                calculate_statistics(ndvi_src.read(1)),
                calculate_statistics(ndwi_src.read(1)),
            )

    def _save_results(self):
        """Persist the results dict to the log directory as JSON."""
        log_dir = Path(self.config.get("project", "log_dir"))
        output_file = log_dir / f"results_{datetime.now():%Y%m%d_%H%M%S}.json"

        payload = {
            "timestamp": self.start_time.isoformat() if self.start_time else None,
            "results": self.results,
        }
        with open(output_file, "w") as f:
            json.dump(payload, f, indent=2, default=str)
