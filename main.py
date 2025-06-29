import os
import typing
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
import cloudinary
import cloudinary.uploader
from pydantic import BaseModel
from dotenv import load_dotenv

# --- Load Environment Variables ---
# This will load the .env file and make the variables available to os.getenv()
load_dotenv()


# --- Cloudinary Configuration ---
# Add your Cloudinary credentials to your .env file.
# CLOUDINARY_CLOUD_NAME=your_cloud_name
# CLOUDINARY_API_KEY=your_api_key
# CLOUDINARY_API_SECRET=your_api_secret
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

from src.sync import AsyncSync
from src.sync.common import Audio, GenerationOptions, Video, Input
from src.sync.common.types.generation_id import GenerationId

# --- Configuration ---
# For security, we load the API key from an environment variable.
# Before running the app, set this in your terminal:
# For Windows CMD: set API_KEY=your_api_key_here
# For PowerShell:  $env:API_KEY="your_api_key_here"
# For Linux/macOS: export API_KEY='your_api_key_here'
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise RuntimeError("API_KEY environment variable not set.")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="LipSync API",
    description="A FastAPI wrapper for the Synchronicity Labs LipSync SDK.",
    version="1.0.0",
)

# --- CORS Middleware Configuration ---
# This allows the frontend (running on a different origin) to communicate with the API.
origins = [
    "http://localhost:8080",  # Standard React dev server
    "http://127.0.0.1:8080",
    "http://localhost:5173",  # Standard Vite dev server
    "http://localhost:3000",  # Common port for Node.js servers
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows specified origins
    allow_credentials=True, # Allows cookies to be included in requests
    allow_methods=["*"],    # Allows all HTTP methods
    allow_headers=["*"],    # Allows all headers
)

# --- SDK Client Initialization ---
# We initialize the AsyncSync client once when the app starts.
client = AsyncSync(api_key=API_KEY)


# --- Pydantic Models for API Requests ---
# These models define the expected request body for our endpoints.

class CreateGenerationRequest(BaseModel):
    video_url: str
    audio_url: str
    model: str = "lipsync-2"


# --- API Endpoints ---

@app.post("/generations", tags=["Generations"])
async def create_generation(request: CreateGenerationRequest):
    """
    Create a new lip-sync generation job.

    - **video_url**: URL of the source video file.
    - **audio_url**: URL of the source audio file.
    - **model**: The model to use for generation (e.g., 'lipsync-2.1-pro').
    """
    try:
        inputs = [
            Video(url=request.video_url),
            Audio(url=request.audio_url),
        ]
        generation = await client.generations.create(input=inputs, model=request.model)
        return generation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/generations/{id}", tags=["Generations"])
async def get_generation(id: GenerationId):
    """
    Get the status and details of a specific generation job by its ID.
    """
    try:
        generation = await client.generations.get(id)
        return generation
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/generations", tags=["Generations"])
async def list_generations():
    """
    List all previous generation jobs.
    """
    try:
        generations = await client.generations.list()
        return generations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generations/estimate-cost", tags=["Generations"])
async def estimate_cost(
    video_file: UploadFile = File(..., description="The video file to upload."),
    audio_file: UploadFile = File(..., description="The audio file to upload."),
    model: str = Form("lipsync-2", description="The model to use for generation."),
):
    """
    Estimate the cost of a generation job by uploading files first.
    """
    try:
        # Upload video to Cloudinary
        video_upload_result = cloudinary.uploader.upload(
            video_file.file,
            resource_type="video",
            folder="lipsync_uploads",
        )
        video_url = video_upload_result.get("secure_url")

        # Upload audio to Cloudinary
        audio_upload_result = cloudinary.uploader.upload(
            audio_file.file,
            resource_type="video",
            folder="lipsync_uploads",
        )
        audio_url = audio_upload_result.get("secure_url")

        if not video_url or not audio_url:
            raise HTTPException(status_code=500, detail="File upload to Cloudinary failed for cost estimation.")

        # Estimate cost with the new Cloudinary URLs
        inputs = [
            Video(url=video_url),
            Audio(url=audio_url),
        ]
        cost = await client.generations.estimate_cost(input=inputs, model=model)
        return cost
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-and-generate", tags=["Generations"])
async def upload_and_generate(
    video_file: UploadFile = File(..., description="The video file to upload."),
    audio_file: UploadFile = File(..., description="The audio file to upload."),
    model: str = Form("lipsync-2", description="The model to use for generation."),
):
    """
    Upload a video and audio file, then create a lip-sync generation.

    This endpoint combines file upload and generation into a single step.
    """
    try:
        # Upload video to Cloudinary
        video_upload_result = cloudinary.uploader.upload(
            video_file.file,
            resource_type="video",
            folder="lipsync_uploads",  # Optional: organize uploads in a folder
        )
        video_url = video_upload_result.get("secure_url")

        # Upload audio to Cloudinary
        audio_upload_result = cloudinary.uploader.upload(
            audio_file.file,
            resource_type="video",  # Audio is treated as a video resource type in Cloudinary
            folder="lipsync_uploads",
        )
        audio_url = audio_upload_result.get("secure_url")

        if not video_url or not audio_url:
            raise HTTPException(status_code=500, detail="File upload to Cloudinary failed.")

        # Create generation with the new Cloudinary URLs
        inputs = [
            Video(url=video_url),
            Audio(url=audio_url),
        ]
        generation = await client.generations.create(input=inputs, model=model)
        return generation

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", tags=["Root"])
async def read_root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Welcome to the LipSync API. Visit /docs for documentation."}


# --- How to Run ---
# 1. Make sure you have an API key from Synchronicity Labs.
# 2. Set the API_KEY environment variable in your terminal.
# 3. Run the application using uvicorn:
#    uvicorn main:app --reload
# 4. Open your browser to http://127.0.0.1:8000/docs to see the API documentation.
