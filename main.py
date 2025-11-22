#!/usr/bin/env python3
"""
Main entry point for GEE Satellite Imagery Downloader.

This is the modularized version of the original gee.py file.
All functionality has been split into organized modules in the gee/ package.
"""
import sys
import os
import logging
import subprocess
import importlib

def check_and_install_dependencies():
    """Check for required dependencies and install missing ones."""
    # Required dependencies: (import_name, pip_package_name, version_spec)
    # Some packages have different import names than pip package names
    required_packages = [
        ('ee', 'earthengine-api', '>=1.0.0'),  # Import as 'ee', install as 'earthengine-api'
        ('rasterio', 'rasterio', '>=1.0.0'),
        ('numpy', 'numpy', '>=1.26.0,<2.0.0'),  # Constrain to <2.0.0 to avoid conflicts with pandas/tensorflow
        ('shapely', 'shapely', '>=1.0.0'),
        ('pyproj', 'pyproj', '>=2.0.0'),
        ('tqdm', 'tqdm', '>=4.0.0'),
        ('requests', 'requests', '>=2.0.0'),
        ('skimage', 'scikit-image', '>=0.15.0'),  # Import as 'skimage', install as 'scikit-image'
        ('psutil', 'psutil', '>=5.0.0'),
        ('reportlab', 'reportlab', '>=3.0.0'),
        ('matplotlib', 'matplotlib', '>=3.0.0'),
        ('s2cloudless', 's2cloudless', '>=1.0.0'),
        ('folium', 'folium', '>=0.14.0'),  # Required for map selector feature
        ('webview', 'pywebview', '>=4.0.0'),  # Import as 'webview', install as 'pywebview'
        ('fiona', 'fiona', '>=1.9.0'),  # GDAL-based geospatial library
    ]
    
    missing_packages = []
    
    # Check which packages are missing
    for import_name, pip_name, version_spec in required_packages:
        try:
            # Try importing the package
            importlib.import_module(import_name)
        except (ImportError, ModuleNotFoundError):
            # Package is not installed - this is the only case where we auto-install
            package_spec = f"{pip_name}{version_spec}"
            missing_packages.append((import_name, pip_name, package_spec, False))  # False = no numpy conflict
            print(f"⚠️  Missing dependency: {import_name} (install as: {pip_name})")
        except Exception as e:
            # Package is installed but has import errors
            # Don't automatically reinstall - this could be due to various reasons
            # (missing transitive dependencies, environment issues, etc.)
            # Only log a warning - user can fix manually if needed
            error_str = str(e).lower()
            if "numpy" in error_str or "binary incompatibility" in error_str or "dtype size changed" in error_str:
                print(f"⚠️  Warning: {import_name} may have compatibility issues: {e}")
                print(f"   Package is installed but may not work correctly.")
                print(f"   If needed, fix manually: pip install --upgrade --force-reinstall {pip_name}")
            else:
                print(f"⚠️  Warning: {import_name} has import error: {e}")
                print(f"   Package is installed but import failed. This may be non-critical.")
            # Don't add to missing_packages - don't auto-reinstall on exceptions
    
    # If any packages are missing, try to install them
    if missing_packages:
        # Extract just the package specs for pip install
        package_specs = [spec for _, _, spec, _ in missing_packages]
        
        # Extract numpy and other packages - install numpy first if missing
        numpy_spec = None
        other_packages = []
        for import_name, pip_name, spec, _ in missing_packages:
            if import_name == 'numpy':
                numpy_spec = spec
            else:
                other_packages.append(spec)
        
        print(f"\n📦 Installing {len(missing_packages)} missing dependencies...")
        print("This may take a few moments. Please wait...\n")
        
        try:
            # Install numpy first if it's missing (required for binary compatibility with other packages)
            if numpy_spec:
                print("Installing numpy first (required for binary compatibility)...")
                sys.stdout.flush()
                numpy_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", numpy_spec]
                numpy_result = subprocess.run(numpy_cmd, check=False)
                if numpy_result.returncode != 0:
                    print("⚠️  Warning: numpy installation had issues, but continuing...")
                else:
                    print("✅ Numpy installed successfully")
                print()
            
            # Install other missing packages
            if other_packages:
                # Constrain numpy version to prevent upgrades when installing other packages
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + other_packages + ["numpy>=1.26.0,<2.0.0"]
            else:
                # Only numpy was needed, skip this step
                cmd = None
            
            if cmd:
                print("Running pip install (this may take a while)...")
                print("=" * 60)
                sys.stdout.flush()  # Ensure message is displayed immediately
                
                # Run pip install with real-time output (no capture_output)
                # This shows progress to the user so it doesn't appear frozen
                result = subprocess.run(
                    cmd,
                    check=False  # Don't raise exception on error, we'll handle it
                )
                
                print("=" * 60)
            else:
                # Only numpy was installed, treat as success
                result = type('obj', (object,), {'returncode': 0})()
            
            if result.returncode == 0:
                print("\n✅ Successfully installed all missing dependencies!\n")
                # Verify installations using import names
                failed_installs = []
                for import_name, pip_name, _, _ in missing_packages:
                    try:
                        importlib.import_module(import_name)
                    except (ImportError, ModuleNotFoundError):
                        failed_installs.append(pip_name)
                    except Exception as e:
                        # Import error after installation - might be a real issue
                        print(f"⚠️  {import_name} has import error after installation: {e}")
                        print(f"   Package may not work correctly. Try: pip install --upgrade --force-reinstall {pip_name}")
                        failed_installs.append(pip_name)
                
                if failed_installs:
                    print(f"\n⚠️  Warning: Some packages may not have installed correctly: {', '.join(failed_installs)}")
                    print("   You may need to install them manually:")
                    print(f"   pip install --upgrade --force-reinstall {' '.join(failed_installs)}")
                    return False
                return True
            else:
                print(f"\n❌ Error installing dependencies (exit code: {result.returncode})")
                print("\n💡 Please install manually by running:")
                print(f"   pip install --upgrade --force-reinstall {' '.join(package_specs)}")
                return False
                
        except Exception as e:
            print(f"❌ Error during dependency installation: {e}")
            print("\n💡 Please install manually by running:")
            print(f"   pip install {' '.join(package_specs)}")
            return False
    else:
        print("✅ All required dependencies are installed!\n")
        return True

