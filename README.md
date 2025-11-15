# 🌍🛰️ GEE Satellite Imagery Downloader & Processor

> **Download the best satellite imagery like a space-obsessed nerd!** 🚀✨

A **production-grade** Python tool for downloading and processing satellite imagery from Google Earth Engine. Supports **multiple sensors** (Sentinel-2, Landsat, MODIS, ASTER, VIIRS) with **intelligent quality-based mosaic generation**. Because who doesn't want the **best pixels** from space? 🎯

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-awesome-brightgreen.svg)
![Satellites](https://img.shields.io/badge/satellites-5+-orange.svg)

---

## 🎯 What Does This Do?

Ever wanted to download satellite imagery but got frustrated with:
- ❌ **Cloudy images** ruining your day? ☁️
- ❌ **Low-resolution data** that looks pixelated? 📉
- ❌ Having to **manually pick** the "best" satellite? 🤔
- ❌ **Complex APIs** that make you cry? 😭

**Well, cry no more!** 😊 This tool automatically:
- ✅ Finds the **best quality** images across **all available satellites** 🏆
- ✅ Intelligently combines them into **beautiful mosaics** 🎨
- ✅ Handles **clouds, shadows, and atmospheric effects** like a pro ☁️➡️☀️
- ✅ Creates **Cloud-Optimized GeoTIFFs (COGs)** ready for analysis 📦
- ✅ Shows you **real-time progress** with a fancy dashboard 📊
- ✅ **Dynamic worker scaling** that pushes your CPU to the limit (but safely!) 💪
- ✅ **24/7 server mode** - designed to run continuously without babysitting 🖥️

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+** (because we're modern like that) 🐍
2. **Google Earth Engine account** (it's free! 🎉)
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
   pip install earthengine-api rasterio numpy shapely pyproj tqdm requests scikit-image psutil
   ```
   
   *(Optional but recommended: `s2cloudless` for advanced cloud detection)*
   ```bash
   pip install s2cloudless
   ```

3. **Run it!**
   ```bash
   python main.py
   ```
   
   Or on Windows, just double-click `run_gee.bat` 🪟

---

## 📖 How to Use

### GUI Mode (Recommended for Humans 🧑)

Just run `python main.py` and a friendly GUI will pop up! Fill in:
- **Bounding Box**: Where do you want imagery? (lon_min, lat_min, lon_max, lat_max) 📍
- **Date Range**: When do you want imagery? (YYYY-MM-DD format) 📅
- **Output Folder**: Where should we save your beautiful mosaics? 💾
- **Max Tiles**: How many tiles? (auto-validates against 40MB limit) 🔢
- **Options**: Toggle satellites, harmonization, ML cloud cleanup, dynamic workers, etc. ⚙️

Click **Submit** and watch the magic happen! ✨

The dashboard will automatically open in your browser showing:
- 📊 Real-time satellite usage histogram
- ⏱️ Countdown timer (estimated time remaining)
- 📋 Detailed test results table (all satellites tested per tile)
- 🎯 Quality scores, cloud fractions, band completeness
- 🌟 Highlighted selected images and fallback images

### CLI Mode (For Terminal Lovers 💻)

If you're a command-line warrior, the tool will prompt you for all the same information. No GUI? No problem!

### Programmatic Usage

```python
from gee import process_month

# Process a single month
process_month(
    bbox=(34.9, 31.0, 35.8, 32.0),  # Dead Sea region
    year=2024,
    month=11,
    out_folder="my_outputs",
    workers=8,  # Or use dynamic workers!
    enable_harmonize=True,
    include_modis=True,
    include_aster=True,
    include_viirs=True,
    max_tiles=2000  # Optional: limit tile count
)
```

---

## 🛰️ Supported Satellites

Our tool is like a **satellite buffet**! 🍽️ We support:

| Satellite | Resolution | Best For | Status | Notes |
|-----------|-----------|----------|--------|-------|
| **Copernicus Sentinel-2** | 10m | High-res, recent imagery | ⭐ Favorite | Best quality, frequent revisits |
| **Landsat 5/7/8/9** | 30m | Historical data, consistency | 🏆 Reliable | Longest time series (1984-present) |
| **ASTER** | 15m | 2000-2008 period | 📅 Retro | Good for early 2000s |
| **MODIS** | 250m | Large-scale analysis | 🌍 Big picture | Daily coverage, penalized for low res |
| **VIIRS** | 375m | Night lights, large areas | 🌙 Night mode | Started 2011 |

The tool **automatically picks the best pixels** from all available satellites based on:
- ☁️ **Cloud coverage** (less is more!)
- 📊 **Image quality** (comprehensive scoring system)
- 📈 **Resolution** (higher is better!)
- 🆕 **Temporal recency** (newer is fresher!)
- 🌞 **Solar/view angles** (better geometry = better quality)
- 🎯 **Band completeness** (missing bands = penalty)

---

## 🏗️ Architecture

This project is **modular** (because we like clean code! 🧹):

```
gee/
├── config.py              # ⚙️ Settings and constants
├── utils.py               # 🔧 Helper functions
├── ee_collections.py      # 🛰️ Earth Engine collections
├── cloud_detection.py     # ☁️ Cloud masking magic
├── image_preparation.py   # 🖼️ Image processing & harmonization
├── quality_scoring.py     # 📊 Quality assessment (the brain!)
├── mosaic_builder.py     # 🎨 Mosaic creation (the artist!)
├── raster_processing.py   # 💾 Local raster ops (stitching, COG creation)
├── download.py            # ⬇️ Download helpers
├── manifest.py           # 📋 Tracking & provenance
├── visualization.py       # 📊 Real-time dashboard (HTML/Chart.js)
├── processing.py          # 🚀 Main processing logic (orchestration)
└── cli_gui.py            # 🖥️ User interface (GUI + CLI)
```

Each module has a clear purpose, making the code:
- 🧪 **Testable**: Test individual components
- 🔧 **Maintainable**: Easy to fix bugs
- 🚀 **Extensible**: Add new features easily
- 📚 **Readable**: Your future self will thank you

---

## 🎨 Features

### 🏆 Quality-Based Selection
**No sensor bias!** The tool picks pixels based purely on quality metrics. A 30m Landsat image with 5% clouds beats a 250m MODIS image with 0% clouds. It's all about that **quality score**! 📊

The quality scoring system considers:
- Cloud fraction (weight: 0.25)
- Solar zenith angle (weight: 0.15)
- View zenith angle (weight: 0.10)
- Valid pixel fraction (weight: 0.15)
- Temporal recency (weight: 0.15)
- Resolution penalty (weight: 0.10)
- Band completeness (weight: 0.10)

### 📊 Real-Time Dashboard
Watch your tiles process in **real-time** with a beautiful HTML dashboard showing:
- 📈 Which satellites are being used (live histogram)
- ⏱️ **Countdown timer** (estimated time remaining based on actual processing times)
- 📋 **Detailed test results table** (every satellite tested, sorted by tile & quality)
- 🎯 Quality scores, cloud fractions, band completeness
- 🌟 **Highlighted selected images** (yellow) and **fallback images** (blue)
- 📥 **Copy table to clipboard** button (CSV format)

The dashboard **auto-refreshes every second** and **auto-archives** when complete!

### ☁️ Intelligent Cloud Handling
- **Advanced cloud masking** for each sensor type
- **Metadata-based cloud fraction** estimation (fast! ⚡)
- **Fallback to mask-based** calculation when needed
- **MODIS cloud detection** bug fixed! 🐛➡️✅
- **Per-pixel fallback** - if a pixel is cloudy in the best image, it automatically uses the next best image that has valid data at that pixel location

### 💪 Memory Efficient
- **Band-by-band processing** for large rasters
- Prevents memory errors on big datasets
- Handles **35+ GB mosaics** without breaking a sweat
- **Dynamic tile size calculation** to stay under 40MB per tile

### 🎨 Feather Blending
Smooth transitions between tiles using **cosine-based feathering**. No harsh edges! Your mosaics will look seamless. 🎨

### ⚡ Dynamic Worker Scaling
**24/7 server mode** - the tool automatically scales workers based on system performance:
- 📈 **Increases workers** when CPU < 95% and memory < 90% (aggressive mode!)
- 📉 **Decreases workers** ONLY when CPU > 95% or memory > 95% (critical territory)
- 🔄 **Checks every 10 completed tiles** (not time-based, more accurate)
- 💪 **Designed for continuous operation** - pushes your system hard but safely

### 🧮 Local Index Calculation
Vegetation and water indices (NDVI, EVI, SAVI, NDWI, MNDWI, AVI, FVI) are calculated **locally** after download - much faster than server-side computation! 🚀

---

## 📊 Output

For each month processed, you get:
- **Mosaic GeoTIFF**: Stitched tiles with feather blending 🎨
- **Cloud-Optimized GeoTIFF (COG)**: Ready for cloud storage ☁️
- **Provenance JSON**: Track which satellites were used 📋
- **Satellite Histogram**: Visual dashboard of satellite usage 📊
- **Archived Histograms**: Timestamped snapshots when complete 🗄️
- **Manifest CSV**: Keep track of all processed months 📝
- **Processing Log**: Detailed log file in output directory 📄

---

## 🐛 Known Issues & Fixes

- ✅ **MODIS Cloud Detection**: Fixed incorrect cloud fraction calculation (was using masked image)
- ✅ **Memory Errors**: Fixed by processing bands individually (handles 35+ GB files)
- ✅ **Tile Size Limits**: Handles 50MB download limit gracefully with validation
- ✅ **Band Type Mismatch**: Fixed homogeneous collection requirement for qualityMosaic
- ✅ **Landsat Band Selection**: Fixed missing SR_B6 handling for Landsat 5/7
- ✅ **Countdown Timer**: Fixed to use actual processing times and unique tile count
- ✅ **Dynamic Workers**: Made more aggressive for 24/7 server operation

---

## 🔧 Configuration

Key settings in `gee/config.py`:
- `TARGET_RES`: Target resolution (default: 5m) 📏
- `MAX_CONCURRENT_TILES`: Max concurrent downloads (default: 10) 🔢
- `DEFAULT_WORKERS`: Default worker count (default: min(CPU_count, 8)) 👷
- `ENABLE_DYNAMIC_WORKERS`: Enable dynamic scaling (default: True) ⚡
- `DYNAMIC_WORKER_CHECK_INTERVAL`: Check every N tiles (default: 10) 🔄
- `MIN_WORKERS`: Minimum workers (default: 1) 📉
- `MAX_WORKERS`: Maximum workers (default: 16) 📈

---

## 🤝 Contributing

Found a bug? 🐛 Have an idea? 💡 Want to add a feature? 🚀

1. Fork the repo 🍴
2. Create a feature branch (`git checkout -b feature/amazing-feature`) 🌿
3. Commit your changes (`git commit -m 'Add amazing feature'`) 💾
4. Push to the branch (`git push origin feature/amazing-feature`) 📤
5. Open a Pull Request 🎯

We love contributions! ❤️

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **Google Earth Engine** for providing amazing satellite data 🌍
- **All the satellite missions** for looking down on Earth 🛰️
- **The open-source community** for awesome tools like `rasterio`, `numpy`, `Chart.js`, and more 🎉
- **NASA, ESA, USGS** for operating these amazing satellites 🚀

---

## 💬 Support

Having issues? Questions? Want to chat? 💬

- 📧 Open an issue on GitHub
- 📚 Check the documentation in the code (it's well-commented!)
- 🔍 Read the module docstrings for detailed function descriptions
- 🐛 Check the log files in `logs/` directory

---

## 🎉 Fun Facts

- This tool can process imagery from **2000 to present** (that's 24+ years!) 📅
- It supports **5 different satellite constellations** 🛰️
- The quality scoring system considers **7 different factors** 📊
- Real-time dashboard updates **every second** (because we're impatient!) ⚡
- Dynamic workers can scale from **1 to 16 workers** automatically 🔄
- The tool tests **top 5 images per satellite** (sorted by cloud cover) 🎯
- **Per-pixel fallback** means every pixel gets the best possible data from any satellite 🌟
- Indices are calculated **locally** for speed (10x faster than server-side!) 🚀
- The dashboard **auto-archives** when complete and **auto-resets** for next mosaic 📦

---

## 🎯 Performance Tips

- 💪 **Use dynamic workers** for 24/7 operation (default: ON)
- 🖥️ **More CPU cores = faster processing** (scales up to 16 workers)
- 💾 **SSD storage** recommended for faster tile I/O
- 🌐 **Stable internet** for Earth Engine downloads
- 📊 **Monitor the dashboard** to see which satellites are being used

---

**Made with ❤️, lots of ☕, and an unhealthy obsession with satellites 🛰️**

*Happy satellite downloading!* 🚀✨🌍

---

## 📸 Example Output

```
Processing Month 2024-11...
📊 Opened satellite histogram dashboard
⏱️ Estimated time remaining: 02:15:30
📈 Workers: 8 (CPU: 45%, Mem: 62%)
✅ Tile 0001: Landsat-8 (Score: 0.845)
✅ Tile 0002: Sentinel-2 (Score: 0.912)
✅ Tile 0003: Landsat-8 (Score: 0.831)
...
🎉 Mosaic complete! Saved to: outputs/2024_11/deadsea_2024_11_COG.tif
```

---

*Last updated: November 2024* 📅
