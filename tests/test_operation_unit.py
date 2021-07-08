import brownie
import constants_unit


def test_full(deployer, learners, steward, contracts, token):
    kernel, learning_curve = contracts

    tx = kernel.createCourse(
        constants_unit.FEE,
        constants_unit.CHECKPOINTS,
        constants_unit.CHECKPOINT_BLOCK_SPACING,
        {"from": steward}
    )

    assert "CourseCreated" in tx.events
    assert tx.events["CourseCreated"]["courseId"] == 0
    assert tx.events["CourseCreated"]["checkpoints"] == constants_unit.CHECKPOINTS
    assert tx.events["CourseCreated"]["fee"] == constants_unit.FEE
    assert tx.events["CourseCreated"]["checkpointBlockSpacing"] == constants_unit.CHECKPOINT_BLOCK_SPACING

    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants_unit.FEE,
            {"from": deployer}
        )
        token.approve(kernel, constants_unit.FEE, {"from": learner})
        before_bal = token.balanceOf(kernel)
        tx = kernel.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_unit.FEE == token.balanceOf(kernel)

    assert kernel.getCurrentBatchTotal() == constants_unit.FEE * len(learners)
    assert token.balanceOf(kernel) == constants_unit.FEE * len(learners)

    brownie.chain.mine(500)

    assert kernel.verify(learners[0], 0, {"from": steward}) == constants_unit.CHECKPOINTS

    for n, learner in enumerate(learners):
        tx = kernel.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        print("User " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("DAI collateral: " + str(token.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
    n = 0
    
    for learner in reversed(learners):

        print(learning_curve.getBurnableForReserveAmount(constants_unit.FEE))
        print("User " + str(n) + " balance before: " + str(learning_curve.balanceOf(learner)))
        learning_curve.approve(
            learning_curve,
            learning_curve.getBurnableForReserveAmount(constants_unit.FEE),
            {"from": learner})
        tx = learning_curve.burn(constants_unit.FEE, {"from": learner})
        print("User " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("DAI balance: " + str(token.balanceOf(learner)))
        print("DAI collateral: " + str(token.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
        n += 1