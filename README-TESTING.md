# OSTutorLLM Acceptance Testing

This project includes `TEST-ALL.bat` for a faculty/demo acceptance run after Docker is started.

## One-click test

Double-click `TEST-ALL.bat` or run from CMD:

```cmd
TEST-ALL.bat
```

The test suite covers health, authentication, role-based access, dashboard, topics, grounded AI Tutor, progress/mastery persistence, all bundled OS simulators, Python Lab, Shell Lab, quiz generation and scoring, RAG rebuild, source upload validation, evaluation metrics, admin analytics, OpenAPI, and frontend health.

## Manual data testing

A faculty user can also upload a PDF, PPTX, DOCX, TXT, or MD file from the Knowledge Base screen. The API validates the extension, 15 MB size limit, text extraction, ingestion, checksum and indexing. The acceptance suite separately uploads a generated Markdown file to verify the upload path.

## Expected result

A clean run ends with:

`ALL ACCEPTANCE TESTS PASSED`

A failure gives the backend log command to investigate:

```cmd
docker compose logs api --tail=100
```
