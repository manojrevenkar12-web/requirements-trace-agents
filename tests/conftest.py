import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def cfg():
    return yaml.safe_load((ROOT / "config/pipeline.yaml").read_text())


@pytest.fixture(scope="session")
def world():
    from rta.world.spec import load
    return load(ROOT / "config/world.yaml", quick=True)


@pytest.fixture(scope="session")
def baseline(world, cfg):
    from rta.product import reqif as rif
    from rta.product.trace import Baseline
    from rta.world.docs import reqif
    return Baseline(rif.read(reqif(world.system, world.baseline, world.subsystems)), cfg)
