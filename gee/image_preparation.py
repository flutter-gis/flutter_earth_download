"""
Image preparation functions for different satellite sensors.
Includes band renaming, NDWI calculation, vegetation indices, and harmonization.
"""
import logging
import ee
from .cloud_detection import s2_cloud_mask_advanced, landsat_cloud_mask_advanced
from .ee_collections import apply_dem_illumination_correction
from .config import HARMONIZATION_COEFFS


def add_vegetation_indices(img):
    """
    Add vegetation indices to image: NDVI, EVI, SAVI, AVI, FVI.
    Also adds aquatic vegetation index for detecting vegetation in water.
    All indices are created only if required bands are available.
    """
    try:
        band_names = img.bandNames().getInfo()
    except Exception:
        return img  # Can't get band names, return image as-is
    
    # NDVI: (NIR - Red) / (NIR + Red) - standard vegetation index
    try:
        if "B8" in band_names and "B4" in band_names:
            ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
            img = img.addBands(ndvi)
    except Exception as e:
        logging.debug(f"Error creating NDVI: {e}")
    
    # EVI: Enhanced Vegetation Index - better for dense vegetation
    # EVI = 2.5 * ((NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1))
    try:
        if "B8" in band_names and "B4" in band_names and "B2" in band_names:
            nir = img.select("B8")
            red = img.select("B4")
            blue = img.select("B2")
            evi = nir.subtract(red).divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1)).multiply(2.5).rename("EVI")
            img = img.addBands(evi)
    except Exception as e:
        logging.debug(f"Error creating EVI: {e}")
    
    # SAVI: Soil-Adjusted Vegetation Index - better for sparse vegetation
    # SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L), where L = 0.5
    try:
        if "B8" in band_names and "B4" in band_names:
            nir = img.select("B8")
            red = img.select("B4")
            L = 0.5
            savi = nir.subtract(red).divide(nir.add(red).add(L)).multiply(1 + L).rename("SAVI")
            img = img.addBands(savi)
    except Exception as e:
        logging.debug(f"Error creating SAVI: {e}")
    
    # Aquatic Vegetation Index (AVI): Detects vegetation in water
    try:
        # Check if NDVI was created (refresh band names)
        current_bands = img.bandNames().getInfo()
        if "NDVI" in current_bands:
            ndvi_band = img.select("NDVI")
            # Use MNDWI if available (better for water), otherwise NDWI
            if "MNDWI" in current_bands:
                water_idx = img.select("MNDWI").abs()
            elif "NDWI" in current_bands:
                water_idx = img.select("NDWI").abs()
            else:
                water_idx = None
            
            if water_idx is not None:
                # AVI: high NDVI AND presence of water (moderate water index, not too high)
                water_mask = water_idx.lt(0.3)  # Moderate water presence
                avi = ndvi_band.multiply(water_mask).multiply(water_idx.multiply(-1).add(1)).rename("AVI")
                img = img.addBands(avi)
    except Exception as e:
        logging.debug(f"Error creating AVI: {e}")
    
    # Floating Vegetation Index (FVI): Specifically for floating aquatic vegetation
    # FVI = (NIR - SWIR1) / (NIR + SWIR1) - only if both bands exist
    try:
        current_bands = img.bandNames().getInfo()
        if "B8" in current_bands and "B11" in current_bands:
            nir = img.select("B8")
            swir1 = img.select("B11")
            # Floating vegetation has high NIR and moderate SWIR
            fvi = nir.subtract(swir1).divide(nir.add(swir1)).rename("FVI")
            img = img.addBands(fvi)
    except Exception as e:
        logging.debug(f"Error creating FVI: {e}")
    
    return img


