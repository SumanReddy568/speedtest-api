# Requires: python-multipart package for file uploads
# Install: pip install fastapi uvicorn python-multipart

from fastapi import FastAPI, Request
import time, os
import requests
import socket
import ipaddress
from typing import Dict, Any

app = FastAPI(
    title="Internet Speed Test API",
    version="3.0.0",
    description="API for testing upload and download speeds with network information"
)

# Helper to generate random data
def random_data(size_mb: int):
    return os.urandom(size_mb * 1024 * 1024)

# Simulate network conditions
def simulate_network_transfer(size_mb: float, direction: str = "download"):
    """Simulate realistic network transfer with latency and bandwidth limits."""
    # Typical latency: 10-100ms
    latency = 0.05  # 50ms base latency
    
    # Simulate bandwidth limits (in Mbps)
    max_speeds = {
        "download": 100,  # 100 Mbps download
        "upload": 20      # 20 Mbps upload
    }
    
    # Calculate theoretical transfer time based on bandwidth
    bits = size_mb * 8  # Convert MB to Mb
    bandwidth_time = bits / max_speeds[direction]
    
    # Add latency and some random variation (±10%)
    import random
    variation = random.uniform(0.9, 1.1)
    return (bandwidth_time + latency) * variation

# Perform a simulated download test
def test_download(size_mb: int = 5):
    start = time.time()
    _ = random_data(size_mb)  # Generate data
    
    # Simulate network transfer
    time.sleep(simulate_network_transfer(size_mb, "download"))
    
    duration = time.time() - start
    speed_mbps = (size_mb * 8) / duration if duration > 0 else 0
    return {
        "size_mb": size_mb,
        "duration_sec": round(duration, 3),
        "speed_mbps": round(min(speed_mbps, 100), 2)  # Cap at 100 Mbps
    }

# Perform a simulated upload test (reads local file)
def test_upload(file_path: str = "testfile.bin"):
    if not os.path.exists(file_path):
        # Auto-create test file if missing
        with open(file_path, "wb") as f:
            f.write(os.urandom(5 * 1024 * 1024))  # 5 MB test file

    start = time.time()
    with open(file_path, "rb") as f:
        content = f.read()
    
    # Simulate network transfer
    size_mb = len(content) / (1024 * 1024)
    time.sleep(simulate_network_transfer(size_mb, "upload"))
    
    duration = time.time() - start
    speed_mbps = (size_mb * 8) / duration if duration > 0 else 0
    return {
        "file": file_path,
        "size_mb": round(size_mb, 2),
        "duration_sec": round(duration, 3),
        "speed_mbps": round(min(speed_mbps, 20), 2)  # Cap at 20 Mbps
    }

def is_private_ip(ip: str) -> bool:
    """Check if IP address is private."""
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False

async def get_network_details(request: Request) -> Dict[str, Any]:
    """Get network details including IPs and location data."""
    try:
        # Get server details
        hostname = socket.gethostname()
        server_ip = socket.gethostbyname(hostname)
        
        # Get client IP
        client_ip = request.client.host
        
        # Get public IP for geolocation if we're dealing with private IPs
        if is_private_ip(client_ip):
            try:
                public_ip = requests.get('https://api.ipify.org?format=json', timeout=2).json()['ip']
            except:
                public_ip = None
        else:
            public_ip = client_ip
            
        # Additional network info
        network_info = {
            "server": {
                "hostname": hostname,
                "ip": server_ip,
                "is_private": is_private_ip(server_ip),
                "docker": hostname.startswith('') and len(hostname) == 12,
            },
            "client": {
                "ip": client_ip,
                "public_ip": public_ip,
                "is_private": is_private_ip(client_ip),
                "location": {
                    "country": "Local Network",
                    "city": "Local Network",
                    "isp": "Local Network"
                }
            }
        }
        
        # Only try geolocation for public IPs
        if public_ip and not is_private_ip(public_ip):
            ip_info = requests.get(f"http://ip-api.com/json/{public_ip}", timeout=2).json()
            if ip_info.get('status') == 'success':
                network_info["client"]["location"] = {
                    "country": ip_info.get("country", "Unknown"),
                    "city": ip_info.get("city", "Unknown"),
                    "isp": ip_info.get("isp", "Unknown"),
                    "region": ip_info.get("regionName", "Unknown"),
                    "timezone": ip_info.get("timezone", "Unknown")
                }
        
        return network_info
    except Exception as e:
        return {
            "error": f"Could not fetch network details: {str(e)}",
            "server": {"hostname": socket.gethostname()},
            "client": {"ip": request.client.host}
        }

def run_multiple_tests(test_func, attempts: int = 3, **kwargs):
    """Run multiple tests and return the best result."""
    results = []
    for _ in range(attempts):
        result = test_func(**kwargs)
        results.append(result)
        time.sleep(0.5)  # Brief pause between tests
    
    # Return the result with highest speed
    return max(results, key=lambda x: x["speed_mbps"])

@app.get("/", tags=["Info"])
async def root():
    """Get API information and available endpoints."""
    return {
        "message": "Welcome to the Internet Speed Test API",
        "routes": {
            "info": "/",
            "docs": "/docs",
            "download_test": "/api/speedtest/download",
            "upload_test": "/api/speedtest/upload",
            "full_test": "/api/speedtest/test"
        }
    }

@app.get("/api/speedtest/download", tags=["Speed Test"])
async def download_test(size_mb: int = 5):
    """
    Test download speed by simulating file download.
    
    Parameters:
    - size_mb: Size of test data in megabytes (default: 5)
    
    Returns:
    - Test results including speed in Mbps
    """
    return run_multiple_tests(test_download, size_mb=size_mb)

@app.get("/api/speedtest/upload", tags=["Speed Test"])
async def upload_test(file_path: str = "testfile.bin"):
    """
    Test upload speed by simulating file upload.
    
    Parameters:
    - file_path: Path to test file (default: testfile.bin)
    
    Returns:
    - Test results including speed in Mbps
    """
    return run_multiple_tests(test_upload, file_path=file_path)

@app.get("/api/speedtest/test", tags=["Speed Test"])
async def full_test(
    request: Request,
    file_path: str = "testfile.bin",
    size_mb: int = 5
):
    """
    Run complete speed test including upload, download and network details.
    
    Parameters:
    - file_path: Path to test file (default: testfile.bin)
    - size_mb: Size of download test in megabytes (default: 5)
    
    Returns:
    - Complete test results including:
      * Download speed
      * Upload speed
      * Network details
    """
    download_result = run_multiple_tests(test_download, size_mb=size_mb)
    upload_result = run_multiple_tests(test_upload, file_path=file_path)
    network_details = await get_network_details(request)

    return {
        "summary": {
            "download_speed_mbps": download_result["speed_mbps"],
            "upload_speed_mbps": upload_result["speed_mbps"],
            "tests_per_direction": 3
        },
        "details": {
            "download": download_result,
            "upload": upload_result,
            "network": network_details
        }
    }
