import sys
import os
from pathlib import Path

# Add all skill script directories to Python path immediately
# This must happen at top level so imports work during test collection
SKILLS_ROOT = Path(__file__).parent.parent

SKILL_DIRS = [
    "imessage-core/scripts",
    "imessage-archiver/scripts",  # Added this
    "image-processor/lib",
    "image-processor/scripts",
    "square-image-upload/scripts",
    "square-image-upload-cowork/scripts",
    "square-cache/scripts",
    "square-crm/scripts",
    "rg-full-auto/scripts",
    "product-labeler/scripts",
    "photos-library/scripts",
    "alpaca-market-data/scripts"
]

for skill_dir in SKILL_DIRS:
    path = SKILLS_ROOT / skill_dir
    if path.exists():
        sys.path.insert(0, str(path))
