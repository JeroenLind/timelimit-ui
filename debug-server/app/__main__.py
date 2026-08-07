"""Application entry point for running the debug server as a module.

This allows the server to be started with:
    python -m app

"""

import uvicorn
from app.main import app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)