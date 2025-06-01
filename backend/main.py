from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import logging
from scrapers import get_odds_data
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/props")
async def get_props() -> List[Dict]:
    """
    Get player props from multiple sources.
    Returns a list of dictionaries containing prop information.
    """
    try:
        props = get_odds_data()
        if not props:
            logger.warning("No props data available")
            return []
            
        logger.info(f"Successfully retrieved {len(props)} props")
        return props
        
    except Exception as e:
        logger.error(f"Error getting props: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 