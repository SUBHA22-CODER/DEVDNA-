# Security, Privacy & Isolation Architecture

DevDNA is designed to analyze software repositories and execute controlled fault-injection tests without compromising the host machine, leaking confidential credentials, or enabling remote code execution.

---

## 1. Threat Model & Security Boundaries

DevDNA handles untrusted source code during static analysis and dynamic fault injection:

| Threat Vector | Mitigation Strategy | Implementation |
| :--- | :--- | :--- |
| **Malicious Code Execution** | Untrusted code execution is blocked unless running inside a hardened Docker container. | [`backend/app/experiments/runner.py:47-54`](../backend/app/experiments/runner.py#L47-L54) |
| **Path Traversal in ZIP Uploads** | Strict validation of archive entry paths, rejecting `..`, absolute paths, Windows drive letters, and symlinks. | [`backend/app/analyzer/zip_safety.py`](../backend/app/analyzer/zip_safety.py) |
| **Archive Decompression Bombs** | Strict entry count limit (10,000 files) and uncompressed byte size limit (500 MB). | [`backend/app/analyzer/zip_safety.py`](../backend/app/analyzer/zip_safety.py) |
| **Secret / Credential Leakage** | Automated multi-pattern redaction filter applied to all code snippets, logs, and evidence before storage or display. | [`backend/app/analyzer/redact.py`](../backend/app/analyzer/redact.py) |
| **Arbitrary Command Injection** | Fixed execution commands (`python -m pytest ...`); user-supplied shell commands are strictly disallowed. | [`backend/app/experiments/runner.py:126`](../backend/app/experiments/runner.py#L126) |
| **Unauthorized Local Filesystem Access** | Server-side directory whitelist required for local repository ingestion (`DEVDNA_ALLOWED_LOCAL_ROOTS`). | [`backend/app/config.py:32-35`](../backend/app/config.py#L32-L35) |

---

## 2. Dynamic Execution Isolation Controls

### A. Local Restricted Harness (Trusted Sample Projects Only)
When executing experiments on the bundled, trusted sample project:
* The codebase is copied into a temporary, disposable directory (`devdna-exp-*`).
* All environment variables are scrubbed (`_scrubbed_env`); no host credentials, API keys, or system tokens are inherited.
* The directory is completely destroyed (`shutil.rmtree`) upon completion in a `finally` block.
* Output size is capped at 20,000 characters and sanitized with the redaction pipeline.

### B. Docker Container Sandbox (Uploaded / Untrusted Code)
When running tests on uploaded or external projects, Docker is mandatory:

```bash
docker run --rm \
  --network none \
  --memory 512m \
  --cpus 1 \
  --pids-limit 128 \
  --read-only \
  --tmpfs /tmp:rw,size=64m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  -v <project_dir>:/src:ro \
  -v <harness_dir>:/harness:ro \
  -v <workdir>:/out:rw \
  devdna-sandbox:latest python -m pytest ...
```

* `--network none`: Complete network isolation. The analyzed application cannot make outbound calls, exfiltrate data, or access local networks.
* `--read-only`: The container root filesystem and mounted source code are strictly read-only.
* `--cap-drop ALL`: All Linux capabilities are dropped.
* `--security-opt no-new-privileges`: Prevents privilege escalation.
* `--memory 512m`, `--cpus 1`, `--pids-limit 128`: Enforces strict resource exhaustion protection (fork-bomb and memory-exhaustion prevention).

> **Policy Enforcement:** If Docker is not available on the host machine, experiments on untrusted repositories are **BLOCKED** with a clear explanation. Code is never run unsandboxed.

---

## 3. Secret Redaction Pipeline

*Implementation Reference:* [`backend/app/analyzer/redact.py`](../backend/app/analyzer/redact.py)

Before any source code snippet, JUnit failure message, or graph evidence token is stored in the database or sent to Gemma 4, it is sanitized using regular expression patterns:

* **OpenAI / Anthropic API Keys:** `sk-live-...`, `sk-proj-...`, `sk-ant-...`
* **Google Gemini API Keys:** `AIza[0-9A-Za-z-_]{35}`
* **GitHub Personal Access Tokens:** `ghp_...`, `gho_...`, `ghu_...`
* **Authorization Headers:** `Bearer [token]`
* **Database Connection URIs:** `postgres://user:password@host/db`, `mongodb://...`, `mysql://...`
* **Password Assignments:** `password = "..."`, `secret: '...'`

---

## 4. Responsible Disclosure

If you discover a security vulnerability in DevDNA, please file an issue or reach out directly to the repository maintainer with reproduction details.
