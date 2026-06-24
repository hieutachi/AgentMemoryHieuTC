"""Tests for the scanner module."""

import tempfile
from pathlib import Path

from agent_memory_hieutc.scanner import classify_file, compute_importance


def test_classify_training_script():
    assert classify_file("train.py") == "training_script"
    assert classify_file("run_training.py") == "training_script"


def test_classify_config():
    assert classify_file("config.yaml") == "config_file"
    assert classify_file("config_ppo.json") == "config_file"


def test_classify_paper():
    assert classify_file("paper.tex") == "paper_latex"
    assert classify_file("main.tex") == "paper_latex"


def test_classify_figure_script():
    assert classify_file("plot_results.py") == "figure_generation_script"
    assert classify_file("generate_figures.py") == "figure_generation_script"


def test_classify_result():
    assert classify_file("results_final.json") == "result_file"
    assert classify_file("metrics.csv") == "result_file"


def test_classify_source():
    assert classify_file("utils.py") == "source_code"
    assert classify_file("models/network.py") == "source_code"


def test_importance_training():
    score = compute_importance("training_script", "train.py")
    assert score >= 8.0


def test_importance_unknown():
    score = compute_importance("unknown", "random_file.xyz")
    assert score == 1.0
