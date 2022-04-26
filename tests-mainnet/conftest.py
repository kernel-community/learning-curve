import pytest
import time
import constants_mainnet
from brownie import (
    DeSchool,
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
def contracts(deployer, token):
    learning_curve = LearningCurve.deploy(token.address, {"from": deployer})
    token.transfer(deployer, 1e18, {"from": deployer})
    token.approve(learning_curve, 1e18, {"from": deployer})
    learning_curve.initialise({"from": deployer})
    yield DeSchool.deploy(
        token.address,
        learning_curve.address,
        constants_mainnet.REGISTRY,
        {"from": deployer}), \
        learning_curve


@pytest.fixture(scope="function")
def contracts_with_courses(contracts, steward):
    deschool, learning_curve = contracts
    for n in range(5):
        tx = deschool.createCourse(
        constants_mainnet.STAKE,
        constants_mainnet.DURATION,
        constants_mainnet.URL,
        steward,
        {"from": steward}
        )
    yield deschool, learning_curve


@pytest.fixture(scope="function")
def contracts_with_scholarships(contracts_with_courses, token, deployer, provider):
    deschool, learning_curve = contracts_with_courses
    token.transfer(provider, (constants_mainnet.SCHOLARSHIP_AMOUNT * 5), {"from": deployer})
    assert token.balanceOf(provider) == (constants_mainnet.SCHOLARSHIP_AMOUNT * 5)
    token.approve(deschool, (constants_mainnet.SCHOLARSHIP_AMOUNT * 5), {"from": provider})
    for n in range(5):
        tx = deschool.createScholarships(
            n,
            constants_mainnet.SCHOLARSHIP_AMOUNT,
            {"from": provider}
        )
    yield deschool, learning_curve

@pytest.fixture(scope="function")
def contracts_with_learners(contracts_with_courses, learners, token, deployer):
    deschool, learning_curve = contracts_with_courses
    for n, learner in enumerate(learners):
        token.transfer(learner, constants_mainnet.STAKE, {"from": deployer})
        token.approve(deschool, constants_mainnet.STAKE, {"from": learner})
        deschool.register(0, {"from": learner})
    yield deschool, learning_curve


@pytest.fixture
def steward(accounts):
    yield accounts[1]


@pytest.fixture
def learners(accounts):
    yield accounts[2:6]


@pytest.fixture
def provider(accounts):
    yield accounts[7]


@pytest.fixture
def hackerman(accounts):
    yield accounts[8]
  

@pytest.fixture
def token():
    yield Contract.from_explorer(constants_mainnet.DAI)


@pytest.fixture
def ytoken():
    yield Contract.from_explorer(constants_mainnet.VAULT)


@pytest.fixture
def gen_lev_strat():
    yield Contract.from_explorer(constants_mainnet.GEN_LEV)


@pytest.fixture
def keeper():
    yield accounts.at(constants_mainnet.KEEPER, force=True)


@pytest.fixture
def kernelTreasury(accounts):
    yield accounts.at("0x297a3C4B8bB87E671d31C475C5DbE434E24dFC1F", force=True)

