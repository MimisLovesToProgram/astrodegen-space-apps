


debug=False
debugLevel=0


storyMode=False

localhost=True
db_endpoint=""


def setup_logging():
    """Configure root logging once from engine_conf flags.

    debugLevel > 0 enables DEBUG output (per-record detail); otherwise
    INFO and above are shown. Call this before importing/running the
    pipeline modules so their loggers emit correctly.
    """
    import logging

    level = logging.DEBUG if debugLevel > 0 else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

