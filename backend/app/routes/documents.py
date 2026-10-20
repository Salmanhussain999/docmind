import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from ..db import connect
from ..ingest.extract import SUPPORTED_TYPES
from ..ingestion import ingest_document
from ..schemas import DocumentOut

router = APIRouter(prefix="/api/documents", tags=["documents"])

COLUMNS = "id, name, media_type, size_bytes, page_count, chunk_count, status, error, created_at"


def _files_dir(request: Request) -> Path:
    path: Path = request.app.state.settings.data_dir / "files"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get(request: Request, document_id: str) -> DocumentOut:
    with connect(request.app.state.settings.db_path) as conn:
        row = conn.execute(f"select {COLUMNS} from documents where id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return DocumentOut(**dict(row))


@router.get("", response_model=list[DocumentOut])
def list_documents(request: Request) -> list[DocumentOut]:
    with connect(request.app.state.settings.db_path) as conn:
        rows = conn.execute(f"select {COLUMNS} from documents order by created_at desc").fetchall()
    return [DocumentOut(**dict(r)) for r in rows]


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(request: Request, file: UploadFile, background: BackgroundTasks) -> DocumentOut:
    """Saves the file and returns straight away; text extraction and embedding run in the background."""
    settings = request.app.state.settings
    name = Path(file.filename or "document").name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "DocMind reads PDF, TXT and Markdown files. Convert the file first.",
        )

    # Read at most one byte past the limit, so an oversized upload is rejected without buffering all of it.
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"Files can be up to {settings.max_upload_mb} MB."
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This file is empty.")
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This file has a .pdf name but isn't a PDF.")

    document_id = uuid.uuid4().hex
    path = _files_dir(request) / f"{document_id}{suffix}"
    path.write_bytes(data)

    with connect(settings.db_path) as conn:
        conn.execute(
            "insert into documents (id, name, media_type, size_bytes, status) values (?, ?, ?, ?, 'processing')",
            (document_id, name[:255], SUPPORTED_TYPES[suffix], len(data)),
        )

    state = request.app.state
    background.add_task(ingest_document, document_id, path, suffix, settings, state.embedder, state.index)
    return _get(request, document_id)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(request: Request, document_id: str) -> DocumentOut:
    return _get(request, document_id)


@router.get("/{document_id}/file")
def download_original(request: Request, document_id: str) -> FileResponse:
    """The original upload, shown inline so the browser's PDF viewer can open it at a page (#page=N)."""
    document = _get(request, document_id)
    suffix = next(s for s, t in SUPPORTED_TYPES.items() if t == document.media_type)
    path = _files_dir(request) / f"{document_id}{suffix}"
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The original file is no longer stored")
    return FileResponse(
        path, media_type=document.media_type, filename=document.name, content_disposition_type="inline"
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(request: Request, document_id: str) -> Response:
    document = _get(request, document_id)
    with connect(request.app.state.settings.db_path) as conn:
        conn.execute("delete from documents where id = ?", (document_id,))  # chunks cascade
    for suffix, media_type in SUPPORTED_TYPES.items():
        if media_type == document.media_type:
            (_files_dir(request) / f"{document_id}{suffix}").unlink(missing_ok=True)
    request.app.state.index.evict(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