def harmonize_image(img, mode="S2_to_LS"):
    """Harmonize image between sensor types using linear transforms."""
    coeff = HARMONIZATION_COEFFS.get(mode)
    if not coeff:
        return img
    a = coeff["a"]
    b = coeff["b"]
    # apply to visible and IR bands if present (B4/B3/B2/B8/B11/B12)
    try:
        b4 = img.select("B4").multiply(a).add(b)
        b3 = img.select("B3").multiply(a).add(b)
        b2 = img.select("B2").multiply(a).add(b)
        
        # Harmonize IR bands too
        harmonized_bands = [b4, b3, b2]
        band_names = img.bandNames().getInfo()
        
        if "B8" in band_names:
            b8 = img.select("B8").multiply(a).add(b)
            harmonized_bands.append(b8)
        if "B11" in band_names:
            b11 = img.select("B11").multiply(a).add(b)
            harmonized_bands.append(b11)
        if "B12" in band_names:
            b12 = img.select("B12").multiply(a).add(b)
            harmonized_bands.append(b12)
        
        rest = img.select(img.bandNames().removeAll(["B4","B3","B2","B8","B11","B12"]))
        return ee.Image.cat(harmonized_bands + [rest])
    except Exception:
        return img


def s2_prepare_image(img):
    """Server-side S2 prep: add NDWI, MNDWI, IR bands, vegetation indices, and advanced cloud masking."""
    img2 = img
    
    # Check available bands first
    try:
        band_names = img2.bandNames().getInfo()
    except Exception:
        band_names = []
    
    # Calculate NDWI (Green-NIR) - standard water index
    # Only create if required bands exist
    if "B3" in band_names and "B8" in band_names:
        try:
            ndwi = img2.normalizedDifference(["B3","B8"]).rename("NDWI")
            img2 = img2.addBands(ndwi)
        except Exception as e:
            logging.debug(f"Error creating Sentinel-2 NDWI: {e}")
    
    # Calculate MNDWI (Modified NDWI) - better for water detection: (Green-SWIR1)/(Green+SWIR1)
    # Only create if SWIR1 exists
    if "B3" in band_names and "B11" in band_names:
        try:
            mndwi = img2.normalizedDifference(["B3","B11"]).rename("MNDWI")
            img2 = img2.addBands(mndwi)
        except Exception as e:
            logging.debug(f"Error creating Sentinel-2 MNDWI: {e}")
    
    # Rename IR bands to unified naming: B8 (NIR), B11 (SWIR1), B12 (SWIR2)
    # Sentinel-2 already uses these names, but ensure they're present
    try:
        band_names = img2.bandNames().getInfo()
        # B8 (NIR) should already exist, but ensure it's named correctly
        if "B8" not in band_names:
            # Try to find NIR band
            if "B8A" in band_names:
                img2 = img2.select(["B4","B3","B2","B8A","B11","B12"]).rename(["B4","B3","B2","B8","B11","B12"])
    except Exception:
        pass
    
    # Use advanced cloud masking
    img2 = s2_cloud_mask_advanced(img2)
    img2 = apply_dem_illumination_correction(img2)
    
    # Add vegetation indices
    img2 = add_vegetation_indices(img2)
    
    return img2


