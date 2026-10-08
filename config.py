import os

from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# DIFY CHAT API
# ============================================================

DIFY_API_KEY = os.getenv("DIFY_API_KEY")

DIFY_API_URL = os.getenv(
    "DIFY_API_URL",
    "https://api.dify.ai/v1/chat-messages",
)


# ============================================================
# DIFY KNOWLEDGE BASE API
# ============================================================

DIFY_KB_API_KEY = os.getenv("DIFY_KB_API_KEY")

DIFY_KB_DATASET_ID = os.getenv(
    "DIFY_KB_DATASET_ID"
)


# ============================================================
# DIFY ASSESSMENT / WORKFLOW API
# ============================================================

DIFY_REPORT_API_KEY = os.getenv(
    "DIFY_REPORT_API_KEY"
)

DIFY_REPORT_API_URL = os.getenv(
    "DIFY_REPORT_API_URL",
    "https://api.dify.ai/v1/workflows/run",
)


# ============================================================
# REQUIRED CONFIGURATION
# ============================================================

if not DIFY_API_KEY:
    raise RuntimeError(
        "DIFY_API_KEY is not set"
    )


if not DIFY_KB_API_KEY:
    raise RuntimeError(
        "DIFY_KB_API_KEY is not set"
    )


if not DIFY_KB_DATASET_ID:
    raise RuntimeError(
        "DIFY_KB_DATASET_ID is not set"
    )


if not DIFY_REPORT_API_KEY:
    raise RuntimeError(
        "DIFY_REPORT_API_KEY is not set"
    )


if not DIFY_REPORT_API_URL:
    raise RuntimeError(
        "DIFY_REPORT_API_URL is not set"
    )
