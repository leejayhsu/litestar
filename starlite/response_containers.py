from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterable,
    AsyncIterator,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Literal,
    TypeVar,
)

from starlite.background_tasks import BackgroundTask, BackgroundTasks
from starlite.constants import DEFAULT_CHUNK_SIZE
from starlite.datastructures.cookie import Cookie
from starlite.datastructures.headers import ETag
from starlite.enums import MediaType
from starlite.exceptions import ImproperlyConfiguredException
from starlite.file_system import BaseLocalFileSystem
from starlite.response import (
    FileResponse,
    RedirectResponse,
    StreamingResponse,
    TemplateResponse,
)
from starlite.types import FileInfo
from starlite.types.composite_types import PathType, StreamType

__all__ = ("File", "Redirect", "ResponseContainer", "Stream", "Template")


if TYPE_CHECKING:
    from starlite.app import Starlite
    from starlite.connection import Request

R_co = TypeVar("R_co", covariant=True)


class ResponseContainer(ABC, Generic[R_co]):
    """Generic response container."""

    background: BackgroundTask | BackgroundTasks | None
    """A :class:`BackgroundTask <starlite.datastructures.BackgroundTask>` instance or.

    :class:`BackgroundTasks <starlite.datastructures.BackgroundTasks>` to execute after the response is finished.
    Defaults to None.
    """
    headers: dict[str, Any]
    """A string/string dictionary of response headers.

    Header keys are insensitive. Defaults to None.
    """
    cookies: list[Cookie]
    """A list of Cookie instances to be set under the response 'Set-Cookie' header.

    Defaults to None.
    """
    media_type: MediaType | str | None
    """If defined, overrides the media type configured in the route decorator."""
    encoding: str
    """The encoding to be used for the response headers."""

    @abstractmethod
    def to_response(
        self,
        headers: dict[str, Any],
        media_type: MediaType | str,
        status_code: int,
        app: Starlite,
        request: Request,
    ) -> R_co:  # pragma: no cover
        """Abstract method that should be implemented by subclasses.

        Args:
            headers: A dictionary of headers.
            media_type: A string or member of the :class:`MediaType <starlite.enums.MediaType>` enum.
            status_code: A response status code.
            app: The :class:`Starlite <starlite.app.Starlite>` application instance.
            request: A :class:`Request <starlite.connection.request.Request>` instance.

        Returns:
            A Response Object
        """
        raise NotImplementedError("not implemented")


@dataclass
class File(ResponseContainer[FileResponse]):
    """Container type for returning File responses."""

    path: PathType
    """Path to the file to send."""
    background: BackgroundTask | BackgroundTasks | None = field(default=None)
    """A :class:`BackgroundTask <starlite.datastructures.BackgroundTask>` instance or.

    :class:`BackgroundTasks <starlite.datastructures.BackgroundTasks>` to execute after the response is finished.
    Defaults to None.
    """
    headers: dict[str, Any] = field(default_factory=dict)
    """A string/string dictionary of response headers.

    Header keys are insensitive. Defaults to None.
    """
    cookies: list[Cookie] = field(default_factory=list)
    """A list of Cookie instances to be set under the response 'Set-Cookie' header.

    Defaults to None.
    """
    media_type: MediaType | str | None = field(default=None)
    """If defined, overrides the media type configured in the route decorator."""
    encoding: str = field(default="utf-8")
    """The encoding to be used for the response headers."""
    filename: str | None = field(default=None)
    """An optional filename to set in the header."""
    stat_result: os.stat_result | None = field(default=None)
    """An optional result of calling 'os.stat'.

    If not provided, this will be done by the response constructor.
    """
    chunk_size: int = field(default=DEFAULT_CHUNK_SIZE)
    """The size of chunks to use when streaming the file."""
    content_disposition_type: Literal["attachment", "inline"] = field(default="attachment")
    """The type of the 'Content-Disposition'.

    Either 'inline' or 'attachment'.
    """
    etag: ETag | None = field(default=None)
    """An optional :class:`ETag <starlite.datastructures.ETag>` instance.

    If not provided, an etag will be automatically generated.
    """
    file_system: Any = field(default_factory=BaseLocalFileSystem)
    """The file_system spec to use loading the file.

    Notes:
        - A file_system is a class that adheres to the
            :class:`FileSystemProtocol <starlite.types.FileSystemProtocol>`.
        - You can use any of the file systems exported from the
            [fsspec](https://filesystem-spec.readthedocs.io/en/latest/) library for this purpose.
    """
    file_info: FileInfo | None = field(default=None)
    """The output of calling `file_system.info(..)`, equivalent to providing a ``stat_result``."""

    def __post_init__(self) -> None:
        if not (
            callable(getattr(self.file_system, "info", None)) and callable(getattr(self.file_system, "open", None))
        ):
            raise ImproperlyConfiguredException("file_system must adhere to the FileSystemProtocol type")

        if not self.stat_result:
            self.stat_result = Path(self.path).stat()

    def to_response(
        self,
        headers: dict[str, Any],
        media_type: MediaType | str | None,
        status_code: int,
        app: Starlite,
        request: Request,
    ) -> FileResponse:
        """Create a FileResponse instance.

        Args:
            headers: A dictionary of headers.
            media_type: A string or member of the :class:`MediaType <starlite.enums.MediaType>` enum.
            status_code: A response status code.
            app: The :class:`Starlite <starlite.app.Starlite>` application instance.
            request: A :class:`Request <starlite.connection.request.Request>` instance.

        Returns:
            A FileResponse instance
        """
        return FileResponse(
            background=self.background,
            chunk_size=self.chunk_size,
            content_disposition_type=self.content_disposition_type,
            encoding=self.encoding,
            etag=self.etag,
            file_info=self.file_info,
            file_system=self.file_system,
            filename=self.filename,
            headers=headers,
            media_type=media_type,
            path=self.path,
            stat_result=self.stat_result,
            status_code=status_code,
        )


