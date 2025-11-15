"""
Image preparation functions for different satellite sensors.
Includes band renaming, NDWI calculation, vegetation indices, and harmonization.
"""
import ee
from .cloud_detection import s2_cloud_mask_advanced, landsat_cloud_mask_advanced
from .ee_collections import apply_dem_illumination_correction
from .config import HARMONIZATION_COEFFS


def add_vegetation_indices(img):
    """
    Add vegetation indices to image: NDVI, EVI, SAVI.
    Also adds aquatic vegetation index for detecting vegetation in water.
    """
    try:
        band_names = img.bandNames().getInfo()
        
        # NDVI: (NIR - Red) / (NIR + Red) - standard vegetation index
        try:
            if "B8" in band_names and "B4" in band_names:
                ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
                img = img.addBands(ndvi)
        except Exception:
            pass
        
        # EVI: Enhanced Vegetation Index - better for dense vegetation
        # EVI = 2.5 * ((NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1))
        try:
            if "B8" in band_names and "B4" in band_names and "B2" in band_names:
                nir = img.select("B8")
                red = img.select("B4")
                blue = img.select("B2")
                evi = nir.subtract(red).divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1)).multiply(2.5).rename("EVI")
                img = img.addBands(evi)
        except Exception:
            pass
        
        # SAVI: Soil-Adjusted Vegetation Index - better for sparse vegetation
        # SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L), where L = 0.5
        try:
            if "B8" in band_names and "B4" in band_names:
                nir = img.select("B8")
                red = img.select("B4")
                L = 0.5
                savi = nir.subtract(red).divide(nir.add(red).add(L)).multiply(1 + L).rename("SAVI")
                img = img.addBands(savi)
        except Exception:
            pass
        
        # Aquatic Vegetation Index (AVI): Detects vegetation in water
        try:
            if "NDVI" in img.bandNames().getInfo():
                ndvi_band = img.select("NDVI")
                # Use MNDWI if available (better for water), otherwise NDWI
                if "MNDWI" in band_names:
                    water_idx = img.select("MNDWI").abs()
                elif "NDWI" in band_names:
                    water_idx = img.select("NDWI").abs()
                else:
                    water_idx = None
                
                if water_idx is not None:
                    # AVI: high NDVI AND presence of water (moderate water index, not too high)
                    water_mask = water_idx.lt(0.3)  # Moderate water presence
                    avi = ndvi_band.multiply(water_mask).multiply(water_idx.multiply(-1).add(1)).rename("AVI")
                    img = img.addBands(avi)
        except Exception:
            pass
        
        # Floating Vegetation Index (FVI): Specifically for floating aquatic vegetation
        try:
            if "B8" in band_names and "B11" in band_names:
                nir = img.select("B8")
                swir1 = img.select("B11")
                # Floating vegetation has high NIR and moderate SWIR
                fvi = nir.subtract(swir1).divide(nir.add(swir1)).rename("FVI")
                img = img.addBands(fvi)
        except Exception:
            pass
        
    except Exception:
        pass
    
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
    # Calculate NDWI (Green-NIR) - standard water index
    ndwi = img2.normalizedDifference(["B3","B8"]).rename("NDWI")
    # Calculate MNDWI (Modified NDWI) - better for water detection: (Green-SWIR1)/(Green+SWIR1)
    try:
        mndwi = img2.normalizedDifference(["B3","B11"]).rename("MNDWI")
        img2 = img2.addBands(mndwi)
    except Exception:
        pass  # SWIR1 might not be available
    img2 = img2.addBands(ndwi)
    
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
    # Add NDWI - try different band combinations
    try:
        # For Landsat 8/9: use Green (SR_B3) and SWIR1 (SR_B6) for MNDWI, or NIR (SR_B5) for NDWI
        ndwi = img.normalizedDifference(["SR_B3","SR_B5"]).rename("NDWI")
        # MNDWI: (Green - SWIR1) / (Green + SWIR1) - better for water
        try:
            mndwi = img.normalizedDifference(["SR_B3","SR_B6"]).rename("MNDWI")
            img = img.addBands(mndwi)
        except Exception:
            pass
        img = img.addBands(ndwi)
        
        # Rename and add IR bands to unified naming: B8 (NIR), B11 (SWIR1), B12 (SWIR2)
        try:
            # Landsat 8/9: SR_B5 = NIR, SR_B6 = SWIR1, SR_B7 = SWIR2
            nir = img.select("SR_B5").rename("B8")
            swir1 = img.select("SR_B6").rename("B11")
            swir2 = img.select("SR_B7").rename("B12")
            img = img.addBands([nir, swir1, swir2])
        except Exception:
            pass
    except Exception:
        try:
            # Fallback for older Landsat (L5/L7)
            ndwi = img.normalizedDifference(["B3","B5"]).rename("NDWI")
            img = img.addBands(ndwi)
            
            # Older Landsat: B4 = NIR, B5 = SWIR1, B7 = SWIR2
            try:
                nir = img.select("B4").rename("B8")
                swir1 = img.select("B5").rename("B11")
                swir2 = img.select("B7").rename("B12")
                img = img.addBands([nir, swir1, swir2])
            except Exception:
                pass
        except Exception:
            pass
    
    # Rename RGB bands to unified names if needed
    try:
        band_names = img.bandNames().getInfo()
        if "SR_B4" in band_names and "B4" not in band_names:
            # Rename Landsat 8/9 bands to unified names
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
        
        # Add NDWI: (Green - NIR) / (Green + NIR) using MODIS bands
        green = img.select("sur_refl_b04")  # Band 4 = Green
        nir = img.select("sur_refl_b02")    # Band 2 = NIR
        ndwi = green.subtract(nir).divide(green.add(nir)).rename("NDWI")
        img = img.addBands(ndwi)
        
        # Select RGB equivalent bands: Red=1, Green=4, Blue=3
        # Scale from 0-10000 to 0-1 for consistency
        red = img.select("sur_refl_b01").multiply(0.0001).rename("B4")
        green_band = img.select("sur_refl_b04").multiply(0.0001).rename("B3")
        blue = img.select("sur_refl_b03").multiply(0.0001).rename("B2")
        
        # Add IR bands: NIR=2, SWIR1=6, SWIR2=7
        nir_band = img.select("sur_refl_b02").multiply(0.0001).rename("B8")
        try:
            swir1 = img.select("sur_refl_b06").multiply(0.0001).rename("B11")
            swir2 = img.select("sur_refl_b07").multiply(0.0001).rename("B12")
            img = ee.Image.cat([red, green_band, blue, nir_band, swir1, swir2, img.select("NDWI")])
        except Exception:
            # If SWIR not available, just include NIR
            img = ee.Image.cat([red, green_band, blue, nir_band, img.select("NDWI")])
        
        # Add vegetation indices
        img = add_vegetation_indices(img)
    except Exception:
        pass
    return img


