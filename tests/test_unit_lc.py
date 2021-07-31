import brownie
from brownie import LearningCurve
import constants_unit
from math import log as ln


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
            constants_unit.MINT_AMOUNT,
            {"from": deployer}
        )
        token.approve(learning_curve, constants_unit.MINT_AMOUNT, {"from": learner})
        before_bal = token.balanceOf(learning_curve)
        learner_before_dai_bal = token.balanceOf(learner)
        learner_before_lc_bal = learning_curve.balanceOf(learner)
        numerator = float((learning_curve.reserveBalance() / 1e18 + constants_unit.MINT_AMOUNT / 1e18))
        predicted_mint = float(constants_unit.K * ln(numerator / (learning_curve.reserveBalance() / 1e18))) * 1e18
        lc_supply_before = learning_curve.totalSupply()
        assert abs(predicted_mint - learning_curve.getMintableForReserveAmount(constants_unit.MINT_AMOUNT)) < \
               constants_unit.ACCURACY
        learning_curve.mint(constants_unit.MINT_AMOUNT, {"from": learner})
        assert abs(learner_before_lc_bal + predicted_mint - learning_curve.balanceOf(learner)) < constants_unit.ACCURACY
        assert learner_before_dai_bal - constants_unit.MINT_AMOUNT == token.balanceOf(learner)
        assert before_bal + constants_unit.MINT_AMOUNT == token.balanceOf(
            learning_curve) == learning_curve.reserveBalance()
        assert abs(learning_curve.totalSupply() - (predicted_mint + lc_supply_before)) < constants_unit.ACCURACY


def test_burn(learners, token, deployer, contracts):
    _, learning_curve = contracts
    for learner in learners:
        token.transfer(
            learner,
            constants_unit.MINT_AMOUNT,
            {"from": deployer}
        )
        token.approve(learning_curve, constants_unit.MINT_AMOUNT, {"from": learner})
        learning_curve.mint(constants_unit.MINT_AMOUNT, {"from": learner})

    n = 0
    for learner in reversed(learners):
        before_bal = token.balanceOf(learning_curve)
        learner_before_dai_bal = token.balanceOf(learner)
        learner_before_lc_bal = learning_curve.balanceOf(learner)
        numerator = float((learning_curve.reserveBalance() / 1e18))
        predicted_burn = constants_unit.MINT_AMOUNT
        lc_supply_before = learning_curve.totalSupply()
        print(abs(predicted_burn - learning_curve.getPredictedBurn(learner_before_lc_bal)))
        print(learning_curve.totalSupply())
        print(token.balanceOf(learning_curve))
        tx = learning_curve.burn(learning_curve.balanceOf(learner), {"from": learner})
        print(tx.events["LearnBurned"])
        assert abs(learner_before_lc_bal - tx.events["LearnBurned"]["amountBurned"] + learning_curve.balanceOf(learner)) < constants_unit.ACCURACY
        assert abs(
            learner_before_dai_bal + constants_unit.MINT_AMOUNT - token.balanceOf(learner)) <= constants_unit.ACCURACY
        assert before_bal - constants_unit.MINT_AMOUNT - token.balanceOf(learning_curve) <= constants_unit.ACCURACY
        assert before_bal - constants_unit.MINT_AMOUNT - learning_curve.reserveBalance() <= constants_unit.ACCURACY
        assert abs(learning_curve.totalSupply() + (learner_before_lc_bal - lc_supply_before)) < constants_unit.ACCURACY
        print(token.balanceOf(learner))
        print(learner_before_lc_bal, learning_curve.balanceOf(learner))
    print(learning_curve.totalSupply())
    print(token.balanceOf(learning_curve))
