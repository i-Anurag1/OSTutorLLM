# OSTutorLLM Knowledge Base Provenance

The repository ships a curated 16-document Operating Systems course corpus in `documents/`. These Markdown files are authored/curated project material; the repository does not claim they are copied from Silberschatz, faculty notes, YouTube transcripts, or another copyrighted source.

The case-study specification lists these target knowledge categories: OS textbooks, Linux command notes, shell lab manuals, lecture PPTs, previous question papers, viva questions, Linux manual pages, lab solutions, animations, faculty notes, YouTube transcripts, and case studies. The ingestion pipeline accepts PDF, PPTX, DOCX, TXT and Markdown so legally obtained institutional material can be added through the Faculty/Admin upload flow.

Do not bundle copyrighted textbooks, faculty-only material, paid course material, or video transcripts unless you have permission/licensing. Add source metadata and provenance when importing institutional material.

## Current bundled corpus

01_foundations.md through 16_exam_revision.md are the project's curated OS teaching notes.
The benchmark in `benchmarks/os_questions.json` is an evaluation benchmark, not a model-training dataset.
