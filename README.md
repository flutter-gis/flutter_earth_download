# 🌸 Flutter Earth 🌸

> **Download the prettiest satellite imagery with the gentlest touch!** ✨🦋

A beautifully crafted Python tool for downloading and processing satellite imagery from Google Earth Engine. Supports **12+ satellite sensors** (Sentinel-2, Landsat 4/5/7/8/9, Landsat MSS 1-3, SPOT 1-4, MODIS, ASTER, VIIRS, NOAA AVHRR) covering **1972 to present** with **intelligent adaptive quality-based mosaic generation**. Features **dynamic thresholds**, **fallback mechanisms**, and **real-time progress tracking** for the entire processing pipeline. Because every pixel deserves to be perfect! 💖

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-adorable-pink.svg)
![Satellites](https://img.shields.io/badge/satellites-12+-lavender.svg)
![Coverage](https://img.shields.io/badge/coverage-1972--present-purple.svg)
![Resolution](https://img.shields.io/badge/resolution-10m%20target-brightgreen.svg)

---

## 📋 Table of Contents

- [What Does This Do?](#-what-does-this-do)
- [Quick Start](#-quick-start)
- [How to Use](#-how-to-use)
- [Key Features](#-key-features)
- [Multi-Sensor Support](#-multi-sensor-support-12-satellites)
- [Configuration](#-configuration)
- [Output Structure](#-output-structure)
- [Project Ideas](#-project-ideas-what-can-you-build)
- [Best Practices](#-best-practices)
- [Troubleshooting](#-troubleshooting)
- [Technical Details](#-technical-details)
- [Contributing](#-contributing)
- [License](#-license)
- [Support](#-support)

---

## 🌈 What Does This Do?

Ever wanted to download satellite imagery but got frustrated with:

- ❌ **Cloudy images** ruining your beautiful mosaics? ☁️💔
- ❌ **Low-resolution data** that looks pixelated? 📉😢
- ❌ Having to **manually pick** the "best" satellite? 🤔😓
- ❌ **Complex APIs** that make you cry? 😭💧

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

1. **Python 3.7+** (because we're modern and lovely!) 🐍💕
2. **Google Earth Engine account** (it's free!) 🎉✨
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
   pip install earthengine-api rasterio numpy shapely pyproj tqdm requests scikit-image psutil reportlab matplotlib
   ```

3. **Run it!**
   ```bash
   python main.py
   ```
   
   Or on Windows, just double-click `run_gee.bat` 🪟💖

---

## 📖 How to Use

### GUI Mode (Recommended for Everyone!) 🧑💕

Just run `python main.py` and a friendly GUI will pop up! Fill in:

- **Bounding Box**: Where do you want imagery? (lon_min, lat_min, lon_max, lat_max) 📍🌍
- **Date Range**: When do you want imagery? (YYYY-MM-DD format) 📅✨
- **Output Folder**: Where should we save your beautiful mosaics? 💾🌸
- **Max Tiles**: How many tiles? (auto-validates against 40MB limit) 🔢💖
- **Options**: Toggle satellites, harmonization, dynamic workers, server mode, etc. ⚙️🌈

Click **Submit** and watch the magic happen! ✨🦋

The dashboard will automatically open in your browser showing:

- 📊 Real-time progress bars (tile, mosaic, and full project!)
- ⏱️ Countdown timer (estimated time remaining) ⏰
- 📋 Console output with timestamps and color-coded messages 💬
- 🛰️ Satellite usage statistics with quality metrics 🌟

### CLI Mode (For Terminal Lovers) 💻

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
    enable_harmonize=True,
    include_modis=True,
    include_aster=True,
    include_viirs=True
)
```

---

## ✨ Key Features

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
- **Comprehensive PDF reports** with statistics, visualizations, and satellite usage 📄💕

### 🎨 Advanced Processing

- **Adaptive Cloud Thresholds** - Automatically relaxes cloud limits (20% → 80%) if no images pass! ☁️📉
- **Adaptive Quality Thresholds** - Automatically lowers quality bar (0.9 → 0.0) if no images meet standard! 📊📈
- **Pre-Check System** - Counts all available images first to optimize threshold strategy! 🔍🎯
- **Fallback Mechanisms**:
  - If all images rejected by clouds → Uses **least cloudy** image (clouds > holes!) ☁️>🕳️
  - If all images rejected by quality → Uses **highest quality** image (bad > nothing!) 📉>❌
- **Cloud masking** with multiple algorithms (Sentinel-2 QA60, Landsat QA_PIXEL, pixel-level cloud detection) ☁️🎭
- **Multi-sensor harmonization** (Sentinel-2 ↔ Landsat ↔ SPOT ↔ MSS ↔ AVHRR) 🔄🌈
- **Band standardization** - All satellites normalized to same band structure (B2/B3/B4/B8/B11/B12) 🎨✨
- **Feather blending** with soft-edge weight masks for seamless tile merging 🪶✨
- **COG creation** with overviews (2x, 4x, 8x, 16x, 32x) for fast viewing 📦⚡

---

## 🦋 Multi-Sensor Support (12+ Satellites!)

### High Resolution (≤30m):

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

### Medium Resolution (60-400m):

- 🔬 **ASTER** (15-90m, 2000-2008) - The detailed scientist! 💜

### Low Resolution (>400m):

- 🌎 **MODIS Terra** (250m, 2000-present) - The wide-eyed watcher! 🧡
- 🌎 **MODIS Aqua** (250m, 2002-present) - The water-focused twin! 🧡
- 🌌 **VIIRS** (375m, 2011-present) - The night vision specialist! 💛
- 🌍 **NOAA AVHRR** (1km, 1978-present) - **ABSOLUTE LAST RESORT** only! ⚠️🔴
  - Only used when ALL other satellites fail (very coarse resolution!)

### Coverage Timeline:

- 🌟 **1972-1982**: Landsat MSS 1-3 only (60m, historical)
- 🌟 **1982-1985**: Landsat 4 TM (early 30m era)
- 🌟 **1985-1993**: Landsat 4 + 5 overlap **(best coverage!)** 🎯
- 🌟 **1993-1999**: Landsat 5 only (30m reliable)
- 🌟 **1999-2013**: Landsat 5 + 7 (with SLC stripes after 2003)
- 🌟 **2013-2015**: Landsat 7 + 8 (transition period)
- 🌟 **2015-present**: Sentinel-2 + Landsat 7/8/9 **(golden era - 10m + 30m!)** ✨

**Default Start Date: 1985** - Ensures both Landsat 4 and 5 are operational for maximum redundancy! 🎯

---

## 🎨 Configuration

### Default Settings

- **Default Start Date**: 1985-01-01 (both Landsat 4 and 5 operational for redundancy!) 📅✨
- **Default End Date**: Current date 📅
- **Target Resolution**: 10 meters per pixel (native Sentinel-2 - preserves best quality!) 🎯
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
│   ├── mosaic_YYYY_MM_COG.tif      # Cloud-Optimized GeoTIFF
│   ├── mosaic_YYYY_MM_mask.tif     # Water mask
│   ├── processing_YYYY_MM.log      # Detailed log
│   ├── mosaic_report_YYYY_MM.pdf   # Comprehensive report
│   └── progress.html                # Real-time dashboard
└── manifest.csv                     # Processing manifest
```

---

## 🚀 Project Ideas: What Can You Build?

Ready to dive into some amazing projects? We've created **50+ pre-configured bounding boxes** for exciting research projects! Each project includes a ready-to-use GeoJSON file in the `bbox_files/` folder that you can import directly. Just click "Import" in the map selector and choose your project!

### 💧 Water Resources & Hydrology

<details>
<summary><b>💧 Water Resources Projects</b> - Click to expand!</summary>

- **Dead Sea Shrinking Analysis** (1985-2024) - Track the dramatic shrinking of the Dead Sea over decades. Monitor water area changes, shoreline retreat, and salt evaporation ponds. *File: `dead_sea_shrinking_analysis.geojson`*
- **Mekong Delta Subsidence** (2000-2024) - Monitor land subsidence and sea level rise impacts in Vietnam. Track flood frequency and salinity intrusion. *File: `mekong_delta_subsidence.geojson`*
- **Lake Chad Shrinking** (1985-2024) - Track dramatic lake shrinkage in Central Africa. One of the world's most visible climate change impacts! *File: `lake_chad_shrinking.geojson`*
- **Aral Sea Disappearance** (1985-2024) - Document one of the world's worst environmental disasters. Watch a sea disappear before your eyes. *File: `aral_sea_disappearance.geojson`*
- **Three Gorges Dam Impact** (2000-2024) - Study reservoir filling and downstream impacts of the world's largest dam. *File: `three_gorges_dam_impact.geojson`*
- **Okavango Delta Flooding** (2000-2024) - Track seasonal flooding patterns in Africa's incredible inland delta. *File: `okavango_delta_flooding.geojson`*
- **Colorado River Basin** (2000-2024) - Monitor drought and water usage in the American Southwest. *File: `colorado_river_basin.geojson`*
- **Great Salt Lake Shrinking** (1985-2024) - Monitor lake level decline and dust storm impacts. *File: `great_salt_lake_shrinking.geojson`*
- **Great Lakes Water Levels** (2000-2024) - Monitor lake level changes and shoreline dynamics. *File: `great_lakes_water_levels.geojson`*
- **Las Vegas Water Usage** (1985-2024) - Monitor water consumption and urban heat island effects in the desert. *File: `las_vegas_water_usage.geojson`*

</details>

### 🌡️ Climate Change & Cryosphere

<details>
<summary><b>🌡️ Climate Change Projects</b> - Click to expand!</summary>

- **Arctic Sea Ice Monitoring** (2000-2024) - Track sea ice extent and thickness changes in the Arctic. Critical for climate research! *File: `arctic_sea_ice_monitoring.geojson`*
- **Greenland Ice Sheet Melting** (2000-2024) - Track ice sheet mass loss and glacier retreat. Watch the ice disappear in real-time! *File: `greenland_ice_sheet_melting.geojson`*
- **Himalayan Glacier Monitoring** (2000-2024) - Track glacier retreat in the "Third Pole". Monitor glacial lakes and snow cover. *File: `himalayan_glacier_monitoring.geojson`*
- **Iceland Glacier Retreat** (1985-2024) - Document rapid glacier melting in one of the world's most visible locations. *File: `iceland_glacier_retreat.geojson`*
- **Patagonian Ice Fields** (1985-2024) - Track ice field retreat in South America's stunning Patagonia region. *File: `patagonian_ice_fields.geojson`*
- **Antarctic Ice Shelf Collapse** (2000-2024) - Monitor ice shelf stability and calving events. *File: `antarctic_ice_shelf_collapse.geojson`*
- **Antarctic Peninsula Warming** (2000-2024) - Monitor rapid warming impacts on one of the fastest-warming regions on Earth. *File: `antarctic_peninsula_warming.geojson`*
- **Siberian Permafrost Thaw** (2000-2024) - Monitor permafrost degradation and methane release. Critical for climate feedback loops! *File: `siberian_permafrost_thaw.geojson`*
- **Alaska Permafrost Thaw** (2000-2024) - Track permafrost degradation in North America. *File: `alaska_permafrost_thaw.geojson`*
- **Sahara Desert Expansion** (1985-2024) - Track desertification and Sahel boundary shifts. *File: `sahara_desert_expansion.geojson`*
- **Mongolian Desertification** (1985-2024) - Track desert expansion in Central Asia. *File: `mongolian_desertification.geojson`*
- **Maldives Sea Level Rise** (2000-2024) - Monitor impacts of rising sea levels on low-lying islands. *File: `maldives_sea_level_rise.geojson`*
- **Himalayan Glacial Lakes** (2000-2024) - Track dangerous glacial lake growth and flood risk. *File: `himalayan_glacial_lakes.geojson`*
- **Himalayan Snow Cover** (2000-2024) - Monitor snow cover trends and water availability. *File: `himalayan_snow_cover.geojson`*
- **Arctic Tundra Changes** (2000-2024) - Track tundra ecosystem shifts and vegetation change. *File: `arctic_tundra_changes.geojson`*

</details>

### 🌳 Conservation & Deforestation

<details>
<summary><b>🌳 Conservation Projects</b> - Click to expand!</summary>

- **Amazon Rainforest Deforestation** (1985-2024) - Monitor deforestation rates in the Brazilian Amazon. Track forest loss, NDVI trends, and fire detection. *File: `amazon_rainforest_deforestation.geojson`*
- **Congo Basin Deforestation** (2000-2024) - Track forest loss in Central Africa's second-largest rainforest. *File: `congo_basin_deforestation.geojson`*
- **Borneo Palm Oil Plantations** (2000-2024) - Track deforestation for palm oil production. Monitor plantation expansion and biodiversity impacts. *File: `borneo_palm_oil_plantations.geojson`*
- **Amazon Gold Mining** (2010-2024) - Monitor illegal mining impacts in the Amazon. Track mining extent, deforestation, and water pollution. *File: `amazon_gold_mining.geojson`*
- **Yellowstone National Park** (1985-2024) - Track ecosystem health and wildfire impacts in America's first national park. *File: `yellowstone_national_park.geojson`*
- **Everglades Restoration** (2000-2024) - Track restoration project effectiveness in Florida's unique ecosystem. *File: `everglades_restoration.geojson`*
- **Sahara Green Wall** (2010-2024) - Track reforestation project across the Sahel. Monitor tree planting and vegetation growth. *File: `sahara_green_wall.geojson`*
- **Himalayan Biodiversity** (2000-2024) - Monitor ecosystem health in one of the world's biodiversity hotspots. *File: `himalayan_biodiversity.geojson`*

</details>

### 🏙️ Urban Development & Infrastructure

<details>
<summary><b>🏙️ Urban Development Projects</b> - Click to expand!</summary>

- **Dubai Urban Expansion** (1990-2024) - Document rapid urban growth and artificial islands. Watch a city grow from desert! *File: `dubai_urban_expansion.geojson`*
- **Sao Paulo Urban Growth** (1985-2024) - Document megacity expansion in South America's largest city. *File: `sao_paulo_urban_growth.geojson`*
- **Mumbai Coastal Development** (1990-2024) - Monitor coastal reclamation projects and urban growth. *File: `mumbai_coastal_development.geojson`*
- **Suez Canal Expansion** (2014-2016) - Document the canal widening project. Short but intense monitoring period! *File: `suez_canal_expansion.geojson`*
- **Mekong River Dams** (2010-2024) - Study dam impacts on the Mekong River system. *File: `mekong_river_dams.geojson`*

</details>

### 🔥 Disaster Monitoring & Recovery

<details>
<summary><b>🔥 Disaster Monitoring Projects</b> - Click to expand!</summary>

- **California Wildfire Recovery** (2018-2024) - Track vegetation recovery after major wildfires. Monitor NDVI recovery and burn scar evolution. *File: `california_wildfire_recovery.geojson`*
- **Australian Bushfire Recovery** (2019-2024) - Monitor ecosystem recovery after the devastating 2019-2020 fires. *File: `australian_bushfire_recovery.geojson`*
- **Bangladesh Flooding** (2000-2024) - Track monsoon flooding patterns and impacts. Monitor flood extent, frequency, and crop damage. *File: `bangladesh_flooding.geojson`*
- **Yangtze River Flooding** (2020-2024) - Monitor recent flood patterns in China's longest river. *File: `yangtze_river_flooding.geojson`*
- **Himalayan Landslide Monitoring** (2015-2024) - Track landslide-prone areas and recovery. *File: `himalayan_landslide_monitoring.geojson`*
- **Florida Everglades Fires** (2017-2024) - Track wildfire patterns in the Everglades. *File: `florida_everglades_fires.geojson`*

</details>

### 🌊 Marine & Coastal Conservation

<details>
<summary><b>🌊 Marine Conservation Projects</b> - Click to expand!</summary>

- **Great Barrier Reef Health** (2015-2024) - Monitor coral bleaching and reef health. Track coral coverage, water clarity, and bleaching events. *File: `great_barrier_reef_health.geojson`*
- **Mississippi River Delta** (1985-2024) - Monitor land loss and delta subsidence. Track wetland health and sediment deposition. *File: `mississippi_river_delta.geojson`*
- **Venice Lagoon Changes** (2000-2024) - Monitor sea level impacts on Venice. Track flood frequency and lagoon health. *File: `venice_lagoon_changes.geojson`*

</details>

### 🌾 Agriculture & Food Security

<details>
<summary><b>🌾 Agriculture Projects</b> - Click to expand!</summary>

- **Nile Delta Agriculture** (1985-2024) - Monitor agricultural productivity and irrigation in Egypt's breadbasket. *File: `nile_delta_agriculture.geojson`*
- **Indus River Agriculture** (1985-2024) - Monitor irrigation and crop patterns in Pakistan's agricultural heartland. *File: `indus_river_agriculture.geojson`*

</details>

### ⚡ Renewable Energy & Infrastructure

<details>
<summary><b>⚡ Renewable Energy Projects</b> - Click to expand!</summary>

- **North Sea Wind Farms** (2010-2024) - Monitor offshore wind farm development. Track farm expansion and marine impacts. *File: `north_sea_wind_farms.geojson`*
- **Sahara Solar Farms** (2015-2024) - Track solar farm development in the world's largest desert. *File: `sahara_solar_farms.geojson`*

</details>

### 🔬 Environmental Monitoring & Research

<details>
<summary><b>🔬 Environmental Research Projects</b> - Click to expand!</summary>

- **Chernobyl Exclusion Zone** (1986-2024) - Study ecosystem recovery after nuclear disaster. Monitor forest regrowth and wildlife habitat. *File: `chernobyl_exclusion_zone.geojson`*
- **Ganges River Pollution** (2000-2024) - Monitor water quality and sediment in one of the world's most polluted rivers. *File: `ganges_river_pollution.geojson`*
- **Niger Delta Oil Spills** (2000-2024) - Track oil spill impacts and ecosystem damage. *File: `niger_delta_oil_spills.geojson`*
- **California Drought Impact** (2012-2024) - Track drought severity and recovery in California. *File: `california_drought_impact.geojson`*

</details>

### 📊 How to Use Project Bounding Boxes

1. **Start Flutter Earth** and click the map selector button
2. **Click "Import"** in the map interface
3. **Navigate to** `bbox_files/` folder
4. **Select any** `.geojson` file from the project list above
5. **The bounding box will load automatically!** Just adjust dates and start processing!

**Pro Tip:** Each project file includes metadata about the project, recommended date ranges, and key metrics to monitor. Check the GeoJSON properties for details!

---

## 🎯 Best Practices

1. **Start small** - Test with a small date range first! 🧪
2. **Use Server Mode** - For dedicated processing machines 🖥️💪
3. **Check the dashboard** - Monitor progress in real-time! 📊✨
4. **Review PDF reports** - Get detailed statistics and insights! 📄💕
5. **Be patient** - Quality takes time, but it's worth it! ⏰🌸

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

## 🔬 Technical Details

This section provides comprehensive technical documentation of all protocols, procedures, and algorithms used in Flutter Earth.

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

#### 5. Gap-Filling Algorithm

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

#### 6. Index Calculation

**Calculated Indices**:
- **NDVI**: `(NIR - Red) / (NIR + Red)` - Vegetation health! 🌿
- **NDWI**: `(Green - NIR) / (Green + NIR)` - Water detection! 💧
- **MNDWI**: `(Green - SWIR1) / (Green + SWIR1)` - Better water detection! 🌊
- **EVI**: `2.5 * ((NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1))` - Enhanced Vegetation Index 🌳
- **SAVI**: `((NIR - Red) / (NIR + Red + 0.5)) * 1.5` - Soil-Adjusted Vegetation Index 🌱
- **FVI**: `(NIR - SWIR1) / (NIR + SWIR1)` - Floating Vegetation Index 🌾
- **AVI**: `NDVI * (1 - |water_index|)` - Aquatic Vegetation Index 🌊🌿

#### 7. COG Creation

- **Format**: Cloud-Optimized GeoTIFF (COG) with internal tiling
- **Overviews**: 2x, 4x, 8x, 16x, 32x (for fast multi-resolution viewing)
- **Compression**: LZW (lossless, good compression ratio)
- **Tile Size**: 512x512 pixels (optimal for web mapping)
- **BigTIFF**: IF_SAFER (handles files >4GB)

### 🚀 Performance Optimizations

1. **Parallel Metadata Fetching**: Uses `ThreadPoolExecutor` with configurable workers (default 4, server mode 16)
2. **Band-by-Band Processing**: Processes mosaic bands individually to reduce memory usage
3. **Cached Timestamps**: Stores timestamps in `detailed_stats` to avoid redundant `getInfo()` calls during gap-filling
4. **Early Stopping**: Stops searching after finding 3 excellent images per satellite (efficiency!)
5. **Progress Detection**: Breaks gap-filling loop if no progress after 3 iterations
6. **Memory-Efficient Reprojection**: Temporary files cleaned up automatically

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

**MIT License** - Feel free to use Flutter Earth however you'd like! 🌸✨

---

## 💕 Acknowledgments

Built with love and care for the geospatial community! 🌍💖

**Special thanks to:**
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

## 🌟 Fun Facts & Easter Eggs! 🥚✨

### Did You Know? 🤓

**The Satellite Family Tree**:
- **Landsat 5** holds the Guinness World Record for the longest-operating Earth observation satellite (28 years, 10 months)! 🏆 It's like the Energizer Bunny of space! 🔋
- **Sentinel-2** takes a picture of the entire Earth every 5 days - that's like taking a selfie of the whole planet! 📸🌍
- The **Dead Sea** (our default example region) is the lowest point on Earth's surface and gets **saltier every year** - it's literally evaporating before our eyes! 💧🔬

**The Power of Resolution**:
- At **10m resolution** (Sentinel-2), you can see individual **parking spaces** in a parking lot! 🚗🅿️
- Flutter Earth uses **10m as the target resolution** - preserving Sentinel-2's native quality while upsampling other satellites to match! ✨
- At **30m resolution** (Landsat), you can distinguish **large buildings** but not individual cars! 🏢
- At **250m resolution** (MODIS), you can see **entire neighborhoods** but not much detail! 🏘️

**Cloud Fun Facts**:
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

**Made with 💖 and lots of ✨ by the Flutter Earth team**

*"Because every pixel deserves to be perfect!"* 🌸

---

## 💝 Special Thanks & Credits 🙏

**Made by a trans girl who loves GIS** 🏳️‍⚧️✨💖🌈🦋🛰️🌍💕✨🎨🦄🌸💎🚀🎯💝⚡🔬🌊💙💜💚🧡💛🤍🖤❤️🧡💛💚💙💜🤎🖤🤍♥️🧡💛💚💙💜🖤🤍💖💕💗💓💞💝❣️💟

*P.S. - If you see this, you found the easter egg! 🥚✨ Trans rights are human rights! 🏳️‍⚧️💖*
