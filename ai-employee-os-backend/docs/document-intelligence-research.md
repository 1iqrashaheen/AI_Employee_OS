# AI Employee OS: Document Intelligence (Research Notes)

**Owner:** Muhammad Arham
**Status:** Draft v1 (research only, no module code yet)
**Branch:** `feature/document-intelligence`

---

## 1. What the module must deliver

From the team plan:

1. Upload a supported document and read its text
2. Summarize documents
3. Answer simple questions based on the content
4. Basic document search
5. Text extraction from images (OCR) where possible

**Submit:** working module, sample test files, code on my branch, README, testing evidence.
**Not in scope (future work):** contract analysis, policy understanding, company-wide knowledge base, Elasticsearch, S3/R2 at scale.

---

## 2. Pipeline

```
Upload -> validate -> save file -> extract text -> clean -> chunk -> store
                                                                  |
                              +-----------------+-----------------+
                              v                 v                 v
                          Summarize           Search             Q&A
```

Extraction, cleaning and chunking are pure Python and do not depend on the database, the API or the AI provider. They are built and tested first.

---

## 3. Text extraction

| File type | Approach | Notes |
|---|---|---|
| TXT | Read as UTF-8, fall back to another encoding | Detect bad encodings instead of crashing |
| DOCX | `python-docx` (paragraphs and tables) | Headers, footers and text boxes are not covered |
| PDF with a text layer | PDF text library | Keep the page number with each piece of text |
| Scanned PDF | Render each page to an image, then OCR | Detect by "page has almost no extractable text" |
| Images (PNG, JPG) | OCR | Resize and convert to grayscale before OCR |

### PDF libraries compared

| Library | License | Strengths | Weaknesses |
|---|---|---|---|
| PyMuPDF (`fitz`) | AGPL-3.0 (commercial license available) | Fast, good text order, can render pages to images | AGPL matters if the product is sold as closed source |
| pypdf | BSD | Pure Python, simple | Weaker layout handling |
| pdfplumber | MIT | Good for tables | Slower |

**Proposed:** PyMuPDF for speed and page rendering, since this is a student demonstration. The AGPL point goes in the limitations section of the README. If the team wants a permissive license, pypdf plus pdf2image is the alternative.

---

## 4. OCR options

| Option | Cost | Setup | Accuracy on messy scans | Notes |
|---|---|---|---|---|
| Tesseract (`pytesseract`) | Free | Needs the Tesseract binary installed on every machine | Medium | Works offline, language packs available |
| EasyOCR | Free | Large download, heavier on CPU | Medium to good | Slower startup |
| Cloud OCR APIs | Paid per page | API key | Good | Sends documents to a third party |
| Vision-capable LLM | API usage | API key only | Good | Simplest to set up, but costs per image and sends documents to a third party |

**Proposed:** Tesseract as the default, behind a small interface so a vision model can replace it later without changing the rest of the code. If the team does not want to install Tesseract on every machine, the vision LLM is the fallback.

Known OCR risks: poor scans, handwriting, tables, Urdu and mixed-language text.

---

## 5. Chunking

Documents are split into overlapping chunks so that search and Q&A can work with small pieces.

| Decision | Proposal | Reason |
|---|---|---|
| Chunk size | About 800 to 1,200 characters | Small enough to be specific, large enough to keep context |
| Overlap | About 10 to 15 percent | Avoids cutting an answer in half |
| Split points | Paragraph, then sentence, then word | Keeps meaning together |
| Metadata per chunk | Chunk index and page number | Needed for citations like "page 3" |

---

## 6. Search

| Option | Pros | Cons |
|---|---|---|
| PostgreSQL full-text search | Built in, no new service, fits the team's database | Keyword-based, no meaning-based matches |
| pgvector (semantic search) | Finds results by meaning | Needs a different Postgres Docker image and an embeddings model |
| Elasticsearch (named in the project description) | Powerful | Extra service, too heavy for this prototype |

**Proposed:** PostgreSQL full-text search first. pgvector and Elasticsearch are listed as future work.

---

## 7. Question answering (RAG)

1. Find the most relevant chunks for the question
2. Send only those chunks and the question to the LLM
3. Return the answer with the pages it came from
4. If nothing relevant is found, answer "not found in the document" and skip the LLM call

Short documents can go to the model directly without retrieval.

### Summaries

- Short documents are summarized in one call
- Long documents are summarized chunk by chunk, then the partial summaries are combined

### Risks

| Risk | Mitigation |
|---|---|
| Hallucination | Answer only from the supplied chunks, cite pages, allow "not found" |
| Prompt injection through the document text | The prompt states that the document is data and not instructions |
| API cost and rate limits | Limit chunks per question, cap document size |
| Wrong text from bad OCR | Show the extraction method and flag low-confidence results |

---

## 8. Upload safety

- Allowed types only, checked by file signature and not only by extension
- Maximum file size
- Reject empty or corrupted files
- Store files under a generated name, never the user's filename
- Keep each company's files separate

---

## 9. Dependencies on other members

| Depends on | For | Status |
|---|---|---|
| Hadeed (backend) | Auth, database session, `company_id` from the token | Auth branch exists |
| Team decision | AI provider and API key | Open |
| Team decision | File storage location (local disk vs S3/R2) | Open |
| Arayash (integration) | Merging Alembic migrations (multiple heads) | To be raised |

---

## 10. Proposed decisions (to confirm with the team)

1. Python and FastAPI, following the existing backend conventions
2. PyMuPDF and `python-docx` for extraction
3. Tesseract for OCR, behind an interface
4. PostgreSQL full-text search
5. Local disk storage behind a small wrapper
6. AI provider behind a small wrapper, with a mock model for tests so they run without a key

---

## 11. Build plan

| Phase | Work | Touches shared files |
|---|---|---|
| 0 | Research notes (this file), local setup | No |
| 1 | Standalone extraction and chunking core with tests and sample files | No |
| 2 | Database tables, migration, upload and list endpoints | Yes (models, main) |
| 3 | OCR, search | No |
| 4 | Summaries and Q&A (needs the AI key) | No |
| 5 | README, test evidence, sample files | No |

Phase 2 waits until the other modules have settled.
