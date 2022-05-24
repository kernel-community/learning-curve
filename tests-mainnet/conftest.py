import pytest
import time
import constants_mainnet
from ape import (
    project,
    accounts,
    Contract,
)


@pytest.fixture(scope="function", autouse=True)
def isolate_func(fn_isolation):
    # perform a chain rewind after completing each test, to ensure proper isolation
    # https://eth-ape.readthedocs.io/en/v1.10.3/tests-pytest-intro.html#isolation-fixtures
    pass


@pytest.fixture
def deployer():
    yield accounts.at("0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503", force=True)


@pytest.fixture(scope="function", autouse=True)
def contracts(deployer, token):
    learning_curve = project.LearningCurve.deploy(token.address, sender=deployer)
    token.transfer(deployer, 1*10**18, sender=deployer)
    token.approve(learning_curve, 1*10**18, sender=deployer)
    learning_curve.initialise(sender=deployer)
    yield project.DeSchool.deploy(
        token.address,
        learning_curve.address,
        constants_mainnet.REGISTRY,
        sender=deployer), \
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
        sender=steward
        )
    yield deschool, learning_curve


@pytest.fixture(scope="function")
def contracts_with_scholarships(contracts_with_courses, token, deployer, provider):
    deschool, learning_curve = contracts_with_courses
    token.transfer(provider, (constants_mainnet.SCHOLARSHIP_AMOUNT * 5), sender=deployer)
    assert token.balanceOf(provider) == (constants_mainnet.SCHOLARSHIP_AMOUNT * 5)
    token.approve(deschool, (constants_mainnet.SCHOLARSHIP_AMOUNT * 5), sender=provider)
    for n in range(5):
        tx = deschool.createScholarships(
            n,
            constants_mainnet.SCHOLARSHIP_AMOUNT,
            sender=provider
        )
    yield deschool, learning_curve


@pytest.fixture(scope="function")
def course_with_many_scholars(contracts_with_courses, token, deployer, provider, scholars):
    deschool, learning_curve = contracts_with_courses
    token.transfer(provider, (constants_mainnet.SCHOLARSHIP_AMOUNT * 10), sender=deployer)
    token.approve(deschool, (constants_mainnet.SCHOLARSHIP_AMOUNT * 10), sender=provider)
    tx = deschool.createScholarships(
            0,
            constants_mainnet.SCHOLARSHIP_AMOUNT * 10,
            sender=provider
        )
    for n, scholar in enumerate(scholars):
        deschool.registerScholar(
            0,
            sender=scholar
        )
    # slot 5 is where "scholars" is stored in the course struct
    assert deschool.courses(0)[4] == 11
    yield deschool, learning_curve

@pytest.fixture(scope="function")
def contracts_with_learners(contracts_with_courses, learners, token, deployer):
    deschool, learning_curve = contracts_with_courses
    for n, learner in enumerate(learners):
        token.transfer(learner, constants_mainnet.STAKE, sender=deployer)
        token.approve(deschool, constants_mainnet.STAKE, sender=learner)
        deschool.register(0, sender=learner)
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
def scholars(accounts):
    for i in range(11):
        accounts.add()
    yield accounts[9:20]
    

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

