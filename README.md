# 🌸 Flutter Earth 🌸

> **Download the prettiest satellite imagery with the gentlest touch!** ✨🦋

A **beautifully crafted** Python tool for downloading and processing satellite imagery from Google Earth Engine. Supports **12+ satellite sensors** (Sentinel-2, Landsat 4/5/7/8/9, Landsat MSS 1-3, SPOT 1-4, MODIS, ASTER, VIIRS, NOAA AVHRR) covering **1972 to present** with **intelligent adaptive quality-based mosaic generation**. Features **dynamic thresholds**, **fallback mechanisms**, and **real-time progress tracking** for the entire processing pipeline. Because every pixel deserves to be perfect! 💖

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-adorable-pink.svg)
![Satellites](https://img.shields.io/badge/satellites-12+-lavender.svg)
![Coverage](https://img.shields.io/badge/coverage-1972--present-purple.svg)
![Resolution](https://img.shields.io/badge/resolution-10m%20target-brightgreen.svg)

---

## 🌈 What Does This Do?

Ever wanted to download satellite imagery but got frustrated with:
- ❌ **Cloudy images** ruining your beautiful mosaics? ☁️💔
- ❌ **Low-resolution data** that looks pixelated? 📉😢
- Having to **manually pick** the "best" satellite? 🤔😓
- **Complex APIs** that make you cry? 😭💧

**Well, worry no more!** 🌸✨ Flutter Earth automatically:
- ✅ Finds the **best quality** images across **all available satellites** 🏆💎
- ✅ Intelligently combines them into **gorgeous mosaics** 🎨🌈
- ✅ Handles **clouds, shadows, and atmospheric effects** like magic ☁️➡️☀️✨
- ✅ Creates **Cloud-Optimized GeoTIFFs (COGs)** ready for analysis 📦💖
- ✅ Shows you **real-time progress** with a beautiful dashboard 📊🦋
- ✅ **Progress bars for EVERYTHING** - tile processing, mosaic stitching, index calculation, COG creation! 📊✨
- ✅ **Adaptive quality thresholds** - automatically lowers standards if only poor images exist! 📉📈
- ✅ **Fallback mechanisms** - uses best available image even if all are "bad" (clouds better than holes!) ☁️>🕳️
- ✅ **Pre-check system** - counts all available images first to optimize strategy! 🔍🎯
- ✅ **Dynamic worker scaling** that works efficiently and gently 💪🌸
- ✅ **Server mode** - designed to run continuously with care 🖥️💕

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+** (because we're modern and lovely! 🐍💕)
2. **Google Earth Engine account** (it's free! 🎉✨)
   - Sign up at: https://earthengine.google.com/
3. **Authenticate with Earth Engine:**
   ```bash
   earthengine authenticate
   ```

### Installation

1. **Clone this repository:**
   ```bash
   git clone https://github.com/flutter-gis/flutter_earth_download.git
   cd flutter_earth_download
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or install individually:
   ```bash
   pip install earthengine-api rasterio numpy shapely pyproj tqdm requests scikit-image psutil reportlab matplotlib s2cloudless
   ```
   
   *(Optional but recommended: `s2cloudless` for advanced cloud detection)* ☁️🔍

3. **Run it!**
   ```bash
   python main.py
   ```
   
   Or on Windows, just double-click `run_gee.bat` 🪟💖

---

## 📖 How to Use

### GUI Mode (Recommended for Everyone! 🧑💕)

Just run `python main.py` and a friendly GUI will pop up! Fill in:
- **Bounding Box**: Where do you want imagery? (lon_min, lat_min, lon_max, lat_max) 📍🌍
- **Date Range**: When do you want imagery? (YYYY-MM-DD format) 📅✨
- **Output Folder**: Where should we save your beautiful mosaics? 💾🌸
- **Max Tiles**: How many tiles? (auto-validates against 40MB limit) 🔢💖
- **Options**: Toggle satellites, harmonization, ML cloud cleanup, dynamic workers, server mode, etc. ⚙️🌈

Click **Submit** and watch the magic happen! ✨🦋

The dashboard will automatically open in your browser showing:
- 📊 Real-time progress bars (tile, mosaic, and full project!)
- ⏱️ Countdown timer (estimated time remaining) ⏰
- 📋 Console output with timestamps and color-coded messages 💬
- 🛰️ Satellite usage statistics with quality metrics 🌟
- 🎯 Pause/Resume button for gentle control ⏸️▶️

### CLI Mode (For Terminal Lovers 💻)

If you're a command-line warrior, the tool will prompt you for all the same information. No GUI? No problem! 💪

### Programmatic Usage

```python
from gee import process_month

# Process a single month
process_month(
    bbox=(34.9, 31.0, 35.8, 32.0),  # Dead Sea region
    year=2024,
    month=1,
    out="output_folder",
    workers=8,
    enable_ml=False,
    enable_harmonize=True,
    include_modis=True,
    include_aster=True,
    include_viirs=True
)
```

---

## ✨ Features

### 🎯 Intelligent Quality Scoring

Flutter Earth evaluates each satellite image based on:
- ☁️ **Cloud fraction** (less is better!)
- ☀️ **Solar zenith angle** (optimal lighting!)
- ✅ **Valid pixel fraction** (data completeness!)
- 📅 **Temporal recency** (fresh data!)
- 🔍 **Native resolution** (crisp details!)
- 🎨 **Band completeness** (full spectrum!)

### 🌈 Resolution-First Gap Filling

When filling gaps in mosaics, Flutter Earth prioritizes:
- 🏆 **Higher resolution** images (even with minor clouds!)
- 💎 **Quality scores** as tiebreakers
- ✨ **Smart iteration** until coverage is complete

---

## 🦋 The Magical Image Selection Process: How Flutter Earth Chooses the Perfect Pixels! ✨

Ever wondered how Flutter Earth magically picks the best satellite images from thousands of options? Let's dive into the beautiful, intricate process that makes every pixel perfect! 💖

### 📊 Phase 1: The Great Image Hunt 🎯

When Flutter Earth starts processing a tile, it embarks on an epic quest to find the best images from **all available satellites**! Here's what happens:

#### Step 1: Collection Gathering 🌍

Flutter Earth queries **multiple satellite collections** simultaneously:
- 🛰️ **Sentinel-2** (10m resolution, launched 2015) - The sharp-eyed observer!
- 🌍 **Landsat 4/5/7/8/9** (30m resolution, 1982-present) - The reliable workhorses! 🏆
- 🌎 **MODIS** (250m resolution, 2000-present) - The wide-eyed watcher!
- 🔬 **ASTER** (15-90m resolution, 2000-2008) - The detailed scientist!
- 🌌 **VIIRS** (375m resolution, 2011-present) - The night vision specialist!

Each satellite is checked to see if it was **operational** during your requested date range. For example, if you're looking at imagery from 2000, Sentinel-2 won't be available (it didn't launch until 2015)! Flutter Earth knows this and gracefully skips unavailable satellites. 🎯

#### Step 2: Pre-Check System - The Intelligence Gathering Phase! 🔍

Before processing any images, Flutter Earth performs a **smart pre-check**:
- **Counts total available images** across ALL satellites for the tile/date range
- Uses this count to **dynamically set threshold strategy**:
  - **≤3 images total**: Very aggressive lowering (after 1 test) - every image counts! 🎯
  - **≤10 images total**: Moderate lowering (after 2 tests) - can afford some testing
  - **>10 images total**: Conservative lowering (after 3 tests) - plenty of options!
- This ensures the system **adapts to scarcity** - if only 2 images exist, it won't reject them all! ✨

#### Step 3: Client-Side Adaptive Filtering ⚡

Flutter Earth uses **adaptive thresholds** that progressively relax if no images pass:
- **No server-side cloud filtering** - all images checked client-side with adaptive logic!
- Sorts by **cloud cover** (best images first!)
- Limits to **top images per satellite** (efficiency is key!)

**Adaptive Cloud Thresholds** (Metadata & Calculated):
- Start: 20% clouds (strict!)
- If no images pass → Lower to 30%
- Still none → 40% → 50% → 60% → 80% (very lenient!)
- **Progressive relaxation** ensures something is always found! 📉✨

**Adaptive Quality Thresholds**:
- Start: 0.9 (90% quality - excellent images only!)
- If no images pass → Lower to 0.7 (70% - good images)
- Still none → 0.5 (50% - moderate) → 0.3 (30% - poor) → 0.0 (accept anything!)
- **Never gives up** until all images are checked! 📊📈

#### Step 3: The Quality Scoring Magic ✨

For each candidate image, Flutter Earth calculates a **comprehensive quality score** (0.0 to 1.0, where 1.0 is perfect!). Here's how each factor contributes:

**☁️ Cloud Fraction (25% weight)**
- Less clouds = better score!
- Formula: `cloud_score = max(0.0, 1.0 - cloud_fraction * 1.5)`
- A 10% cloudy image gets: `1.0 - 0.10 * 1.5 = 0.85` (85% of cloud score)
- A 50% cloudy image gets: `1.0 - 0.50 * 1.5 = 0.25` (25% of cloud score)
- **Heavy penalty** for cloudy images! ☁️💔

**☀️ Solar Zenith Angle (15% weight)**
- Lower zenith = sun higher in sky = better lighting!
- Optimal: <30° zenith (perfect score!)
- Good: 30-60° zenith (gradual penalty)
- Poor: >60° zenith (significant penalty, low sun = shadows!)
- Formula accounts for time of day and season! 🌅

**👁️ View Zenith Angle (10% weight)**
- Lower = more nadir (straight down) = less distortion!
- Optimal: <10° (perfect score!)
- Acceptable: 10-50° (gradual penalty)
- Poor: >50° (significant penalty, oblique angles = stretched pixels!)

**✅ Valid Pixel Fraction (15% weight)**
- More valid data = better score!
- Minimum 30% valid pixels required (below this = heavy penalty!)
- Accounts for sensor errors, scan line gaps, and data quality issues!

**📅 Temporal Recency (5% weight)**
- Newer images get slightly higher scores!
- Formula: `temporal_score = max(0.5, 1.0 - (days_since_start / max_days) * 0.5)`
- A 1-day-old image gets ~100% of temporal score
- A 365-day-old image gets ~50% of temporal score
- **Small but meaningful** preference for fresh data! 🆕

**🔍 Native Resolution (30% weight) - THE BIGGEST FACTOR!** 🏆
- **Resolution is king!** Higher resolution = dramatically better score!
- Scoring tiers:
  - **≤4m**: Perfect score (1.0) - Ultra-high resolution! 💎
  - **≤15m**: Excellent (0.95) - Sentinel-2, ASTER! ✨
  - **≤30m**: Good (0.85) - Landsat family! 🌍
  - **≤60m**: Moderate (0.60) - Lower-res Landsat variants
  - **≤250m**: Poor (0.40) - MODIS territory! 🌎
  - **≤400m**: Very poor (0.25) - VIIRS range! 🌌
  - **>400m**: Worst (0.15) - Coarse resolution! 😢

**Why resolution matters so much:**
- A **10m Sentinel-2** image with 5% clouds beats a **250m MODIS** image with 0% clouds!
- Resolution determines how much detail you can see!
- Flutter Earth **prioritizes crisp, detailed imagery** over perfect cloud-free conditions! 🎯

**🎨 Band Completeness (10% weight)**
- Checks for critical bands: RGB (required!), NIR, SWIR1, SWIR2 (highly desired!)
- Missing IR bands = significant penalty (can't compute vegetation indices!)
- Formula: `completeness = RGB_score * 0.2 + IR_score * 0.6 + index_score * 0.2`
- Ensures images have the spectral data needed for analysis! 🌈

#### Step 4: Fallback Mechanisms - Never Give Up! 🛡️

Flutter Earth has **two-layer fallback protection**:

**Layer 1: Cloud Fallback** ☁️
- Tracks the **best rejected by clouds** (lowest cloud percentage)
- If ALL images fail cloud checks → Uses the **least cloudy** rejected image
- Philosophy: **"Clouds are better than big holes!"** ☁️>🕳️
- Example: If all images have 60-98% clouds, uses the one with 60% clouds!

**Layer 2: Quality Fallback** 📊
- Tracks the **best rejected by quality** (highest quality score)
- If ALL images fail quality checks → Uses the **highest quality** rejected image
- Philosophy: **"Bad quality is better than no quality!"** 📉>❌
- Example: If all images score 0.3-0.5, uses the one with 0.5 score!

**Result**: Flutter Earth **always finds something**, even if it's not perfect! 💪✨

#### Step 5: The Two-Phase Selection Strategy 🎭

Flutter Earth uses a **smart two-phase approach** to select images:

**Phase 1A: Excellent Image Collection** ⭐
- Searches for "excellent" images (quality score ≥ 0.9) from each satellite
- Collects up to **3 excellent images per satellite**
- Stops searching a satellite once it finds 3 excellent images (efficiency!)
- Tracks all excellent candidates in a special list

**Phase 1B: Best Overall Selection** 🏆
- Takes all excellent images from all satellites
- Sorts them by quality score (highest first!)
- Selects the **top 5 overall images** (regardless of satellite!)
- This ensures you get the **absolute best quality**, not just the best per satellite!

**Why this matters:**
- If Sentinel-2 has 5 excellent images (scores: 0.95, 0.94, 0.93, 0.92, 0.91)
- And Landsat-8 has 2 excellent images (scores: 0.96, 0.95)
- Flutter Earth will pick: **Landsat-8 (0.96), Landsat-8 (0.95), Sentinel-2 (0.95), Sentinel-2 (0.94), Sentinel-2 (0.93)**
- The **best overall**, not just best per satellite! 🎯

#### Step 6: Band Standardization 🎨

Before images can be combined, Flutter Earth **standardizes all bands**:
- Renames bands to standard names: `B4` (Red), `B3` (Green), `B2` (Blue), `B8` (NIR), `B11` (SWIR1), `B12` (SWIR2)
- Handles different naming conventions (Sentinel-2 uses `B4`, Landsat-8 uses `SR_B4`, etc.)
- Fills missing bands with zeros (they'll be filled from fallback images later!)
- Ensures all images have the **same band structure** for seamless combination! ✨

---

### 🎬 Phase 1.5: Real-Time Progress Tracking! 📊

During the image selection process, you'll see detailed progress updates:

**During Satellite Processing:**
- `[Tile 0042] LANDSAT_5 1985-01-28 Test 01: cloud_frac=19.0%, valid_frac=50.0%`
- `[Tile 0042] LANDSAT_5 1985-01-28 Test 02: SKIPPED (>30% clouds)`
- `[Tile 0042] Lowered cloud threshold for Landsat-5 from 20% to 30% (no images found at lower threshold)`
- `[Tile 0042] Lowered quality threshold for Landsat-5 from 0.9 to 0.7 (no images found at higher threshold)`
- `[Tile 0042] Landsat-5 image added to prepared list with quality score 0.783`

**Fallback Activation:**
- `[Tile 0042] LANDSAT_5: No images passed cloud checks, using best rejected by clouds (19.0% clouds - clouds better than holes)`
- `[Tile 0042] LANDSAT_5: No images passed quality checks, using best rejected image (quality 0.65 - bad better than nothing)`

You always know what's happening! 💬✨

---

### 🌈 Phase 2: The Targeted Gap-Filling Adventure! 🎯

Once the initial best images are selected, Flutter Earth creates a mosaic and checks for **gaps** (missing pixels). This is where the magic really happens! ✨

#### Step 1: Coverage Detection 📊

Flutter Earth creates a test mosaic from the selected images and checks:
- **Coverage percentage**: How much of the tile has valid data?
- Uses RGB bands (`B4`, `B3`, `B2`) to detect valid pixels
- Calculates mean coverage across all bands
- Target: **99.9% coverage** (practical ceiling - 100% is often impossible!)

#### Step 2: Gap Identification 🔍

If coverage < 99.9%, Flutter Earth identifies **gap areas**:
- Creates a **gap mask**: `gap_mask = valid_mask.Not()`
- This includes:
  1. **True gaps**: Pixels with no data from any image
  2. **Cloud gaps**: Pixels that are cloud-masked in the best image
- Cloud-masked pixels are treated as gaps to be filled! ☁️➡️☀️

#### Step 3: Resolution-First Gap Filling! 🏆

This is where Flutter Earth's **resolution-first strategy** shines! For each gap area:

**The Resolution-First Selection Logic:**

1. **Much Better Resolution (>50m better)**: 
   - If a new image has **>50m better resolution**, it wins even if quality score is **10% lower**!
   - Example: A 30m Landsat image (score 0.75) beats a 250m MODIS image (score 0.85)!
   - Why? **Resolution is the biggest factor!** 🎯

2. **Moderately Better Resolution (20-50m better)**:
   - If a new image has **20-50m better resolution**, it wins if quality score is within **5%**!
   - Example: A 30m Landsat image (score 0.80) beats a 60m image (score 0.82)!
   - Small quality difference is acceptable for better resolution! ✨

3. **Similar Resolution (within 20m)**:
   - If resolutions are similar, **quality score** is the tiebreaker!
   - Example: Two 30m Landsat images - the one with lower clouds wins! 🌍

4. **Worse Resolution**:
   - If a new image has **worse resolution**, it only wins if quality is **significantly better**!
   - Example: A 250m MODIS image needs to be **15% better** in quality to beat a 30m Landsat image!
   - This prevents low-resolution images from dominating! 🛡️

**The Iterative Process:**
- **Iteration 1**: Quality threshold = 0.5 (moderate quality required)
- **Iteration 2**: Quality threshold = 0.45 (slightly lower)
- **Iteration 3**: Quality threshold = 0.40 (even lower)
- ...and so on, down to 0.2 (very low threshold for desperate gaps!)
- **Maximum 20 iterations** to prevent infinite loops!

**Why This Works:**
- First iterations: Fill gaps with high-quality, high-resolution images! 🏆
- Later iterations: Fill remaining gaps with lower-quality images (but still prioritize resolution!)
- Each iteration checks coverage again - stops when coverage ≥ 99.9%! ✅

#### Step 4: The Fallback Strategy 🛡️

If no suitable image is found with the normal threshold, Flutter Earth tries a **fallback strategy**:
- Lowers quality threshold to **0.1** (very permissive!)
- **Still prioritizes resolution** even in fallback mode!
- Only gives up if truly no images are available

#### Step 5: Quality Mosaic Magic! ✨

Once all images are selected, Flutter Earth uses Earth Engine's **`qualityMosaic`** function:
- For each pixel, selects the image with the **highest quality score** where that pixel is valid!
- If the best image has a cloud-masked pixel, **automatically fills it** with the next-best image's data!
- This creates a **seamless mosaic** with the best data everywhere! 🌈

**Example:**
- Pixel (100, 200): 
  - Sentinel-2 (score 0.95) has valid data → **Selected!** ✅
- Pixel (150, 250):
  - Sentinel-2 (score 0.95) has cloud → **Skip!**
  - Landsat-8 (score 0.85) has valid data → **Selected!** ✅
- Pixel (200, 300):
  - Sentinel-2 (score 0.95) has cloud → **Skip!**
  - Landsat-8 (score 0.85) has cloud → **Skip!**
  - MODIS (score 0.70) has valid data → **Selected!** ✅

This ensures **every pixel** gets the best available data! 💖

---

### 🎨 Phase 3: Stitching & Final Touches! ✨

After all tiles are processed, Flutter Earth stitches them into beautiful mosaics with **full progress tracking**:

#### Step 1: Reprojection to Common Grid 🗺️

- Creates **common grid** for all tiles (UTM coordinates)
- Reprojects each tile to the common grid
- **Progress bar**: `Reprojecting tiles: 500/2009` (updates for every tile!)
- Shows which tile is being reprojected in real-time

#### Step 2: Feather Blending 🪶

- Blends overlapping pixels with **soft weight masks** (feathering)
- Uses **cosine-based feathering** for smooth transitions
- Processes **band by band** for memory efficiency
- **Progress bars**:
  - `Processing bands: 1/6` (overall band progress)
  - `Blending Band 1: tile 1500/2009` (updates every 100 tiles)
- Shows which band and tile are being processed

#### Step 3: Writing Mosaic File 💾

- Stacks all bands together
- Writes final mosaic file with compression (LZW)
- **Progress**: `Writing mosaic file...`
- Creates **multi-band GeoTIFF** ready for analysis

#### Step 4: Reprojection to UTM (if needed) 🗺️

- Determines optimal **UTM zone** for the mosaic's location
- Reprojects to UTM coordinates for **maximum accuracy**
- Ensures **consistent pixel size** (10m by default - native Sentinel-2!)

#### Step 5: Index Calculation 🌈

After the mosaic is unified, Flutter Earth calculates **vegetation and water indices** with **detailed progress tracking**:

**Progress Updates:**
- `[Indices] Reading bands and calculating valid mask... (1/9)`
- `[Indices] Calculating NDVI... (2/9)`
- `[Indices] Calculating NDWI... (3/9)`
- `[Indices] Calculating MNDWI... (4/9)`
- `[Indices] Calculating EVI... (5/9)`
- `[Indices] Calculating SAVI... (6/9)`
- `[Indices] Calculating FVI... (7/9)`
- `[Indices] Calculating AVI... (8/9)`
- `[Indices] Writing indices to mosaic file... (9/9)`
- `[Indices] Replacing mosaic with indexed version... (9/9)`

**Calculated Indices:**
- **NDVI**: `(NIR - Red) / (NIR + Red)` - Vegetation health! 🌿
- **NDWI**: `(Green - NIR) / (Green + NIR)` - Water detection! 💧
- **MNDWI**: `(Green - SWIR1) / (Green + SWIR1)` - Better water detection! 🌊
- **EVI**: `2.5 * ((NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1))` - Enhanced Vegetation Index (more sensitive!) 🌳
- **SAVI**: `((NIR - Red) / (NIR + Red + 0.5)) * 1.5` - Soil-Adjusted Vegetation Index (accounts for soil!) 🌱
- **FVI**: `(NIR - SWIR1) / (NIR + SWIR1)` - Floating Vegetation Index 🌾
- **AVI**: `NDVI * (1 - |water_index|)` - Aquatic Vegetation Index (for water vegetation!) 🌊🌿

These indices are calculated **after** the mosaic is unified, so they use the best available data for each pixel! ✨

#### Step 6: COG Creation 📦

- Creates **Cloud-Optimized GeoTIFF (COG)** from the mosaic
- Adds **overview pyramids** (2x, 4x, 8x, 16x, 32x) for fast viewing
- **Progress**: `Creating COG from mosaic...`
- Optimized for web mapping and fast access! ⚡

---

### 📊 The Complete Selection Flowchart! 🗺️

```
Start Processing Tile
    ↓
Pre-Check: Count Total Available Images (S2, L4/5/7/8/9, SPOT 1-4, MSS 1-3, MODIS, ASTER, VIIRS, AVHRR)
    ↓
Set MIN_TESTS_BEFORE_LOWERING based on total count
    ↓
Query All Satellites (S2, L4/5/7/8/9, SPOT 1-4, MSS 1-3, MODIS, ASTER, VIIRS, AVHRR last resort only)
    ↓
Filter by Operational Dates
    ↓
Sort by Cloud Cover (client-side adaptive filtering, no server filter!)
    ↓
For Each Satellite:
    ├─→ Fetch Top Images (up to MAX_IMAGES_PER_SATELLITE)
    ├─→ Initialize Fallback Trackers (best rejected by clouds, best rejected by quality)
    ├─→ For Each Image:
    │   ├─→ ADAPTIVE CLOUD CHECK (metadata & calculated):
    │   │   ├─→ Start: 20% threshold
    │   │   ├─→ If no images pass after MIN_TESTS: Lower to 30% → 40% → 50% → 60% → 80%
    │   │   └─→ Track best rejected by clouds (lowest cloud %)
    │   ├─→ Calculate Quality Score:
    │   │   ├─→ Cloud Fraction (25%)
    │   │   ├─→ Solar Zenith (15%)
    │   │   ├─→ View Zenith (10%)
    │   │   ├─→ Valid Pixels (15%)
    │   │   ├─→ Temporal Recency (5%)
    │   │   ├─→ Native Resolution (30%) ⭐ BIGGEST FACTOR!
    │   │   └─→ Band Completeness (10%)
    │   ├─→ ADAPTIVE QUALITY CHECK:
    │   │   ├─→ Start: 0.9 threshold
    │   │   ├─→ If no images pass after MIN_TESTS: Lower to 0.7 → 0.5 → 0.3 → 0.0
    │   │   └─→ Track best rejected by quality (highest score)
    │   ├─→ If Score ≥ 0.9: Add to Excellent List
    │   └─→ Standardize Bands
    ├─→ If No Images Accepted:
    │   ├─→ Try Cloud Fallback (use best rejected by clouds)
    │   └─→ If Still None: Try Quality Fallback (use best rejected by quality)
    └─→ Stop After 3 Excellent Images (or continue for more in server mode)
    ↓
Select Top 5 Overall Images (Best Quality, All Satellites)
    ↓
Create Initial Mosaic
    ↓
Check Coverage
    ↓
If Coverage < 99.9%:
    ├─→ Identify Gap Areas
    ├─→ For Each Gap:
    │   ├─→ Find Best Gap-Filling Image:
    │   │   ├─→ Resolution-First Selection:
    │   │   │   ├─→ >50m better res? → Win if score ≥ 90% of best
    │   │   │   ├─→ 20-50m better res? → Win if score ≥ 95% of best
    │   │   │   ├─→ Similar res (±20m)? → Use quality score
    │   │   │   └─→ Worse res? → Only if score ≥ 110-115% of best
    │   │   └─→ Add to Mosaic
    │   └─→ Check Coverage Again
    └─→ Repeat Until Coverage ≥ 99.9% or Max Iterations
    ↓
Apply Quality Mosaic (Best Pixel Per Location)
    ↓
STITCHING PHASE (with progress bars!):
    ├─→ Reproject all tiles to common grid (progress: X/Total tiles)
    ├─→ Open all datasets
    ├─→ For each band (progress: X/Total bands):
    │   ├─→ For each tile (progress every 100 tiles):
    │   │   ├─→ Read band data
    │   │   ├─→ Calculate feather weights
    │   │   └─→ Blend into mosaic
    │   └─→ Normalize by sum of weights
    └─→ Write mosaic file (progress: "Writing mosaic file...")
    ↓
INDEX CALCULATION PHASE (with progress bars!):
    ├─→ Read bands (progress: 1/9)
    ├─→ Calculate NDVI (progress: 2/9)
    ├─→ Calculate NDWI (progress: 3/9)
    ├─→ Calculate MNDWI (progress: 4/9)
    ├─→ Calculate EVI (progress: 5/9)
    ├─→ Calculate SAVI (progress: 6/9)
    ├─→ Calculate FVI (progress: 7/9)
    ├─→ Calculate AVI (progress: 8/9)
    └─→ Write indices to file (progress: 9/9)
    ↓
COG CREATION (with progress!):
    └─→ Create Cloud-Optimized GeoTIFF with overviews
    ↓
Done! ✨
```

---

## 🔬 Technical Specifications & Procedures

### 📐 Processing Pipeline Details

#### 1. Tile Generation & Geometry
- **Tile System**: UTM-based tiles, auto-calculated based on `max_tiles` parameter
- **Tile Size Validation**: Automatically adjusts to stay under 40MB per tile (Earth Engine download limit)
- **Geometry Filtering**: Only tiles that intersect with your bounding box are processed
- **Tile Count**: Typical values: 500-2000 tiles depending on area size and `max_tiles` setting

#### 2. Image Collection Processing
- **Collection IDs**: Uses official Google Earth Engine collection IDs (e.g., `LANDSAT/LC08/C02/T1_L2`)
- **Date Filtering**: Strict `filterDate(start, end)` for exact month ranges
- **Bounds Filtering**: `filterBounds(geometry)` to limit to your area of interest
- **Cloud Filtering**: Client-side adaptive (no server-side filters that could prevent fallbacks!)
- **Sorting**: By cloud cover (ascending - best images first)

#### 3. Quality Scoring Algorithm
**Formula**: `quality_score = (cloud_score * 0.25) + (solar_zenith_score * 0.15) + (view_zenith_score * 0.10) + (valid_pixel_score * 0.15) + (temporal_score * 0.05) + (resolution_score * 0.30) + (band_completeness_score * 0.10)`

**Component Details**:
- **Cloud Score**: `max(0.0, 1.0 - cloud_fraction * 1.5)` - Heavy penalty for clouds!
- **Solar Zenith**: Optimal <30° = 1.0, 30-60° = linear decay, >60° = 0.1
- **View Zenith**: Optimal <10° = 1.0, 10-50° = linear decay, >50° = 0.1
- **Valid Pixels**: `valid_fraction` directly, but minimum 30% required (below = heavy penalty)
- **Temporal**: `max(0.5, 1.0 - (days_since_start / max_days) * 0.5)`
- **Resolution**: Tiered scoring (≤4m=1.0, ≤15m=0.95, ≤30m=0.85, ≤60m=0.60, ≤250m=0.40, ≤400m=0.25, >400m=0.15)
- **Band Completeness**: `RGB_score * 0.2 + IR_score * 0.6 + index_score * 0.2`

#### 4. Adaptive Threshold System
**Cloud Thresholds** (Metadata & Calculated Fraction):
- Initial: 20% (strict)
- Lowering sequence: 20% → 30% → 40% → 50% → 60% → 80% (very lenient)
- **Trigger**: After `MIN_TESTS_BEFORE_LOWERING` images fail to pass
- **MIN_TESTS_BEFORE_LOWERING**: 
  - 1 if `total_available_images <= 3`
  - 2 if `total_available_images <= 10`
  - 3 otherwise (default)

**Quality Thresholds**:
- Initial: 0.9 (90% quality - excellent images only)
- Lowering sequence: 0.9 → 0.7 → 0.5 → 0.3 → 0.0 (accept anything)
- **Trigger**: After `MIN_TESTS_BEFORE_LOWERING` images fail to pass
- **Same MIN_TESTS logic** as cloud thresholds

#### 5. Fallback Mechanisms
**Cloud Fallback**:
- Tracks `best_rejected_by_clouds` with lowest cloud percentage
- Activated when `images_accepted == 0` after all adaptive lowering
- Philosophy: "Clouds are better than big holes!" ☁️>🕳️

**Quality Fallback**:
- Tracks `best_rejected_by_quality` with highest quality score
- Activated when `images_accepted == 0` after all adaptive lowering
- Philosophy: "Bad quality is better than no quality!" 📉>❌

#### 6. Gap-Filling Algorithm
**Iterative Process**:
- Maximum iterations: 20 (prevents infinite loops)
- Target coverage: 99.9% (practical ceiling)
- Quality threshold lowering: 0.5 → 0.45 → 0.40 → ... → 0.2 (very low for desperate gaps)

**Resolution-First Selection Logic**:
- **>50m better resolution**: Win even if quality score is 10% lower
- **20-50m better resolution**: Win if quality score is within 5%
- **Similar resolution (±20m)**: Use quality score as tiebreaker
- **Worse resolution**: Only win if quality is 15% better

**Progress Detection**:
- Tracks `previous_coverage` and `no_progress_count`
- Breaks if coverage improves by <0.1% for 3 consecutive iterations
- Prevents wasting time on impossible gaps

#### 7. Mosaic Stitching & Blending
**Reprojection**:
- Common grid calculation: Uses union of all tile bounds
- Reprojection method: Bilinear resampling (for smooth transitions)
- Target resolution: 10m per pixel (preserves Sentinel-2 native quality)

**Feather Blending**:
- Feather distance: 50-80 pixels (default 80px for large mosaics)
- Weight function: Cosine-based `weight = 0.5 * (1 + cos(π * d / feather_px))`
- Normalization: `mosaic_band = sum(weighted_values) / sum(weights)` (prevents division by zero)
- Memory efficiency: Processes band-by-band (doesn't load entire mosaic into memory)

**Interpolation** (for missing IR bands):
- Only applies to bands 4+ (IR bands and indices, not RGB)
- Distance threshold: 20 pixels (100m at 5m resolution)
- Method: Nearest valid neighbor (simple but effective)

#### 8. Index Calculation
**Local Calculation** (much faster than Earth Engine server):
- NDVI: `(NIR - Red) / (NIR + Red)`
- NDWI: `(Green - NIR) / (Green + NIR)`
- MNDWI: `(Green - SWIR1) / (Green + SWIR1)`
- EVI: `2.5 * ((NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1))`
- SAVI: `((NIR - Red) / (NIR + Red + 0.5)) * 1.5`
- FVI: `(NIR - SWIR1) / (NIR + SWIR1)`
- AVI: `NDVI * (1 - |water_index|)` (where water_index is MNDWI or NDWI)

**Band Order Expected**:
- Band 1: B4 (Red)
- Band 2: B3 (Green)
- Band 3: B2 (Blue)
- Band 4: B8 (NIR)
- Band 5: B11 (SWIR1)
- Band 6: B12 (SWIR2)
- Bands 7+: Indices (NDVI, NDWI, MNDWI, EVI, SAVI, FVI, AVI)

#### 9. COG Creation
**Format**: Cloud-Optimized GeoTIFF (COG) with internal tiling
**Overviews**: 2x, 4x, 8x, 16x, 32x (for fast multi-resolution viewing)
**Compression**: LZW (lossless, good compression ratio)
**Tile Size**: 512x512 pixels (optimal for web mapping)
**BigTIFF**: IF_SAFER (handles files >4GB)

#### 10. Progress Tracking
**Tile Processing**:
- Status updates: `[Tile XXXX] ✅ SUCCESS`, `[Tile XXXX] ❌ FAILED: reason`
- Progress bar: `Tile: 1234/2009` with percentage and ETA

**Mosaic Stitching**:
- Reprojection: `Reprojecting tiles: 500/2009` (updates for every tile)
- Band processing: `Processing bands: 1/6` (overall) + `Blending Band 1: tile 1500/2009` (detailed)
- File writing: `Writing mosaic file...`

**Index Calculation**:
- Step-by-step: `Calculating NDVI... (2/9)`, `Calculating EVI... (5/9)`, etc.
- File writing: `Writing indices to mosaic file... (9/9)`

**COG Creation**:
- Status: `Creating COG from mosaic...`

### 🗄️ Data Structures

**Tile Information**:
```python
tile_info = {
    "tile_idx": int,           # 0-based tile index
    "bounds": (min_x, min_y, max_x, max_y),  # Bounding box coordinates
    "geometry": ee.Geometry,   # Earth Engine geometry object
    "utm_zone": int,           # UTM zone for reprojection
}
```

**Image Metadata**:
```python
metadata = {
    "system:id": str,           # Unique Earth Engine image ID
    "system:time_start": int,   # Timestamp (milliseconds since epoch)
    "cloud_cover": float,       # Cloud fraction (0.0-1.0)
    "CLOUDY_PIXEL_PERCENTAGE": float,  # Alternative cloud metadata
    "SOLAR_ZENITH": float,      # Solar zenith angle (degrees)
    "SOLAR_AZIMUTH": float,     # Solar azimuth angle (degrees)
    "SPACECRAFT_ID": str,       # Satellite identifier
}
```

**Quality Score Components**:
```python
detailed_stats = {
    "quality_score": float,     # Overall quality (0.0-1.0)
    "cloud_fraction": float,    # Cloud fraction (0.0-1.0)
    "valid_fraction": float,    # Valid pixel fraction (0.0-1.0)
    "solar_zenith": float,      # Solar zenith angle (degrees)
    "view_zenith": float,       # View zenith angle (degrees)
    "resolution": float,        # Native resolution (meters)
    "timestamp": int,           # Cached timestamp for gap-filling
}
```

### 🚀 Performance Optimizations

1. **Parallel Metadata Fetching**: Uses `ThreadPoolExecutor` with configurable workers (default 4, server mode 16)
2. **Band-by-Band Processing**: Processes mosaic bands individually to reduce memory usage
3. **Server-Side Filtering** (removed in favor of adaptive client-side): All filtering now client-side for better control
4. **Cached Timestamps**: Stores timestamps in `detailed_stats` to avoid redundant `getInfo()` calls during gap-filling
5. **Early Stopping**: Stops searching after finding 3 excellent images per satellite (efficiency!)
6. **Progress Detection**: Breaks gap-filling loop if no progress after 3 iterations
7. **Memory-Efficient Reprojection**: Temporary files cleaned up automatically

---

### 💡 Key Insights: Why Flutter Earth is So Smart! 🧠

1. **Resolution is King!** 👑
   - A 10m image with 5% clouds beats a 250m image with 0% clouds!
   - Flutter Earth prioritizes **detail** over perfect conditions!

2. **No Sensor Bias!** ⚖️
   - All satellites are evaluated **equally** based on quality!
   - Sentinel-2 doesn't automatically win - it must earn its place!

3. **Smart Gap Filling!** 🎯
   - Fills gaps **iteratively** with the best available images!
   - Prioritizes resolution even when quality is slightly lower!

4. **Automatic Cloud Handling!** ☁️
   - Cloud-masked pixels are treated as gaps!
   - Automatically filled with valid data from other images!

5. **Efficiency First!** ⚡
   - Server-side filtering saves time!
   - Stops searching satellites after finding excellent images!
   - Limits iterations to prevent infinite loops!

---

### 🎉 The Result: Perfect Pixels Everywhere! ✨

After this intricate, beautiful process, Flutter Earth delivers:
- ✅ **Highest quality** images selected from all satellites
- ✅ **Maximum resolution** prioritized throughout
- ✅ **Complete coverage** with intelligent gap-filling
- ✅ **Seamless mosaics** with best data everywhere
- ✅ **Rich spectral data** with all indices calculated

**Every pixel is perfect because Flutter Earth cares!** 💖🦋✨

### 🦋 Multi-Sensor Support (12+ Satellites!)

**High Resolution (≤30m):**
- 🛰️ **Sentinel-2** (10m, 2015-present) - The sharp-eyed observer! 💙
- 🌍 **Landsat 4 TM** (30m, 1982-1993) - The early pioneer! 💚
- 🌍 **Landsat 5 TM** (30m, 1984-2013) - The record-holder (28+ years!) 🏆💚
- 🌍 **Landsat 7 ETM+** (30m, 1999-present) - The striped survivor! 💚
- 🌍 **Landsat 8 OLI/TIRS** (30m, 2013-present) - The modern workhorse! 💚
- 🌍 **Landsat 9 OLI-2/TIRS-2** (30m, 2021-present) - The newest addition! 💚
- 🌍 **Landsat 1-3 MSS** (60m, 1972-1983) - The historical archive! 📜💚
- 🛰️ **SPOT 1** (10m pan, 20m MS, 1986-2003) - The French precision! 🇫🇷
- 🛰️ **SPOT 2** (10m pan, 20m MS, 1990-2009) - The reliable backup! 🇫🇷
- 🛰️ **SPOT 3** (10m pan, 20m MS, 1993-1997) - The short-lived star! 🇫🇷
- 🛰️ **SPOT 4** (10m pan, 20m MS, 1998-2013) - The extended mission! 🇫🇷

**Medium Resolution (60-400m):**
- 🔬 **ASTER** (15-90m, 2000-2008) - The detailed scientist! 💜

**Low Resolution (>400m):**
- 🌎 **MODIS Terra** (250m, 2000-present) - The wide-eyed watcher! 🧡
- 🌎 **MODIS Aqua** (250m, 2002-present) - The water-focused twin! 🧡
- 🌌 **VIIRS** (375m, 2011-present) - The night vision specialist! 💛
- 🌍 **NOAA AVHRR** (1km, 1978-present) - **ABSOLUTE LAST RESORT** only! ⚠️🔴
  - Only used when ALL other satellites fail (very coarse resolution!)

**Coverage Timeline:**
- 🌟 **1972-1982**: Landsat MSS 1-3 only (60m, historical)
- 🌟 **1982-1985**: Landsat 4 TM (early 30m era)
- 🌟 **1985-1993**: Landsat 4 + 5 overlap (best coverage!)
- 🌟 **1993-1999**: Landsat 5 only (30m reliable)
- 🌟 **1999-2013**: Landsat 5 + 7 (with SLC stripes after 2003)
- 🌟 **2013-2015**: Landsat 7 + 8 (transition period)
- 🌟 **2015-present**: Sentinel-2 + Landsat 7/8/9 (golden era - 10m + 30m!)

**Default Start Date: 1985** - Ensures both Landsat 4 and 5 are operational for maximum redundancy! 🎯

### 🎨 Advanced Processing

- **Adaptive Cloud Thresholds** - Automatically relaxes cloud limits (20% → 80%) if no images pass! ☁️📉
- **Adaptive Quality Thresholds** - Automatically lowers quality bar (0.9 → 0.0) if no images meet standard! 📊📈
- **Pre-Check System** - Counts all available images first to optimize threshold strategy! 🔍🎯
- **Fallback Mechanisms**:
  - If all images rejected by clouds → Uses **least cloudy** image (clouds > holes!) ☁️>🕳️
  - If all images rejected by quality → Uses **highest quality** image (bad > nothing!) 📉>❌
- **Cloud masking** with multiple algorithms (Sentinel-2 QA60, Landsat QA_PIXEL, pixel-level cloud detection) ☁️🎭
- **Shadow detection** and correction 🌑✨
- **Multi-sensor harmonization** (Sentinel-2 ↔ Landsat ↔ SPOT ↔ MSS ↔ AVHRR) 🔄🌈
- **Band standardization** - All satellites normalized to same band structure (B2/B3/B4/B8/B11/B12) 🎨✨
- **NDWI water masking** for coastal areas 💧🌊
- **Feather blending** with soft-edge weight masks for seamless tile merging 🪶✨
- **COG creation** with overviews (2x, 4x, 8x, 16x, 32x) for fast viewing 📦⚡
- **Progress tracking** for EVERY phase: reprojection, blending, index calculation, file writing! 📊💫

### 💖 User-Friendly Features

- **Beautiful HTML dashboard** that auto-refreshes every 2 seconds 📊🦋
- **Real-time progress tracking** with countdown timers ⏱️✨
- **Progress bars for EVERYTHING**:
  - Tile processing: `[Tile 1234/2009] ✅ SUCCESS`
  - Reprojection: `Reprojecting tiles: 500/2009`
  - Band blending: `Blending Band 1: tile 1500/2009`
  - Index calculation: `Calculating NDVI... (2/9)`, `Calculating EVI... (5/9)`
  - File writing: `Writing mosaic file...`, `Writing indices to mosaic file...`
  - COG creation: `Creating COG from mosaic...`
- **Detailed console logging** with timestamps and color-coded messages 💬
- **Pause/Resume functionality** for gentle control ⏸️▶️
- **Comprehensive PDF reports** with statistics, visualizations, and satellite usage 📄💕
- **Satellite usage statistics** showing which satellites contributed to each tile 🛰️📊
- **Quality score tracking** - see exactly how good each image is! 🏆
- **Server mode** for maximum resource utilization (uses all CPU cores, max workers) 🖥️💪

---

## 🎨 Configuration

### Default Settings

- **Default Start Date**: 1985-01-01 (both Landsat 4 and 5 operational for redundancy!) 📅✨
- **Default End Date**: Current date (2025-11-30) 📅
- **Target Resolution**: 10 meters per pixel 🎯 (native Sentinel-2 - preserves best quality!)
- **Tile Size**: Auto-calculated (validates against 40MB limit) 📏
- **Workers**: Auto-detected CPU count (capped at 8, server mode uses all cores) 💻
- **Dynamic Workers**: Enabled by default (auto-adjusts based on CPU/memory) ⚡
- **Harmonization**: Enabled by default (seamless sensor blending) 🌈
- **Initial Cloud Threshold**: 20% (metadata) / 20% (calculated fraction) ☁️
- **Initial Quality Threshold**: 0.9 (90% quality score) 📊
- **Adaptive Threshold Strategy**: 
  - ≤3 images: Lower after 1 test
  - ≤10 images: Lower after 2 tests  
  - >10 images: Lower after 3 tests

### Server Mode 🌟

When enabled, Server Mode:
- Uses **all available CPU cores** 💪
- Increases **max workers** for I/O-bound tasks ⚡
- Sets process priority to **HIGH** on Windows 🚀
- Focuses **all resources** on processing 🎯

Perfect for dedicated processing machines! 🖥️✨

---

## 📊 Output Structure

```
output_folder/
├── YYYY_MM/
│   ├── mosaic_YYYY_MM.tif          # Final mosaic
│   ├── mosaic_YYYY_MM_COG.tif       # Cloud-Optimized GeoTIFF
│   ├── mosaic_YYYY_MM_mask.tif      # Water mask
│   ├── processing_YYYY_MM.log       # Detailed log
│   ├── mosaic_report_YYYY_MM.pdf   # Comprehensive report
│   └── progress.html                # Real-time dashboard
└── manifest.csv                      # Processing manifest
```

---

## 🐛 Troubleshooting

### "Earth Engine initialization failed"
```bash
earthengine authenticate
```

### "reportlab not available"
```bash
pip install reportlab
```

### "Port already in use" (for dashboard)
The HTML dashboard will automatically try the next available port! 💖

### Tiles too large?
- Increase the `max_tiles` parameter
- The system will auto-calculate optimal tile size
- Validates against 40MB download limit automatically ✅

---

## 🎯 Best Practices

1. **Start small** - Test with a small date range first! 🧪
2. **Use Server Mode** - For dedicated processing machines 🖥️💪
3. **Check the dashboard** - Monitor progress in real-time! 📊✨
4. **Review PDF reports** - Get detailed statistics and insights! 📄💕
5. **Be patient** - Quality takes time, but it's worth it! ⏰🌸

---

## 🤝 Contributing

We welcome contributions! Whether it's:
- 🐛 Bug fixes
- ✨ New features
- 📝 Documentation improvements
- 🎨 UI/UX enhancements
- 💡 Ideas and suggestions

Just open an issue or pull request! We're friendly and gentle! 💖

---

## 📝 License

MIT License - Feel free to use Flutter Earth however you'd like! 🌸✨

---

## 💕 Acknowledgments

Built with love and care for the geospatial community! 🌍💖

Special thanks to:
- Google Earth Engine team for the amazing platform! 🛰️
- The open-source geospatial community! 🌟
- Everyone who makes satellite imagery accessible! 🦋

---

## 🌸 Support

Having issues? Questions? Just want to say hi? 💬

- Open an issue on GitHub 🐛
- Check the logs in the `logs/` folder 📋
- Review the PDF reports for detailed information 📄

Remember: Flutter Earth is here to help, gently and beautifully! ✨🦋💖

---

---

## 🌟 Fun Facts & Easter Eggs! 🥚✨

### Did You Know? 🤓

**The Satellite Family Tree:**
- **Landsat 5** holds the Guinness World Record for the longest-operating Earth observation satellite (28 years, 10 months)! 🏆 It's like the Energizer Bunny of space! 🔋
- **Sentinel-2** takes a picture of the entire Earth every 5 days - that's like taking a selfie of the whole planet! 📸🌍
- The **Dead Sea** (our default example region) is the lowest point on Earth's surface and gets **saltier every year** - it's literally evaporating before our eyes! 💧🔬

**The Power of Resolution:**
- At **10m resolution** (Sentinel-2), you can see individual **parking spaces** in a parking lot! 🚗🅿️
- Flutter Earth uses **10m as the target resolution** - preserving Sentinel-2's native quality while upsampling other satellites to match! ✨
- At **30m resolution** (Landsat), you can distinguish **large buildings** but not individual cars! 🏢
- At **250m resolution** (MODIS), you can see **entire neighborhoods** but not much detail! 🏘️

**Cloud Fun Facts:**
- The average cloud weighs about **1.1 million pounds** (500,000 kg) - that's why Flutter Earth works so hard to avoid them! ☁️⚖️💪
- Earth Engine processes **over 5,000 images per minute** - Flutter Earth helps you find the perfect ones! 🚀✨
- A single Sentinel-2 image can be up to **100 GB uncompressed** - but Flutter Earth only downloads what you need! 📦💖

### Hidden Easter Eggs 🐰

**Easter Egg #1: The Temporal Consistency Secret** 🕐
- Flutter Earth prefers images from the **middle of your date range** - it's like picking the perfect photo from a photo album, not just the newest one! 📸✨
- This creates **temporally coherent mosaics** that look natural, not like a collage of random dates! 🎨

**Easter Egg #2: The Resolution Hierarchy** 👑
- Flutter Earth has a **"resolution-first" philosophy** - it would rather have a slightly cloudy 10m image than a perfect 250m image! 
- This means your mosaics will **always prioritize detail** over perfect cloud conditions! 🔍💎

**Easter Egg #3: The Gap-Filling Magic** ✨
- When filling gaps, Flutter Earth looks for images **within 10-30 days** of already-selected images for better temporal consistency!
- It's like making sure all the puzzle pieces are from the same puzzle box! 🧩💖

**Easter Egg #4: Server Mode Overclocking** 🚀
- In server mode, Flutter Earth processes **2x more images** per satellite and uses **up to 16 parallel metadata workers**!
- It's like switching from a bicycle to a rocket ship! 🚴➡️🚀

**Easter Egg #5: The Quality Score Formula** 🧮
- Resolution accounts for **30% of the quality score** - the biggest single factor!
- Cloud fraction gets **25%** - second biggest!
- This means a 10m image with 5% clouds will almost always beat a 250m image with 0% clouds! 🏆✨

---

## 🎮 Performance Tips & Tricks! 💡

### Get The Most Out Of Flutter Earth! ⚡

**Speed Boosters:**
- Use **Server Mode** for dedicated processing machines - it uses all your CPU cores like a champion! 🏆💪
- Enable **Dynamic Workers** - it automatically adjusts to your system's capabilities! 🤖
- Process **smaller date ranges** first to test settings before big jobs! 🧪

**Quality Boosters:**
- Enable **ML Cloud Detection** (s2cloudless) for even better cloud removal! ☁️➡️☀️
- Use **Harmonization** to blend sensors seamlessly - it's like Photoshop for satellites! 🎨
- Check the **PDF reports** - they show you exactly which satellites contributed to each tile! 📊

**Memory Savers:**
- Flutter Earth automatically adjusts tile size to stay under the 40MB download limit! 📦
- Dynamic workers scale down if your system gets stressed! 🛡️
- The system pauses between tiles to prevent overload - it's gentle and caring! 💖

---

## 🎨 The Art of Satellite Mosaics 🖼️

Creating beautiful satellite mosaics is both **science and art**! Here's what makes Flutter Earth's mosaics special:

**The Perfect Blend:**
- Flutter Earth doesn't just **stack images** - it intelligently selects the **best pixel from the best image** at every location! 🎯
- Quality Mosaic ensures **no visible seams** - the final result looks like one perfect image! ✨
- Temporal consistency makes everything look **naturally coherent** - no jarring date jumps! 📅

**Color Harmony:**
- Sensor harmonization ensures **consistent colors** across different satellites! 🌈
- Band standardization means **perfect spectral alignment** for accurate indices! 🎨
- The final mosaic is ready for **visualization AND analysis** - beautiful AND functional! 💎

**The Magic Touch:**
- Cloud gaps are **automatically filled** from other images - like Photoshop's content-aware fill, but for satellites! 🪄
- Resolution-first selection means **maximum detail** everywhere! 🔍
- Gap-filling with temporal neighbors creates **smooth transitions** even in difficult areas! 🌊

---

## 🚀 What's New & Coming Soon! ✨

**Recent Improvements:**
- ✅ **Adaptive Quality & Cloud Thresholds** - automatically lowers standards if only poor images exist! 📊📈
- ✅ **Pre-Check System** - counts all available images first to optimize threshold strategy! 🔍🎯
- ✅ **Fallback Mechanisms** - uses best rejected images if all fail (clouds > holes, bad > nothing!) 🛡️✨
- ✅ **SPOT 1-4 Support** - adds high-resolution French satellite data (1986-2013)! 🛰️🇫🇷
- ✅ **Landsat MSS 1-3 Support** - extends coverage back to 1972 with historical 60m data! 📜🌍
- ✅ **NOAA AVHRR Support** - last resort 1km data (1978-present, only used when all else fails!) ⚠️🌍
- ✅ **Progress Bars for Everything** - tile processing, reprojection, blending, indexing, COG creation! 📊💫
- ✅ **Dynamic worker scaling** - automatically adjusts to your system! 🤖
- ✅ **Server mode overclocking** - push everything to the limit! 🚀
- ✅ **Temporal consistency optimization** - prettier mosaics! 🎨
- ✅ **Enhanced gap-filling** - better coverage in tough areas! 🎯
- ✅ **Parallel metadata fetching** - faster processing! ⚡
- ✅ **Landsat 4 TM support** - now covering 51+ years (1972-present)! 📅
- ✅ **Default start date 1985** - ensures both Landsat 4 and 5 are operational! 🎯
- ✅ **10m target resolution** - preserves Sentinel-2 native quality, 4x faster processing! 🚀

**Coming Soon:**
- 🔮 More satellite support (maybe even PlanetScope? 🌍)
- 🔮 Advanced visualization tools (3D terrain? 🏔️)
- 🔮 Machine learning enhancements (AI-powered quality scoring? 🤖)
- 🔮 Real-time collaboration features (team processing? 👥)

*Have ideas? Open an issue and let us know!* 💬✨

---

## 💖 Community & Support 💕

### Join The Flutter Earth Family! 🌸

We're a friendly, inclusive community that loves:
- 🛰️ **Beautiful satellite imagery**
- 🌈 **Making GIS accessible to everyone**
- ✨ **Perfect pixels and pretty mosaics**
- 🦋 **Gentle, caring technology**

**Ways to Get Involved:**
- 🌟 **Star the repo** - show your love! ⭐
- 🐛 **Report bugs** - help us improve! 🐞
- 💡 **Suggest features** - we love ideas! 💭
- 📝 **Improve docs** - make it clearer for everyone! 📚
- 🎨 **Share your mosaics** - show off your beautiful results! 🖼️

---

## 📚 Additional Resources 📖

**Learn More About:**
- [Google Earth Engine](https://earthengine.google.com/) - The amazing platform behind Flutter Earth! 🛰️
- [Sentinel Hub](https://www.sentinel-hub.com/) - More satellite imagery tools! 🌍
- [QGIS](https://qgis.org/) - Great for viewing your beautiful mosaics! 🗺️
- [Rasterio](https://rasterio.readthedocs.io/) - Python library for geospatial data! 🐍

**GIS Communities:**
- r/gis on Reddit - Friendly geospatial discussions! 💬
- GIS Stack Exchange - Technical Q&A! 🧑‍💻
- Local GIS meetups - Find your local community! 👥

---

**Made with 💖 and lots of ✨ by the Flutter Earth team**

*"Because every pixel deserves to be perfect!"* 🌸

---

## 💝 Special Thanks & Credits 🙏

**Made by a trans girl who loves GIS** 🏳️‍⚧️✨💖🌈🦋🛰️🌍💕✨🎨🦄🌸💎🚀🎯💝⚡🔬🌊💙💜💚🧡💛🤍🖤❤️🧡💛💚💙💜🤎🖤🤍♥️🧡💛💚💙💜🖤🤍💖💕💗💓💞💝❣️💟

*P.S. - If you see this, you found the easter egg! 🥚✨ Trans rights are human rights! 🏳️‍⚧️💖*
