# Requires: python-multipart package for file uploads
# Install: pip install fastapi uvicorn python-multipart

from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import os
import requests
import socket
import ipaddress
from typing import Dict, Any
import asyncio

app = FastAPI(
    title="Internet Speed Test API",
    version="4.0.0",
    description="API for testing client network speeds"
)

# Enable CORS for browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        hostname = socket.gethostname()
        server_ip = socket.gethostbyname(hostname)
        client_ip = request.client.host
        
        # Get real client IP from headers (for reverse proxy scenarios)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        # Get public IP
        public_ip = client_ip if not is_private_ip(client_ip) else None
        
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
                    "country": "Unknown",
                    "city": "Unknown",
                    "isp": "Unknown"
                }
            }
        }
        
        # Get geolocation for client
        if public_ip:
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

@app.get("/", response_class=HTMLResponse, tags=["Info"])
async def root():
    """Serve interactive speed test page."""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Speed Test</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }
        button { width: 100%; padding: 15px; font-size: 18px; background: #4CAF50; color: white; border: none; cursor: pointer; border-radius: 5px; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        .result { margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 5px; }
        .speed { font-size: 32px; font-weight: bold; color: #4CAF50; }
        .label { color: #666; margin-bottom: 5px; }
        .status { text-align: center; margin: 15px 0; color: #666; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>🚀 Internet Speed Test</h1>
    <button onclick="runTest()" id="btn">Start Test</button>
    <div class="status" id="status">Click to start</div>
    
    <div class="grid">
        <div class="result">
            <div class="label">Download</div>
            <div class="speed" id="download">-- Mbps</div>
        </div>
        <div class="result">
            <div class="label">Upload</div>
            <div class="speed" id="upload">-- Mbps</div>
        </div>
    </div>
    
    <div class="result" id="info" style="display:none;">
        <div class="label">Your Location</div>
        <div id="location">--</div>
        <div class="label" style="margin-top:10px;">ISP</div>
        <div id="isp">--</div>
        <div class="label" style="margin-top:10px;">Latency</div>
        <div id="latency">--</div>
    </div>

    <script>
        async function runTest() {
            const btn = document.getElementById('btn');
            btn.disabled = true;
            
            try {
                // Test Download
                document.getElementById('status').textContent = 'Testing download...';
                const dlStart = performance.now();
                const dlResponse = await fetch('/api/speedtest/download?size_mb=10');
                const dlData = await dlResponse.arrayBuffer();
                const dlEnd = performance.now();
                const dlSpeed = (10 * 8) / ((dlEnd - dlStart) / 1000);
                document.getElementById('download').textContent = dlSpeed.toFixed(2) + ' Mbps';
                
                // Test Upload
                document.getElementById('status').textContent = 'Testing upload...';
                const uploadData = new Uint8Array(5 * 1024 * 1024);
                const blob = new Blob([uploadData]);
                const formData = new FormData();
                formData.append('file', blob, 'test.bin');
                
                const upResponse = await fetch('/api/speedtest/upload', {
                    method: 'POST',
                    body: formData
                });
                const upResult = await upResponse.json();
                document.getElementById('upload').textContent = upResult.speed_mbps + ' Mbps';
                
                // Get network info
                document.getElementById('status').textContent = 'Getting location...';
                const infoResponse = await fetch('/api/speedtest/network');
                const info = await infoResponse.json();
                
                const loc = info.client.location;
                document.getElementById('location').textContent = loc.city + ', ' + loc.country;
                document.getElementById('isp').textContent = loc.isp;
                document.getElementById('info').style.display = 'block';
                
                // Test latency
                const pingStart = performance.now();
                await fetch('/api/speedtest/ping');
                const pingEnd = performance.now();
                document.getElementById('latency').textContent = (pingEnd - pingStart).toFixed(0) + ' ms';
                
                document.getElementById('status').textContent = '✅ Test complete!';
            } catch (error) {
                document.getElementById('status').textContent = '❌ Error: ' + error.message;
            } finally {
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
    """

@app.get("/api/speedtest/ping", tags=["Speed Test"])
async def test_ping():
    """Ping endpoint for latency measurement."""
    return {"timestamp": time.time()}

@app.get("/api/speedtest/download", tags=["Speed Test"])
async def test_download(size_mb: int = 10):
    """
    Stream data for download speed test.
    Client measures time to download.
    """
    def generate():
        chunk_size = 256 * 1024
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
            "Cache-Control": "no-cache"
        }
    )

@app.post("/api/speedtest/upload", tags=["Speed Test"])
async def test_upload(file: UploadFile):
    """
    Receive file upload. Returns file size and timestamp for client-side speed calculation.
    Client should measure their own upload time for accurate results.
    """
    size = 0
    chunk_size = 256 * 1024
    while chunk := await file.read(chunk_size):
        size += len(chunk)
    
    return {
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "server_timestamp": time.time(),
        "note": "Calculate speed on client side: (size_mb * 8) / upload_duration_seconds"
    }

@app.get("/api/speedtest/network", tags=["Network"])
async def network_info(request: Request):
    """Get client network details."""
    return await get_network_details(request)

@app.get("/api/speedtest/test", tags=["Speed Test"])
async def speed_test_info(request: Request):
    """
    Get network info and instructions.
    For actual speed test, visit the root URL (/) for interactive test.
    """
    network = await get_network_details(request)
    
    return {
        "message": "Speed tests are performed client-side for accuracy",
        "your_network": network,
        "to_test_speed": {
            "interactive": "Visit / in browser for the most accurate results",
            "api_download": "GET /api/speedtest/download?size_mb=10 and measure time client-side",
            "api_upload": "POST /api/speedtest/upload with file and measure time client-side"
        },
        "note": "All speed measurements should be done on the client side for accurate results"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)