@dataclass
class Redirect(ResponseContainer[RedirectResponse]):
    """Container type for returning Redirect responses."""

    path: str
    """Redirection path."""
    background: BackgroundTask | BackgroundTasks | None = field(default=None)
    """A :class:`BackgroundTask <starlite.datastructures.BackgroundTask>` instance or.

    :class:`BackgroundTasks <starlite.datastructures.BackgroundTasks>` to execute after the response is finished.
    Defaults to None.
    """
    headers: dict[str, Any] = field(default_factory=dict)
    """A string/string dictionary of response headers.

    Header keys are insensitive. Defaults to None.
    """
    cookies: list[Cookie] = field(default_factory=list)
    """A list of Cookie instances to be set under the response 'Set-Cookie' header.

    Defaults to None.
    """
    media_type: MediaType | str | None = field(default=None)
    """If defined, overrides the media type configured in the route decorator."""
    encoding: str = field(default="utf-8")
    """The encoding to be used for the response headers."""

    def to_response(  # type: ignore[override]
        self,
        headers: dict[str, Any],
        # TODO: update the redirect response to support HTML as well.
        #   This argument is currently ignored.
        media_type: MediaType | str,
        status_code: Literal[301, 302, 303, 307, 308],
        app: Starlite,
        request: Request,
    ) -> RedirectResponse:
        """Create a RedirectResponse instance.

        Args:
            headers: A dictionary of headers.
            media_type: A string or member of the :class:`MediaType <starlite.enums.MediaType>` enum.
            status_code: A response status code.
            app: The :class:`Starlite <starlite.app.Starlite>` application instance.
            request: A :class:`Request <starlite.connection.request.Request>` instance.

        Returns:
            A RedirectResponse instance
        """
        return RedirectResponse(
            background=self.background,
            encoding=self.encoding,
            headers=headers,
            status_code=status_code,
            url=self.path,
        )


