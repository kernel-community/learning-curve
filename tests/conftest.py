import pytest
import constants_unit
from ape import (
    accounts,
    project
)


@pytest.fixture(scope="function", autouse=True)
def isolate_func(_function_isolation):
    # perform a chain rewind after completing each test, to ensure proper isolation
    # https://eth-ape.readthedocs.io/en/v1.10.3/tests-pytest-intro.html#isolation-fixtures
    pass


@pytest.fixture(scope="function", autouse=True)
def token(deployer):
    token = project.Dai.deploy(1, sender=deployer)
    token.mint(deployer, 1_000_000_000_000_000_000_000_000_000_000, sender=deployer)
    yield token


@pytest.fixture(scope="function")
def contracts(deployer, token):
    learning_curve = project.LearningCurve.deploy(token.address, sender=deployer)
    token.approve(learning_curve, 10**18, sender=deployer)
    learning_curve.initialise(sender=deployer)
    yield project.DeSchool.deploy(
        token.address,
        learning_curve.address,
        constants_unit.REGISTRY,
        sender=deployer), \
        learning_curve


@pytest.fixture(scope="function")
def contracts_with_courses(contracts, steward):
    deschool, learning_curve = contracts
    for n in range(5):
        tx = deschool.createCourse(
        constants_unit.STAKE,
        constants_unit.DURATION,
        constants_unit.URL,
        constants_unit.CREATOR,
        sender=steward
        )
    yield deschool, learning_curve


@pytest.fixture(scope="function")
def contracts_with_learners(contracts_with_courses, learners, token, deployer):
    deschool, learning_curve = contracts_with_courses
    for n, learner in enumerate(learners):
        token.transfer(learner, constants_unit.STAKE, sender=deployer)
        token.approve(deschool, constants_unit.STAKE, sender=learner)
        deschool.register(0, sender=learner)
    yield deschool, learning_curve


@pytest.fixture
def deployer(accounts):
    yield accounts[0]


@pytest.fixture
def steward(accounts):
    yield accounts[1]


@pytest.fixture
def hackerman(accounts):
    yield accounts[9]


@pytest.fixture
def learners(accounts):
    yield accounts[2:8]


@pytest.fixture
def kernelTreasury(accounts):
    yield accounts.at("0x297a3C4B8bB87E671d31C475C5DbE434E24dFC1F", force=True)

