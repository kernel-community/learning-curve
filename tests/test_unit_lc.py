import brownie
from brownie import Contract, chain, web3, LearningCurve, KernelFactory
import pytest
import constants
from numpy import log as ln


def test_init(token, deployer):
    learning_curve = LearningCurve.deploy(token.address, {"from": deployer})
    token.approve(learning_curve, 1e18, {"from": deployer})
    learning_curve.initialise({"from": deployer})
    assert token.balanceOf(learning_curve) == 1e18
    assert learning_curve.totalSupply() == 10001e18
    assert learning_curve.reserveBalance() == 1e18


def test_init_malicious(token, deployer, hackerman):
    learning_curve = LearningCurve.deploy(token.address, {"from": deployer})
    with brownie.reverts('ERC20: transfer amount exceeds balance'):
        learning_curve.initialise({"from": hackerman})
    with brownie.reverts('ERC20: transfer amount exceeds allowance'):
        learning_curve.initialise({"from": deployer})
    token.approve(learning_curve, 1e18, {"from": deployer})
    learning_curve.initialise({"from": deployer})
    with brownie.reverts("initialised"):
        learning_curve.initialise({"from": hackerman})


def test_mint(learners, token, deployer, contracts):
    _, learning_curve = contracts
    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants.MINT_AMOUNT,
            {"from": deployer}
        )
        token.approve(learning_curve, constants.MINT_AMOUNT, {"from": learner})
        before_bal = token.balanceOf(learning_curve)
        learner_before_dai_bal = token.balanceOf(learner)
        learner_before_lc_bal = learning_curve.balanceOf(learner)
        numerator = float((learning_curve.reserveBalance() / 1e18 + constants.MINT_AMOUNT / 1e18))
        predicted_mint = float(constants.K * ln(numerator / (learning_curve.reserveBalance()/1e18))) * 1e18
        lc_supply_before = learning_curve.totalSupply()
        assert abs(predicted_mint - learning_curve.getMintableForReserveAmount(constants.MINT_AMOUNT)) < constants.ACCURACY

        learning_curve.mint(constants.MINT_AMOUNT, {"from": learner})

        assert abs(learner_before_lc_bal + predicted_mint - learning_curve.balanceOf(learner)) < constants.ACCURACY
        assert learner_before_dai_bal - constants.MINT_AMOUNT == token.balanceOf(learner)
        assert before_bal + constants.MINT_AMOUNT == token.balanceOf(learning_curve) == learning_curve.reserveBalance()
        assert abs(learning_curve.totalSupply() - (predicted_mint + lc_supply_before)) < constants.ACCURACY


def test_burn(learners, token, deployer, contracts):
    _, learning_curve = contracts
    for learner in learners:
        token.transfer(
            learner,
            constants.MINT_AMOUNT,
            {"from": deployer}
        )
        token.approve(learning_curve, constants.MINT_AMOUNT, {"from": learner})
        learning_curve.mint(constants.MINT_AMOUNT, {"from": learner})

    n = 0
    for learner in reversed(learners):
        before_bal = token.balanceOf(learning_curve)
        learner_before_dai_bal = token.balanceOf(learner)
        learner_before_lc_bal = learning_curve.balanceOf(learner)
        numerator = float((learning_curve.reserveBalance() / 1e18))
        predicted_burn = float(constants.K * ln(numerator /
                                    (learning_curve.reserveBalance()/1e18 - constants.MINT_AMOUNT/1e18))) * 1e18
        lc_supply_before = learning_curve.totalSupply()
        assert abs(predicted_burn - learning_curve.getBurnableForReserveAmount(constants.MINT_AMOUNT)) < constants.ACCURACY
        learning_curve.burn(constants.MINT_AMOUNT, {"from": learner})
        assert abs(learner_before_lc_bal - predicted_burn + learning_curve.balanceOf(learner)) < constants.ACCURACY
        assert learner_before_dai_bal + constants.MINT_AMOUNT == token.balanceOf(learner)
        assert before_bal - constants.MINT_AMOUNT == token.balanceOf(learning_curve) == learning_curve.reserveBalance()
        assert abs(learning_curve.totalSupply() + (predicted_burn - lc_supply_before)) < constants.ACCURACY