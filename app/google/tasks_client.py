from __future__ import annotations

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.google.credentials import GoogleCredentialsProvider
from app.google.errors import map_google_http_error


class TasksClientError(Exception):
    """Raised when Google Tasks operations fail."""


class TasksClient:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.credentials_provider = GoogleCredentialsProvider(session, self.settings)

    def _service(self, *, external_subject: str, tenant_id: str | None = None):
        credentials = self.credentials_provider.get_for_user(
            external_subject=external_subject,
            tenant_id=tenant_id,
        )
        return build("tasks", "v1", credentials=credentials, cache_discovery=False)

    def list_tasklists(
        self,
        *,
        external_subject: str,
        tenant_id: str | None = None,
        max_results: int = 100,
        page_token: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        kwargs: dict[str, object] = {"maxResults": max_results}
        if page_token:
            kwargs["pageToken"] = page_token
        try:
            return service.tasklists().list(**kwargs).execute()
        except HttpError as exc:
            raise TasksClientError(str(map_google_http_error(exc))) from exc

    def create_tasklist(
        self,
        *,
        external_subject: str,
        title: str,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.tasklists().insert(body={"title": title}).execute()
        except HttpError as exc:
            raise TasksClientError(str(map_google_http_error(exc))) from exc

    def update_tasklist(
        self,
        *,
        external_subject: str,
        tasklist_id: str,
        title: str,
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.tasklists().patch(tasklist=tasklist_id, body={"title": title}).execute()
        except HttpError as exc:
            raise TasksClientError(str(map_google_http_error(exc))) from exc

    def delete_tasklist(
        self,
        *,
        external_subject: str,
        tasklist_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            service.tasklists().delete(tasklist=tasklist_id).execute()
        except HttpError as exc:
            raise TasksClientError(str(map_google_http_error(exc))) from exc

    def list_tasks(
        self,
        *,
        external_subject: str,
        tasklist_id: str,
        tenant_id: str | None = None,
        max_results: int = 100,
        page_token: str | None = None,
        show_completed: bool = True,
        show_hidden: bool = False,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        kwargs: dict[str, object] = {
            "tasklist": tasklist_id,
            "maxResults": max_results,
            "showCompleted": show_completed,
            "showHidden": show_hidden,
        }
        if page_token:
            kwargs["pageToken"] = page_token
        try:
            return service.tasks().list(**kwargs).execute()
        except HttpError as exc:
            raise TasksClientError(str(map_google_http_error(exc))) from exc

    def create_task(
        self,
        *,
        external_subject: str,
        tasklist_id: str,
        task_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
        except HttpError as exc:
            raise TasksClientError(str(map_google_http_error(exc))) from exc

    def update_task(
        self,
        *,
        external_subject: str,
        tasklist_id: str,
        task_id: str,
        task_body: dict[str, object],
        tenant_id: str | None = None,
    ) -> dict[str, object]:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            return service.tasks().patch(tasklist=tasklist_id, task=task_id, body=task_body).execute()
        except HttpError as exc:
            raise TasksClientError(str(map_google_http_error(exc))) from exc

    def delete_task(
        self,
        *,
        external_subject: str,
        tasklist_id: str,
        task_id: str,
        tenant_id: str | None = None,
    ) -> None:
        service = self._service(external_subject=external_subject, tenant_id=tenant_id)
        try:
            service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
        except HttpError as exc:
            raise TasksClientError(str(map_google_http_error(exc))) from exc
