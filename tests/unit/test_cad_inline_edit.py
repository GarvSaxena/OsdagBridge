"""Tests for inline 2D-CAD label editing (Task I).

The CAD widgets emit ``parameter_edited(key, value)`` with the canonical
``common.py`` key and the value in the unit the main input dictionary expects:

* span / carriageway width / girder spacing -> metres
* deck thickness -> millimetres
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLineEdit

from osdagbridge.core.utils.common import (
    KEY_CARRIAGEWAY_WIDTH,
    KEY_SPAN,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_GIRDER_SPACING,
)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _commit(widget, text, key):
    editor = QLineEdit(widget)
    editor.setText(text)
    widget._label_editor = editor

    captured = []
    widget.parameter_edited.connect(lambda k, v: captured.append((k, v)))
    widget._commit_label_edit(editor, key)
    return captured


def test_cross_section_emits_deck_thickness_in_millimetres(app):
    from osdagbridge.desktop.ui.docks.cad_cross_section import CrossSectionCADWidget

    widget = CrossSectionCADWidget()
    assert _commit(widget, "275", KEY_TS_DECK_THICKNESS) == [
        (KEY_TS_DECK_THICKNESS, 275.0)
    ]


def test_cross_section_emits_girder_spacing_in_metres(app):
    from osdagbridge.desktop.ui.docks.cad_cross_section import CrossSectionCADWidget

    widget = CrossSectionCADWidget()
    assert _commit(widget, "2.75", KEY_TS_GIRDER_SPACING) == [
        (KEY_TS_GIRDER_SPACING, 2.75)
    ]


def test_cross_section_emits_carriageway_width_in_metres(app):
    from osdagbridge.desktop.ui.docks.cad_cross_section import CrossSectionCADWidget

    widget = CrossSectionCADWidget()
    assert _commit(widget, "10.5", KEY_CARRIAGEWAY_WIDTH) == [
        (KEY_CARRIAGEWAY_WIDTH, 10.5)
    ]


def test_top_view_emits_span_in_metres(app):
    from osdagbridge.desktop.ui.docks.cad_top_view import TopViewCADWidget

    widget = TopViewCADWidget()
    assert _commit(widget, "35", KEY_SPAN) == [(KEY_SPAN, 35.0)]


@pytest.mark.parametrize("text", ["", "abc", "0", "-3", "nan", "inf"])
def test_invalid_edits_are_ignored(app, text):
    from osdagbridge.desktop.ui.docks.cad_cross_section import CrossSectionCADWidget

    widget = CrossSectionCADWidget()
    assert _commit(widget, text, KEY_TS_DECK_THICKNESS) == []


def test_editable_label_registration_carries_key_and_unit_value(app):
    from osdagbridge.desktop.ui.docks.cad_cross_section import CrossSectionCADWidget

    widget = CrossSectionCADWidget()
    widget.editable_labels = []

    pixmap = QPixmap(200, 100)
    painter = QPainter(pixmap)
    try:
        widget.draw_text_with_background(
            painter, 10, 50, "Deck Thickness = 250 mm",
            QColor(255, 255, 255), QColor(0, 0, 0), 9, False,
            editable=(KEY_TS_DECK_THICKNESS, 250.0, 0),
        )
    finally:
        painter.end()

    assert len(widget.editable_labels) == 1
    _rect, key, value, decimals = widget.editable_labels[0]
    assert key == KEY_TS_DECK_THICKNESS
    assert value == 250.0
    assert decimals == 0


def test_top_view_editable_label_registration(app):
    from osdagbridge.desktop.ui.docks.cad_top_view import TopViewCADWidget

    widget = TopViewCADWidget()
    widget.editable_labels = []

    pixmap = QPixmap(200, 100)
    painter = QPainter(pixmap)
    try:
        widget.draw_text_with_background(
            painter, 10, 50, "Span Length = 35.00 m",
            QColor(255, 255, 255), QColor(0, 0, 0), 9, False,
            editable=(KEY_SPAN, 35.0, 2),
        )
    finally:
        painter.end()

    assert len(widget.editable_labels) == 1
    _rect, key, value, decimals = widget.editable_labels[0]
    assert key == KEY_SPAN
    assert value == 35.0
    assert decimals == 2
