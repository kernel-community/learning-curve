import brownie
from brownie import Contract, chain, web3, LearningCurve, KernelFactory
import pytest
import constants


def test_batch_success(
        contracts_with_learners,
        keeper,
        token,
        ydai,
        learners
):
    kernel, learning_curve = contracts_with_learners
    kf_balance_before = token.balanceOf(kernel)
    batch_id_before = kernel.getCurrentBatchId()
    tx = kernel.batchDeposit({"from": keeper})
    assert "BatchDeposited" in tx.events
    assert batch_id_before == \
           0 == \
           tx.events["BatchDeposited"]["batchId"] == \
           kernel.getCurrentBatchId() - 1
    assert token.balanceOf(kernel) == 0
    assert kf_balance_before == tx.events["BatchDeposited"]["batchAmount"] == constants.FEE * len(learners)
    assert ydai.balanceOf(kernel) > 0
    assert ydai.balanceOf(kernel) == tx.events["BatchDeposited"]["batchYieldAmount"]


def test_batch_malicious(contracts_with_courses, keeper):
    kernel, learning_curve = contracts_with_courses
    with brownie.reverts("batchDeposit: no funds to deposit"):
        kernel.batchDeposit({"from": keeper})


def test_register_diff_batches(contracts_with_courses, keeper, token, learners, deployer, ydai):
    kernel, learning_curve = contracts_with_courses
    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants.FEE,
            {"from": deployer}
        )
        token.approve(kernel, constants.FEE, {"from": learner})
        before_bal = token.balanceOf(kernel)
        tx = kernel.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants.FEE == token.balanceOf(kernel)
        kf_balance_before = token.balanceOf(kernel)
        batch_id_before = kernel.getCurrentBatchId()
        ydai_bal_before = ydai.balanceOf(kernel)
        tx = kernel.batchDeposit({"from": keeper})
        assert "BatchDeposited" in tx.events
        assert batch_id_before == \
               n == \
               tx.events["BatchDeposited"]["batchId"] == \
               kernel.getCurrentBatchId() - 1
        assert token.balanceOf(kernel) == 0
        assert kf_balance_before == tx.events["BatchDeposited"]["batchAmount"] == constants.FEE
        assert ydai.balanceOf(kernel) > ydai_bal_before
        assert ydai.balanceOf(kernel) - ydai_bal_before == tx.events["BatchDeposited"]["batchYieldAmount"]


def test_mint(contracts_with_learners, learners, token, keeper, gen_lev_strat, ydai):
    kernel, learning_curve = contracts_with_learners
    brownie.chain.mine(constants.CHECKPOINTS * constants.CHECKPOINT_BLOCK_SPACING)
    tx = kernel.batchDeposit({"from": keeper})
    brownie.chain.mine(constants.CHECKPOINT_BLOCK_SPACING * 5)
    brownie.chain.sleep(1000)
    gen_lev_strat.harvest({"from": keeper})

    for n, learner in enumerate(learners):
        dai_balance = kernel.getUserCourseEligibleFunds(learner, 0)
        mintable_balance = learning_curve.getMintableForReserveAmount(dai_balance)
        lc_dai_balance = token.balanceOf(learning_curve)
        kf_dai_balance = token.balanceOf(kernel)
        learner_lc_balance = learning_curve.balanceOf(learner)
        tx = kernel.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        assert abs(tx.events["LearnMintedFromCourse"]["learnMinted"] - mintable_balance) < constants.ACCURACY_Y
        assert abs(tx.events["LearnMintedFromCourse"]["stableConverted"] - dai_balance) < constants.ACCURACY_Y
        assert kernel.verify(learner, 0) == constants.CHECKPOINTS
        assert kernel.getUserCourseEligibleFunds(learner, 0) == 0
        assert abs(token.balanceOf(learning_curve) - lc_dai_balance - dai_balance) < constants.ACCURACY_Y
        assert abs(token.balanceOf(kernel) - kf_dai_balance) < constants.ACCURACY
        assert abs(learning_curve.balanceOf(learner) - learner_lc_balance - mintable_balance) < constants.ACCURACY_Y
    assert token.balanceOf(kernel) == 0
    assert ydai.balanceOf(kernel) < 1000

