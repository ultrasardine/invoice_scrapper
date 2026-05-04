"""Tests for table detector module."""

from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

from invoice_scrapper.table_detector import TableDetector


def _make_test_image(w: int = 200, h: int = 200) -> Image.Image:
    return Image.fromarray(np.zeros((h, w, 3), dtype=np.uint8))


def test_choose_best_both_empty():
    assert TableDetector._choose_best([], []) == []


def test_choose_best_one_empty():
    tables = [[["a", "b"], ["c", "d"]]]
    assert TableDetector._choose_best(tables, []) == tables
    assert TableDetector._choose_best([], tables) == tables


def test_choose_best_prefers_more_content():
    a = [[["a", ""], ["", ""]]]
    b = [[["a", "b"], ["c", "d"]]]
    result = TableDetector._choose_best(a, b)
    assert result == b


@patch.object(TableDetector, "_detect_borderless")
@patch.object(TableDetector, "_detect_with_opencv")
@patch.object(TableDetector, "_detect_with_img2table")
def test_img2table_result_used(mock_img2table, mock_opencv, mock_borderless):
    mock_img2table.return_value = [[["val1", "val2"]]]
    mock_opencv.return_value = []
    mock_borderless.return_value = []

    detector = TableDetector.__new__(TableDetector)
    detector.lang = "por"
    result = detector.detect_tables(_make_test_image())

    assert len(result) == 1
    assert result[0][0] == ["val1", "val2"]


@patch.object(TableDetector, "_detect_borderless")
@patch.object(TableDetector, "_detect_with_opencv")
@patch.object(TableDetector, "_detect_with_img2table")
def test_opencv_fallback(mock_img2table, mock_opencv, mock_borderless):
    mock_img2table.return_value = []
    mock_opencv.return_value = [[["x", "y"]]]
    mock_borderless.return_value = []

    detector = TableDetector.__new__(TableDetector)
    detector.lang = "por"
    result = detector.detect_tables(_make_test_image())

    assert len(result) == 1


@patch.object(TableDetector, "_detect_borderless")
@patch.object(TableDetector, "_detect_with_opencv")
@patch.object(TableDetector, "_detect_with_img2table")
def test_borderless_fallback(mock_img2table, mock_opencv, mock_borderless):
    mock_img2table.return_value = []
    mock_opencv.return_value = []
    mock_borderless.return_value = [[["a", "b"], ["c", "d"]]]

    detector = TableDetector.__new__(TableDetector)
    detector.lang = "por"
    result = detector.detect_tables(_make_test_image())

    assert len(result) == 1


@patch.object(TableDetector, "_detect_borderless")
@patch.object(TableDetector, "_detect_with_opencv")
@patch.object(TableDetector, "_detect_with_img2table")
def test_no_tables_found(mock_img2table, mock_opencv, mock_borderless):
    mock_img2table.return_value = []
    mock_opencv.return_value = []
    mock_borderless.return_value = []

    detector = TableDetector.__new__(TableDetector)
    detector.lang = "por"
    result = detector.detect_tables(_make_test_image())

    assert result == []


def test_find_line_positions():
    detector = TableDetector.__new__(TableDetector)
    proj = np.zeros(100)
    proj[10:15] = 100
    proj[50:55] = 100
    proj[90:95] = 100
    positions = detector._find_line_positions(proj, min_gap=15)
    assert len(positions) >= 3
