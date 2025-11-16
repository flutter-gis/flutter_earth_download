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
try:
    from scipy.ndimage import binary_dilation, distance_transform_edt
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

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
            
            # INTERPOLATION: Fill missing bands (zeros) from neighboring tiles
            # This helps when a tile is missing IR bands but neighbors have them
            if SCIPY_AVAILABLE and np.any(~mask_valid) and band_idx > 3:  # Only interpolate IR bands and indices (bands 4+), not RGB
                # Find pixels that are zero/missing but have valid neighbors
                missing_mask = ~mask_valid
                
                # Dilate valid pixels to find nearby valid data
                # Use a 5-pixel radius for interpolation (about 25m at 5m resolution)
                dilated_valid = binary_dilation(mask_valid, structure=np.ones((5, 5)))
                interpolation_candidates = missing_mask & dilated_valid
                
                if np.any(interpolation_candidates):
                    # For each missing pixel, find nearest valid pixel and use its value
                    # Use distance transform to find closest valid pixel
                    dist_to_valid = distance_transform_edt(~mask_valid)
                    
                    # Only interpolate if within reasonable distance (20 pixels = 100m)
                    max_interp_dist = 20
                    can_interpolate = (dist_to_valid <= max_interp_dist) & missing_mask
                    
                    if np.any(can_interpolate):
                        # For each pixel to interpolate, find the closest valid pixel
                        # Simple approach: use the value from the nearest valid neighbor
                        # More sophisticated: could use inverse distance weighting
                        for y, x in zip(*np.where(can_interpolate)):
                            # Find nearest valid pixel using distance transform
                            # Get a small window around this pixel
                            y_min = max(0, y - max_interp_dist)
                            y_max = min(out_h, y + max_interp_dist + 1)
                            x_min = max(0, x - max_interp_dist)
                            x_max = min(out_w, x + max_interp_dist + 1)
                            
                            window = mask_valid[y_min:y_max, x_min:x_max]
                            if np.any(window):
                                # Get valid pixels in window
                                valid_y, valid_x = np.where(window)
                                valid_y += y_min
                                valid_x += x_min
                                
                                # Find closest valid pixel
                                distances = np.sqrt((valid_y - y)**2 + (valid_x - x)**2)
                                closest_idx = np.argmin(distances)
                                
                                # Use value from closest valid pixel
                                closest_y, closest_x = valid_y[closest_idx], valid_x[closest_idx]
                                mosaic_band[y, x] = mosaic_band[closest_y, closest_x]
                                mask_valid[y, x] = True  # Mark as valid after interpolation
            
            # Set nodata where no valid data (and couldn't be interpolated)
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


