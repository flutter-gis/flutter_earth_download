# <span style="color: #ff6b9d;">🌸</span> <span style="color: #4ecdc4; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);">Flutter Earth</span> <span style="color: #ff6b9d;">🌸</span>

> <span style="color: #667eea; font-size: 1.1em;">**Download the prettiest satellite imagery with the gentlest touch!**</span> ✨🦋

A <span style="color: #f093fb; font-weight: bold;">**beautifully crafted**</span> Python tool for downloading and processing satellite imagery from Google Earth Engine. Supports <span style="color: #4facfe; font-weight: bold;">**12+ satellite sensors**</span> (<span style="color: #00d2ff;">Sentinel-2</span>, <span style="color: #a8edea;">Landsat 4/5/7/8/9</span>, <span style="color: #a8edea;">Landsat MSS 1-3</span>, <span style="color: #ffecd2;">SPOT 1-4</span>, <span style="color: #fcb69f;">MODIS</span>, <span style="color: #ff9a9e;">ASTER</span>, <span style="color: #fecfef;">VIIRS</span>, <span style="color: #ffd89b;">NOAA AVHRR</span>) covering <span style="color: #ff6b6b; font-weight: bold;">**1972 to present**</span> with <span style="color: #4ecdc4; font-weight: bold;">**intelligent adaptive quality-based mosaic generation**</span>. Features <span style="color: #a8c0ff;">**dynamic thresholds**</span>, <span style="color: #ffecd2;">**fallback mechanisms**</span>, and <span style="color: #ff9a9e;">**real-time progress tracking**</span> for the entire processing pipeline. <span style="color: #ff6b9d; font-style: italic;">Because every pixel deserves to be perfect!</span> 💖

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-adorable-pink.svg)
![Satellites](https://img.shields.io/badge/satellites-12+-lavender.svg)
![Coverage](https://img.shields.io/badge/coverage-1972--present-purple.svg)
![Resolution](https://img.shields.io/badge/resolution-10m%20target-brightgreen.svg)

---

## <span style="color: #667eea; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">🌈 What Does This Do?</span>

Ever wanted to download satellite imagery but got frustrated with:
- <span style="color: #ff6b6b;">❌ **Cloudy images** ruining your beautiful mosaics?</span> ☁️💔
- <span style="color: #ffa500;">❌ **Low-resolution data** that looks pixelated?</span> 📉😢
- <span style="color: #ff6b9d;">Having to **manually pick** the "best" satellite?</span> 🤔😓
- <span style="color: #ff4757;">**Complex APIs** that make you cry?</span> 😭💧

<span style="color: #4ecdc4; font-size: 1.1em; font-weight: bold;">**Well, worry no more!**</span> 🌸✨ <span style="color: #ff6b9d; font-weight: bold;">Flutter Earth</span> automatically:
- <span style="color: #00d2ff;">✅ Finds the **best quality** images across **all available satellites**</span> 🏆💎
- <span style="color: #a8edea;">✅ Intelligently combines them into **gorgeous mosaics**</span> 🎨🌈
- <span style="color: #ffecd2;">✅ Handles **clouds, shadows, and atmospheric effects** like magic</span> ☁️➡️☀️✨
- <span style="color: #ff9a9e;">✅ Creates **Cloud-Optimized GeoTIFFs (COGs)** ready for analysis</span> 📦💖
- <span style="color: #f093fb;">✅ Shows you **real-time progress** with a beautiful dashboard</span> 📊🦋
- <span style="color: #4facfe;">✅ **Progress bars for EVERYTHING** - tile processing, mosaic stitching, index calculation, COG creation!</span> 📊✨
- <span style="color: #a8c0ff;">✅ **Adaptive quality thresholds** - automatically lowers standards if only poor images exist!</span> 📉📈
- <span style="color: #ffd89b;">✅ **Fallback mechanisms** - uses best available image even if all are "bad" (clouds better than holes!)</span> ☁️>🕳️
- <span style="color: #fcb69f;">✅ **Pre-check system** - counts all available images first to optimize strategy!</span> 🔍🎯
- <span style="color: #667eea;">✅ **Dynamic worker scaling** that works efficiently and gently</span> 💪🌸
- <span style="color: #764ba2;">✅ **Server mode** - designed to run continuously with care</span> 🖥️💕

---

## <span style="color: #ff6b6b; background: linear-gradient(90deg, #ff6b6b 0%, #ee5a6f 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">🚀 Quick Start</span>

### <span style="color: #4facfe;">Prerequisites</span>

1. <span style="color: #00d2ff; font-weight: bold;">**Python 3.7+**</span> <span style="color: #a8edea;">(because we're modern and lovely!)</span> 🐍💕
2. <span style="color: #4ecdc4; font-weight: bold;">**Google Earth Engine account**</span> <span style="color: #ffd89b;">(it's free!)</span> 🎉✨
   - Sign up at: <span style="color: #667eea;">https://earthengine.google.com/</span>
3. <span style="color: #f093fb;">**Authenticate with Earth Engine:**</span>
   ```bash
   earthengine authenticate
   ```

### <span style="color: #ff9a9e;">Installation</span>

1. <span style="color: #a8c0ff; font-weight: bold;">**Clone this repository:**</span>
   ```bash
   git clone https://github.com/flutter-gis/flutter_earth_download.git
   cd flutter_earth_download
   ```

2. <span style="color: #fcb69f; font-weight: bold;">**Install dependencies:**</span>
   ```bash
   pip install -r requirements.txt
   ```
   
   Or install individually:
   ```bash
   pip install earthengine-api rasterio numpy shapely pyproj tqdm requests scikit-image psutil reportlab matplotlib s2cloudless
   ```
   
   <span style="color: #ff6b9d; font-style: italic;">*(Optional but recommended: `s2cloudless` for advanced cloud detection)*</span> ☁️🔍

3. <span style="color: #ff6b6b; font-weight: bold; font-size: 1.1em;">**Run it!**</span>
   ```bash
   python main.py
   ```
   
   Or on Windows, just double-click <span style="color: #4ecdc4;">`run_gee.bat`</span> 🪟💖

---

## <span style="color: #667eea; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">📖 How to Use</span>

### <span style="color: #4facfe; font-size: 1.1em;">GUI Mode</span> <span style="color: #ff6b9d;">(Recommended for Everyone!)</span> 🧑💕

Just run <span style="color: #00d2ff; font-family: monospace; background: rgba(0,210,255,0.1); padding: 2px 6px; border-radius: 3px;">`python main.py`</span> and a friendly GUI will pop up! Fill in:
- <span style="color: #4ecdc4; font-weight: bold;">**Bounding Box**</span>: <span style="color: #a8edea;">Where do you want imagery?</span> <span style="color: #ffd89b;">(lon_min, lat_min, lon_max, lat_max)</span> 📍🌍
- <span style="color: #f093fb; font-weight: bold;">**Date Range**</span>: <span style="color: #ff9a9e;">When do you want imagery?</span> <span style="color: #fcb69f;">(YYYY-MM-DD format)</span> 📅✨
- <span style="color: #a8c0ff; font-weight: bold;">**Output Folder**</span>: <span style="color: #ffecd2;">Where should we save your beautiful mosaics?</span> 💾🌸
- <span style="color: #667eea; font-weight: bold;">**Max Tiles**</span>: <span style="color: #764ba2;">How many tiles?</span> <span style="color: #ff6b9d;">(auto-validates against 40MB limit)</span> 🔢💖
- <span style="color: #ff6b6b; font-weight: bold;">**Options**</span>: <span style="color: #ee5a6f;">Toggle satellites, harmonization, ML cloud cleanup, dynamic workers, server mode, etc.</span> ⚙️🌈

Click <span style="color: #4facfe; font-weight: bold; font-size: 1.1em;">**Submit**</span> and watch the magic happen! ✨🦋

The dashboard will automatically open in your browser showing:
- <span style="color: #00d2ff;">📊 Real-time progress bars</span> <span style="color: #a8edea;">(tile, mosaic, and full project!)</span>
- <span style="color: #ffd89b;">⏱️ Countdown timer</span> <span style="color: #fcb69f;">(estimated time remaining)</span> ⏰
- <span style="color: #f093fb;">📋 Console output</span> <span style="color: #ff9a9e;">with timestamps and color-coded messages</span> 💬
- <span style="color: #a8c0ff;">🛰️ Satellite usage statistics</span> <span style="color: #667eea;">with quality metrics</span> 🌟
- <span style="color: #764ba2;">🎯 Pause/Resume button</span> <span style="color: #ff6b9d;">for gentle control</span> ⏸️▶️

### <span style="color: #4facfe;">CLI Mode</span> <span style="color: #ff6b9d;">(For Terminal Lovers)</span> 💻

If you're a <span style="color: #00d2ff;">command-line warrior</span>, the tool will prompt you for all the same information. <span style="color: #a8edea;">No GUI? No problem!</span> 💪

### <span style="color: #4facfe;">Programmatic Usage</span>

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

## <span style="color: #ff6b6b; background: linear-gradient(90deg, #ff6b6b 0%, #ee5a6f 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">✨ Features</span>

### <span style="color: #4facfe; font-size: 1.1em;">🎯 Intelligent Quality Scoring</span>

<span style="color: #a8edea;">Flutter Earth evaluates each satellite image based on:</span>
- <span style="color: #00d2ff;">☁️ **Cloud fraction**</span> <span style="color: #ffd89b;">(less is better!)</span>
- <span style="color: #ffa500;">☀️ **Solar zenith angle**</span> <span style="color: #fcb69f;">(optimal lighting!)</span>
- <span style="color: #4ecdc4;">✅ **Valid pixel fraction**</span> <span style="color: #a8edea;">(data completeness!)</span>
- <span style="color: #f093fb;">📅 **Temporal recency**</span> <span style="color: #ff9a9e;">(fresh data!)</span>
- <span style="color: #a8c0ff;">🔍 **Native resolution**</span> <span style="color: #667eea;">(crisp details!)</span>
- <span style="color: #764ba2;">🎨 **Band completeness**</span> <span style="color: #ff6b9d;">(full spectrum!)</span>

### <span style="color: #667eea; font-size: 1.1em;">🌈 Resolution-First Gap Filling</span>

<span style="color: #4facfe;">When filling gaps in mosaics, Flutter Earth prioritizes:</span>
- <span style="color: #00d2ff;">🏆 **Higher resolution** images</span> <span style="color: #a8edea;">(even with minor clouds!)</span>
- <span style="color: #ffd89b;">💎 **Quality scores** as tiebreakers</span>
- <span style="color: #fcb69f;">✨ **Smart iteration** until coverage is complete</span>

---

## <span style="color: #667eea; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.4em;">🦋 The Magical Image Selection Process: How Flutter Earth Chooses the Perfect Pixels!</span> ✨

<span style="color: #4facfe;">Ever wondered how Flutter Earth magically picks the best satellite images from thousands of options?</span> <span style="color: #ff6b9d;">Let's dive into the beautiful, intricate process that makes every pixel perfect!</span> 💖

### <span style="color: #4facfe; font-size: 1.2em;">📊 Phase 1: The Great Image Hunt</span> 🎯

<span style="color: #a8edea;">When Flutter Earth starts processing a tile, it embarks on an epic quest to find the best images from</span> <span style="color: #00d2ff; font-weight: bold;">**all available satellites**</span><span style="color: #a8edea;">!</span> <span style="color: #ffd89b;">Here's what happens:</span>

#### <span style="color: #4ecdc4;">Step 1: Collection Gathering</span> 🌍

<span style="color: #f093fb;">Flutter Earth queries</span> <span style="color: #ff9a9e; font-weight: bold;">**multiple satellite collections**</span> <span style="color: #fcb69f;">simultaneously:</span>
- <span style="color: #00d2ff;">🛰️ **Sentinel-2**</span> <span style="color: #a8edea;">(10m resolution, launched 2015)</span> <span style="color: #ffd89b;">- The sharp-eyed observer!</span>
- <span style="color: #4ecdc4;">🌍 **Landsat 4/5/7/8/9**</span> <span style="color: #a8edea;">(30m resolution, 1982-present)</span> <span style="color: #fcb69f;">- The reliable workhorses!</span> 🏆
- <span style="color: #ffa500;">🌎 **MODIS**</span> <span style="color: #ffd89b;">(250m resolution, 2000-present)</span> <span style="color: #fcb69f;">- The wide-eyed watcher!</span>
- <span style="color: #f093fb;">🔬 **ASTER**</span> <span style="color: #ff9a9e;">(15-90m resolution, 2000-2008)</span> <span style="color: #a8c0ff;">- The detailed scientist!</span>
- <span style="color: #667eea;">🌌 **VIIRS**</span> <span style="color: #764ba2;">(375m resolution, 2011-present)</span> <span style="color: #ff6b9d;">- The night vision specialist!</span>

<span style="color: #4facfe;">Each satellite is checked to see if it was</span> <span style="color: #00d2ff; font-weight: bold;">**operational**</span> <span style="color: #a8edea;">during your requested date range.</span> <span style="color: #ffd89b;">For example, if you're looking at imagery from 2000, Sentinel-2 won't be available (it didn't launch until 2015)!</span> <span style="color: #4ecdc4;">Flutter Earth knows this and gracefully skips unavailable satellites.</span> 🎯

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

#### <span style="color: #4facfe;">Step 3: The Quality Scoring Magic</span> ✨

<span style="color: #a8edea;">For each candidate image, Flutter Earth calculates a</span> <span style="color: #00d2ff; font-weight: bold;">**comprehensive quality score**</span> <span style="color: #ffd89b;">(0.0 to 1.0, where 1.0 is perfect!).</span> <span style="color: #fcb69f;">Here's how each factor contributes:</span>

<span style="color: #00d2ff; font-weight: bold; font-size: 1.1em;">**☁️ Cloud Fraction (25% weight)**</span>
- <span style="color: #a8edea;">Less clouds = better score!</span>
- <span style="color: #4ecdc4;">Formula:</span> <span style="color: #f093fb; font-family: monospace; background: rgba(240,147,251,0.1); padding: 2px 6px; border-radius: 3px;">`cloud_score = max(0.0, 1.0 - cloud_fraction * 1.5)`</span>
- <span style="color: #ff9a9e;">A 10% cloudy image gets:</span> <span style="color: #a8c0ff; font-family: monospace; background: rgba(168,192,255,0.1); padding: 2px 6px; border-radius: 3px;">`1.0 - 0.10 * 1.5 = 0.85`</span> <span style="color: #667eea;">(85% of cloud score)</span>
- <span style="color: #764ba2;">A 50% cloudy image gets:</span> <span style="color: #ff6b9d; font-family: monospace; background: rgba(255,107,157,0.1); padding: 2px 6px; border-radius: 3px;">`1.0 - 0.50 * 1.5 = 0.25`</span> <span style="color: #ff6b6b;">(25% of cloud score)</span>
- <span style="color: #ee5a6f; font-weight: bold;">**Heavy penalty** for cloudy images!</span> ☁️💔

<span style="color: #ffa500; font-weight: bold; font-size: 1.1em;">**☀️ Solar Zenith Angle (15% weight)**</span>
- <span style="color: #ffd89b;">Lower zenith = sun higher in sky = better lighting!</span>
- <span style="color: #4ecdc4;">Optimal:</span> <span style="color: #00d2ff; font-weight: bold;"><30° zenith</span> <span style="color: #a8edea;">(perfect score!)</span>
- <span style="color: #fcb69f;">Good:</span> <span style="color: #ff9a9e;">30-60° zenith</span> <span style="color: #a8c0ff;">(gradual penalty)</span>
- <span style="color: #667eea;">Poor:</span> <span style="color: #764ba2;">>60° zenith</span> <span style="color: #ff6b9d;">(significant penalty, low sun = shadows!)</span>
- <span style="color: #4facfe;">Formula accounts for time of day and season!</span> 🌅

<span style="color: #4ecdc4; font-weight: bold; font-size: 1.1em;">**👁️ View Zenith Angle (10% weight)**</span>
- <span style="color: #a8edea;">Lower = more nadir (straight down) = less distortion!</span>
- <span style="color: #00d2ff;">Optimal:</span> <span style="color: #4ecdc4; font-weight: bold;"><10°</span> <span style="color: #f093fb;">(perfect score!)</span>
- <span style="color: #ff9a9e;">Acceptable:</span> <span style="color: #fcb69f;">10-50°</span> <span style="color: #a8c0ff;">(gradual penalty)</span>
- <span style="color: #667eea;">Poor:</span> <span style="color: #764ba2;">>50°</span> <span style="color: #ff6b9d;">(significant penalty, oblique angles = stretched pixels!)</span>

<span style="color: #4facfe; font-weight: bold; font-size: 1.1em;">**✅ Valid Pixel Fraction (15% weight)**</span>
- <span style="color: #00d2ff;">More valid data = better score!</span>
- <span style="color: #a8edea;">Minimum 30% valid pixels required</span> <span style="color: #ffd89b;">(below this = heavy penalty!)</span>
- <span style="color: #fcb69f;">Accounts for sensor errors, scan line gaps, and data quality issues!</span>

<span style="color: #f093fb; font-weight: bold; font-size: 1.1em;">**📅 Temporal Recency (5% weight)**</span>
- <span style="color: #ff9a9e;">Newer images get slightly higher scores!</span>
- <span style="color: #a8c0ff;">Formula:</span> <span style="color: #667eea; font-family: monospace; background: rgba(102,126,234,0.1); padding: 2px 6px; border-radius: 3px;">`temporal_score = max(0.5, 1.0 - (days_since_start / max_days) * 0.5)`</span>
- <span style="color: #764ba2;">A 1-day-old image gets</span> <span style="color: #ff6b9d; font-weight: bold;">~100%</span> <span style="color: #ff6b6b;">of temporal score</span>
- <span style="color: #ee5a6f;">A 365-day-old image gets</span> <span style="color: #ffa500; font-weight: bold;">~50%</span> <span style="color: #ffd89b;">of temporal score</span>
- <span style="color: #4ecdc4; font-weight: bold;">**Small but meaningful** preference for fresh data!</span> 🆕

<span style="color: #ff6b6b; font-weight: bold; font-size: 1.2em;">**🔍 Native Resolution (30% weight) - THE BIGGEST FACTOR!**</span> 🏆
- <span style="color: #ee5a6f; font-weight: bold; font-size: 1.1em;">**Resolution is king!**</span> <span style="color: #ffa500;">Higher resolution = dramatically better score!</span>
- <span style="color: #ffd89b;">Scoring tiers:</span>
  - <span style="color: #00d2ff; font-weight: bold;">**≤4m**:</span> <span style="color: #4ecdc4;">Perfect score (1.0)</span> <span style="color: #a8edea;">- Ultra-high resolution!</span> 💎
  - <span style="color: #4facfe; font-weight: bold;">**≤15m**:</span> <span style="color: #f093fb;">Excellent (0.95)</span> <span style="color: #ff9a9e;">- Sentinel-2, ASTER!</span> ✨
  - <span style="color: #a8c0ff; font-weight: bold;">**≤30m**:</span> <span style="color: #667eea;">Good (0.85)</span> <span style="color: #764ba2;">- Landsat family!</span> 🌍
  - <span style="color: #ff6b9d; font-weight: bold;">**≤60m**:</span> <span style="color: #ff6b6b;">Moderate (0.60)</span> <span style="color: #ee5a6f;">- Lower-res Landsat variants</span>
  - <span style="color: #ffa500; font-weight: bold;">**≤250m**:</span> <span style="color: #ffd89b;">Poor (0.40)</span> <span style="color: #fcb69f;">- MODIS territory!</span> 🌎
  - <span style="color: #667eea; font-weight: bold;">**≤400m**:</span> <span style="color: #764ba2;">Very poor (0.25)</span> <span style="color: #ff6b9d;">- VIIRS range!</span> 🌌
  - <span style="color: #ff6b6b; font-weight: bold;">**>400m**:</span> <span style="color: #ee5a6f;">Worst (0.15)</span> <span style="color: #ffa500;">- Coarse resolution!</span> 😢

<span style="color: #4facfe; font-weight: bold;">**Why resolution matters so much:**</span>
- <span style="color: #00d2ff;">A</span> <span style="color: #4ecdc4; font-weight: bold;">**10m Sentinel-2**</span> <span style="color: #a8edea;">image with 5% clouds beats a</span> <span style="color: #ffd89b; font-weight: bold;">**250m MODIS**</span> <span style="color: #fcb69f;">image with 0% clouds!</span>
- <span style="color: #f093fb;">Resolution determines how much detail you can see!</span>
- <span style="color: #ff9a9e;">Flutter Earth</span> <span style="color: #a8c0ff; font-weight: bold;">**prioritizes crisp, detailed imagery**</span> <span style="color: #667eea;">over perfect cloud-free conditions!</span> 🎯

<span style="color: #764ba2; font-weight: bold; font-size: 1.1em;">**🎨 Band Completeness (10% weight)**</span>
- <span style="color: #ff6b9d;">Checks for critical bands:</span> <span style="color: #ff6b6b; font-weight: bold;">RGB (required!)</span><span style="color: #ff6b9d;">,</span> <span style="color: #ee5a6f; font-weight: bold;">NIR, SWIR1, SWIR2 (highly desired!)</span>
- <span style="color: #ffa500;">Missing IR bands = significant penalty</span> <span style="color: #ffd89b;">(can't compute vegetation indices!)</span>
- <span style="color: #fcb69f;">Formula:</span> <span style="color: #f093fb; font-family: monospace; background: rgba(240,147,251,0.1); padding: 2px 6px; border-radius: 3px;">`completeness = RGB_score * 0.2 + IR_score * 0.6 + index_score * 0.2`</span>
- <span style="color: #ff9a9e;">Ensures images have the spectral data needed for analysis!</span> 🌈

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

### <span style="color: #667eea; font-size: 1.2em;">🦋 Multi-Sensor Support (12+ Satellites!)</span>

<span style="color: #4facfe; font-weight: bold; font-size: 1.1em;">**High Resolution (≤30m):**</span>
- <span style="color: #00d2ff;">🛰️ **Sentinel-2**</span> <span style="color: #a8edea;">(10m, 2015-present)</span> <span style="color: #ffd89b;">- The sharp-eyed observer!</span> 💙
- <span style="color: #4ecdc4;">🌍 **Landsat 4 TM**</span> <span style="color: #a8edea;">(30m, 1982-1993)</span> <span style="color: #fcb69f;">- The early pioneer!</span> 💚
- <span style="color: #4ecdc4;">🌍 **Landsat 5 TM**</span> <span style="color: #a8edea;">(30m, 1984-2013)</span> <span style="color: #f093fb;">- The record-holder (28+ years!)</span> 🏆💚
- <span style="color: #4ecdc4;">🌍 **Landsat 7 ETM+**</span> <span style="color: #a8edea;">(30m, 1999-present)</span> <span style="color: #ff9a9e;">- The striped survivor!</span> 💚
- <span style="color: #4ecdc4;">🌍 **Landsat 8 OLI/TIRS**</span> <span style="color: #a8edea;">(30m, 2013-present)</span> <span style="color: #a8c0ff;">- The modern workhorse!</span> 💚
- <span style="color: #4ecdc4;">🌍 **Landsat 9 OLI-2/TIRS-2**</span> <span style="color: #a8edea;">(30m, 2021-present)</span> <span style="color: #667eea;">- The newest addition!</span> 💚
- <span style="color: #4ecdc4;">🌍 **Landsat 1-3 MSS**</span> <span style="color: #a8edea;">(60m, 1972-1983)</span> <span style="color: #764ba2;">- The historical archive!</span> 📜💚
- <span style="color: #ffa500;">🛰️ **SPOT 1**</span> <span style="color: #ffd89b;">(10m pan, 20m MS, 1986-2003)</span> <span style="color: #fcb69f;">- The French precision!</span> 🇫🇷
- <span style="color: #ffa500;">🛰️ **SPOT 2**</span> <span style="color: #ffd89b;">(10m pan, 20m MS, 1990-2009)</span> <span style="color: #f093fb;">- The reliable backup!</span> 🇫🇷
- <span style="color: #ffa500;">🛰️ **SPOT 3**</span> <span style="color: #ffd89b;">(10m pan, 20m MS, 1993-1997)</span> <span style="color: #ff9a9e;">- The short-lived star!</span> 🇫🇷
- <span style="color: #ffa500;">🛰️ **SPOT 4**</span> <span style="color: #ffd89b;">(10m pan, 20m MS, 1998-2013)</span> <span style="color: #a8c0ff;">- The extended mission!</span> 🇫🇷

<span style="color: #f093fb; font-weight: bold; font-size: 1.1em;">**Medium Resolution (60-400m):**</span>
- <span style="color: #ff9a9e;">🔬 **ASTER**</span> <span style="color: #a8c0ff;">(15-90m, 2000-2008)</span> <span style="color: #667eea;">- The detailed scientist!</span> 💜

<span style="color: #ff6b6b; font-weight: bold; font-size: 1.1em;">**Low Resolution (>400m):**</span>
- <span style="color: #ffa500;">🌎 **MODIS Terra**</span> <span style="color: #ffd89b;">(250m, 2000-present)</span> <span style="color: #fcb69f;">- The wide-eyed watcher!</span> 🧡
- <span style="color: #ffa500;">🌎 **MODIS Aqua**</span> <span style="color: #ffd89b;">(250m, 2002-present)</span> <span style="color: #f093fb;">- The water-focused twin!</span> 🧡
- <span style="color: #667eea;">🌌 **VIIRS**</span> <span style="color: #764ba2;">(375m, 2011-present)</span> <span style="color: #ff6b9d;">- The night vision specialist!</span> 💛
- <span style="color: #ff6b6b;">🌍 **NOAA AVHRR**</span> <span style="color: #ee5a6f;">(1km, 1978-present)</span> <span style="color: #ff6b6b; font-weight: bold;">- **ABSOLUTE LAST RESORT** only!</span> ⚠️🔴
  - <span style="color: #ffa500;">Only used when ALL other satellites fail</span> <span style="color: #ffd89b;">(very coarse resolution!)</span>

<span style="color: #4facfe; font-weight: bold; font-size: 1.1em;">**Coverage Timeline:**</span>
- <span style="color: #00d2ff;">🌟 **1972-1982**:</span> <span style="color: #a8edea;">Landsat MSS 1-3 only</span> <span style="color: #ffd89b;">(60m, historical)</span>
- <span style="color: #4ecdc4;">🌟 **1982-1985**:</span> <span style="color: #a8edea;">Landsat 4 TM</span> <span style="color: #fcb69f;">(early 30m era)</span>
- <span style="color: #f093fb;">🌟 **1985-1993**:</span> <span style="color: #ff9a9e;">Landsat 4 + 5 overlap</span> <span style="color: #a8c0ff; font-weight: bold;">(best coverage!)</span>
- <span style="color: #667eea;">🌟 **1993-1999**:</span> <span style="color: #764ba2;">Landsat 5 only</span> <span style="color: #ff6b9d;">(30m reliable)</span>
- <span style="color: #ff6b6b;">🌟 **1999-2013**:</span> <span style="color: #ee5a6f;">Landsat 5 + 7</span> <span style="color: #ffa500;">(with SLC stripes after 2003)</span>
- <span style="color: #ffd89b;">🌟 **2013-2015**:</span> <span style="color: #fcb69f;">Landsat 7 + 8</span> <span style="color: #f093fb;">(transition period)</span>
- <span style="color: #4facfe; font-weight: bold;">🌟 **2015-present**:</span> <span style="color: #00d2ff;">Sentinel-2 + Landsat 7/8/9</span> <span style="color: #4ecdc4; font-weight: bold;">(golden era - 10m + 30m!)</span>

<span style="color: #ff6b6b; font-weight: bold;">**Default Start Date: 1985**</span> <span style="color: #ee5a6f;">- Ensures both Landsat 4 and 5 are operational for maximum redundancy!</span> 🎯

### <span style="color: #667eea; font-size: 1.1em;">🎨 Advanced Processing</span>

- <span style="color: #00d2ff; font-weight: bold;">**Adaptive Cloud Thresholds**</span> <span style="color: #a8edea;">- Automatically relaxes cloud limits</span> <span style="color: #ffd89b;">(20% → 80%)</span> <span style="color: #fcb69f;">if no images pass!</span> ☁️📉
- <span style="color: #4ecdc4; font-weight: bold;">**Adaptive Quality Thresholds**</span> <span style="color: #a8edea;">- Automatically lowers quality bar</span> <span style="color: #f093fb;">(0.9 → 0.0)</span> <span style="color: #ff9a9e;">if no images meet standard!</span> 📊📈
- <span style="color: #a8c0ff; font-weight: bold;">**Pre-Check System**</span> <span style="color: #667eea;">- Counts all available images first to optimize threshold strategy!</span> 🔍🎯
- <span style="color: #764ba2; font-weight: bold;">**Fallback Mechanisms**:</span>
  - <span style="color: #ff6b9d;">If all images rejected by clouds → Uses</span> <span style="color: #ff6b6b; font-weight: bold;">**least cloudy**</span> <span style="color: #ee5a6f;">image</span> <span style="color: #ffa500;">(clouds > holes!)</span> ☁️>🕳️
  - <span style="color: #ffd89b;">If all images rejected by quality → Uses</span> <span style="color: #fcb69f; font-weight: bold;">**highest quality**</span> <span style="color: #f093fb;">image</span> <span style="color: #ff9a9e;">(bad > nothing!)</span> 📉>❌
- <span style="color: #4facfe; font-weight: bold;">**Cloud masking**</span> <span style="color: #00d2ff;">with multiple algorithms</span> <span style="color: #a8edea;">(Sentinel-2 QA60, Landsat QA_PIXEL, pixel-level cloud detection)</span> ☁️🎭
- <span style="color: #4ecdc4; font-weight: bold;">**Shadow detection**</span> <span style="color: #ffd89b;">and correction</span> 🌑✨
- <span style="color: #f093fb; font-weight: bold;">**Multi-sensor harmonization**</span> <span style="color: #ff9a9e;">(Sentinel-2 ↔ Landsat ↔ SPOT ↔ MSS ↔ AVHRR)</span> 🔄🌈
- <span style="color: #a8c0ff; font-weight: bold;">**Band standardization**</span> <span style="color: #667eea;">- All satellites normalized to same band structure</span> <span style="color: #764ba2;">(B2/B3/B4/B8/B11/B12)</span> 🎨✨
- <span style="color: #ff6b9d; font-weight: bold;">**NDWI water masking**</span> <span style="color: #ff6b6b;">for coastal areas</span> 💧🌊
- <span style="color: #ffa500; font-weight: bold;">**Feather blending**</span> <span style="color: #ffd89b;">with soft-edge weight masks for seamless tile merging</span> 🪶✨
- <span style="color: #fcb69f; font-weight: bold;">**COG creation**</span> <span style="color: #f093fb;">with overviews</span> <span style="color: #ff9a9e;">(2x, 4x, 8x, 16x, 32x)</span> <span style="color: #a8c0ff;">for fast viewing</span> 📦⚡
- <span style="color: #667eea; font-weight: bold;">**Progress tracking**</span> <span style="color: #764ba2;">for EVERY phase:</span> <span style="color: #ff6b9d;">reprojection, blending, index calculation, file writing!</span> 📊💫

### <span style="color: #ff6b9d; font-size: 1.1em;">💖 User-Friendly Features</span>

- <span style="color: #4facfe; font-weight: bold;">**Beautiful HTML dashboard**</span> <span style="color: #00d2ff;">that auto-refreshes every 2 seconds</span> 📊🦋
- <span style="color: #4ecdc4; font-weight: bold;">**Real-time progress tracking**</span> <span style="color: #a8edea;">with countdown timers</span> ⏱️✨
- <span style="color: #f093fb; font-weight: bold;">**Progress bars for EVERYTHING**:</span>
  - <span style="color: #ff9a9e;">Tile processing:</span> <span style="color: #a8c0ff; font-family: monospace; background: rgba(168,192,255,0.1); padding: 2px 6px; border-radius: 3px;">`[Tile 1234/2009] ✅ SUCCESS`</span>
  - <span style="color: #667eea;">Reprojection:</span> <span style="color: #764ba2; font-family: monospace; background: rgba(118,75,162,0.1); padding: 2px 6px; border-radius: 3px;">`Reprojecting tiles: 500/2009`</span>
  - <span style="color: #ff6b9d;">Band blending:</span> <span style="color: #ff6b6b; font-family: monospace; background: rgba(255,107,107,0.1); padding: 2px 6px; border-radius: 3px;">`Blending Band 1: tile 1500/2009`</span>
  - <span style="color: #ee5a6f;">Index calculation:</span> <span style="color: #ffa500; font-family: monospace; background: rgba(255,165,0,0.1); padding: 2px 6px; border-radius: 3px;">`Calculating NDVI... (2/9)`</span><span style="color: #ffa500;">,</span> <span style="color: #ffd89b; font-family: monospace; background: rgba(255,216,155,0.1); padding: 2px 6px; border-radius: 3px;">`Calculating EVI... (5/9)`</span>
  - <span style="color: #fcb69f;">File writing:</span> <span style="color: #f093fb; font-family: monospace; background: rgba(240,147,251,0.1); padding: 2px 6px; border-radius: 3px;">`Writing mosaic file...`</span><span style="color: #f093fb;">,</span> <span style="color: #ff9a9e; font-family: monospace; background: rgba(255,154,158,0.1); padding: 2px 6px; border-radius: 3px;">`Writing indices to mosaic file...`</span>
  - <span style="color: #a8c0ff;">COG creation:</span> <span style="color: #667eea; font-family: monospace; background: rgba(102,126,234,0.1); padding: 2px 6px; border-radius: 3px;">`Creating COG from mosaic...`</span>
- <span style="color: #764ba2; font-weight: bold;">**Detailed console logging**</span> <span style="color: #ff6b9d;">with timestamps and color-coded messages</span> 💬
- <span style="color: #ff6b6b; font-weight: bold;">**Pause/Resume functionality**</span> <span style="color: #ee5a6f;">for gentle control</span> ⏸️▶️
- <span style="color: #ffa500; font-weight: bold;">**Comprehensive PDF reports**</span> <span style="color: #ffd89b;">with statistics, visualizations, and satellite usage</span> 📄💕
- <span style="color: #fcb69f; font-weight: bold;">**Satellite usage statistics**</span> <span style="color: #f093fb;">showing which satellites contributed to each tile</span> 🛰️📊
- <span style="color: #ff9a9e; font-weight: bold;">**Quality score tracking**</span> <span style="color: #a8c0ff;">- see exactly how good each image is!</span> 🏆
- <span style="color: #667eea; font-weight: bold;">**Server mode**</span> <span style="color: #764ba2;">for maximum resource utilization</span> <span style="color: #ff6b9d;">(uses all CPU cores, max workers)</span> 🖥️💪

---

## <span style="color: #667eea; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">🎨 Configuration</span>

### <span style="color: #4facfe; font-size: 1.1em;">Default Settings</span>

- <span style="color: #00d2ff; font-weight: bold;">**Default Start Date**:</span> <span style="color: #a8edea;">1985-01-01</span> <span style="color: #ffd89b;">(both Landsat 4 and 5 operational for redundancy!)</span> 📅✨
- <span style="color: #4ecdc4; font-weight: bold;">**Default End Date**:</span> <span style="color: #a8edea;">Current date (2025-11-30)</span> 📅
- <span style="color: #f093fb; font-weight: bold;">**Target Resolution**:</span> <span style="color: #ff9a9e;">10 meters per pixel</span> <span style="color: #a8c0ff;">(native Sentinel-2 - preserves best quality!)</span> 🎯
- <span style="color: #667eea; font-weight: bold;">**Tile Size**:</span> <span style="color: #764ba2;">Auto-calculated</span> <span style="color: #ff6b9d;">(validates against 40MB limit)</span> 📏
- <span style="color: #ff6b6b; font-weight: bold;">**Workers**:</span> <span style="color: #ee5a6f;">Auto-detected CPU count</span> <span style="color: #ffa500;">(capped at 8, server mode uses all cores)</span> 💻
- <span style="color: #ffd89b; font-weight: bold;">**Dynamic Workers**:</span> <span style="color: #fcb69f;">Enabled by default</span> <span style="color: #f093fb;">(auto-adjusts based on CPU/memory)</span> ⚡
- <span style="color: #ff9a9e; font-weight: bold;">**Harmonization**:</span> <span style="color: #a8c0ff;">Enabled by default</span> <span style="color: #667eea;">(seamless sensor blending)</span> 🌈
- <span style="color: #764ba2; font-weight: bold;">**Initial Cloud Threshold**:</span> <span style="color: #ff6b9d;">20% (metadata) / 20% (calculated fraction)</span> ☁️
- <span style="color: #ff6b6b; font-weight: bold;">**Initial Quality Threshold**:</span> <span style="color: #ee5a6f;">0.9 (90% quality score)</span> 📊
- <span style="color: #ffa500; font-weight: bold;">**Adaptive Threshold Strategy**:</span> 
  - <span style="color: #00d2ff;">≤3 images:</span> <span style="color: #a8edea;">Lower after 1 test</span>
  - <span style="color: #4ecdc4;">≤10 images:</span> <span style="color: #ffd89b;">Lower after 2 tests</span>  
  - <span style="color: #f093fb;">>10 images:</span> <span style="color: #ff9a9e;">Lower after 3 tests</span>

### <span style="color: #4facfe; font-size: 1.1em;">Server Mode</span> 🌟

<span style="color: #a8edea;">When enabled, Server Mode:</span>
- <span style="color: #00d2ff;">Uses</span> <span style="color: #4ecdc4; font-weight: bold;">**all available CPU cores**</span> 💪
- <span style="color: #ffd89b;">Increases</span> <span style="color: #fcb69f; font-weight: bold;">**max workers**</span> <span style="color: #f093fb;">for I/O-bound tasks</span> ⚡
- <span style="color: #ff9a9e;">Sets process priority to</span> <span style="color: #a8c0ff; font-weight: bold;">**HIGH**</span> <span style="color: #667eea;">on Windows</span> 🚀
- <span style="color: #764ba2;">Focuses</span> <span style="color: #ff6b9d; font-weight: bold;">**all resources**</span> <span style="color: #ff6b6b;">on processing</span> 🎯

<span style="color: #4facfe;">Perfect for dedicated processing machines!</span> 🖥️✨

---

## <span style="color: #667eea; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">📊 Output Structure</span>

```
output_folder/
├── <span style="color: #4facfe;">YYYY_MM/</span>
│   ├── <span style="color: #00d2ff;">mosaic_YYYY_MM.tif</span>          # Final mosaic
│   ├── <span style="color: #4ecdc4;">mosaic_YYYY_MM_COG.tif</span>       # Cloud-Optimized GeoTIFF
│   ├── <span style="color: #a8edea;">mosaic_YYYY_MM_mask.tif</span>      # Water mask
│   ├── <span style="color: #ffd89b;">processing_YYYY_MM.log</span>       # Detailed log
│   ├── <span style="color: #fcb69f;">mosaic_report_YYYY_MM.pdf</span>   # Comprehensive report
│   └── <span style="color: #f093fb;">progress.html</span>                # Real-time dashboard
└── <span style="color: #ff9a9e;">manifest.csv</span>                      # Processing manifest
```

---

## <span style="color: #ff6b6b; background: linear-gradient(90deg, #ff6b6b 0%, #ee5a6f 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">🐛 Troubleshooting</span>

### <span style="color: #ff6b6b;">"Earth Engine initialization failed"</span>
```bash
earthengine authenticate
```

### <span style="color: #ffa500;">"reportlab not available"</span>
```bash
pip install reportlab
```

### <span style="color: #ffd89b;">"Port already in use"</span> <span style="color: #fcb69f;">(for dashboard)</span>
<span style="color: #f093fb;">The HTML dashboard will automatically try the next available port!</span> 💖

### <span style="color: #ff9a9e;">Tiles too large?</span>
- <span style="color: #a8c0ff;">Increase the</span> <span style="color: #667eea; font-family: monospace; background: rgba(102,126,234,0.1); padding: 2px 6px; border-radius: 3px;">`max_tiles`</span> <span style="color: #764ba2;">parameter</span>
- <span style="color: #ff6b9d;">The system will auto-calculate optimal tile size</span>
- <span style="color: #ff6b6b;">Validates against 40MB download limit automatically</span> ✅

---

## 🚀 Project Ideas: What Can You Build?

<span style="color: #4facfe;">Ready to dive into some amazing projects?</span> <span style="color: #00d2ff;">We've created</span> <span style="color: #4ecdc4; font-weight: bold; font-size: 1.1em;">**50+ pre-configured bounding boxes**</span> <span style="color: #a8edea;">for exciting research projects!</span> <span style="color: #ffd89b;">Each project includes a ready-to-use GeoJSON file in the</span> <span style="color: #fcb69f; font-family: monospace; background: rgba(252,182,159,0.1); padding: 2px 6px; border-radius: 3px;">`bbox_files/`</span> <span style="color: #f093fb;">folder that you can import directly.</span> <span style="color: #ff9a9e;">Just click "Import" in the map selector and choose your project!</span>

### 💧 Water Resources & Hydrology

<details>
<summary><b style="color: #0066cc;">💧 Water Resources Projects</b> - Click to expand!</summary>

- **<span style="color: #0066cc;">Dead Sea Shrinking Analysis</span>** (1985-2024) - Track the dramatic shrinking of the Dead Sea over decades. Monitor water area changes, shoreline retreat, and salt evaporation ponds. *File: `dead_sea_shrinking_analysis.geojson`*

- **<span style="color: #0066cc;">Mekong Delta Subsidence</span>** (2000-2024) - Monitor land subsidence and sea level rise impacts in Vietnam. Track flood frequency and salinity intrusion. *File: `mekong_delta_subsidence.geojson`*

- **<span style="color: #0066cc;">Lake Chad Shrinking</span>** (1985-2024) - Track dramatic lake shrinkage in Central Africa. One of the world's most visible climate change impacts! *File: `lake_chad_shrinking.geojson`*

- **<span style="color: #0066cc;">Aral Sea Disappearance</span>** (1985-2024) - Document one of the world's worst environmental disasters. Watch a sea disappear before your eyes. *File: `aral_sea_disappearance.geojson`*

- **<span style="color: #0066cc;">Three Gorges Dam Impact</span>** (2000-2024) - Study reservoir filling and downstream impacts of the world's largest dam. *File: `three_gorges_dam_impact.geojson`*

- **<span style="color: #0066cc;">Okavango Delta Flooding</span>** (2000-2024) - Track seasonal flooding patterns in Africa's incredible inland delta. *File: `okavango_delta_flooding.geojson`*

- **<span style="color: #0066cc;">Colorado River Basin</span>** (2000-2024) - Monitor drought and water usage in the American Southwest. *File: `colorado_river_basin.geojson`*

- **<span style="color: #0066cc;">Great Salt Lake Shrinking</span>** (1985-2024) - Monitor lake level decline and dust storm impacts. *File: `great_salt_lake_shrinking.geojson`*

- **<span style="color: #0066cc;">Great Lakes Water Levels</span>** (2000-2024) - Monitor lake level changes and shoreline dynamics. *File: `great_lakes_water_levels.geojson`*

- **<span style="color: #0066cc;">Las Vegas Water Usage</span>** (1985-2024) - Monitor water consumption and urban heat island effects in the desert. *File: `las_vegas_water_usage.geojson`*

</details>

### 🌡️ Climate Change & Cryosphere

<details>
<summary><b style="color: #00cc99;">🌡️ Climate Change Projects</b> - Click to expand!</summary>

- **<span style="color: #00cc99;">Arctic Sea Ice Monitoring</span>** (2000-2024) - Track sea ice extent and thickness changes in the Arctic. Critical for climate research! *File: `arctic_sea_ice_monitoring.geojson`*

- **<span style="color: #00cc99;">Greenland Ice Sheet Melting</span>** (2000-2024) - Track ice sheet mass loss and glacier retreat. Watch the ice disappear in real-time! *File: `greenland_ice_sheet_melting.geojson`*

- **<span style="color: #00cc99;">Himalayan Glacier Monitoring</span>** (2000-2024) - Track glacier retreat in the "Third Pole". Monitor glacial lakes and snow cover. *File: `himalayan_glacier_monitoring.geojson`*

- **<span style="color: #00cc99;">Iceland Glacier Retreat</span>** (1985-2024) - Document rapid glacier melting in one of the world's most visible locations. *File: `iceland_glacier_retreat.geojson`*

- **<span style="color: #00cc99;">Patagonian Ice Fields</span>** (1985-2024) - Track ice field retreat in South America's stunning Patagonia region. *File: `patagonian_ice_fields.geojson`*

- **<span style="color: #00cc99;">Antarctic Ice Shelf Collapse</span>** (2000-2024) - Monitor ice shelf stability and calving events. *File: `antarctic_ice_shelf_collapse.geojson`*

- **<span style="color: #00cc99;">Antarctic Peninsula Warming</span>** (2000-2024) - Monitor rapid warming impacts on one of the fastest-warming regions on Earth. *File: `antarctic_peninsula_warming.geojson`*

- **<span style="color: #00cc99;">Siberian Permafrost Thaw</span>** (2000-2024) - Monitor permafrost degradation and methane release. Critical for climate feedback loops! *File: `siberian_permafrost_thaw.geojson`*

- **<span style="color: #00cc99;">Alaska Permafrost Thaw</span>** (2000-2024) - Track permafrost degradation in North America. *File: `alaska_permafrost_thaw.geojson`*

- **<span style="color: #00cc99;">Sahara Desert Expansion</span>** (1985-2024) - Track desertification and Sahel boundary shifts. *File: `sahara_desert_expansion.geojson`*

- **<span style="color: #00cc99;">Mongolian Desertification</span>** (1985-2024) - Track desert expansion in Central Asia. *File: `mongolian_desertification.geojson`*

- **<span style="color: #00cc99;">Maldives Sea Level Rise</span>** (2000-2024) - Monitor impacts of rising sea levels on low-lying islands. *File: `maldives_sea_level_rise.geojson`*

- **<span style="color: #00cc99;">Himalayan Glacial Lakes</span>** (2000-2024) - Track dangerous glacial lake growth and flood risk. *File: `himalayan_glacial_lakes.geojson`*

- **<span style="color: #00cc99;">Himalayan Snow Cover</span>** (2000-2024) - Monitor snow cover trends and water availability. *File: `himalayan_snow_cover.geojson`*

- **<span style="color: #00cc99;">Arctic Tundra Changes</span>** (2000-2024) - Track tundra ecosystem shifts and vegetation change. *File: `arctic_tundra_changes.geojson`*

</details>

### 🌳 Conservation & Deforestation

<details>
<summary><b style="color: #00aa00;">🌳 Conservation Projects</b> - Click to expand!</summary>

- **<span style="color: #00aa00;">Amazon Rainforest Deforestation</span>** (1985-2024) - Monitor deforestation rates in the Brazilian Amazon. Track forest loss, NDVI trends, and fire detection. *File: `amazon_rainforest_deforestation.geojson`*

- **<span style="color: #00aa00;">Congo Basin Deforestation</span>** (2000-2024) - Track forest loss in Central Africa's second-largest rainforest. *File: `congo_basin_deforestation.geojson`*

- **<span style="color: #00aa00;">Borneo Palm Oil Plantations</span>** (2000-2024) - Track deforestation for palm oil production. Monitor plantation expansion and biodiversity impacts. *File: `borneo_palm_oil_plantations.geojson`*

- **<span style="color: #00aa00;">Amazon Gold Mining</span>** (2010-2024) - Monitor illegal mining impacts in the Amazon. Track mining extent, deforestation, and water pollution. *File: `amazon_gold_mining.geojson`*

- **<span style="color: #00aa00;">Yellowstone National Park</span>** (1985-2024) - Track ecosystem health and wildfire impacts in America's first national park. *File: `yellowstone_national_park.geojson`*

- **<span style="color: #00aa00;">Everglades Restoration</span>** (2000-2024) - Track restoration project effectiveness in Florida's unique ecosystem. *File: `everglades_restoration.geojson`*

- **<span style="color: #00aa00;">Sahara Green Wall</span>** (2010-2024) - Track reforestation project across the Sahel. Monitor tree planting and vegetation growth. *File: `sahara_green_wall.geojson`*

- **<span style="color: #00aa00;">Himalayan Biodiversity</span>** (2000-2024) - Monitor ecosystem health in one of the world's biodiversity hotspots. *File: `himalayan_biodiversity.geojson`*

</details>

### 🏙️ Urban Development & Infrastructure

<details>
<summary><b style="color: #cc6600;">🏙️ Urban Development Projects</b> - Click to expand!</summary>

- **<span style="color: #cc6600;">Dubai Urban Expansion</span>** (1990-2024) - Document rapid urban growth and artificial islands. Watch a city grow from desert! *File: `dubai_urban_expansion.geojson`*

- **<span style="color: #cc6600;">Sao Paulo Urban Growth</span>** (1985-2024) - Document megacity expansion in South America's largest city. *File: `sao_paulo_urban_growth.geojson`*

- **<span style="color: #cc6600;">Mumbai Coastal Development</span>** (1990-2024) - Monitor coastal reclamation projects and urban growth. *File: `mumbai_coastal_development.geojson`*

- **<span style="color: #cc6600;">Suez Canal Expansion</span>** (2014-2016) - Document the canal widening project. Short but intense monitoring period! *File: `suez_canal_expansion.geojson`*

- **<span style="color: #cc6600;">Mekong River Dams</span>** (2010-2024) - Study dam impacts on the Mekong River system. *File: `mekong_river_dams.geojson`*

</details>

### 🔥 Disaster Monitoring & Recovery

<details>
<summary><b style="color: #ff3300;">🔥 Disaster Monitoring Projects</b> - Click to expand!</summary>

- **<span style="color: #ff3300;">California Wildfire Recovery</span>** (2018-2024) - Track vegetation recovery after major wildfires. Monitor NDVI recovery and burn scar evolution. *File: `california_wildfire_recovery.geojson`*

- **<span style="color: #ff3300;">Australian Bushfire Recovery</span>** (2019-2024) - Monitor ecosystem recovery after the devastating 2019-2020 fires. *File: `australian_bushfire_recovery.geojson`*

- **<span style="color: #ff3300;">Bangladesh Flooding</span>** (2000-2024) - Track monsoon flooding patterns and impacts. Monitor flood extent, frequency, and crop damage. *File: `bangladesh_flooding.geojson`*

- **<span style="color: #ff3300;">Yangtze River Flooding</span>** (2020-2024) - Monitor recent flood patterns in China's longest river. *File: `yangtze_river_flooding.geojson`*

- **<span style="color: #ff3300;">Himalayan Landslide Monitoring</span>** (2015-2024) - Track landslide-prone areas and recovery. *File: `himalayan_landslide_monitoring.geojson`*

- **<span style="color: #ff3300;">Florida Everglades Fires</span>** (2017-2024) - Track wildfire patterns in the Everglades. *File: `florida_everglades_fires.geojson`*

</details>

### 🌊 Marine & Coastal Conservation

<details>
<summary><b style="color: #0066ff;">🌊 Marine Conservation Projects</b> - Click to expand!</summary>

- **<span style="color: #0066ff;">Great Barrier Reef Health</span>** (2015-2024) - Monitor coral bleaching and reef health. Track coral coverage, water clarity, and bleaching events. *File: `great_barrier_reef_health.geojson`*

- **<span style="color: #0066ff;">Mississippi River Delta</span>** (1985-2024) - Monitor land loss and delta subsidence. Track wetland health and sediment deposition. *File: `mississippi_river_delta.geojson`*

- **<span style="color: #0066ff;">Venice Lagoon Changes</span>** (2000-2024) - Monitor sea level impacts on Venice. Track flood frequency and lagoon health. *File: `venice_lagoon_changes.geojson`*

</details>

### 🌾 Agriculture & Food Security

<details>
<summary><b style="color: #ff9900;">🌾 Agriculture Projects</b> - Click to expand!</summary>

- **<span style="color: #ff9900;">Nile Delta Agriculture</span>** (1985-2024) - Monitor agricultural productivity and irrigation in Egypt's breadbasket. *File: `nile_delta_agriculture.geojson`*

- **<span style="color: #ff9900;">Indus River Agriculture</span>** (1985-2024) - Monitor irrigation and crop patterns in Pakistan's agricultural heartland. *File: `indus_river_agriculture.geojson`*

</details>

### ⚡ Renewable Energy & Infrastructure

<details>
<summary><b style="color: #ffcc00;">⚡ Renewable Energy Projects</b> - Click to expand!</summary>

- **<span style="color: #ffcc00;">North Sea Wind Farms</span>** (2010-2024) - Monitor offshore wind farm development. Track farm expansion and marine impacts. *File: `north_sea_wind_farms.geojson`*

- **<span style="color: #ffcc00;">Sahara Solar Farms</span>** (2015-2024) - Track solar farm development in the world's largest desert. *File: `sahara_solar_farms.geojson`*

</details>

### 🔬 Environmental Monitoring & Research

<details>
<summary><b style="color: #9900cc;">🔬 Environmental Research Projects</b> - Click to expand!</summary>

- **<span style="color: #9900cc;">Chernobyl Exclusion Zone</span>** (1986-2024) - Study ecosystem recovery after nuclear disaster. Monitor forest regrowth and wildlife habitat. *File: `chernobyl_exclusion_zone.geojson`*

- **<span style="color: #9900cc;">Ganges River Pollution</span>** (2000-2024) - Monitor water quality and sediment in one of the world's most polluted rivers. *File: `ganges_river_pollution.geojson`*

- **<span style="color: #9900cc;">Niger Delta Oil Spills</span>** (2000-2024) - Track oil spill impacts and ecosystem damage. *File: `niger_delta_oil_spills.geojson`*

- **<span style="color: #9900cc;">California Drought Impact</span>** (2012-2024) - Track drought severity and recovery in California. *File: `california_drought_impact.geojson`*

</details>

### <span style="color: #4facfe; font-size: 1.1em;">📊 How to Use Project Bounding Boxes</span>

1. <span style="color: #00d2ff; font-weight: bold;">**Start Flutter Earth**</span> <span style="color: #a8edea;">and click the map selector button</span>
2. <span style="color: #4ecdc4; font-weight: bold;">**Click "Import"**</span> <span style="color: #ffd89b;">in the map interface</span>
3. <span style="color: #f093fb; font-weight: bold;">**Navigate to**</span> <span style="color: #ff9a9e; font-family: monospace; background: rgba(255,154,158,0.1); padding: 2px 6px; border-radius: 3px;">`bbox_files/`</span> <span style="color: #a8c0ff;">folder</span>
4. <span style="color: #667eea; font-weight: bold;">**Select any**</span> <span style="color: #764ba2; font-family: monospace; background: rgba(118,75,162,0.1); padding: 2px 6px; border-radius: 3px;">`.geojson`</span> <span style="color: #ff6b9d;">file from the project list above</span>
5. <span style="color: #ff6b6b; font-weight: bold; font-size: 1.1em;">**The bounding box will load automatically!**</span> <span style="color: #ee5a6f;">Just adjust dates and start processing!</span>

<span style="color: #ffa500; font-weight: bold;">**Pro Tip:**</span> <span style="color: #ffd89b;">Each project file includes metadata about the project, recommended date ranges, and key metrics to monitor.</span> <span style="color: #fcb69f;">Check the GeoJSON properties for details!</span>

---

## <span style="color: #667eea; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">🎯 Best Practices</span>

1. <span style="color: #00d2ff; font-weight: bold;">**Start small**</span> <span style="color: #a8edea;">- Test with a small date range first!</span> 🧪
2. <span style="color: #4ecdc4; font-weight: bold;">**Use Server Mode**</span> <span style="color: #ffd89b;">- For dedicated processing machines</span> 🖥️💪
3. <span style="color: #f093fb; font-weight: bold;">**Check the dashboard**</span> <span style="color: #ff9a9e;">- Monitor progress in real-time!</span> 📊✨
4. <span style="color: #a8c0ff; font-weight: bold;">**Review PDF reports**</span> <span style="color: #667eea;">- Get detailed statistics and insights!</span> 📄💕
5. <span style="color: #764ba2; font-weight: bold;">**Be patient**</span> <span style="color: #ff6b9d;">- Quality takes time, but it's worth it!</span> ⏰🌸

---

## <span style="color: #ff6b6b; background: linear-gradient(90deg, #ff6b6b 0%, #ee5a6f 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">🤝 Contributing</span>

<span style="color: #4facfe;">We welcome contributions!</span> <span style="color: #00d2ff;">Whether it's:</span>
- <span style="color: #ff6b6b;">🐛 Bug fixes</span>
- <span style="color: #ffa500;">✨ New features</span>
- <span style="color: #4ecdc4;">📝 Documentation improvements</span>
- <span style="color: #f093fb;">🎨 UI/UX enhancements</span>
- <span style="color: #ff9a9e;">💡 Ideas and suggestions</span>

<span style="color: #a8c0ff;">Just open an issue or pull request!</span> <span style="color: #667eea;">We're friendly and gentle!</span> 💖

---

## <span style="color: #667eea; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">📝 License</span>

<span style="color: #4facfe; font-weight: bold;">MIT License</span> <span style="color: #00d2ff;">- Feel free to use Flutter Earth however you'd like!</span> 🌸✨

---

## <span style="color: #ff6b9d; background: linear-gradient(90deg, #ff6b9d 0%, #ff6b6b 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">💕 Acknowledgments</span>

<span style="color: #4facfe;">Built with love and care for the geospatial community!</span> 🌍💖

<span style="color: #00d2ff; font-weight: bold;">Special thanks to:</span>
- <span style="color: #4ecdc4;">Google Earth Engine team</span> <span style="color: #a8edea;">for the amazing platform!</span> 🛰️
- <span style="color: #ffd89b;">The open-source geospatial community!</span> 🌟
- <span style="color: #fcb69f;">Everyone who makes satellite imagery accessible!</span> 🦋

---

## <span style="color: #667eea; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 1.3em;">🌸 Support</span>

<span style="color: #4facfe;">Having issues? Questions? Just want to say hi?</span> 💬

- <span style="color: #00d2ff;">Open an issue on GitHub</span> 🐛
- <span style="color: #4ecdc4;">Check the logs in the</span> <span style="color: #a8edea; font-family: monospace; background: rgba(168,237,234,0.1); padding: 2px 6px; border-radius: 3px;">`logs/`</span> <span style="color: #ffd89b;">folder</span> 📋
- <span style="color: #fcb69f;">Review the PDF reports</span> <span style="color: #f093fb;">for detailed information</span> 📄

<span style="color: #ff9a9e;">Remember:</span> <span style="color: #a8c0ff;">Flutter Earth is here to help, gently and beautifully!</span> ✨🦋💖

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
