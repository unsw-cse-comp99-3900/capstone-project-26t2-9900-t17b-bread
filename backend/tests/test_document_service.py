import pytest

from app.services.document_service import parse_uploaded_document
from app.services.errors import ErrorCode, PipelineError, PipelineStage


def test_parse_docx_document():
    from docx import Document
    import io

    document = Document()
    document.add_paragraph(
        "The government announced a sweeping new national budget on Tuesday for all citizens."
    )
    buffer = io.BytesIO()
    document.save(buffer)

    article = parse_uploaded_document(buffer.getvalue(), "budget.docx", article_ref="A")
    assert article.source_type == "upload"
    assert "budget" in article.body_text.lower()


def test_parse_rejects_txt():
    with pytest.raises(PipelineError) as exc:
        parse_uploaded_document(b"hello", "notes.txt", article_ref="A")
    assert exc.value.code == ErrorCode.UPLOAD_UNSUPPORTED_TYPE
    assert exc.value.stage == PipelineStage.UPLOAD
