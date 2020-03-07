import logging

LOG_LEVELS = {
    '0': logging.ERROR,
    '1': logging.WARNING,
    '2': logging.INFO,
    '3': logging.DEBUG,
}


def pytest_configure(config):
    # Note: enable DEBUG logging to debug the parsing. But this becomes very
    # verbose very quickly
    logging.basicConfig(
        level=LOG_LEVELS.get(config.option.verbose, logging.INFO))

