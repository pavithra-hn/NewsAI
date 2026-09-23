"""Settings that have to be in place before the pipeline is imported.

The pipeline reads its settings from the environment once, when app.config is
first imported. On Streamlit Community Cloud they are typed into the app's
Secrets box instead, so they are copied into the environment here, first.

This module must not import the pipeline, or the copy would come too late.
"""

import json
from collections.abc import Mapping, MutableMapping

import streamlit as st
from streamlit.errors import StreamlitAPIException


def read_streamlit_secrets() -> dict:
    # st.secrets raises when there is no secrets file, which is the normal
    # local case, and when the file is malformed. Either way there are none.
    try:
        return dict(st.secrets)
    except (StreamlitAPIException, FileNotFoundError):
        return {}


def export_secrets(secrets: Mapping, environ: MutableMapping) -> None:
    """Copy root-level secrets into the environment.

    A variable already set in the real environment wins. A table, such as
    MODELS written as TOML, becomes JSON, which is the form the pipeline reads.
    """
    for name, value in secrets.items():
        if name in environ:
            continue
        environ[name] = json.dumps(dict(value)) if isinstance(value, Mapping) else str(value)
