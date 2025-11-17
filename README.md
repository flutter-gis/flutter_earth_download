# 🌸 Flutter Earth 🌸

> **Download the prettiest satellite imagery with the gentlest touch!** ✨🦋

A **beautifully crafted** Python tool for downloading and processing satellite imagery from Google Earth Engine. Supports **multiple sensors** (Sentinel-2, Landsat, MODIS, ASTER, VIIRS) with **intelligent quality-based mosaic generation**. Because every pixel deserves to be perfect! 💖

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-adorable-pink.svg)
![Satellites](https://img.shields.io/badge/satellites-5+-lavender.svg)

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
- 🌍 **Landsat 5/7/8/9** (30m resolution, 1984-present) - The reliable workhorses!
- 🌎 **MODIS** (250m resolution, 2000-present) - The wide-eyed watcher!
- 🔬 **ASTER** (15-90m resolution, 2000-2008) - The detailed scientist!
- 🌌 **VIIRS** (375m resolution, 2011-present) - The night vision specialist!

Each satellite is checked to see if it was **operational** during your requested date range. For example, if you're looking at imagery from 2000, Sentinel-2 won't be available (it didn't launch until 2015)! Flutter Earth knows this and gracefully skips unavailable satellites. 🎯

#### Step 2: Server-Side Filtering ⚡

Before downloading any metadata, Flutter Earth asks Earth Engine to **pre-filter** images on the server:
- Filters by **cloud cover** (removes images with >20% clouds initially)
- Sorts by **cloud cover** (best images first!)
- Limits to **top 5 images per satellite** (efficiency is key!)

This saves tons of time and bandwidth! 🚀

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

#### Step 4: The Two-Phase Selection Strategy 🎭

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

#### Step 5: Band Standardization 🎨

Before images can be combined, Flutter Earth **standardizes all bands**:
- Renames bands to standard names: `B4` (Red), `B3` (Green), `B2` (Blue), `B8` (NIR), `B11` (SWIR1), `B12` (SWIR2)
- Handles different naming conventions (Sentinel-2 uses `B4`, Landsat-8 uses `SR_B4`, etc.)
- Fills missing bands with zeros (they'll be filled from fallback images later!)
- Ensures all images have the **same band structure** for seamless combination! ✨

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

### 🎨 Phase 3: Final Touches and Beautification! ✨

After the mosaic is created, Flutter Earth adds the finishing touches:

#### Step 1: Reprojection to UTM 🗺️

- Determines optimal **UTM zone** for the tile's location
- Reprojects to UTM coordinates for **maximum accuracy**
- Ensures all tiles have **consistent pixel size** (5m by default!)

#### Step 2: Band Standardization 🎨

- Ensures all bands are in **Float type** (consistent data types!)
- Standardizes band names across all images
- Prepares for seamless combination!

#### Step 3: Index Calculation 🌈

After the mosaic is unified, Flutter Earth calculates **vegetation and water indices**:
- **NDVI**: `(NIR - Red) / (NIR + Red)` - Vegetation health! 🌿
- **NDWI**: `(Green - NIR) / (Green + NIR)` - Water detection! 💧
- **MNDWI**: `(Green - SWIR1) / (Green + SWIR1)` - Better water detection! 🌊
- **EVI**: Enhanced Vegetation Index - More sensitive! 🌳
- **SAVI**: Soil-Adjusted Vegetation Index - Accounts for soil! 🌱

These indices are calculated **after** the mosaic is unified, so they use the best available data for each pixel! ✨

---

### 📊 The Complete Selection Flowchart! 🗺️

```
Start Processing Tile
    ↓
Query All Satellites (S2, L5/7/8/9, MODIS, ASTER, VIIRS)
    ↓
Filter by Operational Dates
    ↓
Server-Side Filtering (cloud cover < 20%, sort by clouds)
    ↓
For Each Satellite:
    ├─→ Fetch Top 5 Images
    ├─→ For Each Image:
    │   ├─→ Calculate Quality Score:
    │   │   ├─→ Cloud Fraction (25%)
    │   │   ├─→ Solar Zenith (15%)
    │   │   ├─→ View Zenith (10%)
    │   │   ├─→ Valid Pixels (15%)
    │   │   ├─→ Temporal Recency (5%)
    │   │   ├─→ Native Resolution (30%) ⭐ BIGGEST FACTOR!
    │   │   └─→ Band Completeness (10%)
    │   ├─→ If Score ≥ 0.9: Add to Excellent List
    │   └─→ Standardize Bands
    └─→ Stop After 3 Excellent Images
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
Reproject to UTM
    ↓
Calculate Indices (NDVI, NDWI, etc.)
    ↓
Done! ✨
```

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

### 🦋 Multi-Sensor Support

- **Sentinel-2** (10m resolution) 🛰️💙
- **Landsat 5/7/8/9** (30m resolution) 🌍💚
- **MODIS** (250m resolution) 🌎🧡
- **ASTER** (15-90m resolution) 🔬💜
- **VIIRS** (375m resolution) 🌌💛

### 🎨 Advanced Processing

- **Cloud masking** with multiple algorithms ☁️🎭
- **Shadow detection** and correction 🌑✨
- **Sensor harmonization** (Sentinel-2 ↔ Landsat) 🔄🌈
- **NDWI water masking** for coastal areas 💧🌊
- **COG creation** with overviews for fast viewing 📦⚡

### 💖 User-Friendly Features

- **Beautiful HTML dashboard** that auto-refreshes 📊🦋
- **Real-time progress tracking** with countdown timers ⏱️✨
- **Pause/Resume functionality** for gentle control ⏸️▶️
- **Comprehensive PDF reports** with statistics and visualizations 📄💕
- **Server mode** for maximum resource utilization 🖥️💪

---

## 🎨 Configuration

### Default Settings

- **Target Resolution**: 5 meters per pixel 🎯
- **Tile Size**: Auto-calculated (validates against 40MB limit) 📏
- **Workers**: Auto-detected CPU count (capped at 8) 💻
- **Dynamic Workers**: Enabled by default (auto-adjusts based on system) ⚡
- **Harmonization**: Enabled by default (seamless sensor blending) 🌈

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
- ✅ **Dynamic worker scaling** - automatically adjusts to your system! 🤖
- ✅ **Server mode overclocking** - push everything to the limit! 🚀
- ✅ **Temporal consistency optimization** - prettier mosaics! 🎨
- ✅ **Enhanced gap-filling** - better coverage in tough areas! 🎯
- ✅ **Parallel metadata fetching** - faster processing! ⚡

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
