import brownie
import constants_unit


def test_full(deployer, learners, steward, contracts, token):
    deschool, learning_curve = contracts

    tx = deschool.createCourse(
        constants_unit.FEE,
        constants_unit.DURATION,
        constants_unit.URL,
        constants_unit.CREATOR,
        {"from": steward}
    )

    assert "CourseCreated" in tx.events
    assert tx.events["CourseCreated"]["courseId"] == 0
    assert tx.events["CourseCreated"]["duration"] == constants_unit.DURATION
    assert tx.events["CourseCreated"]["fee"] == constants_unit.FEE
    assert tx.events["CourseCreated"]["url"] == constants_unit.URL
    assert tx.events["CourseCreated"]["creator"] == constants_unit.CREATOR

    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants_unit.FEE,
            {"from": deployer}
        )
        token.approve(deschool, constants_unit.FEE, {"from": learner})
        before_bal = token.balanceOf(deschool)
        tx = deschool.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_unit.FEE == token.balanceOf(deschool)

    assert deschool.getCurrentBatchTotal() == constants_unit.FEE * len(learners)
    assert token.balanceOf(deschool) == constants_unit.FEE * len(learners)

    brownie.chain.mine(constants_unit.DURATION)

    assert deschool.verify(learners[0], 0, {"from": steward})

    for n, learner in enumerate(learners):
        tx = deschool.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        print("Learner " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("DAI collateral: " + str(token.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
    n = 0
    
    for learner in reversed(learners):

        print("Learner " + str(n) + " balance before: " + str(learning_curve.balanceOf(learner)))
        learning_curve.approve(
            learning_curve,
            learning_curve.balanceOf(learner),
            {"from": learner})
        tx = learning_curve.burn(learning_curve.balanceOf(learner), {"from": learner})
        print("Learner " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("DAI balance: " + str(token.balanceOf(learner)))
        print("DAI collateral: " + str(token.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
        n += 1