# Check and install dependencies on startup (only when running as script)
# This needs to happen before any imports that might fail
_DEPS_CHECKED = False
if __name__ == "__main__":
    print("🔍 Checking dependencies...")
    deps_ok = check_and_install_dependencies()
    _DEPS_CHECKED = True
    if not deps_ok:
        print("\n❌ Failed to install required dependencies.")
        print("   Please install them manually and try again:")
        print("   pip install -r requirements.txt")
        print("\nExiting...")
        sys.exit(1)

# Initialize Earth Engine (only after dependency check if running as script)
def find_service_account_key():
    """Find service account key file in common locations."""
    import os
    from gee.config import GEE_SERVICE_ACCOUNT_KEY
    from gee.settings import get_service_account_key
    
    # Check saved settings first
    settings_key = get_service_account_key()
    if settings_key:
        return settings_key
    
    # Check config
    if GEE_SERVICE_ACCOUNT_KEY and os.path.exists(GEE_SERVICE_ACCOUNT_KEY):
        return GEE_SERVICE_ACCOUNT_KEY
    
    # Check environment variable
    env_key = os.environ.get('GEE_SERVICE_ACCOUNT_KEY')
    if env_key and os.path.exists(env_key):
        return env_key
    
    # Check common locations relative to project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    common_paths = [
        os.path.join(project_root, "gee_service_account.json"),
        os.path.join(project_root, "keys", "gee_service_account.json"),
        os.path.join(project_root, "gee-service-account.json"),
        os.path.join(project_root, "service_account_key.json"),
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None