def prepare_aster_image(img):
    """Prepare ASTER image: add NDWI, IR bands, and basic processing."""
    try:
        # ASTER bands: VNIR_Band3N (Red/NIR), VNIR_Band2 (Green), VNIR_Band1 (Blue)
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
        try:
            # Try to get SWIR bands if available
            swir1 = img.select("SWIR_Band4").rename("B11")
            swir2 = img.select("SWIR_Band6").rename("B12")
            img = ee.Image.cat([red, green_band, blue, nir_band, swir1, swir2, img.select("NDWI")])
        except Exception:
            # If SWIR not available, just include NIR
            img = ee.Image.cat([red, green_band, blue, nir_band, img.select("NDWI")])
        
        # Add vegetation indices
        img = add_vegetation_indices(img)
    except Exception:
        pass
    return img


def prepare_viirs_image(img):
    """Prepare VIIRS image: add NDWI, IR bands, and cloud mask."""
    try:
        # VIIRS quality band: QF1
        qa = img.select("QF1")
        cloud_mask = qa.bitwiseAnd(1 << 0).eq(0)
        img = img.updateMask(cloud_mask)
        
        # VIIRS bands: I1=Red, I2=NIR, I3=Blue, M3=Green, M11=SWIR1, M12=SWIR2
        green = img.select("M3")
        nir = img.select("I2")
        ndwi = green.subtract(nir).divide(green.add(nir)).rename("NDWI")
        img = img.addBands(ndwi)
        
        # Select RGB: I1=Red, M3=Green, I3=Blue
        red = img.select("I1").rename("B4")
        green_band = img.select("M3").rename("B3")
        blue = img.select("I3").rename("B2")
        nir_band = img.select("I2").rename("B8")
        
        # Add SWIR bands if available
        try:
            swir1 = img.select("M11").rename("B11")
            swir2 = img.select("M12").rename("B12")
            img = ee.Image.cat([red, green_band, blue, nir_band, swir1, swir2, img.select("NDWI")])
        except Exception:
            # If SWIR not available, just include NIR
            img = ee.Image.cat([red, green_band, blue, nir_band, img.select("NDWI")])
        
        # Add vegetation indices
        try:
            img = add_vegetation_indices(img)
        except Exception:
            pass
    except Exception:
        pass
    return img

