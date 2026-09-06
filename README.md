# RockLens Geological Intelligence Backend API

RockLens Backend provides high-accuracy rock and mineral identification via Google Cloud Vision API, geospatial specimen management, and secure cloud storage.

## Features

- **Google Cloud Vision Identification**: `POST /api/v1/specimens/identify` extracts web entities, best guess labels, and cross-references against the geological knowledge database.
- **Geological Knowledge Engine**: Comprehensive properties (Chemical Formula, Mohs Hardness, Mineral Group, Cleavage, Crystal System, Luster, Economic Value).
- **Cloud Database & Sync Engine**: PostgreSQL persistence and Cloudinary CDN photo uploads.
