import pytest
import time
import constants
from brownie import (
    KernelFactory,
    LearningCurve,
    BasicERC20,
    accounts,
    web3,
    Wei,
    chain,
    Contract,
)


@pytest.fixture(scope="function", autouse=True)
def isolate_func(fn_isolation):
    # perform a chain rewind after completing each test, to ensure proper isolation
    # https://eth-brownie.readthedocs.io/en/v1.10.3/tests-pytest-intro.html#isolation-fixtures
    pass


@pytest.fixture(scope="function", autouse=True)
def contracts(deployer, token, kernelTreasury):
    learning_curve = LearningCurve.deploy(token.address, {"from": deployer})
    token.approve(learning_curve, 1e18, {"from": deployer})
    learning_curve.initialise({"from": deployer})
    yield KernelFactory.deploy(
        token.address,
        learning_curve.address,
        constants.VAULT,
        kernelTreasury.address,
        {"from": deployer}), \
        learning_curve


@pytest.fixture(scope="function", autouse=True)
def token(deployer):
    token = BasicERC20.deploy("Test", "TT", {"from": deployer})
    token.mint(1000000e18)
    yield token


@pytest.fixture
def deployer(accounts):
    yield accounts[0]


@pytest.fixture
def steward(accounts):
    yield accounts[1]


@pytest.fixture
def learners(accounts):
    yield accounts[2:10]


@pytest.fixture
def kernelTreasury(accounts):
    yield accounts.at("0x297a3C4B8bB87E671d31C475C5DbE434E24dFC1F", force=True)

