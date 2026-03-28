"""
Raster processing utilities for geospatial operations.
"""

import logging

import numpy as np
import rasterio
from pyproj import CRS as PyCRS
from rasterio.crs import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject

logger = logging.getLogger(__name__)


def save_geotiff(
    path: str,
    array: np.ndarray,
    crs: CRS,
    transform: rasterio.Affine,
    nodata: float = np.nan,
):
    """
    Save a 2-D numpy array as a single-band GeoTIFF.

    Args:
        path:      Output file path.
        array:     2-D data array.
        crs:       Coordinate reference system (rasterio CRS object).
        transform: Affine transform that maps pixel coords to spatial coords.
        nodata:    Value used to mark missing / invalid pixels (default NaN).
    """
    logger.info(f"Saving GeoTIFF: {path}")

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype=array.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
        compress="lzw",
    ) as dst:
        dst.write(array, 1)

    logger.info(f"Saved: {path} ({array.shape[1]}x{array.shape[0]})")


def reproject_raster(
    src_path: str,
    dst_path: str,
    dst_crs: PyCRS,
    resampling: Resampling = Resampling.nearest,
):
    """
    Reproject a single-band raster to a different CRS.

    Args:
        src_path:   Path to the source raster.
        dst_path:   Path where the reprojected raster will be written.
        dst_crs:    Target CRS (pyproj CRS object).
        resampling: Resampling algorithm (default: nearest-neighbour).
    """
    logger.info(f"Reprojecting {src_path} → {dst_crs}")

    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )

        meta = src.meta.copy()
        meta.update(
            {
                "crs": dst_crs,
                "transform": transform,
                "width": width,
                "height": height,
                "compress": "lzw",
            }
        )

        with rasterio.open(dst_path, "w", **meta) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=resampling,
            )

    logger.info(f"Reprojected: {dst_path}")


def determine_utm_crs(polygon) -> PyCRS:
    """
    Return the most appropriate UTM CRS for a polygon given in WGS84.

    The UTM zone is derived from the longitude of the polygon's centroid.
    Northern-hemisphere polygons get an EPSG code in the 32600 series;
    southern-hemisphere polygons get one in the 32700 series.

    Args:
        polygon: Shapely polygon with coordinates in WGS84 (EPSG:4326).

    Returns:
        pyproj CRS object for the matching UTM zone.
    """
    centroid = polygon.centroid
    utm_zone = int((centroid.x + 180) / 6) + 1
    epsg_code = 32600 + utm_zone if centroid.y >= 0 else 32700 + utm_zone
    utm_crs = PyCRS.from_epsg(epsg_code)

    logger.info(
        f"UTM zone: {utm_zone} ({'North' if centroid.y >= 0 else 'South'}), "
        f"EPSG:{epsg_code}"
    )

    return utm_crs
