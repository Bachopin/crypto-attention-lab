"""
[DEPRECATED] Legacy storage module.
This module is deprecated and should not be used.
Please use src.data.db_storage instead.
"""

import logging

logger = logging.getLogger(__name__)

def _raise_deprecated():
    raise RuntimeError(
        "src.data.storage is deprecated and CSV storage is disabled. "
        "Please use src.data.db_storage for all data access."
    )

def load_price_data(*args, **kwargs):
    _raise_deprecated()

def load_attention_data(*args, **kwargs):
    _raise_deprecated()

def load_news_data(*args, **kwargs):
    _raise_deprecated()

def ensure_price_data_exists(*args, **kwargs):
    _raise_deprecated()

def ensure_attention_data_exists(*args, **kwargs):
    _raise_deprecated()