def landsat_prepare_image(img):
    """Server-side Landsat prep: advanced cloud masking, NDWI/MNDWI, IR bands, and vegetation indices."""
    img = landsat_cloud_mask_advanced(img)
    
    # Check available bands first to determine Landsat version
    try:
        band_names = img.bandNames().getInfo()
    except Exception:
        band_names = []
    
    # Add NDWI/MNDWI and IR bands - handle different Landsat versions
    try:
        # Check if this is Landsat 8/9 (has SR_B bands) or older Landsat (has B bands or SR_B but no SR_B6)
        has_sr_bands = any("SR_B" in b for b in band_names)
        has_sr_b1 = "SR_B1" in band_names  # Landsat 4/5 have SR_B1, Landsat 8/9 don't
        has_sr_b6 = "SR_B6" in band_names
        has_sr_b5 = "SR_B5" in band_names
        has_sr_b7 = "SR_B7" in band_names
        
        if has_sr_bands:
            if has_sr_b1:
                # Landsat 4/5 Collection 2: SR_B1=Blue, SR_B2=Green, SR_B3=Red, SR_B4=NIR, SR_B5=SWIR1, SR_B7=SWIR2
                # Add NDWI: (Green - NIR) / (Green + NIR)
                if "SR_B2" in band_names and "SR_B4" in band_names:
                    ndwi = img.normalizedDifference(["SR_B2","SR_B4"]).rename("NDWI")
                    img = img.addBands(ndwi)
                
                # MNDWI: (Green - SWIR1) / (Green + SWIR1)
                if "SR_B2" in band_names and "SR_B5" in band_names:
                    try:
                        mndwi = img.normalizedDifference(["SR_B2","SR_B5"]).rename("MNDWI")
                        img = img.addBands(mndwi)
                    except Exception:
                        pass
                
                # Rename and add IR bands to unified naming: B8 (NIR), B11 (SWIR1), B12 (SWIR2)
                try:
                    if "SR_B4" in band_names:  # NIR
                        nir = img.select("SR_B4").rename("B8")
                        img = img.addBands(nir)
                    
                    if "SR_B5" in band_names:  # SWIR1
                        swir1 = img.select("SR_B5").rename("B11")
                        img = img.addBands(swir1)
                    
                    if "SR_B7" in band_names:  # SWIR2
                        swir2 = img.select("SR_B7").rename("B12")
                        img = img.addBands(swir2)
                except Exception as e:
                    logging.debug(f"Error adding IR bands for Landsat 4/5: {e}")
                    pass
            else:
                # Landsat 8/9 or Landsat 7 Collection 2 (has SR_B bands but no SR_B1)
                # Add NDWI: (Green - NIR) / (Green + NIR)
                if "SR_B3" in band_names and "SR_B5" in band_names:
                    ndwi = img.normalizedDifference(["SR_B3","SR_B5"]).rename("NDWI")
                    img = img.addBands(ndwi)
                
                # MNDWI: (Green - SWIR1) / (Green + SWIR1) - only if SWIR1 exists
                if "SR_B3" in band_names and has_sr_b6:
                    try:
                        mndwi = img.normalizedDifference(["SR_B3","SR_B6"]).rename("MNDWI")
                        img = img.addBands(mndwi)
                    except Exception:
                        pass  # SWIR1 might not be available (Landsat 5)
                
                # Rename and add IR bands to unified naming: B8 (NIR), B11 (SWIR1), B12 (SWIR2)
                try:
                    # Landsat 8/9: SR_B5 = NIR, SR_B6 = SWIR1, SR_B7 = SWIR2
                    # Landsat 7 Collection 2: SR_B5 = NIR, SR_B7 = SWIR2 (no SR_B6)
                    if has_sr_b5:
                        nir = img.select("SR_B5").rename("B8")
                        img = img.addBands(nir)
                    
                    if has_sr_b6:
                        swir1 = img.select("SR_B6").rename("B11")
                        img = img.addBands(swir1)
                    
                    if has_sr_b7:
                        swir2 = img.select("SR_B7").rename("B12")
                        img = img.addBands(swir2)
                except Exception as e:
                    logging.debug(f"Error adding IR bands in landsat_prepare_image: {e}")
                    pass
        else:
            # Older Landsat (L5/L7) with original band names (B1, B2, B3, etc.)
            # Add NDWI: (Green - NIR) / (Green + NIR)
            # For older Landsat: B2 = Green, B4 = NIR
            if "B2" in band_names and "B4" in band_names:
                ndwi = img.normalizedDifference(["B2","B4"]).rename("NDWI")
                img = img.addBands(ndwi)
            
            # Older Landsat: B4 = NIR, B5 = SWIR1, B7 = SWIR2
            try:
                if "B4" in band_names:
                    nir = img.select("B4").rename("B8")
                    img = img.addBands(nir)
                if "B5" in band_names:
                    swir1 = img.select("B5").rename("B11")
                    img = img.addBands(swir1)
                if "B7" in band_names:
                    swir2 = img.select("B7").rename("B12")
                    img = img.addBands(swir2)
            except Exception:
                pass
    except Exception as e:
        logging.debug(f"Error in landsat_prepare_image NDWI/IR setup: {e}")
        pass
    
    # Rename RGB bands to unified names if needed
    try:
        band_names = img.bandNames().getInfo()
        has_sr_b1 = "SR_B1" in band_names
        
        if has_sr_b1:
            # Landsat 4/5 Collection 2: SR_B1=Blue, SR_B2=Green, SR_B3=Red
            if "SR_B1" in band_names and "B2" not in band_names:
                blue = img.select("SR_B1").rename("B2")
                img = img.addBands(blue)
            if "SR_B2" in band_names and "B3" not in band_names:
                green = img.select("SR_B2").rename("B3")
                img = img.addBands(green)
            if "SR_B3" in band_names and "B4" not in band_names:
                red = img.select("SR_B3").rename("B4")
                img = img.addBands(red)
        else:
            # Landsat 8/9 Collection 2: SR_B2=Blue, SR_B3=Green, SR_B4=Red
            if "SR_B4" in band_names and "B4" not in band_names:
                red = img.select("SR_B4").rename("B4")
                green = img.select("SR_B3").rename("B3")
                blue = img.select("SR_B2").rename("B2")
                img = img.addBands([red, green, blue])
    except Exception:
        pass
    
    img = apply_dem_illumination_correction(img)
    
    # Add vegetation indices
    img = add_vegetation_indices(img)
    
    return img


