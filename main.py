# Requires: python-multipart package for file uploads
# Install: pip install fastapi uvicorn python-multipart

from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import time
import os
import requests
import socket
import ipaddress
from typing import Dict, Any
import asyncio

app = FastAPI(
    title="Internet Speed Test API",
    version="3.0.0",
    description="API for testing real client network speeds"
)

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
            try:
                ip_info = requests.get(f"http://ip-api.com/json/{public_ip}", timeout=2).json()
                if ip_info.get('status') == 'success':
                    network_info["client"]["location"] = {
                        "country": ip_info.get("country", "Unknown"),
                        "city": ip_info.get("city", "Unknown"),
                        "isp": ip_info.get("isp", "Unknown"),
                        "region": ip_info.get("regionName", "Unknown"),
                        "timezone": ip_info.get("timezone", "Unknown")
                    }
            except:
                pass
        
        return network_info
    except Exception as e:
        return {
            "error": f"Could not fetch network details: {str(e)}",
            "server": {"hostname": socket.gethostname()},
            "client": {"ip": request.client.host}
        }

async def measure_latency(request: Request) -> float:
    """Measure latency by timing a simple request."""
    start = time.time()
    # Client should send timestamp and we calculate RTT
    # For now, return minimal processing time
    await asyncio.sleep(0.001)  # Simulate minimal processing
    return round((time.time() - start) * 1000, 2)

@app.get("/", tags=["Info"])
async def root():
    """Get API information and available endpoints."""
    return {
        "message": "Welcome to the Internet Speed Test API",
        "note": "This API measures YOUR (client's) network speed",
        "base_url": "https://speedtest-api-1q3l.onrender.com",
        "routes": {
            "info": "/",
            "docs": "/docs",
            "ping": "/api/speedtest/ping",
            "download": "/api/speedtest/download?size_mb=10",
            "upload": "/api/speedtest/upload (POST with file)",
            "test": "/api/speedtest/test",
            "network": "/api/speedtest/network"
        }
    }

@app.get("/api/speedtest/ping", tags=["Speed Test"])
async def test_ping(request: Request):
    """Measure latency between client and server."""
    return {
        "timestamp": time.time(),
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "Client should measure round-trip time (RTT)"
    }

@app.get("/api/speedtest/download", tags=["Speed Test"])
async def test_download(size_mb: int = 10):
    """
    Stream random data for download speed test.
    CLIENT must measure time from first to last byte.
    
    Usage:
    1. Record start time when first byte arrives
    2. Record end time when last byte arrives
    3. Calculate: speed_mbps = (size_mb * 8) / duration_seconds
    """
    def generate():
        chunk_size = 256 * 1024  # 256KB chunks
        total_bytes = size_mb * 1024 * 1024
        bytes_sent = 0
        
        while bytes_sent < total_bytes:
            chunk = os.urandom(min(chunk_size, total_bytes - bytes_sent))
            bytes_sent += len(chunk)
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(size_mb * 1024 * 1024),
            "X-Test-Start": str(time.time()),
            "X-Size-MB": str(size_mb),
            "Cache-Control": "no-cache"
        }
    )

@app.post("/api/speedtest/upload", tags=["Speed Test"])
async def test_upload(file: UploadFile):
    """
    Receive file and measure upload speed.
    This measures CLIENT's upload speed (how fast they can send to server).
    """
    start_time = time.time()
    size = 0
    
    chunk_size = 256 * 1024
    while chunk := await file.read(chunk_size):
        size += len(chunk)
    
    duration = time.time() - start_time
    size_mb = size / (1024 * 1024)
    speed_mbps = (size_mb * 8) / duration if duration > 0 else 0
    
    return {
        "test_type": "upload",
        "file": file.filename,
        "size_mb": round(size_mb, 2),
        "duration_sec": round(duration, 3),
        "speed_mbps": round(speed_mbps, 2),
        "note": "This is YOUR upload speed (client to server)"
    }

@app.get("/api/speedtest/test", tags=["Speed Test"])
async def full_speed_test(request: Request):
    """
    Get network information and test instructions.
    
    IMPORTANT: This endpoint only provides network info.
    For actual speed measurements, you must:
    
    1. Download Test:
       - Call GET /api/speedtest/download?size_mb=10
       - Measure time from first byte to last byte on CLIENT side
       - Calculate: speed_mbps = (10 * 8) / duration_seconds
    
    2. Upload Test:
       - Generate random data on client
       - POST to /api/speedtest/upload
       - Server returns your upload speed
    
    3. Latency Test:
       - Call GET /api/speedtest/ping
       - Measure round-trip time on CLIENT side
    """
    
    # Get network details
    network_details = await get_network_details(request)
    
    # Measure basic latency
    latency = await measure_latency(request)
    
    return {
        "test_type": "speed_test_info",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server_latency_ms": latency,
        "network": network_details,
        "instructions": {
            "note": "This endpoint only provides info. For actual speeds:",
            "download_test": {
                "endpoint": "GET /api/speedtest/download?size_mb=10",
                "client_action": "Measure time from first to last byte",
                "calculation": "speed_mbps = (size_mb * 8) / duration_seconds"
            },
            "upload_test": {
                "endpoint": "POST /api/speedtest/upload",
                "client_action": "Send file, server returns your upload speed",
                "note": "Server measures how fast it receives your data"
            },
            "latency_test": {
                "endpoint": "GET /api/speedtest/ping",
                "client_action": "Measure round-trip time (send request -> receive response)"
            }
        },
        "why_client_side": "Network speed must be measured by timing actual data transfer over the network. Server-side generation of random data doesn't measure network speed - it only measures server's memory/CPU speed.",
        "example_clients": {
            "curl_download": "time curl -o /dev/null https://speedtest-api-1q3l.onrender.com/api/speedtest/download?size_mb=10",
            "curl_upload": "curl -X POST -F 'file=@testfile.bin' https://speedtest-api-1q3l.onrender.com/api/speedtest/upload",
            "python": "requests.get('https://speedtest-api-1q3l.onrender.com/api/speedtest/download')",
            "javascript": "fetch('https://speedtest-api-1q3l.onrender.com/api/speedtest/download')"
        }
    }

@app.get("/api/speedtest/network", tags=["Network"])
async def network_info(request: Request):
    """Get network details only."""
    return await get_network_details(request)


if __name__ == "__main__":
    import uvicorn
    # Use environment variables or remove completely
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)