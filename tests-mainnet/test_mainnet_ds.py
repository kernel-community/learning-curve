import brownie
import constants_mainnet
from eth_account import Account
from eth_account._utils.structured_data.hashing import hash_domain
from eth_account.messages import encode_structured_data
from eth_utils import encode_hex


def test_register_permit(contracts_with_courses, learners, token, deployer):
    deschool, learning_curve = contracts_with_courses
    signer = Account.create()
    holder = signer.address
    token.transfer(holder, constants_mainnet.FEE, {"from": deployer})
    assert token.balanceOf(holder) == constants_mainnet.FEE
    permit = build_permit(holder, str(deschool), token, 3600)
    signed = signer.sign_message(permit)
    print(token.balanceOf(deschool.address))
    tx = deschool.permitAndRegister(0, 0, 0, signed.v, signed.r, signed.s, {"from": holder})
    print(token.balanceOf(deschool.address))
    assert "LearnerRegistered" in tx.events
    assert tx.events["LearnerRegistered"]["courseId"] == 0


def test_redeem(contracts_with_learners, learners, token, steward, keeper, gen_lev_strat, ydai):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_mainnet.COURSE_RUNNING)
    tx = deschool.batchDeposit({"from": keeper})
    brownie.chain.mine(constants_mainnet.DURATION)
    brownie.chain.sleep(1000)
    gen_lev_strat.harvest({"from": keeper})
    for n, learner in enumerate(learners):
        us_ydai_balance = ydai.balanceOf(deschool)
        tx = deschool.redeem(0, {"from": learner})
        assert "FeeRedeemed" in tx.events
        assert tx.events["FeeRedeemed"]["amount"] == constants_mainnet.FEE
        assert deschool.verify(learner, 0)
        assert token.balanceOf(steward) == 0
        assert deschool.getYieldRewards(steward, {"from": steward}) > 0
        assert ydai.balanceOf(deschool) < us_ydai_balance
        assert token.balanceOf(learner) == constants_mainnet.FEE
        assert token.balanceOf(learning_curve) == 1e18
        assert ydai.balanceOf(learning_curve) == 0
    kt_redemption = deschool.getYieldRewards(steward, {"from": steward})
    deschool.withdrawYieldRewards({"from": steward})
    assert deschool.getYieldRewards(steward, {"from": steward}) == 0
    assert token.balanceOf(steward) == kt_redemption
    assert token.balanceOf(deschool) == 0
    assert ydai.balanceOf(deschool) < 1000


def test_batch_success(
        contracts_with_learners,
        keeper,
        token,
        ydai,
        learners
):
    deschool, learning_curve = contracts_with_learners
    us_balance_before = token.balanceOf(deschool)
    batch_id_before = deschool.getCurrentBatchId()
    tx = deschool.batchDeposit({"from": keeper})
    assert "BatchDeposited" in tx.events
    assert batch_id_before == \
           0 == \
           tx.events["BatchDeposited"]["batchId"] == \
           deschool.getCurrentBatchId() - 1
    assert token.balanceOf(deschool) == 0
    assert us_balance_before == tx.events["BatchDeposited"]["batchAmount"] == constants_mainnet.FEE * len(learners)
    assert ydai.balanceOf(deschool) > 0
    assert ydai.balanceOf(deschool) == tx.events["BatchDeposited"]["batchYieldAmount"]


def test_batch_malicious(contracts_with_courses, keeper):
    deschool, learning_curve = contracts_with_courses
    with brownie.reverts("batchDeposit: no funds to deposit"):
        deschool.batchDeposit({"from": keeper})


def test_register_diff_batches(contracts_with_courses, keeper, token, learners, deployer, ydai):
    deschool, learning_curve = contracts_with_courses
    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants_mainnet.FEE,
            {"from": deployer}
        )
        token.approve(deschool, constants_mainnet.FEE, {"from": learner})
        before_bal = token.balanceOf(deschool)
        tx = deschool.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_mainnet.FEE == token.balanceOf(deschool)
        us_balance_before = token.balanceOf(deschool)
        batch_id_before = deschool.getCurrentBatchId()
        ydai_bal_before = ydai.balanceOf(deschool)
        tx = deschool.batchDeposit({"from": keeper})
        assert "BatchDeposited" in tx.events
        assert batch_id_before == \
               n == \
               tx.events["BatchDeposited"]["batchId"] == \
               deschool.getCurrentBatchId() - 1
        assert token.balanceOf(deschool) == 0
        assert us_balance_before == tx.events["BatchDeposited"]["batchAmount"] == constants_mainnet.FEE
        assert ydai.balanceOf(deschool) > ydai_bal_before
        assert ydai.balanceOf(deschool) - ydai_bal_before == tx.events["BatchDeposited"]["batchYieldAmount"]


def test_mint(contracts_with_learners, learners, token, keeper, gen_lev_strat, ydai, steward):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_mainnet.COURSE_RUNNING)
    tx = deschool.batchDeposit({"from": keeper})
    brownie.chain.mine(constants_mainnet.DURATION)
    brownie.chain.sleep(1000)
    gen_lev_strat.harvest({"from": keeper})

    for n, learner in enumerate(learners):
        mintable_balance = learning_curve.getMintableForReserveAmount(constants_mainnet.FEE)
        lc_dai_balance = token.balanceOf(learning_curve)
        us_dai_balance = token.balanceOf(deschool)
        learner_lc_balance = learning_curve.balanceOf(learner)
        tx = deschool.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        assert abs(tx.events["LearnMintedFromCourse"]["learnMinted"] - mintable_balance) < constants_mainnet.ACCURACY_Y
        assert abs(tx.events["LearnMintedFromCourse"]["stableConverted"] - constants_mainnet.FEE) < constants_mainnet.ACCURACY_Y
        assert deschool.verify(learner, 0)
        assert abs(token.balanceOf(learning_curve) - lc_dai_balance - constants_mainnet.FEE) < constants_mainnet.ACCURACY_Y
        assert abs(token.balanceOf(deschool) - deschool.getYieldRewards(steward)) < constants_mainnet.ACCURACY
        assert abs(learning_curve.balanceOf(learner) - learner_lc_balance - mintable_balance) < constants_mainnet.ACCURACY_Y
    assert token.balanceOf(deschool) == deschool.getYieldRewards(steward)
    assert ydai.balanceOf(deschool) < 1000


def test_verify(contracts_with_learners, learners, keeper):
    deschool, learning_curve = contracts_with_learners
    learner = learners[0]
    tx = deschool.batchDeposit({"from": keeper})
    assert not(deschool.verify(learner, 0, {"from": learner}))
    brownie.chain.mine(constants_mainnet.DURATION)
    assert deschool.verify(learner, 0, {"from": learner})


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