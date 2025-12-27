"""Generate OpenAPI schema from FastAPI app."""

import json
import sys
from pathlib import Path
# Add parent directory to path to import app module
sys.path.insert(0, str(Path(__file__).parent.parent))

from log_setting import initialize, getLogger
from app import app

logger = getLogger()


if __name__ == "__main__":
    # Get OpenAPI schema
    openapi_schema = app.openapi()
    initialize()
    # Write to openapi.json in backend root
    output_path = Path(__file__).parent.parent / "openapi.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    logger.info(f"✓ OpenAPI schema generated: {output_path}")
