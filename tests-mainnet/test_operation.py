import brownie
from brownie import Contract, chain, web3
import pytest
import constants


def test_full_mint(
        deployer,
        learners,
        steward,
        contracts,
        kernelTreasury,
        keeper,
        dai,
        ydai,
        dai_whale,
        gen_lev_strat
):
    kernel, learning_curve = contracts

    tx = kernel.createCourse(
        constants.FEE,
        constants.CHECKPOINTS,
        constants.CHECKPOINT_BLOCK_SPACING,
        {"from": steward}
    )

    assert "CourseCreated" in tx.events
    assert tx.events["CourseCreated"]["courseId"] == 0
    assert tx.events["CourseCreated"]["checkpoints"] == constants.CHECKPOINTS
    assert tx.events["CourseCreated"]["fee"] == constants.FEE
    assert tx.events["CourseCreated"]["checkpointBlockSpacing"] == constants.CHECKPOINT_BLOCK_SPACING
    assert kernel.getNextCourseId() == 1

    for n, learner in enumerate(learners):
        dai.transfer(
            learner,
            constants.FEE,
            {"from": dai_whale}
        )
        dai.approve(kernel, constants.FEE, {"from": learner})
        before_bal = dai.balanceOf(kernel)
        tx = kernel.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants.FEE == dai.balanceOf(kernel)

    assert kernel.getCurrentBatchTotal() == constants.FEE * len(learners)
    assert dai.balanceOf(kernel) == constants.FEE * len(learners)
    tx = kernel.batchDeposit({"from": kernelTreasury})
    assert dai.balanceOf(kernel) == 0
    assert kernel.getCurrentBatchId() == 1
    assert ydai.balanceOf(kernel) > 0
    brownie.chain.mine(100)
    gen_lev_strat.harvest({"from": keeper})

    assert kernel.verify(learners[7], 0, {"from": steward}) == constants.CHECKPOINTS
    print("----- MINT -----")
    for n, learner in enumerate(learners):
        tx = kernel.mint(0, {"from": learner})
        assert "LearnMinted" in tx.events
        print("User " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("YDAI Balance: " + str(ydai.balanceOf(kernel)))
        print("DAI collateral: " + str(dai.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')

    n = 0
    print("----- BURN -----")
    for learner in reversed(learners):
        print(learning_curve.getBurnableForReserveAmount(constants.FEE))
        print("User " + str(n) + " balance before: " + str(learning_curve.balanceOf(learner)))
        learning_curve.approve(
            learning_curve,
            learning_curve.getBurnableForReserveAmount(constants.FEE),
            {"from": learner})
        tx = learning_curve.burn(constants.FEE, {"from": learner})
        print("User " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("DAI balance: " + str(dai.balanceOf(learner)))
        print("DAI collateral: " + str(dai.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
        n += 1


def test_full_redeem(
        deployer,
        learners,
        steward,
        contracts,
        kernelTreasury,
        keeper,
        dai,
        ydai,
        dai_whale,
        gen_lev_strat
):
    kernel, learning_curve = contracts

    tx = kernel.createCourse(
        constants.FEE,
        constants.CHECKPOINTS,
        constants.CHECKPOINT_BLOCK_SPACING,
        {"from": steward}
    )

    assert "CourseCreated" in tx.events
    assert tx.events["CourseCreated"]["courseId"] == 0
    assert tx.events["CourseCreated"]["checkpoints"] == constants.CHECKPOINTS
    assert tx.events["CourseCreated"]["fee"] == constants.FEE
    assert tx.events["CourseCreated"]["checkpointBlockSpacing"] == constants.CHECKPOINT_BLOCK_SPACING
    assert kernel.getNextCourseId() == 1

    for n, learner in enumerate(learners):
        dai.transfer(
            learner,
            constants.FEE,
            {"from": dai_whale}
        )
        dai.approve(kernel, constants.FEE, {"from": learner})
        before_bal = dai.balanceOf(kernel)
        tx = kernel.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants.FEE == dai.balanceOf(kernel)

    assert kernel.getCurrentBatchTotal() == constants.FEE * len(learners)
    assert dai.balanceOf(kernel) == constants.FEE * len(learners)
    tx = kernel.batchDeposit({"from": kernelTreasury})
    assert dai.balanceOf(kernel) == 0
    assert kernel.getCurrentBatchId() == 1
    assert ydai.balanceOf(kernel) > 0
    brownie.chain.mine(100)
    gen_lev_strat.harvest({"from": keeper})

    assert kernel.verify(learners[7], 0, {"from": steward}) == constants.CHECKPOINTS
    print("----- REDEEM -----")
    for n, learner in enumerate(learners):
        tx = kernel.redeem(0, {"from": learner})
        print("User " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("User " + str(n) + " dai balance: " + str(dai.balanceOf(learner)))
        print("YDAI Balance: " + str(ydai.balanceOf(kernel)))
        print("DAI Balance of KernelTreasury: " + str(dai.balanceOf(kernelTreasury)))
        print("DAI collateral: " + str(dai.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
