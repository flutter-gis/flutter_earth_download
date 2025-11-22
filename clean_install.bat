@echo off
echo ========================================
echo GEE Downloader - Clean Uninstall
echo ========================================
echo.
echo This will uninstall all GEE Downloader dependencies
echo to allow for a clean reinstall.
echo.
echo WARNING: This will remove the following packages:
echo   - earthengine-api, rasterio, numpy, shapely, pyproj
echo   - tqdm, requests, scikit-image, psutil
echo   - reportlab, matplotlib, s2cloudless, folium
echo   - and their related dependencies
echo.
set /p confirm="Are you sure you want to continue? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo.
    echo Uninstall cancelled.
    pause
    exit /b
)

echo.
echo ========================================
echo Uninstalling packages...
echo ========================================
echo.

REM Uninstall main packages
echo [1/2] Uninstalling main packages...
python -m pip uninstall -y earthengine-api 2>nul
python -m pip uninstall -y rasterio 2>nul
python -m pip uninstall -y numpy 2>nul
python -m pip uninstall -y shapely 2>nul
python -m pip uninstall -y pyproj 2>nul
python -m pip uninstall -y tqdm 2>nul
python -m pip uninstall -y requests 2>nul
python -m pip uninstall -y scikit-image 2>nul
python -m pip uninstall -y psutil 2>nul
python -m pip uninstall -y reportlab 2>nul
python -m pip uninstall -y matplotlib 2>nul
python -m pip uninstall -y s2cloudless 2>nul
python -m pip uninstall -y folium 2>nul

REM Also uninstall common dependencies that might be left behind
echo [2/2] Uninstalling related dependencies...
python -m pip uninstall -y lightgbm 2>nul
python -m pip uninstall -y opencv-python-headless 2>nul
python -m pip uninstall -y sentinelhub 2>nul
python -m pip uninstall -y branca 2>nul
python -m pip uninstall -y jinja2 2>nul
python -m pip uninstall -y xyzservices 2>nul
python -m pip uninstall -y markupsafe 2>nul
python -m pip uninstall -y imageio 2>nul
python -m pip uninstall -y tifffile 2>nul
python -m pip uninstall -y scipy 2>nul
python -m pip uninstall -y networkx 2>nul
python -m pip uninstall -y pillow 2>nul

echo.
echo ========================================
echo Clean uninstall complete!
echo ========================================
echo.
echo All GEE Downloader dependencies have been removed.
echo.
echo Next steps:
echo   1. Run 'python main.py' or 'run_gee.bat'
echo   2. The program will automatically reinstall all dependencies
echo      with the correct versions
echo.
pause

