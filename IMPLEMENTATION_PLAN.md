# DevDNA: Implementation Roadmap & Prioritized Backlog

**Technical Lead & Lead Architect**: Senior Software Architect / QA / Security Auditor  
**Date**: October 2026  
**Status**: Active Execution  

---

## 1. Prioritized Improvement Backlog

| ID | Problem | Evidence / File | Root Cause | Priority | Impact | Effort | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|---|---|---|
| **ENV-01** | Python virtual environment portability failure on fresh checkout | `backend/.venv/pyvenv.cfg` pointing to `C:\Python314\python.exe` | Venv created with machine-specific hardcoded paths; `pytest` or server commands failed | **P0** | Blocks local execution and developer onboarding | Small | None | Recreated self-contained `.venv` with host Python 3.11; all backend tests pass |
| **ENV-02** | Missing default `.env` causing 403 on manual local repo analysis | `backend/.env.example` vs `backend/.env` | Unconfigured `DEVDNA_ALLOWED_LOCAL_ROOTS` rejects manual local repo paths | **P0** | Blocks manual repository input and analysis | Small | None | `backend/.env` configured with `DEVDNA_ALLOWED_LOCAL_ROOTS` enabling local directory ingestion |
| **API-01** | Dummy/placeholder API keys treated as configured | `backend/app/config.py:53` | `api_key` returned `"your-key-here"` if present in `.env`, triggering 502 instead of 503 unconfigured | **P1** | Breaks test assertions and confusing status reporting | Small | None | `config.py` filters placeholder keys (`"your-key-here"`, `""`, `"None"`), returning `None` |
| **API-02** | Incomplete validation in `/api/projects/local` | `backend/app/api/projects.py:93` | Folder with no Python files was accepted, creating an empty analysis run | **P1** | Unclear failure when user selects non-Python folder | Small | None | Returns 422 `no_python` with descriptive message if directory contains no `.py` files |
| **UI-01** | React Router v7 future flag deprecation warnings in test suite | `frontend/src/test/components.test.jsx:60` | Test `MemoryRouter` lacked `future={{ v7_startTransition: true, v7_relativeSplatPath: true }}` | **P2** | Noise in test outputs, forward compatibility risks | Small | None | Test `MemoryRouter` updated; `vitest run` runs 100% clean with zero warnings |
| **UI-02** | Manual repository input lacked project name, git url guidance, and shortcuts | `frontend/src/components/NewProjectModal.jsx` | Basic path input with no guidance for Git URLs or custom names | **P1** | Frustrating manual repo entry and confusing 404s when entering GitHub URLs | Small | None | Added custom project name input, Git URL helper banner, and streamlined submission |
| **UX-01** | Missing global keyboard shortcuts | `frontend/src/layouts/AppLayout.jsx` | Modals and drawer required mouse clicks; power users couldn't navigate quickly | **P2** | Slower demo navigation during hackathon presentations | Small | None | Added `Cmd/Ctrl+K` (New Project), `Cmd/Ctrl+J` (Ask DevDNA), `Esc` (Close), and `/` |
| **DEMO-01** | One-click demo launchers for judges | `frontend/src/components/Welcome.jsx` | Judges need to see the digital twin predict & prove failures in under 2 minutes | **P2** | High judging impact; avoids manual navigation during live demos | Medium | None | Direct scenario cards on Welcome and Overview pages |

---

## 2. Phase-by-Phase Roadmap

### Phase 1: Stabilization (COMPLETED)
- **Objective**: Eliminate build, runtime, and environment portability blockers.
- **Tasks**:
  1. Recreate clean Python virtual environment using Python 3.11.
  2. Install all dependencies from `requirements.txt`.
  3. Ensure `backend/.env` exists with safe defaults and `DEVDNA_ALLOWED_LOCAL_ROOTS`.
  4. Filter placeholder API keys in `config.py`.
- **Verification**: `backend/.venv/Scripts/python.exe -m pytest -v` -> 68/68 passed.

### Phase 2: Core Functionality & Ingestion (COMPLETED / IN PROGRESS)
- **Objective**: Guarantee reliable repository ingestion (sample, ZIP upload, and manual local folder path).
- **Tasks**:
  1. Add `no_python` validation on `/api/projects/local` endpoint.
  2. Support custom project names in `api.loadLocal` and `NewProjectModal.jsx`.
  3. Provide Git URL assistance in manual input modal.
  4. Ensure background analysis run streams progress smoothly.
- **Verification**: Tests in `test_api.py` and `components.test.jsx`.

### Phase 3: UI & UX Polish (ACTIVE)
- **Objective**: Wow judges with fluid, accessible, responsive design adhering to `design-taste-frontend`.
- **Tasks**:
  1. Global keyboard shortcuts (`Ctrl+K`, `Ctrl+J`, `Esc`, `/`).
  2. Visual shortcut indicators on sidebar and interactive elements.
  3. Mobile drawer and responsive layout polish.
  4. Zero-warning clean test and build runs.
- **Verification**: `npm test -- --run` and `npm run build`.

### Phase 4: Final Hackathon Readiness
- **Objective**: Rehearse end-to-end demo flow, audit logs, and documentation.
- **Tasks**:
  1. Verify 3-minute demo script against live backend.
  2. Ensure Gemma 4 explanations and consent modals function cleanly.
  3. Prepare `project_progress.md` with full execution log.
