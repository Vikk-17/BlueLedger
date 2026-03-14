"""
Satellite data acquisition from Sentinel Hub
"""

import numpy as np
import time
from typing import List, Tuple
import logging

from sentinelhub import (
    SHConfig,
    SentinelHubRequest,
    DataCollection,
    MimeType,
    Geometry
)

logger = logging.getLogger(__name__)

class SatelliteDataAcquisition:
    """Handle satellite data requests"""
    
    def __init__(self, config: dict):
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay_seconds', 5)
        
        self.sh_config = SHConfig()
        self.sh_config.sh_client_id = config.get('client_id')
        self.sh_config.sh_client_secret = config.get('client_secret')
        
        if not self.sh_config.sh_client_id or not self.sh_config.sh_client_secret:
            raise ValueError(
                "Sentinel Hub credentials not set. "
                "Please set SENTINEL_HUB_CLIENT_ID and SENTINEL_HUB_CLIENT_SECRET "
                "environment variables."
            )
            
    def get_evalscript(self) -> str:
        return """
        //VERSION=3
        function setup() {
          return {
            input: ["B03", "B04", "B08", "SCL"],
            output: { bands: 2, sampleType: "FLOAT32" }
          };
        }

        function evaluatePixel(sample) {
          if (sample.SCL == 3 || sample.SCL == 8 || sample.SCL == 9 || sample.SCL == 10) {
            return [NaN, NaN];
          }
          let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
          let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);
          return [ndvi, ndwi];
        }
        """
    
    def request_data(self, geometry: Geometry, time_interval: tuple, output_size: tuple) -> Tuple[np.ndarray, np.ndarray]:
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Requesting Sentinel-2 data for {time_interval[0]} to {time_interval[1]} (Attempt {attempt+1})")
                request = SentinelHubRequest(
                    evalscript=self.get_evalscript(),
                    input_data=[
                        SentinelHubRequest.input_data(
                            data_collection=DataCollection.SENTINEL2_L2A,
                            time_interval=time_interval,
                            mosaicking_order="leastCC"
                        )
                    ],
                    responses=[
                        SentinelHubRequest.output_response("default", MimeType.TIFF)
                    ],
                    geometry=geometry,
                    size=output_size,
                    config=self.sh_config
                )
                data = request.get_data()[0]
                logger.info(f"Successfully downloaded {data.shape[1]}x{data.shape[0]} raster.")
                return data[:, :, 0], data[:, :, 1]
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise

    def get_data(self, geometry: Geometry, time_intervals: List[tuple], output_size: tuple) -> Tuple[np.ndarray, np.ndarray]:
        ndvi_list, ndwi_list = [], []
        logger.info(f"Starting acquisition for {len(time_intervals)} time intervals...")
        for interval in time_intervals:
            try:
                ndvi, ndwi = self.request_data(geometry, interval, output_size)
                ndvi_list.append(ndvi)
                ndwi_list.append(ndwi)
            except Exception as e:
                logger.error(f"Failed to get data for interval {interval}: {e}")
                continue
        
        if not ndvi_list:
            raise ValueError("No data successfully retrieved for any time interval")
            
        logger.info(f"Creating median composite from {len(ndvi_list)} images...")
        ndvi_stack = np.stack(ndvi_list, axis=0)
        ndwi_stack = np.stack(ndwi_list, axis=0)
        
        return np.nanmedian(ndvi_stack, axis=0), np.nanmedian(ndwi_stack, axis=0)
