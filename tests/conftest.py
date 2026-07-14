import os

os.environ.setdefault("EDR_DATABASE_URL", "postgresql+psycopg://edr:edr@localhost:5432/edr")
os.environ.setdefault("EDR_LLM_PROVIDER", "fake")
