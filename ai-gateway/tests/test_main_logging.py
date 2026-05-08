import logging

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