@dataclass
class Stream(ResponseContainer[StreamingResponse]):
    """Container type for returning Stream responses."""

    iterator: StreamType[str | bytes] | Callable[[], StreamType[str | bytes]]
    """Iterator, Iterable,Generator or async Iterator, Iterable or Generator returning chunks to stream."""
    background: BackgroundTask | BackgroundTasks | None = field(default=None)
    """A :class:`BackgroundTask <starlite.datastructures.BackgroundTask>` instance or.

    :class:`BackgroundTasks <starlite.datastructures.BackgroundTasks>` to execute after the response is finished.
    Defaults to None.
    """
    headers: dict[str, Any] = field(default_factory=dict)
    """A string/string dictionary of response headers.

    Header keys are insensitive. Defaults to None.
    """
    cookies: list[Cookie] = field(default_factory=list)
    """A list of Cookie instances to be set under the response 'Set-Cookie' header.

    Defaults to None.
    """
    media_type: MediaType | str | None = field(default=None)
    """If defined, overrides the media type configured in the route decorator."""
    encoding: str = field(default="utf-8")
    """The encoding to be used for the response headers."""

    def __post_init__(self) -> None:
        """Set the iterator value by ensuring that the return value is iterable.

        Args:
            value: An iterable or callable returning an iterable.

        Returns:
            A sync or async iterable.
        """

        if not isinstance(self.iterator, (Iterable, Iterator, AsyncIterable, AsyncIterator)) and callable(
            self.iterator
        ):
            self.iterator = self.iterator()

        if not isinstance(self.iterator, (Iterable, Iterator, AsyncIterable, AsyncIterator)):
            raise ImproperlyConfiguredException(
                "iterator must be either an iterator or a callable that returns an iterator"
            )

    def to_response(
        self,
        headers: dict[str, Any],
        media_type: MediaType | str,
        status_code: int,
        app: Starlite,
        request: Request,
    ) -> StreamingResponse:
        """Create a StreamingResponse instance.

        Args:
            headers: A dictionary of headers.
            media_type: A string or member of the :class:`MediaType <starlite.enums.MediaType>` enum.
            status_code: A response status code.
            app: The :class:`Starlite <starlite.app.Starlite>` application instance.
            request: A :class:`Request <starlite.connection.request.Request>` instance.

        Returns:
            A StreamingResponse instance
        """

        return StreamingResponse(
            background=self.background,
            content=self.iterator if isinstance(self.iterator, (Iterable, AsyncIterable)) else self.iterator(),
            encoding=self.encoding,
            headers=headers,
            media_type=media_type,
            status_code=status_code,
        )


@dataclass
class Template(ResponseContainer[TemplateResponse]):
    """Container type for returning Template responses."""

    name: str
    """Path-like name for the template to be rendered, e.g. "index.html"."""
    context: dict[str, Any] = field(default_factory=dict)
    """A dictionary of key/value pairs to be passed to the temple engine's render method.

    Defaults to None.
    """
    background: BackgroundTask | BackgroundTasks | None = field(default=None)
    """A :class:`BackgroundTask <starlite.datastructures.BackgroundTask>` instance or.

    :class:`BackgroundTasks <starlite.datastructures.BackgroundTasks>` to execute after the response is finished.
    Defaults to None.
    """
    headers: dict[str, Any] = field(default_factory=dict)
    """A string/string dictionary of response headers.

    Header keys are insensitive. Defaults to None.
    """
    cookies: list[Cookie] = field(default_factory=list)
    """A list of Cookie instances to be set under the response 'Set-Cookie' header.

    Defaults to None.
    """
    media_type: MediaType | str | None = field(default=None)
    """If defined, overrides the media type configured in the route decorator."""
    encoding: str = field(default="utf-8")
    """The encoding to be used for the response headers."""

    def to_response(
        self,
        headers: dict[str, Any],
        media_type: MediaType | str,
        status_code: int,
        app: Starlite,
        request: Request,
    ) -> TemplateResponse:
        """Create a TemplateResponse instance.

        Args:
            headers: A dictionary of headers.
            media_type: A string or member of the :class:`MediaType <starlite.enums.MediaType>` enum.
            status_code: A response status code.
            app: The :class:`Starlite <starlite.app.Starlite>` application instance.
            request: A :class:`Request <starlite.connection.request.Request>` instance.

        Raises:
            :class:`ImproperlyConfiguredException <starlite.exceptions.ImproperlyConfiguredException>`: if app.template_engine
                is not configured.

        Returns:
            A TemplateResponse instance
        """
        if not app.template_engine:
            raise ImproperlyConfiguredException("Template engine is not configured")

        return TemplateResponse(
            background=self.background,
            context=self.create_template_context(request=request),
            encoding=self.encoding,
            headers=headers,
            status_code=status_code,
            template_engine=app.template_engine,
            template_name=self.name,
            media_type=media_type,
        )

    def create_template_context(self, request: Request) -> dict[str, Any]:
        """Create a context object for the template.

        Args:
            request: A :class:`Request <starlite.connection.request.Request>` instance.

        Returns:
            A dictionary holding the template context
        """
        csrf_token = request.scope.get("_csrf_token", "")
        return {
            **self.context,
            "request": request,
            "csrf_input": f'<input type="hidden" name="_csrf_token" value="{csrf_token}" />',
        }