import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel
from app.services.vision_service import vision_service

logger = logging.getLogger("rocklens_identification_endpoint")
router = APIRouter(prefix="/specimens", tags=["RockLens Online Vision & Identification"])

class Base64IdentifyRequest(BaseModel):
    image_base64: str
    filename: Optional[str] = "specimen.jpg"

@router.post(
    "/identify",
    summary="Online Rock & Mineral Identification via Google Cloud Vision API",
    description="Directly analyzes a captured field specimen image using Google Cloud Vision API and returns high-accuracy geological data."
)
async def identify_field_specimen(
    file: Optional[UploadFile] = File(None, description="The captured rock/mineral photo"),
    image_base64: Optional[str] = Form(None, description="Optional base64 encoded image string"),
):
    image_bytes = None
    filename = "specimen.jpg"

    if file:
        filename = file.filename or "specimen.jpg"
        image_bytes = await file.read()
    elif image_base64:
        import base64
        try:
            # Strip data URL prefix if present
            raw_b64 = image_base64
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            image_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 image encoding: {e}"
            )

    if not image_bytes or len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image data provided. Please upload a rock image file or base64 data."
        )

    try:
        result = await vision_service.identify_specimen(
            image_bytes=image_bytes,
            filename=filename,
        )
        return result
    except Exception as e:
        logger.error(f"Identification error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Geological identification failed: {str(e)}"
        )
