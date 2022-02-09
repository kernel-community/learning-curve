import pytest
import time
import constants_mainnet
from brownie import (
    KernelFactory,
    LearningCurve,
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


@pytest.fixture
def deployer():
    yield accounts.at("0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503", force=True)


@pytest.fixture(scope="function", autouse=True)
def contracts(deployer, dai):
    learning_curve = LearningCurve.deploy(dai.address, {"from": deployer})
    dai.transfer(deployer, 1e18, {"from": deployer})
    dai.approve(learning_curve, 1e18, {"from": deployer})
    learning_curve.initialise({"from": deployer})
    yield KernelFactory.deploy(
        dai.address,
        learning_curve.address,
        constants_mainnet.REGISTRY,
        {"from": deployer}), \
        learning_curve


@pytest.fixture(scope="function")
def contracts_with_courses(contracts, steward):
    kernel, learning_curve = contracts
    for n in range(5):
        tx = kernel.createCourse(
        constants_mainnet.FEE,
        constants_mainnet.CHECKPOINTS,
        constants_mainnet.CHECKPOINT_BLOCK_SPACING,
        constants_mainnet.URL,
        steward,
        {"from": steward}
        )
    yield kernel, learning_curve


@pytest.fixture(scope="function")
def contracts_with_learners(contracts_with_courses, learners, token, deployer):
    kernel, learning_curve = contracts_with_courses
    for n, learner in enumerate(learners):
        token.transfer(learner, constants_mainnet.FEE, {"from": deployer})
        token.approve(kernel, constants_mainnet.FEE, {"from": learner})
        kernel.register(0, {"from": learner})
    yield kernel, learning_curve


@pytest.fixture
def steward(accounts):
    yield accounts[1]


@pytest.fixture
def learners(accounts):
    yield accounts[2:6]


@pytest.fixture
def hackerman(accounts):
    yield accounts[9]


@pytest.fixture
def dai():
    yield Contract.from_explorer(constants_mainnet.DAI)


@pytest.fixture
def token():
    yield Contract.from_explorer(constants_mainnet.DAI)


@pytest.fixture
def ydai():
    yield Contract.from_explorer(constants_mainnet.VAULT)


@pytest.fixture
def gen_lev_strat():
    yield Contract.from_explorer("0x6341c289b2E0795A04223DF04B53A77970958723")


@pytest.fixture
def keeper():
    yield accounts.at("0x736d7e3c5a6cb2ce3b764300140abf476f6cfccf", force=True)


@pytest.fixture
def kernelTreasury(accounts):
    yield accounts.at("0x297a3C4B8bB87E671d31C475C5DbE434E24dFC1F", force=True)