def prepare_modis_image(img):
    """Prepare MODIS image: add NDWI, IR bands, and cloud mask."""
    try:
        # MODIS uses different band names: Red=1, NIR=2, Blue=3, Green=4, SWIR=6, SWIR2=7
        # Quality band: state_1km
        # Cloud mask from state_1km band
        qa = img.select("state_1km")
        cloud_mask = qa.bitwiseAnd(1 << 0).eq(0)  # Bit 0 = cloud
        img = img.updateMask(cloud_mask)
        
        # Check available bands explicitly
        band_names = img.bandNames().getInfo()
        
        # Add NDWI: (Green - NIR) / (Green + NIR) using MODIS bands
        if "sur_refl_b04" in band_names and "sur_refl_b02" in band_names:
            green = img.select("sur_refl_b04")  # Band 4 = Green
            nir = img.select("sur_refl_b02")    # Band 2 = NIR
            ndwi = green.subtract(nir).divide(green.add(nir)).rename("NDWI")
            img = img.addBands(ndwi)
        
        # Select RGB equivalent bands: Red=1, Green=4, Blue=3
        # Scale from 0-10000 to 0-1 for consistency
        required_rgb = ["sur_refl_b01", "sur_refl_b04", "sur_refl_b03"]
        if all(b in band_names for b in required_rgb):
            red = img.select("sur_refl_b01").multiply(0.0001).rename("B4")
            green_band = img.select("sur_refl_b04").multiply(0.0001).rename("B3")
            blue = img.select("sur_refl_b03").multiply(0.0001).rename("B2")
            
            # Add IR bands: NIR=2, SWIR1=6, SWIR2=7
            if "sur_refl_b02" in band_names:
                nir_band = img.select("sur_refl_b02").multiply(0.0001).rename("B8")
                
                # Check for SWIR bands explicitly
                has_swir1 = "sur_refl_b06" in band_names
                has_swir2 = "sur_refl_b07" in band_names
                
                bands_to_cat = [red, green_band, blue, nir_band]
                
                if has_swir1:
                    swir1 = img.select("sur_refl_b06").multiply(0.0001).rename("B11")
                    bands_to_cat.append(swir1)
                
                if has_swir2:
                    swir2 = img.select("sur_refl_b07").multiply(0.0001).rename("B12")
                    bands_to_cat.append(swir2)
                
                # Add NDWI if it was created
                if "NDWI" in img.bandNames().getInfo():
                    bands_to_cat.append(img.select("NDWI"))
                
                img = ee.Image.cat(bands_to_cat)
            else:
                # Missing NIR - can't create proper image
                logging.warning("MODIS image missing NIR band (sur_refl_b02)")
                return img
        else:
            logging.warning(f"MODIS image missing required RGB bands. Available: {band_names}")
            return img
        
        # Add vegetation indices
        img = add_vegetation_indices(img)
    except Exception as e:
        logging.warning(f"Error preparing MODIS image: {e}")
    return img


