import logging
def configure_logging(level=logging.WARNING):
    logging.basicConfig(level=level, format="%(message)s")
def get_logger(name, **kw):
    return logging.getLogger(name)
def bind_logger(logger, **kw):
    return logger
def log_page_switch(*a, **kw): pass
def log_task_result(*a, **kw): pass
