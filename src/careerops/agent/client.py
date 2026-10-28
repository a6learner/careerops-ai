from typing import TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, SecretStr, ValidationError

from careerops.agent.contracts import AgentConfig, AgentCredentials, AgentError, RecordQuery
from careerops.domain.project_records import (
    CheckpointInput,
    CheckpointPage,
    CheckpointRecord,
    ProjectInput,
    ProjectPage,
    ProjectRecord,
    RecordStatus,
)

T = TypeVar("T", bound=BaseModel)


class _Login(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)


class _Token(BaseModel):
    access_token: SecretStr


class _Identity(BaseModel):
    id: UUID


class ProjectAgentClient:
    def __init__(
        self,
        config: AgentConfig,
        credentials: AgentCredentials,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if config.api_url.rstrip("/") != credentials.api_url.rstrip("/"):
            raise AgentError(
                "ORIGIN_MISMATCH", "Log in to the configured API before sending records."
            )
        self.config = config
        self.credentials = credentials
        self._transport = transport

    async def _request(
        self,
        method: str,
        path: str,
        model: type[T],
        body: BaseModel | None = None,
        key: UUID | None = None,
        params: dict[str, str | int] | None = None,
    ) -> T:
        headers = {"Authorization": f"Bearer {self.credentials.access_token.get_secret_value()}"}
        if key is not None:
            headers["Idempotency-Key"] = str(key)
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(
                base_url=self.config.api_url,
                timeout=10,
                trust_env=False,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    path,
                    headers=headers,
                    params=params,
                    content=body.model_dump_json() if body is not None else None,
                )
        except httpx.TransportError as exc:
            raise AgentError(
                "API_UNAVAILABLE", "No receipt received; retry the same packet.", True
            ) from exc
        check_response(response)
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            raise AgentError(
                "INVALID_API_RESPONSE",
                "API receipt could not be validated; keep the same packet.",
                True,
            ) from exc

    async def verify_identity(self) -> None:
        identity = await self._request("GET", "/api/v1/auth/me", _Identity)
        if identity.id != self.credentials.user_id:
            raise AgentError(
                "ACCOUNT_MISMATCH", "The active account differs from the packet owner."
            )

    async def register_project(self, payload: ProjectInput, key: UUID) -> ProjectRecord:
        await self.verify_identity()
        return await self._request("POST", "/api/v1/projects", ProjectRecord, payload, key)

    async def list_projects(self, query: RecordQuery) -> ProjectPage:
        return await self._request(
            "GET", "/api/v1/projects", ProjectPage, params=page_params(query)
        )

    async def get_project(self, project_id: UUID) -> ProjectRecord:
        return await self._request("GET", f"/api/v1/projects/{project_id}", ProjectRecord)

    async def save_checkpoint(
        self, project_id: UUID, payload: CheckpointInput, key: UUID
    ) -> CheckpointRecord:
        await self.verify_identity()
        return await self._request(
            "POST", f"/api/v1/projects/{project_id}/checkpoints", CheckpointRecord, payload, key
        )

    async def search(
        self, project_id: UUID, query: RecordQuery, status: RecordStatus = RecordStatus.CONFIRMED
    ) -> CheckpointPage:
        params = page_params(query)
        params["status"] = status.value
        if query.query:
            params["q"] = query.query
        return await self._request(
            "GET", f"/api/v1/projects/{project_id}/checkpoints", CheckpointPage, params=params
        )

    async def get_evidence(self, project_id: UUID, checkpoint_id: UUID) -> CheckpointRecord:
        return await self._request(
            "GET", f"/api/v1/projects/{project_id}/checkpoints/{checkpoint_id}", CheckpointRecord
        )


def page_params(query: RecordQuery) -> dict[str, str | int]:
    params: dict[str, str | int] = {"limit": query.limit}
    if query.cursor:
        params["cursor"] = query.cursor
    return params


def check_response(response: httpx.Response) -> None:
    if 200 <= response.status_code < 300:
        return
    if response.status_code == 401:
        raise AgentError(
            "LOGIN_REQUIRED", "Session expired; log in locally, then replay the same packet."
        )
    if response.status_code == 409:
        raise AgentError(
            "INPUT_CONFLICT",
            "The key or record conflicts with stored input; do not change a pending packet.",
        )
    if response.status_code == 404:
        raise AgentError("NOT_FOUND", "The requested resource is unavailable to this account.")
    if response.status_code in {408, 429} or response.status_code >= 500:
        raise AgentError(
            "API_UNAVAILABLE", "API could not return a receipt; retry the same packet later.", True
        )
    raise AgentError(
        "API_REJECTED", "API rejected this request; no successful receipt was accepted."
    )


async def login(
    config: AgentConfig,
    email: str,
    password: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AgentCredentials:
    payload = _Login(email=email, password=SecretStr(password))
    try:
        async with httpx.AsyncClient(
            base_url=config.api_url,
            timeout=10,
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": payload.email,
                    "password": payload.password.get_secret_value(),
                },
            )
        check_response(response)
        token = _Token.model_validate_json(response.content)
        async with httpx.AsyncClient(
            base_url=config.api_url,
            timeout=10,
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        ) as client:
            identity_response = await client.get(
                "/api/v1/auth/me",
                headers={
                    "Authorization": f"Bearer {token.access_token.get_secret_value()}",
                },
            )
        check_response(identity_response)
        identity = _Identity.model_validate_json(identity_response.content)
    except httpx.TransportError as exc:
        raise AgentError(
            "API_UNAVAILABLE", "Cannot reach the local API; no credentials saved.", True
        ) from exc
    except ValidationError as exc:
        raise AgentError(
            "INVALID_API_RESPONSE", "Login response was invalid; no credentials saved."
        ) from exc
    return AgentCredentials(
        api_url=config.api_url, user_id=identity.id, access_token=token.access_token
    )
