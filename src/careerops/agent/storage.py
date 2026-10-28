import ctypes
import json
import os
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from careerops.agent.contracts import AgentCredentials, AgentError

T = TypeVar("T", bound=BaseModel)
ENTROPY = b"careerops-project-agent-v1"


class Protector(Protocol):
    def protect(self, data: bytes) -> bytes: ...
    def unprotect(self, data: bytes) -> bytes: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_char))]


class WindowsProtector:
    """Use the current Windows user's DPAPI; never fall back to plaintext."""

    def _transform(self, data: bytes, decrypt: bool) -> bytes:
        if sys.platform != "win32":
            raise AgentError(
                "PLATFORM_UNSUPPORTED", "Protected local state currently requires Windows."
            )
        buffer = ctypes.create_string_buffer(data)
        entropy = ctypes.create_string_buffer(ENTROPY)
        source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        salt = _DataBlob(len(ENTROPY), ctypes.cast(entropy, ctypes.POINTER(ctypes.c_char)))
        output = _DataBlob()
        # ctypes loads a Windows-only native API here; no provider/SDK dependency is imported.
        loader = ctypes.WinDLL
        crypt32 = loader("crypt32", use_last_error=True)
        kernel32 = loader("kernel32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(_DataBlob),
        ]
        function.restype = ctypes.c_int
        if not function(
            ctypes.byref(source), None, ctypes.byref(salt), None, None, 1, ctypes.byref(output)
        ):
            raise AgentError("STATE_PROTECTION_FAILED", "Cannot protect or open the local state.")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))

    def protect(self, data: bytes) -> bytes:
        return self._transform(data, False)

    def unprotect(self, data: bytes) -> bytes:
        return self._transform(data, True)


class ProtectedStore:
    def __init__(self, root: Path, protector: Protector | None = None) -> None:
        self.root = root
        self._protector = protector if protector is not None else WindowsProtector()

    def _path(self, name: str) -> Path:
        if not name or Path(name).name != name or "/" in name or "\\" in name or ":" in name:
            raise AgentError(
                "INVALID_STATE_PATH", "State names must be generated local identifiers."
            )
        return self.root / name

    def read(self, name: str, model: type[T]) -> T:
        path = self._path(name)
        try:
            if path.is_symlink() or path.stat().st_size > 1048576:
                raise AgentError("STATE_INVALID", "Local state is invalid; it was not sent.")
            return model.model_validate_json(self._protector.unprotect(path.read_bytes()))
        except (OSError, ValueError, ValidationError) as exc:
            raise AgentError(
                "STATE_UNAVAILABLE", "Cannot read protected local state; it was not sent."
            ) from exc

    def write(self, name: str, data: bytes, replace: bool = False) -> bool:
        destination = self._path(name)
        try:
            protected = self._protector.protect(data)
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor, temporary = tempfile.mkstemp(prefix=".writing-", dir=self.root)
        except OSError as exc:
            raise AgentError(
                "STATE_WRITE_FAILED", "Local state was not safely saved; nothing was sent."
            ) from exc
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(protected)
                stream.flush()
                os.fsync(stream.fileno())
            if replace:
                if destination.is_symlink():
                    raise AgentError("STATE_INVALID", "Refusing to replace a linked state file.")
                os.replace(temporary, destination)
            else:
                try:
                    # Publish a complete packet without overwriting another same-key writer.
                    os.link(temporary, destination)
                except FileExistsError:
                    return False
            return True
        except OSError as exc:
            raise AgentError(
                "STATE_WRITE_FAILED", "Local state was not safely saved; nothing was sent."
            ) from exc
        finally:
            # A leftover staging file is encrypted, never a submitted packet.
            with suppress(OSError):
                Path(temporary).unlink(missing_ok=True)

    def save_credentials(self, credentials: AgentCredentials) -> None:
        raw = {
            "api_url": credentials.api_url,
            "user_id": str(credentials.user_id),
            "access_token": credentials.access_token.get_secret_value(),
        }
        self.write("credentials.bin", json.dumps(raw).encode("utf-8"), replace=True)

    def credentials(self) -> AgentCredentials:
        return self.read("credentials.bin", AgentCredentials)
