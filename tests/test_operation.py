import brownie
from brownie import Contract, chain, web3
import pytest
import constants


def test_full(deployer, learners, steward, contracts, token):
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

    assert kernel.getCurrentBatchTotal() == constants.FEE * len(learners)
    assert token.balanceOf(kernel) == constants.FEE * len(learners)

    brownie.chain.mine(500)

    assert kernel.verify(learners[7], 0, {"from": steward}) == constants.CHECKPOINTS

    for n, learner in enumerate(learners):
        tx = kernel.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        print("User " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("DAI collateral: " + str(token.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
    n = 0
    
    for learner in reversed(learners):

        print(learning_curve.getBurnableForReserveAmount(constants.FEE))
        print("User " + str(n) + " balance before: " + str(learning_curve.balanceOf(learner)))
        learning_curve.approve(
            learning_curve,
            learning_curve.getBurnableForReserveAmount(constants.FEE),
            {"from": learner})
        tx = learning_curve.burn(constants.FEE, {"from": learner})
        print("User " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("DAI balance: " + str(token.balanceOf(learner)))
        print("DAI collateral: " + str(token.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
        n += 1