def prepare_aster_image(img):
    """Prepare ASTER image: add NDWI, IR bands, and basic processing."""
    try:
        # Check available bands explicitly
        band_names = img.bandNames().getInfo()
        
        # ASTER bands: VNIR_Band3N (Red/NIR), VNIR_Band2 (Green), VNIR_Band1 (Blue)
        required_vnir = ["VNIR_Band1", "VNIR_Band2", "VNIR_Band3N"]
        if not all(b in band_names for b in required_vnir):
            logging.debug(f"ASTER image missing required VNIR bands. Available: {band_names}")
            return img
        
        green = img.select("VNIR_Band2")
        nir_proxy = img.select("VNIR_Band3N")
        ndwi = green.subtract(nir_proxy).divide(green.add(nir_proxy)).rename("NDWI")
        img = img.addBands(ndwi)
        
        # Select and rename RGB bands
        red = img.select("VNIR_Band3N").rename("B4")
        green_band = img.select("VNIR_Band2").rename("B3")
        blue = img.select("VNIR_Band1").rename("B2")
        
        # ASTER has limited IR bands - use VNIR_Band3N as NIR proxy
        nir_band = img.select("VNIR_Band3N").rename("B8")
        
        # ASTER has SWIR bands in SWIR sensor, but they're at different resolution
        # Check for SWIR bands explicitly
        has_swir1 = "SWIR_Band4" in band_names
        has_swir2 = "SWIR_Band6" in band_names
        
        bands_to_cat = [red, green_band, blue, nir_band]
        
        if has_swir1:
            swir1 = img.select("SWIR_Band4").rename("B11")
            bands_to_cat.append(swir1)
        else:
            logging.debug("ASTER image missing SWIR_Band4 (SWIR1)")
        
        if has_swir2:
            swir2 = img.select("SWIR_Band6").rename("B12")
            bands_to_cat.append(swir2)
        else:
            logging.debug("ASTER image missing SWIR_Band6 (SWIR2)")
        
        # Add NDWI
        bands_to_cat.append(img.select("NDWI"))
        
        img = ee.Image.cat(bands_to_cat)
        
        # Add vegetation indices
        img = add_vegetation_indices(img)
    except Exception as e:
        logging.warning(f"Error preparing ASTER image: {e}")
    return img


def prepare_spot_image(img):
    """
    Prepare SPOT image: standardize bands, add NDWI/MNDWI, and apply cloud masking.
    SPOT bands: XS1 (Green), XS2 (Red), XS3 (NIR) for SPOT 1-3
                B1 (Green), B2 (Red), B3 (NIR), MIR (SWIR) for SPOT 4
    Maps to standard: B3 (Green), B4 (Red), B8 (NIR), B11 (SWIR if available)
    """
    try:
        band_names = img.bandNames().getInfo()
    except Exception:
        band_names = []
    
    # SPOT 1-3 use XS bands, SPOT 4 uses B bands and has MIR (SWIR)
    has_xs = any("XS" in b for b in band_names)
    has_spot4_bands = any(b in ["B1", "B2", "B3", "MIR"] for b in band_names)
    
    # Map bands to standard names
    standardized_bands = []
    
    if has_xs:
        # SPOT 1-3: XS1=Green, XS2=Red, XS3=NIR (all 20m)
        if "XS1" in band_names:
            standardized_bands.append(img.select("XS1").rename("B3"))  # Green
        if "XS2" in band_names:
            standardized_bands.append(img.select("XS2").rename("B4"))  # Red
        if "XS3" in band_names:
            standardized_bands.append(img.select("XS3").rename("B8"))  # NIR
        
        # SPOT doesn't have blue band - create placeholder or use green approximation
        if "XS1" in band_names:
            standardized_bands.append(img.select("XS1").multiply(0.9).rename("B2"))  # Blue approximation from Green
    elif has_spot4_bands:
        # SPOT 4: B1=Green, B2=Red, B3=NIR, MIR=SWIR (all 20m)
        if "B1" in band_names:
            standardized_bands.append(img.select("B1").rename("B3"))  # Green
        if "B2" in band_names:
            standardized_bands.append(img.select("B2").rename("B4"))  # Red
        if "B3" in band_names:
            standardized_bands.append(img.select("B3").rename("B8"))  # NIR
        if "MIR" in band_names:
            standardized_bands.append(img.select("MIR").rename("B11"))  # SWIR1
        
        # Blue band approximation
        if "B1" in band_names:
            standardized_bands.append(img.select("B1").multiply(0.9).rename("B2"))  # Blue approximation
    
    # If no SPOT bands found, return original (shouldn't happen)
    if not standardized_bands:
        return img
    
    # Combine standardized bands
    img2 = ee.Image.cat(standardized_bands)
    
    # Add missing bands as masked placeholders (for compatibility)
    current_bands = img2.bandNames().getInfo()
    if "B12" not in current_bands:
        # SPOT doesn't have SWIR2 - add masked placeholder
        img2 = img2.addBands(ee.Image.constant(0).rename("B12").updateMask(ee.Image(0)))
    
    # Add NDWI: (Green - NIR) / (Green + NIR)
    try:
        if "B3" in current_bands and "B8" in current_bands:
            ndwi = img2.normalizedDifference(["B3", "B8"]).rename("NDWI")
            img2 = img2.addBands(ndwi)
    except Exception:
        pass
    
    # Add MNDWI: (Green - SWIR) / (Green + SWIR) - only if SWIR available
    try:
        current_bands = img2.bandNames().getInfo()
        if "B3" in current_bands and "B11" in current_bands:
            mndwi = img2.normalizedDifference(["B3", "B11"]).rename("MNDWI")
            img2 = img2.addBands(mndwi)
    except Exception:
        pass
    
    # SPOT doesn't have built-in cloud masks like Landsat/Sentinel
    # Use simple threshold on visible bands as basic cloud detection
    try:
        # Simple cloud mask: high reflectance in visible bands
        if "B4" in current_bands and "B3" in current_bands:
            cloud_score = img2.select("B4").add(img2.select("B3")).divide(2)
            cloud_mask = cloud_score.lt(0.6)  # Threshold - adjust as needed
            img2 = img2.updateMask(cloud_mask)
    except Exception:
        pass
    
    # Add vegetation indices
    img2 = add_vegetation_indices(img2)
    
    return img2


