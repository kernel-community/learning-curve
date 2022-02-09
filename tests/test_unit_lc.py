import brownie
from brownie import LearningCurve
import constants_unit
from math import log as ln

from eth_account import Account
from eth_account._utils.structured_data.hashing import hash_domain
from eth_account.messages import encode_structured_data
from eth_utils import encode_hex

def test_flash_behaviour(token, deployer, hackerman, contracts, learners):
    _, learning_curve = contracts
    token.transfer(
        hackerman,
        constants_unit.MALICIOUS_AMOUNT,
        {"from": deployer}
    )
    token.approve(learning_curve, constants_unit.MALICIOUS_AMOUNT, {"from": hackerman})
    learning_curve.mint(constants_unit.MALICIOUS_AMOUNT, {"from": hackerman})
    token_bal_before = token.balanceOf(hackerman)
    learn_bal_before = learning_curve.balanceOf(hackerman)
    print("Token Balance after mint: " + str(token_bal_before))
    print("LEARN balance after mint: " + str(learn_bal_before))

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
        lc_before_bal = token.balanceOf(learning_curve)
        learner_before_dai_bal = token.balanceOf(learner)
        learner_before_lc_bal = learning_curve.balanceOf(learner)
        print("Learning curve balance before: " + str(learning_curve.totalSupply()))
        print("Learning curve dai balance before: " + str(lc_before_bal))
        print("Learner LEARN balance before: " + str(learner_before_lc_bal))
        print("Learner Dai balance before: " + str(learner_before_dai_bal))
        tx = learning_curve.burn(learning_curve.balanceOf(learner), {"from": learner})
        print("Learning curve balance: " + str(learning_curve.totalSupply()))
        print("Learning curve dai balance: " + str(lc_before_bal))
        print("Learner LEARN balance: " + str(learner_before_lc_bal))
        print("Learner Dai balance: " + str(learner_before_dai_bal))
        print("Learner Token Diff: " + str(tx.events["LearnBurned"]["daiReturned"] - constants_unit.MINT_AMOUNT))
        print("Learner LEARN Diff: " + str(tx.events["LearnBurned"]["amountBurned"] - learner_before_lc_bal))
    tx = learning_curve.burn(learning_curve.balanceOf(hackerman), {"from": hackerman})
    print("Token Balance after burn: " + str(token.balanceOf(hackerman)))
    print("LEARN balance after burn: " + str(learning_curve.balanceOf(hackerman)))
    print("Hackerman Token Diff: " + str(tx.events["LearnBurned"]["daiReturned"] - constants_unit.MALICIOUS_AMOUNT))
    print("Hackerman LEARN Diff: " + str(learn_bal_before - tx.events["LearnBurned"]["amountBurned"]))
    print("Final learning curve balance: " + str(learning_curve.totalSupply()))
    print("Final learning curve dai balance: " + str(token.balanceOf(learning_curve)))


def test_init(token, deployer):
    learning_curve = LearningCurve.deploy(token.address, {"from": deployer})
    token.approve(learning_curve, 1e18, {"from": deployer})
    learning_curve.initialise({"from": deployer})
    assert token.balanceOf(learning_curve) == 1e18
    assert learning_curve.totalSupply() == 10001e18
    assert learning_curve.reserveBalance() == 1e18


def test_init_malicious(token, deployer, hackerman):
    learning_curve = LearningCurve.deploy(token.address, {"from": deployer})
    with brownie.reverts():
        learning_curve.initialise({"from": hackerman})
    with brownie.reverts():
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

def test_mint_permit(token, deployer, contracts):
    _, learning_curve = contracts
    signer = Account.create()
    holder = signer.address
    token.transfer(holder, constants_unit.MINT_AMOUNT, {"from": deployer})
    assert token.balanceOf(holder) == constants_unit.MINT_AMOUNT
    permit = build_permit(holder, str(learning_curve), token, 3600)
    signed = signer.sign_message(permit)
    print(token.balanceOf(learning_curve.address))
    before_bal = token.balanceOf(learning_curve)
    learner_before_dai_bal = token.balanceOf(holder)
    learner_before_lc_bal = learning_curve.balanceOf(holder)
    numerator = float((learning_curve.reserveBalance() / 1e18 + constants_unit.MINT_AMOUNT / 1e18))
    predicted_mint = float(constants_unit.K * ln(numerator / (learning_curve.reserveBalance() / 1e18))) * 1e18
    lc_supply_before = learning_curve.totalSupply()
    assert abs(predicted_mint - learning_curve.getMintableForReserveAmount(constants_unit.MINT_AMOUNT)) < \
               constants_unit.ACCURACY
    tx = learning_curve.permitAndMint(constants_unit.MINT_AMOUNT, 0, 0, signed.v, signed.r, signed.s, {"from": holder})
    print(token.balanceOf(learning_curve.address))

    assert abs(learner_before_lc_bal + predicted_mint - learning_curve.balanceOf(holder)) < constants_unit.ACCURACY
    assert learner_before_dai_bal - constants_unit.MINT_AMOUNT == token.balanceOf(holder)
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
        tx = learning_curve.burn(learning_curve.balanceOf(learner), {"from": learner})
        assert abs(learner_before_lc_bal - tx.events["LearnBurned"]["amountBurned"] + learning_curve.balanceOf(learner)) < constants_unit.ACCURACY
        assert abs(
            learner_before_dai_bal + constants_unit.MINT_AMOUNT - token.balanceOf(learner)) <= constants_unit.ACCURACY
        assert before_bal - constants_unit.MINT_AMOUNT - token.balanceOf(learning_curve) <= constants_unit.ACCURACY
        assert before_bal - constants_unit.MINT_AMOUNT - learning_curve.reserveBalance() <= constants_unit.ACCURACY
        assert abs(learning_curve.totalSupply() + (learner_before_lc_bal - lc_supply_before)) < constants_unit.ACCURACY

def build_permit(holder, spender, token, expiry):
    data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Permit": [
                {"name": "holder", "type": "address"},
                {"name": "spender", "type": "address"},
                {"name": "nonce", "type": "uint256"},
                {"name": "expiry", "type": "uint256"},
                {"name": "allowed", "type": "bool"},
            ],
        },
        "domain": {
            "name": token.name(),
            "version": token.version(),
            "chainId": 1,
            "verifyingContract": str(token),
        },
        "primaryType": "Permit",
        "message": {
            "holder": holder,
            "spender": spender,
            "nonce": token.nonces(holder),
            "expiry": 0,
            "allowed": True,
        },
    }
    assert encode_hex(hash_domain(data)) == token.DOMAIN_SEPARATOR()
    return encode_structured_data(data)