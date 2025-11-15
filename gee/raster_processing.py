"""
Local raster processing functions: validation, masking, stitching, feather blending, and COG creation.
"""
import os
import math
import json
import logging
import shutil
import tempfile
import zipfile
import subprocess
from typing import List, Tuple
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling
from skimage.filters import threshold_otsu
from skimage.morphology import remove_small_objects, binary_closing, disk

from .config import TARGET_RES, MIN_WATER_AREA_PX, COG_OVERVIEWS


def extract_and_merge_zip_tiffs(zip_path: str, out_tif: str) -> bool:
    """
    Extract single-band TIFF files from ZIP and merge into multi-band TIFF.
    GEE sometimes returns ZIP files containing multiple single-band TIFFs.
    Preserves band order based on expected band sequence.
    """
    try:
        extract_dir = tempfile.mkdtemp(prefix="gee_zip_extract_")
        try:
            # Extract ZIP file
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find all TIFF files in extracted directory
            tiff_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.lower().endswith('.tif') or file.lower().endswith('.tiff'):
                        tiff_files.append(os.path.join(root, file))
            
            if not tiff_files:
                logging.warning("No TIFF files found in ZIP archive")
                return False
            
            # Expected band order (based on our selection: RGB, IR, water, vegetation indices)
            band_order = ["B4", "B3", "B2", "B8", "B11", "B12", "MNDWI", "NDWI", 
                         "NDVI", "EVI", "SAVI", "AVI", "FVI", "SR_B4", "SR_B3", "SR_B2", 
                         "SR_B5", "SR_B6", "SR_B7"]
            
            def get_band_priority(filepath):
                """Get priority for band ordering based on filename."""
                filename = os.path.basename(filepath).upper()
                for idx, band_name in enumerate(band_order):
                    if band_name.upper() in filename:
                        return idx
                # If no match, use a high number to sort to end
                return 9999
            
            # Sort files by band priority, then alphabetically
            tiff_files.sort(key=lambda x: (get_band_priority(x), os.path.basename(x)))
            
            # Read all bands and merge into single multi-band TIFF
            bands_data = []
            profile = None
            
            for tiff_file in tiff_files:
                with rasterio.open(tiff_file) as src:
                    if profile is None:
                        # Use first file's profile as template
                        profile = src.profile.copy()
                        profile.update(count=len(tiff_files))
                    
                    # Read band data
                    band_data = src.read(1)  # Read first band
                    bands_data.append(band_data)
            
            # Write merged multi-band TIFF
            with rasterio.open(out_tif, 'w', **profile) as dst:
                for band_idx, band_data in enumerate(bands_data, start=1):
                    dst.write(band_data, band_idx)
            
            logging.debug(f"Extracted and merged {len(tiff_files)} bands from ZIP to {out_tif}")
            return True
            
        finally:
            # Clean up extraction directory
            shutil.rmtree(extract_dir, ignore_errors=True)
            
    except Exception as e:
        logging.warning(f"Error extracting ZIP file: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        return False


def validate_geotiff_local(path: str) -> Tuple[bool, str]:
    """Validate GeoTIFF file is readable and has valid dimensions."""
    try:
        if not os.path.exists(path):
            return False, "file_not_found"
        file_size = os.path.getsize(path)
        if file_size == 0:
            return False, "empty_file"
        if file_size < 1024:  # Less than 1KB is suspicious
            return False, "file_too_small"
        with rasterio.open(path) as src:
            if src.width == 0 or src.height == 0:
                return False, "zero-dim"
            if src.count == 0:
                return False, "no_bands"
            # Try reading a small sample from each band
            for band_idx in range(1, min(src.count + 1, 5)):  # Check first 4 bands
                try:
                    sample = src.read(band_idx, out_shape=(1, min(10, src.height), min(10, src.width)))
                    if sample.size == 0:
                        return False, f"band_{band_idx}_empty"
                except Exception as e:
                    return False, f"band_{band_idx}_read_error: {str(e)}"
            # Check CRS is valid
            if src.crs is None:
                logging.warning("GeoTIFF has no CRS information")
        return True, ""
    except rasterio.errors.RasterioIOError as e:
        return False, f"io_error: {str(e)}"
    except Exception as e:
        return False, f"validation_error: {str(e)}"


def compute_ndwi_mask_local(path: str, ndwi_index: int = -1, min_area_px: int = MIN_WATER_AREA_PX):
    """Compute NDWI-based water mask from local GeoTIFF."""
    with rasterio.open(path) as src:
        arr = src.read().astype(np.float32)
        meta = src.meta.copy()
    if arr.shape[0] == 0:
        raise RuntimeError("no bands")
    ndwi = arr[ndwi_index]
    maxv = ndwi.max()
    if maxv > 2:
        ndwi = ndwi / maxv
    try:
        flat = ndwi[~np.isnan(ndwi)]
        thresh = threshold_otsu(flat)
    except Exception:
        thresh = 0.0
    mask = ndwi >= thresh
    mask = remove_small_objects(mask.astype(bool), min_size=min_area_px)
    # Use 'footprint' for newer scikit-image versions, fallback to 'selem' for older versions
    try:
        mask = binary_closing(mask, footprint=disk(2))
    except TypeError:
        # Fallback for older scikit-image versions
        mask = binary_closing(mask, selem=disk(2))
    return mask.astype(np.uint8), meta


def write_mask(mask_arr: np.ndarray, meta: dict, out_path: str):
    """Write mask array to GeoTIFF file."""
    m = meta.copy()
    m.update(dtype=rasterio.uint8, count=1)
    with rasterio.open(out_path, "w", **m) as dst:
        dst.write(mask_arr[np.newaxis, :, :].astype(rasterio.uint8))


def compute_common_grid(tile_paths: List[str], target_res: int = TARGET_RES):
    """Compute common grid for stitching tiles together."""
    refs = [rasterio.open(p) for p in tile_paths]
    ref = refs[0]
    ref_crs = ref.crs
    minx = min([r.bounds.left for r in refs])
    miny = min([r.bounds.bottom for r in refs])
    maxx = max([r.bounds.right for r in refs])
    maxy = max([r.bounds.top for r in refs])
    if ref_crs and ref_crs.is_geographic:
        center_lat = (miny + maxy) / 2.0
        meters_per_deg = 111320 * math.cos(math.radians(center_lat))
        res_deg = target_res / meters_per_deg
        width = int(math.ceil((maxx - minx) / res_deg))
        height = int(math.ceil((maxy - miny) / res_deg))
        transform = from_origin(minx, maxy, res_deg, res_deg)
        for r in refs: 
            r.close()
        return {"crs": ref_crs, "transform": transform, "width": width, "height": height}
    else:
        width = int(math.ceil((maxx - minx) / target_res))
        height = int(math.ceil((maxy - miny) / target_res))
        transform = from_origin(minx, maxy, target_res, target_res)
        for r in refs: 
            r.close()
        return {"crs": ref_crs, "transform": transform, "width": width, "height": height}


def reproject_to_target(src_path: str, target_meta: dict, out_path: str):
    """
    Reproject a tile to target grid. Memory-efficient: processes bands one at a time
    to avoid loading entire dataset into memory.
    """
    with rasterio.open(src_path) as src:
        dst_profile = src.profile.copy()
        dst_profile.update({
            "crs": target_meta["crs"], 
            "transform": target_meta["transform"], 
            "width": target_meta["width"], 
            "height": target_meta["height"],
            "compress": "LZW",
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512
        })
        
        # Memory-efficient: process bands one at a time instead of loading all at once
        # This prevents memory errors for large tiles
        with rasterio.open(out_path, "w", **dst_profile) as dst:
            for band_idx in range(1, src.count + 1):
                try:
                    # Try cubic resampling first for better quality
                    data = src.read(
                        band_idx,
                        out_shape=(target_meta["height"], target_meta["width"]), 
                        resampling=Resampling.cubic
                    )
                except Exception:
                    # Fallback to bilinear if cubic fails
                    data = src.read(
                        band_idx,
                        out_shape=(target_meta["height"], target_meta["width"]), 
                        resampling=Resampling.bilinear
                    )
                dst.write(data, band_idx)


def feather_and_merge(tile_paths: List[str], out_path: str, feather_px: int = 50):
    """
    Reproject tiles to common grid, create soft weight masks near edges, and blend overlapping pixels
    using normalized weighted sum. Uses memory-efficient band-by-band processing for large datasets.
    """
    if not tile_paths:
        raise ValueError("No tiles")
    grid = compute_common_grid(tile_paths)
    tmpdir = tempfile.mkdtemp(prefix="deadsea_reproj_")
    reprojected = []
    try:
        # Reproject all tiles to common grid
        for i, p in enumerate(tile_paths):
            outp = os.path.join(tmpdir, f"reproj_{i}.tif")
            reproject_to_target(p, grid, outp)
            reprojected.append(outp)
        
        # Open all datasets to get metadata
        datasets = [rasterio.open(p) for p in reprojected]
        count = datasets[0].count
        out_h = grid["height"]
        out_w = grid["width"]
        nodata = datasets[0].nodata
        dtype = datasets[0].dtypes[0]
        
        # Create output metadata
        out_meta = datasets[0].meta.copy()
        out_meta.update({
            "height": out_h, 
            "width": out_w, 
            "transform": grid["transform"], 
            "compress": "LZW", 
            "tiled": True, 
            "blockxsize": 512, 
            "blockysize": 512, 
            "bigtiff": "IF_SAFER",
            "nodata": nodata
        })
        
        # Process band by band for memory efficiency
        mosaic_bands = []
        for band_idx in range(1, count + 1):
            # Initialize accumulation arrays
            numerator = np.zeros((out_h, out_w), dtype=np.float64)
            denominator = np.zeros((out_h, out_w), dtype=np.float64)
            
            # Process each tile
            for i, ds in enumerate(datasets):
                # Read band data
                arr_band = ds.read(band_idx).astype(np.float32)  # (h, w)
                
                # Create valid data mask (handle nodata)
                if nodata is not None:
                    valid_mask = (arr_band != nodata) & (arr_band != 0) & np.isfinite(arr_band)
                else:
                    # If no nodata, check for reasonable values
                    valid_mask = (arr_band > 0) & np.isfinite(arr_band)
                
                # Create distance-based feather weight mask
                tile_h, tile_w = arr_band.shape
                weight = np.ones((tile_h, tile_w), dtype=np.float32)
                
                # Only apply feathering if tile is larger than feather region
                if tile_h > feather_px * 2 and tile_w > feather_px * 2:
                    # Create distance arrays for smoother feathering
                    y_coords, x_coords = np.ogrid[:tile_h, :tile_w]
                    
                    # Calculate distances to edges
                    dist_left = x_coords.astype(np.float32)
                    dist_right = (tile_w - 1 - x_coords).astype(np.float32)
                    dist_top = y_coords.astype(np.float32)
                    dist_bottom = (tile_h - 1 - y_coords).astype(np.float32)
                    
                    # Find minimum distance to any edge
                    dist_to_edge = np.minimum(
                        np.minimum(dist_left, dist_right),
                        np.minimum(dist_top, dist_bottom)
                    )
                    
                    # Apply cosine-based feathering for smoother transition
                    mask = dist_to_edge < feather_px
                    if np.any(mask):
                        # Cosine curve: weight = 0.5 * (1 + cos(π * d / feather_px))
                        feather_dist = dist_to_edge[mask] / feather_px
                        weight[mask] = 0.5 * (1.0 + np.cos(np.pi * feather_dist))
                
                # Combine weight with valid data mask
                final_weight = weight * valid_mask.astype(np.float32)
                
                # Accumulate weighted values
                numerator += (arr_band * final_weight).astype(np.float64)
                denominator += final_weight.astype(np.float64)
            
            # Normalize by sum of weights (avoid division by zero)
            mask_valid = denominator > 0
            mosaic_band = np.zeros((out_h, out_w), dtype=dtype)
            
            if np.any(mask_valid):
                mosaic_band[mask_valid] = (numerator[mask_valid] / denominator[mask_valid]).astype(dtype)
            
            # Set nodata where no valid data
            if nodata is not None:
                mosaic_band[~mask_valid] = nodata
            else:
                mosaic_band[~mask_valid] = 0
            
            mosaic_bands.append(mosaic_band)
        
        # Stack bands and write
        mosaic = np.stack(mosaic_bands, axis=0)
        with rasterio.open(out_path, "w", **out_meta) as dst:
            dst.write(mosaic)
        
        for ds in datasets: 
            ds.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return out_path


def create_cog(in_tif: str, out_cog: str):
    """Create Cloud-Optimized GeoTIFF (COG) from input GeoTIFF."""
    tmp = out_cog + ".tmp.tif"
    cmd = ["gdal_translate", in_tif, tmp, "-of", "COG", "-co", "COMPRESS=LZW", "-co", "BLOCKSIZE=512"]
    subprocess.run(cmd, check=True)
    cmd2 = ["gdaladdo", "-r", "average", tmp] + [str(x) for x in COG_OVERVIEWS]
    subprocess.run(cmd2, check=True)
    os.replace(tmp, out_cog)
    return out_cog