def add_indices_to_mosaic_local(mosaic_path: str) -> str:
    """
    Calculate vegetation and water indices locally from the stitched mosaic.
    This is much faster than calculating on Earth Engine server.
    
    Expected band order: B4 (Red), B3 (Green), B2 (Blue), B8 (NIR), B11 (SWIR1), B12 (SWIR2)
    Adds indices: NDVI, NDWI, MNDWI, EVI, SAVI, FVI, AVI
    
    Returns path to updated mosaic (creates new file with indices appended).
    """
    try:
        # Create temporary output file
        tmp_path = mosaic_path + ".with_indices.tif"
        
        with rasterio.open(mosaic_path, "r") as src:
            # Get band indices by name (check descriptions or assume standard order)
            # Standard order: B4, B3, B2, B8, B11, B12
            band_count = src.count
            
            # Check if we have at least 6 bands (RGB + IR)
            if band_count < 6:
                logging.warning(f"Mosaic has only {band_count} bands, cannot calculate indices. Expected at least 6 bands (B4, B3, B2, B8, B11, B12).")
                return mosaic_path
            
            # Read raw bands (assuming standard order)
            # Band 1 = B4 (Red), Band 2 = B3 (Green), Band 3 = B2 (Blue)
            # Band 4 = B8 (NIR), Band 5 = B11 (SWIR1), Band 6 = B12 (SWIR2)
            b4 = src.read(1).astype(np.float32)  # Red
            b3 = src.read(2).astype(np.float32)  # Green
            b2 = src.read(3).astype(np.float32)  # Blue
            b8 = src.read(4).astype(np.float32)  # NIR
            b11 = src.read(5).astype(np.float32)  # SWIR1
            b12 = src.read(6).astype(np.float32)  # SWIR2
            
            # Handle nodata values
            nodata = src.nodata if src.nodata is not None else 0
            valid_mask = (b4 > 0) & (b3 > 0) & (b2 > 0) & (b8 > 0) & np.isfinite(b4) & np.isfinite(b3) & np.isfinite(b2) & np.isfinite(b8)
            
            indices = []
            
            # NDVI: (NIR - Red) / (NIR + Red)
            ndvi = np.zeros_like(b4, dtype=np.float32)
            denominator = b8 + b4
            valid_ndvi = valid_mask & (denominator > 0)
            ndvi[valid_ndvi] = (b8[valid_ndvi] - b4[valid_ndvi]) / denominator[valid_ndvi]
            ndvi[~valid_ndvi] = nodata
            indices.append(("NDVI", ndvi))
            
            # NDWI: (Green - NIR) / (Green + NIR)
            ndwi = np.zeros_like(b3, dtype=np.float32)
            denominator = b3 + b8
            valid_ndwi = valid_mask & (denominator > 0)
            ndwi[valid_ndwi] = (b3[valid_ndwi] - b8[valid_ndwi]) / denominator[valid_ndwi]
            ndwi[~valid_ndwi] = nodata
            indices.append(("NDWI", ndwi))
            
            # MNDWI: (Green - SWIR1) / (Green + SWIR1)
            if np.any(b11 > 0):
                mndwi = np.zeros_like(b3, dtype=np.float32)
                denominator = b3 + b11
                valid_mndwi = valid_mask & (denominator > 0) & (b11 > 0)
                mndwi[valid_mndwi] = (b3[valid_mndwi] - b11[valid_mndwi]) / denominator[valid_mndwi]
                mndwi[~valid_mndwi] = nodata
                indices.append(("MNDWI", mndwi))
            
            # EVI: 2.5 * ((NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1))
            evi = np.zeros_like(b4, dtype=np.float32)
            denominator = b8 + 6 * b4 - 7.5 * b2 + 1
            valid_evi = valid_mask & (denominator > 0)
            evi[valid_evi] = 2.5 * (b8[valid_evi] - b4[valid_evi]) / denominator[valid_evi]
            evi[~valid_evi] = nodata
            indices.append(("EVI", evi))
            
            # SAVI: ((NIR - Red) / (NIR + Red + L)) * (1 + L), where L = 0.5
            savi = np.zeros_like(b4, dtype=np.float32)
            L = 0.5
            denominator = b8 + b4 + L
            valid_savi = valid_mask & (denominator > 0)
            savi[valid_savi] = ((b8[valid_savi] - b4[valid_savi]) / denominator[valid_savi]) * (1 + L)
            savi[~valid_savi] = nodata
            indices.append(("SAVI", savi))
            
            # FVI: Floating Vegetation Index (NIR - SWIR1) / (NIR + SWIR1)
            if np.any(b11 > 0):
                fvi = np.zeros_like(b8, dtype=np.float32)
                denominator = b8 + b11
                valid_fvi = valid_mask & (denominator > 0) & (b11 > 0)
                fvi[valid_fvi] = (b8[valid_fvi] - b11[valid_fvi]) / denominator[valid_fvi]
                fvi[~valid_fvi] = nodata
                indices.append(("FVI", fvi))
            
            # AVI: Aquatic Vegetation Index (requires NDVI and water index)
            # AVI = NDVI * (1 - |water_index|) for pixels with moderate water presence
            if len(indices) > 0:  # We have at least NDVI
                # Use MNDWI if available, otherwise NDWI
                water_idx = None
                for name, arr in indices:
                    if name == "MNDWI":
                        water_idx = np.abs(arr)
                        break
                if water_idx is None:
                    for name, arr in indices:
                        if name == "NDWI":
                            water_idx = np.abs(arr)
                            break
                
                if water_idx is not None:
                    water_mask = water_idx < 0.3  # Moderate water presence
                    avi = np.zeros_like(ndvi, dtype=np.float32)
                    valid_avi = valid_mask & water_mask
                    avi[valid_avi] = ndvi[valid_avi] * (1 - water_idx[valid_avi])
                    avi[~valid_avi] = nodata
                    indices.append(("AVI", avi))
            
            # Create new file with original bands + indices
            new_count = src.count + len(indices)
            out_profile = src.profile.copy()
            out_profile.update({
                "count": new_count,
                "compress": "LZW",
                "tiled": True,
                "blockxsize": 512,
                "blockysize": 512
            })
            
            # Write all bands (original + indices)
            with rasterio.open(tmp_path, "w", **out_profile) as dst:
                # Write original bands
                for band_idx in range(1, src.count + 1):
                    dst.write(src.read(band_idx), band_idx)
                
                # Write indices (append after original bands)
                next_band_idx = src.count + 1
                for name, index_arr in indices:
                    dst.write(index_arr, next_band_idx)
                    logging.debug(f"Added {name} index to mosaic (band {next_band_idx})")
                    next_band_idx += 1
            
            logging.info(f"Added {len(indices)} indices to mosaic: {[name for name, _ in indices]}")
        
        # Replace original file with new file containing indices
        os.replace(tmp_path, mosaic_path)
        return mosaic_path
            
    except Exception as e:
        logging.warning(f"Error calculating indices locally: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        # Clean up temp file if it exists
        tmp_path = mosaic_path + ".with_indices.tif"
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return mosaic_path


def create_cog(in_tif: str, out_cog: str):
    """Create Cloud-Optimized GeoTIFF (COG) from input GeoTIFF."""
    tmp = out_cog + ".tmp.tif"
    cmd = ["gdal_translate", in_tif, tmp, "-of", "COG", "-co", "COMPRESS=LZW", "-co", "BLOCKSIZE=512"]
    subprocess.run(cmd, check=True)
    cmd2 = ["gdaladdo", "-r", "average", tmp] + [str(x) for x in COG_OVERVIEWS]
    subprocess.run(cmd2, check=True)
    os.replace(tmp, out_cog)
    return out_cog

