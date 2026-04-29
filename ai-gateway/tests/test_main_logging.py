import logging

from fastapi import Request, Response

from app import main as main_module


def test_configure_application_logging_writes_file_and_is_idempotent(tmp_path, monkeypatch) -> None:
    """日志配置必须同时保证可落盘与热重载幂等。"""
    log_file_path = tmp_path / "app" / "logs" / "app.log"
    monkeypatch.setattr(main_module, "_APP_LOG_FILE_PATH", log_file_path)

    root_logger = logging.getLogger()
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    original_root_level = root_logger.level
    original_root_handlers = list(root_logger.handlers)
    original_uvicorn_handlers = list(uvicorn_access_logger.handlers)
    original_uvicorn_propagate = uvicorn_access_logger.propagate

    try:
        root_logger.handlers = [
            handler
            for handler in root_logger.handlers
            if handler.get_name() not in {main_module._ROOT_STREAM_HANDLER_NAME, main_module._ROOT_FILE_HANDLER_NAME}
        ]
        uvicorn_access_logger.handlers = [
            handler
            for handler in uvicorn_access_logger.handlers
            if handler.get_name() != main_module._UVICORN_FILE_HANDLER_NAME
        ]
        uvicorn_access_logger.propagate = False

        configured_path = main_module._configure_application_logging()
        logging.getLogger("app.tests.logging").info("file-target-check")

        for handler in root_logger.handlers + uvicorn_access_logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()

        assert configured_path == log_file_path
        assert log_file_path.exists() is True
        assert "file-target-check" in log_file_path.read_text(encoding="utf-8")
        assert (
            sum(1 for handler in root_logger.handlers if handler.get_name() == main_module._ROOT_FILE_HANDLER_NAME) == 1
        )
        assert (
            sum(
                1
                for handler in uvicorn_access_logger.handlers
                if handler.get_name() == main_module._UVICORN_FILE_HANDLER_NAME
            )
            == 1
        )

        main_module._configure_application_logging()

        assert (
            sum(1 for handler in root_logger.handlers if handler.get_name() == main_module._ROOT_FILE_HANDLER_NAME) == 1
        )
        assert (
            sum(
                1
                for handler in uvicorn_access_logger.handlers
                if handler.get_name() == main_module._UVICORN_FILE_HANDLER_NAME
            )
            == 1
        )
    finally:
        for handler in root_logger.handlers + uvicorn_access_logger.handlers:
            if handler.get_name() in {
                main_module._ROOT_STREAM_HANDLER_NAME,
                main_module._ROOT_FILE_HANDLER_NAME,
                main_module._UVICORN_FILE_HANDLER_NAME,
            }:
                handler.close()
        root_logger.handlers = original_root_handlers
        root_logger.setLevel(original_root_level)
        uvicorn_access_logger.handlers = original_uvicorn_handlers
        uvicorn_access_logger.propagate = original_uvicorn_propagate


def test_prometheus_endpoint_label_uses_route_template(monkeypatch) -> None:
    observed: dict[str, str] = {}

    class _CounterLabels:
        def inc(self) -> None:
            return None

    class _LatencyLabels:
        def observe(self, elapsed: float) -> None:
            del elapsed

    class _Counter:
        def labels(self, *, method: str, endpoint: str, status: int) -> _CounterLabels:
            del method, status
            observed["count_endpoint"] = endpoint
            return _CounterLabels()

    class _Latency:
        def labels(self, *, endpoint: str) -> _LatencyLabels:
            observed["latency_endpoint"] = endpoint
            return _LatencyLabels()

    class _Route:
        path = "/api/v1/items/{item_id}"

    monkeypatch.setattr(main_module, "REQUEST_COUNT", _Counter())
    monkeypatch.setattr(main_module, "REQUEST_LATENCY", _Latency())

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/items/123",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
        "client": ("testclient", 50000),
        "route": _Route(),
    }
    request = Request(scope, receive=lambda: None)

    async def call_next(_: Request) -> Response:
        return Response(status_code=200)

    import anyio

    anyio.run(main_module.prometheus_middleware, request, call_next)

    assert observed == {
        "count_endpoint": "/api/v1/items/{item_id}",
        "latency_endpoint": "/api/v1/items/{item_id}",
    }