def prepare_landsat_mss_image(img):
    """
    Prepare Landsat MSS image: standardize bands, add NDWI/MNDWI, and apply basic cloud masking.
    Landsat MSS bands: Band 4 (Green), Band 5 (Red), Band 6 (NIR), Band 7 (NIR2/SWIR approximation)
    Maps to standard: B3 (Green), B4 (Red), B8 (NIR), B11 (SWIR approximation from Band 7)
    Note: MSS has 60m resolution, lower than TM/ETM+ (30m)
    """
    try:
        band_names = img.bandNames().getInfo()
    except Exception:
        band_names = []
    
    # Landsat MSS Collection 1: B4=Green, B5=Red, B6=NIR, B7=NIR2
    # Map to standard names
    standardized_bands = []
    
    # Check if this is MSS Collection 1 or 2 (band naming may differ)
    # Collection 1 uses: B1, B2, B3, B4 (but MSS uses different numbering)
    # Collection 2 MSS uses: SR_B1, SR_B2, SR_B3, SR_B4
    has_sr = any("SR_B" in b for b in band_names)
    
    if has_sr:
        # MSS Collection 2: SR_B1=Green, SR_B2=Red, SR_B3=NIR, SR_B4=NIR2
        if "SR_B1" in band_names:
            standardized_bands.append(img.select("SR_B1").rename("B3"))  # Green
        if "SR_B2" in band_names:
            standardized_bands.append(img.select("SR_B2").rename("B4"))  # Red
        if "SR_B3" in band_names:
            standardized_bands.append(img.select("SR_B3").rename("B8"))  # NIR
        if "SR_B4" in band_names:
            standardized_bands.append(img.select("SR_B4").rename("B11"))  # Use NIR2 as SWIR approximation
        
        # MSS doesn't have blue band - use green approximation
        if "SR_B1" in band_names:
            standardized_bands.append(img.select("SR_B1").multiply(0.85).rename("B2"))  # Blue approximation
    else:
        # MSS Collection 1 or raw: Try standard MSS band names (B1-B4 or different)
        # MSS uses: Band 4, 5, 6, 7 in sensor, but may be named differently in collection
        if "B1" in band_names:
            standardized_bands.append(img.select("B1").rename("B3"))  # Assume B1=Green
        if "B2" in band_names:
            standardized_bands.append(img.select("B2").rename("B4"))  # Assume B2=Red
        if "B3" in band_names:
            standardized_bands.append(img.select("B3").rename("B8"))  # Assume B3=NIR
        if "B4" in band_names:
            standardized_bands.append(img.select("B4").rename("B11"))  # Assume B4=NIR2/SWIR
        
        # Blue approximation
        if "B1" in band_names:
            standardized_bands.append(img.select("B1").multiply(0.85).rename("B2"))
    
    # If no MSS bands found, return original
    if not standardized_bands:
        return img
    
    # Combine standardized bands
    img2 = ee.Image.cat(standardized_bands)
    
    # Add missing bands as masked placeholders
    current_bands = img2.bandNames().getInfo()
    if "B12" not in current_bands:
        # MSS doesn't have SWIR2 - add masked placeholder
        img2 = img2.addBands(ee.Image.constant(0).rename("B12").updateMask(ee.Image(0)))
    
    # Add NDWI: (Green - NIR) / (Green + NIR)
    try:
        if "B3" in current_bands and "B8" in current_bands:
            ndwi = img2.normalizedDifference(["B3", "B8"]).rename("NDWI")
            img2 = img2.addBands(ndwi)
    except Exception:
        pass
    
    # Add MNDWI: (Green - SWIR) / (Green + SWIR) - using Band 7 as SWIR approximation
    try:
        current_bands = img2.bandNames().getInfo()
        if "B3" in current_bands and "B11" in current_bands:
            mndwi = img2.normalizedDifference(["B3", "B11"]).rename("MNDWI")
            img2 = img2.addBands(mndwi)
    except Exception:
        pass
    
    # Basic cloud masking for MSS (similar to SPOT - simple threshold)
    try:
        if "B4" in current_bands and "B3" in current_bands:
            cloud_score = img2.select("B4").add(img2.select("B3")).divide(2)
            cloud_mask = cloud_score.lt(0.6)  # Threshold
            img2 = img2.updateMask(cloud_mask)
    except Exception:
        pass
    
    # Add vegetation indices
    img2 = add_vegetation_indices(img2)
    
    return img2


