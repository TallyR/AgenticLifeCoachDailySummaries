import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

app = FastAPI(title="MessagingCronJob")


@app.get("/")
def read_root():
    return {"status": "ok", "service": "MessagingCronJob"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "supabase_configured": bool(os.getenv("SUPABASE_URL")),
        "blooio_configured": bool(os.getenv("BLOOIO_API_KEY")),
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
    }
