"""Tests for Additional Inputs validation and modified-state tracking.

Covers the two Task II behaviours:

* a ``Custom`` dropdown with an empty companion value blocks Save and shows a
  Critical message in the exact required format;
* ``is_modified`` tracks user edits so the close warning can fire.

The parameter list is derived from ``ADDITIONAL_INPUTS_SCHEMA``; these tests
assert that derivation instead of hardcoding field names.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QWidget

from osdagbridge.desktop.ui.dialogs.custom_messagebox import MessageBoxType


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture(scope="module")
def dialog(app):
    from osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs import (
        AdditionalInputs,
    )

    dlg = AdditionalInputs()
    yield dlg
    dlg.deleteLater()


class _MessageRecorder:
    """Stand-in for ``CustomMessageBox`` that records instead of blocking."""

    calls: list[dict] = []

    def __init__(self, **kwargs):
        _MessageRecorder.calls.append(kwargs)

    def exec(self):
        return "OK"


@pytest.fixture()
def recorded(monkeypatch):
    import osdagbridge.desktop.ui.dialogs.additional_input.additional_inputs as mod

    _MessageRecorder.calls = []
    monkeypatch.setattr(mod, "CustomMessageBox", _MessageRecorder)
    return _MessageRecorder.calls


def _set_mode(mode: QComboBox, text: str):
    mode.blockSignals(True)
    index = mode.findText(text)
    if index >= 0:
        mode.setCurrentIndex(index)
    else:
        mode.addItem(text)
        mode.setCurrentText(text)
    mode.blockSignals(False)


def _set_value(value: QWidget, text: str):
    value.blockSignals(True)
    if isinstance(value, QLineEdit):
        value.setText(text)
    elif isinstance(value, QComboBox):
        if text:
            if value.findText(text) < 0:
                value.addItem(text)
            value.setCurrentText(text)
        else:
            value.setCurrentIndex(-1)
            value.setEditText("")
    value.blockSignals(False)


def test_custom_pairs_are_derived_from_schema(dialog):
    pairs = dialog._custom_field_pairs

    assert pairs, "schema should expose at least one Custom mode/value pair"
    for pair in pairs:
        assert pair["label"], "every pair must carry its schema label"
        assert dialog.findChild(QComboBox, pair["mode"]) is not None, pair
        assert dialog.findChild(QWidget, pair["value"]) is not None, pair


def test_empty_custom_value_blocks_save(dialog, recorded):
    pair = dialog._custom_field_pairs[0]
    mode = dialog.findChild(QComboBox, pair["mode"])
    value = dialog.findChild(QWidget, pair["value"])

    try:
        _set_mode(mode, "Custom")
        _set_value(value, "")

        assert dialog._validate_custom_fields() is False

        assert len(recorded) == 1
        call = recorded[0]
        assert call["text"] == (
            f"Error: The custom value for '{pair['label']}' cannot be empty."
        )
        assert call["dialogType"] == MessageBoxType.Critical
    finally:
        _set_mode(mode, mode.itemText(0))


def test_non_empty_custom_value_allows_save(dialog, recorded):
    pair = dialog._custom_field_pairs[0]
    mode = dialog.findChild(QComboBox, pair["mode"])
    value = dialog.findChild(QWidget, pair["value"])

    try:
        _set_mode(mode, "Custom")
        _set_value(value, "12.5")

        assert dialog._validate_custom_fields() is True
        assert recorded == []
    finally:
        _set_mode(mode, mode.itemText(0))


def test_non_custom_mode_is_not_validated(dialog, recorded):
    pair = dialog._custom_field_pairs[0]
    mode = dialog.findChild(QComboBox, pair["mode"])
    value = dialog.findChild(QWidget, pair["value"])

    try:
        _set_mode(mode, mode.itemText(0))
        _set_value(value, "")

        assert dialog._validate_custom_fields() is True
        assert recorded == []
    finally:
        _set_mode(mode, mode.itemText(0))


def test_is_modified_tracks_edits(dialog):
    dialog.is_modified = False
    dialog._update_input_dict("test.some_key", "1")
    assert dialog.is_modified is True