def initialize_earth_engine():
    """Initialize Earth Engine, automatically authenticating if needed."""
    # Suppress googleapiclient warnings during initialization attempts
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=UserWarning)
        
        try:
            import ee
            import json
            from gee.config import MAX_WORKERS, update_connection_pool_size, GEE_PROJECT
            
            # Try service account authentication first if key file is available
            key_file = find_service_account_key()
            if key_file:
                try:
                    print(f"🔑 Using service account key file: {key_file}")
                    
                    # Read the key file to extract project ID if needed
                    project_id = GEE_PROJECT
                    if not project_id:
                        try:
                            with open(key_file, 'r') as f:
                                key_data = json.load(f)
                                project_id = key_data.get('project_id')
                        except Exception:
                            pass
                    
                    # Authenticate using service account
                    credentials = ee.ServiceAccountCredentials(None, key_file)
                    
                    # Initialize with service account credentials
                    # If project_id is available, use it; otherwise let EE use default
                    if project_id:
                        ee.Initialize(credentials, project=project_id)
                        logging.info(f"Initialized Earth Engine with service account from {key_file} (project: {project_id})")
                        print(f"✅ Earth Engine initialized with service account (project: {project_id})\n")
                    else:
                        ee.Initialize(credentials)
                        logging.info(f"Initialized Earth Engine with service account from {key_file}")
                        print("✅ Earth Engine initialized with service account\n")
                    
                    # Set initial connection pool size
                    initial_pool_size = update_connection_pool_size(MAX_WORKERS)
                    if initial_pool_size:
                        logging.info(f"Initialized urllib3 connection pool size: {initial_pool_size} (based on MAX_WORKERS={MAX_WORKERS})")
                    
                    return True
                except Exception as key_error:
                    # Service account auth failed, fall back to user auth
                    print(f"⚠️  Service account authentication failed: {key_error}")
                    print("   Falling back to user authentication...\n")
                    logging.warning(f"Service account authentication failed: {key_error}")
                    logging.info("Falling back to user authentication...")
                    # Continue to normal initialization below
            
            # Normal user authentication (or fallback from service account)
            # Set initial connection pool size based on MAX_WORKERS
            # This ensures we have enough connections from the start
            initial_pool_size = update_connection_pool_size(MAX_WORKERS)
            if initial_pool_size:
                logging.info(f"Initialized urllib3 connection pool size: {initial_pool_size} (based on MAX_WORKERS={MAX_WORKERS})")
            
            # Get project ID from settings, config, or environment
            from gee.settings import get_project_id
            project_id = get_project_id() or GEE_PROJECT or os.environ.get('GEE_PROJECT') or os.environ.get('GOOGLE_CLOUD_PROJECT')
            
            # Try to initialize with project if specified
            if project_id:
                ee.Initialize(project=project_id)
                logging.info(f"Initialized Earth Engine with project: {project_id}")
            else:
                # Try without project first, but this often fails now
                try:
                    ee.Initialize()
                except Exception as no_project_error:
                    # If it fails because no project, provide helpful error
                    error_str = str(no_project_error).lower()
                    if "no project" in error_str or "project" in error_str:
                        raise Exception(
                            "Earth Engine requires a project ID. Please set one of:\n"
                            "  1. Set GEE_PROJECT in gee/config.py\n"
                            "  2. Set GEE_PROJECT environment variable\n"
                            "  3. Set GOOGLE_CLOUD_PROJECT environment variable\n"
                            f"   Error: {no_project_error}"
                        )
                    raise
            return True
        except Exception as e:
            # Import ee here in case the first import failed
            try:
                import ee
            except ImportError:
                print("ERROR: earthengine-api package not found. Please install it first.", file=sys.stderr)
                return False
            
            error_str = str(e).lower()
            # Check if this is an authentication error
            if "no project found" in error_str or "authentication" in error_str or "permission_denied" in error_str:
                # Check if there's a service account key we should use instead
                key_file = find_service_account_key()
                if key_file:
                    print(f"\n💡 Tip: Found service account key file at {key_file}")
                    print("   If you want to use it, make sure it's valid and has proper permissions.")
                    print("   Otherwise, the application will attempt user authentication.\n")
                
                print("🔐 Earth Engine authentication required.")
                print("   Attempting to authenticate automatically...")
                print("   (A browser window will open for you to sign in)")
                print("\n   💡 Alternative: Use a service account key file for automated authentication.")
                print("      Place your service account JSON key file as 'gee_service_account.json' in the project root.")
                print("      (Service account keys include the project ID automatically)\n")
                print("   📋 Note: If using user authentication, you must set a project ID:")
                print("      1. Set GEE_PROJECT in gee/config.py, OR")
                print("      2. Set GEE_PROJECT environment variable, OR")
                print("      3. Set GOOGLE_CLOUD_PROJECT environment variable\n")
                sys.stdout.flush()
                
                try:
                    # Try to use ee.Authenticate() directly first (if available)
                    try:
                        ee.Authenticate()
                        print("✅ Authentication successful! Retrying initialization...\n")
                        sys.stdout.flush()
                        
                        # Try to initialize again after authentication
                        try:
                            from gee.config import MAX_WORKERS, update_connection_pool_size, GEE_PROJECT
                            initial_pool_size = update_connection_pool_size(MAX_WORKERS)
                            if initial_pool_size:
                                logging.info(f"Initialized urllib3 connection pool size: {initial_pool_size} (based on MAX_WORKERS={MAX_WORKERS})")
                            
                            # Get project ID from settings, config, or environment
                            from gee.settings import get_project_id
                            project_id = get_project_id() or GEE_PROJECT or os.environ.get('GEE_PROJECT') or os.environ.get('GOOGLE_CLOUD_PROJECT')
                            
                            if project_id:
                                ee.Initialize(project=project_id)
                                print(f"✅ Earth Engine initialized successfully with project: {project_id}!\n")
                            else:
                                # Try without project, but it will likely fail
                                ee.Initialize()
                                print("✅ Earth Engine initialized successfully!\n")
                            return True
                        except Exception as retry_e:
                            error_str = str(retry_e).lower()
                            if "no project" in error_str or ("project" in error_str and "found" in error_str):
                                print(f"❌ Initialization failed: Project ID required", file=sys.stderr)
                                print("\n💡 Please set your Earth Engine project ID using one of:", file=sys.stderr)
                                print("   1. Set GEE_PROJECT in gee/config.py", file=sys.stderr)
                                print("   2. Set GEE_PROJECT environment variable", file=sys.stderr)
                                print("   3. Set GOOGLE_CLOUD_PROJECT environment variable", file=sys.stderr)
                                print(f"\n   Error: {retry_e}", file=sys.stderr)
                            else:
                                print(f"❌ Initialization still failed after authentication: {retry_e}", file=sys.stderr)
                                print("   Please try running 'earthengine authenticate' manually.", file=sys.stderr)
                            return False
                    except (AttributeError, TypeError):
                        # ee.Authenticate() not available, try subprocess method
                        pass
                    
                    # Fallback: Run earthengine authenticate command via subprocess
                    # Ensure we're using the same Python executable that's running this script
                    python_exe = sys.executable
                    
                    # Verify the Python executable can see earthengine
                    check_result = subprocess.run(
                        [python_exe, "-c", "import ee; print('OK')"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if check_result.returncode != 0:
                        print(f"⚠️  Warning: Cannot verify earthengine module with {python_exe}")
                        print(f"   Error: {check_result.stderr}")
                    
                    # Run earthengine authenticate command
                    # This will open a browser and wait for user to authenticate
                    result = subprocess.run(
                        [python_exe, "-m", "earthengine", "authenticate"],
                        check=False
                    )
                    
                    if result.returncode == 0:
                        print("✅ Authentication successful! Retrying initialization...\n")
                        sys.stdout.flush()
                        
                        # Try to initialize again after authentication
                        try:
                            from gee.config import MAX_WORKERS, update_connection_pool_size, GEE_PROJECT
                            initial_pool_size = update_connection_pool_size(MAX_WORKERS)
                            if initial_pool_size:
                                logging.info(f"Initialized urllib3 connection pool size: {initial_pool_size} (based on MAX_WORKERS={MAX_WORKERS})")
                            
                            # Get project ID from settings, config, or environment
                            from gee.settings import get_project_id
                            project_id = get_project_id() or GEE_PROJECT or os.environ.get('GEE_PROJECT') or os.environ.get('GOOGLE_CLOUD_PROJECT')
                            
                            if project_id:
                                ee.Initialize(project=project_id)
                                print(f"✅ Earth Engine initialized successfully with project: {project_id}!\n")
                            else:
                                # Try without project, but it will likely fail
                                ee.Initialize()
                                print("✅ Earth Engine initialized successfully!\n")
                            return True
                        except Exception as retry_e:
                            error_str = str(retry_e).lower()
                            if "no project" in error_str or ("project" in error_str and "found" in error_str):
                                print(f"❌ Initialization failed: Project ID required", file=sys.stderr)
                                print("\n💡 Please set your Earth Engine project ID using one of:", file=sys.stderr)
                                print("   1. Set GEE_PROJECT in gee/config.py", file=sys.stderr)
                                print("   2. Set GEE_PROJECT environment variable", file=sys.stderr)
                                print("   3. Set GOOGLE_CLOUD_PROJECT environment variable", file=sys.stderr)
                                print(f"\n   Error: {retry_e}", file=sys.stderr)
                            else:
                                print(f"❌ Initialization still failed after authentication: {retry_e}", file=sys.stderr)
                                print("   Please try running 'earthengine authenticate' manually.", file=sys.stderr)
                            return False
                    else:
                        print("❌ Authentication failed or was cancelled.", file=sys.stderr)
                        print(f"   Please run '{python_exe} -m earthengine authenticate' manually.", file=sys.stderr)
                        return False
                except Exception as auth_e:
                    print(f"❌ Error during authentication: {auth_e}", file=sys.stderr)
                    print(f"   Please run '{sys.executable} -m earthengine authenticate' manually.", file=sys.stderr)
                    return False
            else:
                # Some other error, not authentication-related
                print(f"ERROR: Earth Engine initialization failed: {e}", file=sys.stderr)
                return False

# Logging configuration - output to both console and file
# Set up logging FIRST before any imports that might generate warnings
import os
from datetime import datetime

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# Create log file with timestamp
log_filename = f"gee_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_filepath = os.path.join(log_dir, log_filename)

# Set up logging with both console and file handlers
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Set root logger to DEBUG to capture all messages

# Suppress verbose DEBUG messages from third-party libraries
# These libraries are very chatty at DEBUG level
logging.getLogger('rasterio').setLevel(logging.WARNING)
logging.getLogger('rasterio._env').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
logging.getLogger('googleapiclient').setLevel(logging.ERROR)  # Suppress WARNING level 403 errors
logging.getLogger('googleapiclient.http').setLevel(logging.ERROR)  # Specifically suppress HTTP warnings
logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)
logging.getLogger('google.auth').setLevel(logging.WARNING)
logging.getLogger('google.auth.transport').setLevel(logging.WARNING)

# Don't initialize Earth Engine at startup - let the GUI handle it
# This allows the user to configure settings first if needed
if __name__ == "__main__":
    # Don't try to initialize Earth Engine here - the GUI will check and prompt if needed
    # This prevents error messages and warnings before the UI is ready
    pass

# Console handler - INFO level for console output
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
console_handler.setFormatter(console_format)

# File handler - DEBUG level to capture everything (but third-party libs are suppressed)
file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter("%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s")
file_handler.setFormatter(file_format)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Log startup message
logging.info(f"Logging initialized. Log file: {log_filepath}")
logging.debug("DEBUG logging enabled - detailed information will be written to log file (third-party library DEBUG messages suppressed)")

from gee.cli_gui import gui_and_run


if __name__ == "__main__":
    try:
        print("Starting GEE Downloader...")
        print("Initializing GUI...")
        gui_and_run()
        print("Program completed successfully.")
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logging.exception("Fatal error in main execution")
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("If this is an Earth Engine authentication error, run:")
        print("  earthengine authenticate")
        print("=" * 60)
        input("\nPress Enter to exit...")  # Keep window open to see error
        sys.exit(1)
else:
    # When imported as module, don't automatically initialize
    # Let the caller handle initialization when needed
    pass

