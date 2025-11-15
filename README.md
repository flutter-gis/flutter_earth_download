# 🌍 GEE Satellite Imagery Downloader

> **Download beautiful satellite imagery like a pro!** 🛰️

A production-grade Python tool for downloading and processing satellite imagery from Google Earth Engine. Supports multiple sensors (Sentinel-2, Landsat, MODIS, ASTER, VIIRS) with intelligent quality-based mosaic generation. Because who doesn't want the best pixels? ✨

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-awesome-brightgreen.svg)

## 🎯 What Does This Do?

Ever wanted to download satellite imagery but got frustrated with:
- ❌ Cloudy images ruining your day?
- ❌ Low-resolution data that looks pixelated?
- ❌ Having to manually pick the "best" satellite?
- ❌ Complex APIs that make you cry?

**Well, cry no more!** 😊 This tool automatically:
- ✅ Finds the **best quality** images across **all available satellites**
- ✅ Intelligently combines them into beautiful mosaics
- ✅ Handles clouds, shadows, and other pesky atmospheric effects
- ✅ Creates Cloud-Optimized GeoTIFFs (COGs) ready for analysis
- ✅ Shows you real-time progress with a fancy dashboard

## 🚀 Quick Start

### Prerequisites

1. **Python 3.7+** (because we're modern like that)
2. **Google Earth Engine account** (it's free! 🎉)
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
   pip install earthengine-api rasterio numpy shapely pyproj tqdm requests scikit-image
   ```

   *(Optional but recommended: `s2cloudless` for advanced cloud detection)*

3. **Run it!**
   ```bash
   python main.py
   ```
   
   Or on Windows, just double-click `run_gee.bat` 🪟

## 📖 How to Use

### GUI Mode (Recommended for Humans 🧑)

Just run `python main.py` and a friendly GUI will pop up! Fill in:
- **Bounding Box**: Where do you want imagery? (lon_min, lat_min, lon_max, lat_max)
- **Date Range**: When do you want imagery? (YYYY-MM-DD format)
- **Output Folder**: Where should we save your beautiful mosaics?
- **Options**: Toggle satellites, harmonization, ML cloud cleanup, etc.

Click **Submit** and watch the magic happen! ✨

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
    workers=4,
    enable_harmonize=True,
    include_modis=True,
    include_aster=True,
    include_viirs=True
)
```

## 🛰️ Supported Satellites

Our tool is like a satellite buffet! 🍽️

| Satellite | Resolution | Best For | Status |
|-----------|-----------|----------|--------|
| **Sentinel-2** | 10m | High-res, recent imagery | ⭐ Favorite |
| **Landsat 5/7/8/9** | 30m | Historical data, consistency | 🏆 Reliable |
| **ASTER** | 15m | 2000-2008 period | 📅 Retro |
| **MODIS** | 250m | Large-scale analysis | 🌍 Big picture |
| **VIIRS** | 375m | Night lights, large areas | 🌙 Night mode |

The tool **automatically picks the best pixels** from all available satellites based on:
- Cloud coverage (less is more! ☁️)
- Image quality
- Resolution (higher is better! 📈)
- Temporal recency (newer is fresher! 🆕)

## 🏗️ Architecture

This project is **modular** (because we like clean code! 🧹):

```
gee/
├── config.py              # Settings and constants
├── utils.py               # Helper functions
├── ee_collections.py      # Earth Engine collections
├── cloud_detection.py     # Cloud masking magic
├── image_preparation.py   # Image processing
├── quality_scoring.py     # Quality assessment
├── mosaic_builder.py      # Mosaic creation
├── raster_processing.py   # Local raster ops
├── download.py            # Download helpers
├── manifest.py            # Tracking
├── visualization.py        # Real-time dashboard
├── processing.py          # Main processing logic
└── cli_gui.py            # User interface
```

Each module has a clear purpose, making the code:
- 🧪 **Testable**: Test individual components
- 🔧 **Maintainable**: Easy to fix bugs
- 🚀 **Extensible**: Add new features easily
- 📚 **Readable**: Your future self will thank you

## 🎨 Features

### Quality-Based Selection
No sensor bias! The tool picks pixels based purely on quality metrics. A 30m Landsat image with 5% clouds beats a 250m MODIS image with 0% clouds. It's all about that quality score! 📊

### Real-Time Dashboard
Watch your tiles process in real-time with a beautiful HTML dashboard showing:
- Which satellites are being used
- Progress tracking
- Live updates (auto-refreshes every second!)

### Intelligent Cloud Handling
- Advanced cloud masking for each sensor
- Metadata-based cloud fraction estimation (fast!)
- Fallback to mask-based calculation when needed
- MODIS cloud detection bug fixed! 🐛➡️✅

### Memory Efficient
- Band-by-band processing for large rasters
- Prevents memory errors on big datasets
- Handles 35+ GB mosaics without breaking a sweat 💪

### Feather Blending
Smooth transitions between tiles using cosine-based feathering. No harsh edges! Your mosaics will look seamless. 🎨

## 📊 Output

For each month processed, you get:
- **Mosaic GeoTIFF**: Stitched tiles with feather blending
- **Cloud-Optimized GeoTIFF (COG)**: Ready for cloud storage
- **Provenance JSON**: Track which satellites were used
- **Satellite Histogram**: Visual dashboard of satellite usage
- **Manifest CSV**: Keep track of all processed months

## 🐛 Known Issues & Fixes

- ✅ **MODIS Cloud Detection**: Fixed incorrect cloud fraction calculation
- ✅ **Memory Errors**: Fixed by processing bands individually
- ✅ **Tile Size Limits**: Handles 50MB download limit gracefully

## 🤝 Contributing

Found a bug? Have an idea? Want to add a feature?

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

We love contributions! ❤️

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Google Earth Engine** for providing amazing satellite data
- **All the satellite missions** for looking down on Earth
- **The open-source community** for awesome tools like `rasterio`, `numpy`, and more

## 💬 Support

Having issues? Questions? Want to chat?

- Open an issue on GitHub
- Check the documentation in the code (it's well-commented!)
- Read the module docstrings for detailed function descriptions

## 🎉 Fun Facts

- This tool can process imagery from **2000 to present** (that's 24+ years!)
- It supports **5 different satellite constellations**
- The quality scoring system considers **6 different factors**
- Real-time dashboard updates **every second** (because we're impatient!)

---

**Made with ❤️ and lots of ☕**

*Happy satellite downloading!* 🛰️✨

