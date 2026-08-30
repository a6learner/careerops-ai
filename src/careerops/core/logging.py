import logging


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=log_level,
        format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    )
