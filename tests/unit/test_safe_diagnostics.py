from __future__ import annotations

import io
import json
import logging
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.errors import AppError, OperationOutcomeUnknownError, TemporaryProviderError
from app.google.client_base import GoogleApiClientBase
from app.logging import JsonFormatter, RedactionFilter, record_operation_failure


@pytest.mark.parametrize("json_logs", [False, True])
def test_safe_diagnostic_survives_both_formats_without_exception_content(json_logs):
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter("%(message)s"))
    logger = logging.getLogger("app.google.diagnostics")
    old_handlers, old_propagate, old_level = logger.handlers[:], logger.propagate, logger.level
    logger.handlers, logger.propagate = [handler], False
    logger.setLevel(logging.WARNING)
    session = Mock(spec=Session)
    session.info = {
        "diagnostic_tool": "drive_confirm_write_google_doc",
        "diagnostic_stage": "docs_batch_update",
    }
    try:
        error = TemporaryProviderError(
            "secret-token",
            metadata={
                "provider_status_code": 503,
                "provider_reason": "backendError",
                "content_text": "secret-document",
                "authorization": "secret-bearer",
            },
        )
        diagnostic_id = record_operation_failure(session, error)
        record_operation_failure(session, TimeoutError("secret-timeout"))
    finally:
        logger.handlers, logger.propagate, logger.level = old_handlers, old_propagate, old_level
        handler.close()
    rendered = output.getvalue()
    assert diagnostic_id in rendered
    assert "docs_batch_update" in rendered
    assert "TemporaryProviderError" in rendered and "TimeoutError" in rendered
    assert "backendError" in rendered and "503" in rendered
    assert "secret" not in rendered


@pytest.mark.parametrize("failure", [TimeoutError("secret"), TemporaryProviderError("secret")])
def test_uncertain_write_has_correlated_diagnostic_and_never_retries(failure, caplog):
    session = Mock(spec=Session)
    session.info = {"diagnostic_stage": "docs_batch_update"}
    client = GoogleApiClientBase(session)
    with (
        patch("app.google.client_base.execute_google_request", side_effect=failure) as execute,
        pytest.raises(OperationOutcomeUnknownError) as caught,
    ):
        client._execute(Mock(method="POST"))
    error = caught.value.to_dict()
    assert error["retryable"] is False
    assert error["metadata"]["diagnostic_id"] in caplog.text
    assert "secret" not in caplog.text
    assert execute.call_args.kwargs["max_retries"] == 0
    execute.assert_called_once()
    json.dumps(error)


def test_unknown_provider_metadata_is_not_logged(caplog):
    session = Mock(spec=Session)
    session.info = {}
    record_operation_failure(
        session,
        TemporaryProviderError(
            "secret",
            metadata={
                "provider_status_code": "secret-status",
                "provider_reason": "secret-reason",
            },
        ),
    )
    assert "secret" not in caplog.text
    assert '"provider_reason": "other"' in caplog.text


@pytest.mark.parametrize("fail_after_write", [False, True])
def test_doc_confirmation_preserves_single_use_and_committed_result(fail_after_write, caplog):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.db.base import Base
    from app.db.models import PendingGoogleOperation
    from app.schemas.drive import DriveConfirmOperationInput, DrivePrepareWriteGoogleDocInput
    from app.services.drive_service import DriveService

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        settings = get_settings().model_copy(update={"drive_inline_content_limit_bytes": 1024})
        service = DriveService(session, settings)
        service.client = Mock()
        metadata = {"id": "doc", "name": "Test", "mimeType": "application/vnd.google-apps.document"}
        service.client.get_file.return_value = metadata
        prepared = service.prepare_write_google_doc(
            external_subject="test",
            input_data=DrivePrepareWriteGoogleDocInput(
                file_id="doc", content_text="marker", mode="append"
            ),
        )
        arguments = DriveConfirmOperationInput(operation_id=prepared["operation_id"])
        if fail_after_write:
            service.client.get_file.side_effect = TimeoutError("secret")
            result = service.confirm_write_google_doc(external_subject="test", input_data=arguments)
            assert result["confirmed"] is True and result["metadata_unavailable"] is True
            expected_stage, expected_status = "docs_read_metadata", "confirmed"
        else:
            session.info["diagnostic_stage"] = "docs_batch_update"
            service.client.write_google_doc.side_effect = TimeoutError("secret")
            with pytest.raises(OperationOutcomeUnknownError) as caught:
                service.confirm_write_google_doc(external_subject="test", input_data=arguments)
            assert caught.value.metadata["diagnostic_id"] in caplog.text
            expected_stage, expected_status = "docs_batch_update", "unknown"
        assert expected_stage in caplog.text
        assert "secret" not in caplog.text
        assert session.scalar(select(PendingGoogleOperation)).status == expected_status
        with pytest.raises(AppError):
            service.confirm_write_google_doc(external_subject="test", input_data=arguments)
        service.client.write_google_doc.assert_called_once()
    engine.dispose()


@pytest.mark.parametrize("read_fails", [False, True])
def test_actual_doc_client_labels_read_and_batch_failures(read_fails, caplog):
    from app.errors import AppError
    from app.google.drive_client import DriveClient

    session = Mock(spec=Session)
    session.info = {}
    client = DriveClient(session)
    api = Mock()
    api.documents.return_value.get.return_value.method = "GET"
    api.documents.return_value.batchUpdate.return_value.method = "POST"
    responses = (
        [TimeoutError("secret")]
        if read_fails
        else [
            {"body": {"content": [{"endIndex": 1}]}},
            TimeoutError("secret"),
        ]
    )
    with (
        patch.object(client, "_docs_service", return_value=api),
        patch("app.google.client_base.execute_google_request", side_effect=responses),
        pytest.raises(AppError),
    ):
        client.write_google_doc(
            external_subject="test", file_id="doc", content_text="secret", mode="append"
        )
    assert ("docs_read_document" if read_fails else "docs_batch_update") in caplog.text
    assert "secret" not in caplog.text
