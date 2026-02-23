import os
import uvicorn
from backend.app import get_application


def main():
    """Run the FastAPI application."""
    app = get_application()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))


if __name__ == "__main__":
    main()