def test_mint_diff_checkpoints(contracts_with_learners, learners, token, keeper, gen_lev_strat, ydai):
    kernel, learning_curve = contracts_with_learners
    tx = kernel.batchDeposit({"from": keeper})
    for m in range(constants.CHECKPOINTS):
        brownie.chain.mine(constants.CHECKPOINT_BLOCK_SPACING)
        gen_lev_strat.harvest({"from": keeper})
        for n, learner in enumerate(learners):
            dai_balance = kernel.getUserCourseEligibleFunds(learner, 0)
            mintable_balance = learning_curve.getMintableForReserveAmount(dai_balance)
            lc_dai_balance = token.balanceOf(learning_curve)
            kf_ydai_balance = ydai.balanceOf(kernel)
            learner_lc_balance = learning_curve.balanceOf(learner)
            tx = kernel.mint(0, {"from": learner})
            assert "LearnMintedFromCourse" in tx.events
            assert abs(tx.events["LearnMintedFromCourse"]["learnMinted"] - mintable_balance) < constants.ACCURACY_Y
            assert abs(tx.events["LearnMintedFromCourse"]["stableConverted"] - dai_balance) < constants.ACCURACY_Y
            assert kernel.verify(learner, 0) == m + 1
            assert (constants.FEE - (constants.FEE / constants.CHECKPOINTS) * m) > \
                   kernel.getUserCourseFundsRemaining(learner, 0) > \
                   (constants.FEE - (constants.FEE / constants.CHECKPOINTS) * (m + 2))
            assert kernel.getUserCourseEligibleFunds(learner, 0) == 0
            assert abs(token.balanceOf(learning_curve) - (lc_dai_balance + dai_balance)) < constants.ACCURACY_Y
            assert abs(ydai.balanceOf(kernel) - (kf_ydai_balance - (dai_balance*1e18)/ydai.pricePerShare())) < \
                   constants.ACCURACY_Y
            assert abs(learning_curve.balanceOf(learner) - (learner_lc_balance + mintable_balance)) < constants.ACCURACY_Y
    assert token.balanceOf(kernel) == 0
    assert ydai.balanceOf(kernel) < 1000


def test_redeem(contracts_with_learners, learners, token, kernelTreasury, keeper, gen_lev_strat, ydai):
    kernel, learning_curve = contracts_with_learners
    brownie.chain.mine(constants.CHECKPOINTS * constants.CHECKPOINT_BLOCK_SPACING)
    tx = kernel.batchDeposit({"from": keeper})
    brownie.chain.mine(constants.CHECKPOINT_BLOCK_SPACING * 5)
    brownie.chain.sleep(1000)
    gen_lev_strat.harvest({"from": keeper})
    for n, learner in enumerate(learners):
        dai_balance = kernel.getUserCourseEligibleFunds(learner, 0)
        kt_dai_balance = token.balanceOf(kernelTreasury)
        kf_ydai_balance = ydai.balanceOf(kernel)
        tx = kernel.redeem(0, {"from": learner})
        assert "FeeRedeemed" in tx.events
        assert tx.events["FeeRedeemed"]["amount"] == constants.FEE
        assert kernel.verify(learner, 0) == constants.CHECKPOINTS
        assert kernel.getUserCourseEligibleFunds(learner, 0) == 0
        assert kt_dai_balance <= token.balanceOf(kernelTreasury)
        assert abs(ydai.balanceOf(kernel) - (kf_ydai_balance - (dai_balance*1e18)/ydai.pricePerShare())) < constants.ACCURACY_Y
        assert token.balanceOf(learner) == constants.FEE
        assert token.balanceOf(learning_curve) == 1e18
        assert ydai.balanceOf(learning_curve) == 0
    assert token.balanceOf(kernel) == 0
    assert ydai.balanceOf(kernel) < 1000


def test_redeem_diff_checkpoints(
        contracts_with_learners,
        learners,
        token,
        kernelTreasury,
        keeper,
        gen_lev_strat,
        ydai
):
    kernel, learning_curve = contracts_with_learners
    tx = kernel.batchDeposit({"from": keeper})
    for m in range(constants.CHECKPOINTS):
        brownie.chain.mine(constants.CHECKPOINT_BLOCK_SPACING)
        brownie.chain.sleep(100)
        gen_lev_strat.harvest({"from": keeper})
        for n, learner in enumerate(learners):
            dai_balance = kernel.getUserCourseEligibleFunds(learner, 0)
            kt_dai_balance = token.balanceOf(kernelTreasury)
            kf_ydai_balance = ydai.balanceOf(kernel)
            tx = kernel.redeem(0, {"from": learner})
            assert "FeeRedeemed" in tx.events
            assert abs(tx.events["FeeRedeemed"]["amount"] - dai_balance) < constants.ACCURACY_Y
            assert kernel.verify(learner, 0) == m + 1
            assert (constants.FEE - (constants.FEE / constants.CHECKPOINTS) * m) > \
                   kernel.getUserCourseFundsRemaining(learner, 0) > \
                   (constants.FEE - (constants.FEE / constants.CHECKPOINTS) * (m + 2))
            assert kernel.getUserCourseEligibleFunds(learner, 0) == 0
            assert kt_dai_balance == token.balanceOf(kernelTreasury)
            assert abs(ydai.balanceOf(kernel) - (kf_ydai_balance - (dai_balance * 1e18) / ydai.pricePerShare())) < \
                   constants.ACCURACY_Y
            assert token.balanceOf(learning_curve) == 1e18
            assert ydai.balanceOf(learning_curve) == 0
    assert token.balanceOf(kernel) == 0
    assert ydai.balanceOf(kernel) < 1000


def test_verify(contracts_with_learners, learners, keeper):
    kernel, learning_curve = contracts_with_learners
    learner = learners[0]
    tx = kernel.batchDeposit({"from": keeper})
    for n in range(constants.CHECKPOINTS + 1):
        assert kernel.verify(learner, 0, {"from": learner}) == n
        brownie.chain.mine(constants.CHECKPOINT_BLOCK_SPACING)
