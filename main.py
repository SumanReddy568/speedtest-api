from fastapi import FastAPI, UploadFile
import time, os

app = FastAPI(title="Internet Speed Test API", version="1.0.0")

# Generate random data for download testing
def random_data(size_mb: int):
    return os.urandom(size_mb * 1024 * 1024)

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Internet Speed Test API",
        "routes": {
            "download": "/api/speedtest/download?size_mb=5",
            "upload": "/api/speedtest/upload",
            "docs": "/docs"
        }
    }

@app.get("/api/speedtest/download")
async def download(size_mb: int = 5):
    """Simulate download by sending random binary data."""
    start = time.time()
    data = random_data(size_mb)
    duration = time.time() - start
    return {
        "size_mb": size_mb,
        "generation_time_sec": round(duration, 4),
        "message": f"Generated {size_mb} MB of data for download testing."
    }

@app.post("/api/speedtest/upload")
async def upload(file: UploadFile):
    """Measure upload speed by timing file receipt."""
    start = time.time()
    content = await file.read()
    end = time.time()
    size_mb = len(content) / (1024 * 1024)
    duration = end - start
    speed_mbps = (size_mb * 8) / duration if duration > 0 else 0
    return {
        "upload_size_mb": round(size_mb, 2),
        "duration_sec": round(duration, 2),
        "upload_speed_mbps": round(speed_mbps, 2)
    }