def prepare_noaa_avhrr_image(img):
    """
    Prepare NOAA AVHRR image: standardize bands, add NDWI, and basic processing.
    AVHRR has very coarse resolution (1km) and limited bands.
    AVHRR bands: Channel 1 (Red), Channel 2 (NIR), Channel 3 (Thermal), Channel 4 (Thermal), Channel 5 (Thermal)
    Maps to standard: B4 (Red), B8 (NIR), B11/B12 (approximations from thermal if needed)
    Note: AVHRR is ABSOLUTE LAST RESORT due to very low resolution.
    """
    try:
        band_names = img.bandNames().getInfo()
    except Exception:
        band_names = []
    
    # AVHRR NDVI product typically has: NDVI, brightness, greenness, wetness, or raw channels
    # Check for common AVHRR band names
    standardized_bands = []
    
    # AVHRR NDVI product may have NDVI directly, or we need to compute from channels
    # Try to find Red and NIR channels
    has_ndvi = "NDVI" in band_names
    has_ch1 = "ch1" in band_names or "Channel_1" in band_names or "B1" in band_names
    has_ch2 = "ch2" in band_names or "Channel_2" in band_names or "B2" in band_names
    
    if has_ndvi:
        # If NDVI is available, we can approximate Red and NIR
        # This is a rough approximation - AVHRR is last resort anyway
        ndvi = img.select("NDVI")
        # Very rough approximation: assume moderate NDVI and derive bands
        # This is not ideal but AVHRR is only used when nothing else is available
        standardized_bands.append(ndvi.multiply(0.5).add(0.3).rename("B4"))  # Red approximation
        standardized_bands.append(ndvi.multiply(0.5).add(0.4).rename("B3"))  # Green approximation
        standardized_bands.append(ndvi.multiply(0.4).add(0.3).rename("B2"))  # Blue approximation
        standardized_bands.append(ndvi.multiply(0.6).add(0.5).rename("B8"))  # NIR approximation
    elif has_ch1 and has_ch2:
        # AVHRR Channel 1 (Red) and Channel 2 (NIR)
        ch1 = img.select([b for b in band_names if "ch1" in b.lower() or "channel_1" in b.lower() or b == "B1"][0])
        ch2 = img.select([b for b in band_names if "ch2" in b.lower() or "channel_2" in b.lower() or b == "B2"][0])
        standardized_bands.append(ch1.rename("B4"))  # Red
        standardized_bands.append(ch1.multiply(0.9).rename("B3"))  # Green approximation
        standardized_bands.append(ch1.multiply(0.8).rename("B2"))  # Blue approximation
        standardized_bands.append(ch2.rename("B8"))  # NIR
    else:
        # Fallback: use first available band as proxy
        if band_names:
            proxy = img.select(band_names[0])
            standardized_bands.append(proxy.rename("B4"))  # Red
            standardized_bands.append(proxy.multiply(0.9).rename("B3"))  # Green
            standardized_bands.append(proxy.multiply(0.8).rename("B2"))  # Blue
            standardized_bands.append(proxy.multiply(1.1).rename("B8"))  # NIR
    
    # AVHRR doesn't have SWIR bands - add masked placeholders
    if not standardized_bands:
        # If we couldn't map any bands, return original (shouldn't happen)
        return img
    
    img2 = ee.Image.cat(standardized_bands)
    
    # Add missing SWIR bands as masked placeholders
    current_bands = img2.bandNames().getInfo()
    if "B11" not in current_bands:
        img2 = img2.addBands(ee.Image.constant(0).rename("B11").updateMask(ee.Image(0)))
    if "B12" not in current_bands:
        img2 = img2.addBands(ee.Image.constant(0).rename("B12").updateMask(ee.Image(0)))
    
    # Add NDWI: (Green - NIR) / (Green + NIR)
    try:
        if "B3" in current_bands and "B8" in current_bands:
            ndwi = img2.normalizedDifference(["B3", "B8"]).rename("NDWI")
            img2 = img2.addBands(ndwi)
    except Exception:
        pass
    
    # Basic cloud masking for AVHRR (simple threshold)
    try:
        if "B4" in current_bands and "B3" in current_bands:
            cloud_score = img2.select("B4").add(img2.select("B3")).divide(2)
            cloud_mask = cloud_score.lt(0.7)  # More lenient threshold for AVHRR
            img2 = img2.updateMask(cloud_mask)
    except Exception:
        pass
    
    # Add basic vegetation indices
    img2 = add_vegetation_indices(img2)
    
    return img2


