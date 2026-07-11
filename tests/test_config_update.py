import shutil
from pathlib import Path

import pytest
import yaml

from basis_trade_agent.config import update_config_file

EXAMPLE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.example.yaml"


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    destination = tmp_path / "config.yaml"
    shutil.copy(EXAMPLE_CONFIG_PATH, destination)
    return destination


def test_update_existing_field_preserves_other_lines_and_comments(config_path: Path) -> None:
    originalLines = config_path.read_text().splitlines()
    targetIndex = next(index for index, line in enumerate(originalLines) if line.lstrip().startswith("minNetYieldAprPercent:"))
    originalCommentIndex = originalLines[targetIndex].find("#")
    originalComment = originalLines[targetIndex][originalCommentIndex:]
    updatedConfig = update_config_file(config_path, {"minNetYieldAprPercent": 7.5})
    assert updatedConfig.minNetYieldAprPercent == 7.5
    newLines = config_path.read_text().splitlines()
    assert len(newLines) == len(originalLines)
    for index, (originalLine, newLine) in enumerate(zip(originalLines, newLines)):
        if index == targetIndex:
            assert newLine.startswith("minNetYieldAprPercent: 7.5")
            assert newLine.endswith(originalComment)
        else:
            assert newLine == originalLine


def test_update_unknown_field_raises_and_leaves_file_unchanged(config_path: Path) -> None:
    originalText = config_path.read_text()
    with pytest.raises(ValueError, match="Unknown config field"):
        update_config_file(config_path, {"notARealField": 1})
    assert config_path.read_text() == originalText


def test_update_value_failing_validation_raises_and_leaves_file_unchanged(config_path: Path) -> None:
    originalText = config_path.read_text()
    with pytest.raises(ValueError):
        update_config_file(config_path, {"riskTolerance": "hybrid"})
    assert config_path.read_text() == originalText


def test_update_computed_fields_reflect_new_value(config_path: Path) -> None:
    updatedConfig = update_config_file(config_path, {"minNetYieldAprPercent": 10.0, "hysteresisBandAprPercent": 6.0})
    assert updatedConfig.enterNetYieldAprPercent == pytest.approx(13.0)
    assert updatedConfig.exitNetYieldAprPercent == pytest.approx(7.0)
    rewrittenConfig = yaml.safe_load(config_path.read_text())
    assert rewrittenConfig["minNetYieldAprPercent"] == 10.0
    assert rewrittenConfig["hysteresisBandAprPercent"] == 6.0
