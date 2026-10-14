# Sandbox image for running experiments on UNTRUSTED (uploaded / local) projects.
# Build once:   docker build -t devdna-sandbox:latest backend/sandbox
# DevDNA then runs:  docker run --rm --network none --read-only --memory 512m --cpus 1
#                    --pids-limit 128 --cap-drop ALL --security-opt no-new-privileges ...
# Projects whose tests need packages beyond these will fail their baseline run,
# and the experiment is reported as "Inconclusive" (never as confirmed).
FROM python:3.12-slim
RUN pip install --no-cache-dir "pytest>=8.3" "fastapi>=0.115" "httpx>=0.27" "sqlalchemy>=2.0" "pydantic>=2.9" \
    && useradd --create-home --uid 10001 sandbox
USER sandbox
WORKDIR /src