def prepare_viirs_image(img):
    """Prepare VIIRS image: add NDWI, IR bands, and cloud mask."""
    try:
        # Check available bands explicitly
        band_names = img.bandNames().getInfo()
        
        # VIIRS quality band: QF1
        if "QF1" in band_names:
            qa = img.select("QF1")
            cloud_mask = qa.bitwiseAnd(1 << 0).eq(0)
            img = img.updateMask(cloud_mask)
        
        # VIIRS bands: I1=Red, I2=NIR, I3=Blue, M3=Green, M11=SWIR1, M12=SWIR2
        required_bands = ["I1", "I2", "I3", "M3"]
        if not all(b in band_names for b in required_bands):
            logging.warning(f"VIIRS image missing required bands. Available: {band_names}")
            return img
        
        green = img.select("M3")
        nir = img.select("I2")
        ndwi = green.subtract(nir).divide(green.add(nir)).rename("NDWI")
        img = img.addBands(ndwi)
        
        # Select RGB: I1=Red, M3=Green, I3=Blue
        red = img.select("I1").rename("B4")
        green_band = img.select("M3").rename("B3")
        blue = img.select("I3").rename("B2")
        nir_band = img.select("I2").rename("B8")
        
        # Check for SWIR bands explicitly
        has_swir1 = "M11" in band_names
        has_swir2 = "M12" in band_names
        
        bands_to_cat = [red, green_band, blue, nir_band]
        
        if has_swir1:
            swir1 = img.select("M11").rename("B11")
            bands_to_cat.append(swir1)
        else:
            logging.debug("VIIRS image missing M11 band (SWIR1)")
        
        if has_swir2:
            swir2 = img.select("M12").rename("B12")
            bands_to_cat.append(swir2)
        else:
            logging.debug("VIIRS image missing M12 band (SWIR2)")
        
        # Add NDWI
        bands_to_cat.append(img.select("NDWI"))
        
        img = ee.Image.cat(bands_to_cat)
        
        # Add vegetation indices
        img = add_vegetation_indices(img)
    except Exception as e:
        logging.warning(f"Error preparing VIIRS image: {e}")
    return img

