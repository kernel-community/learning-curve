import ape
import constants_unit


def test_full(deployer, learners, steward, contracts, token):
    deschool, learning_curve = contracts

    tx = deschool.createCourse(
        constants_unit.STAKE,
        constants_unit.DURATION,
        constants_unit.URL,
        constants_unit.CREATOR,
        sender=steward
    )

    assert "CourseCreated" in tx.events
    assert tx.events["CourseCreated"]["courseId"] == 0
    assert tx.events["CourseCreated"]["stake"] == constants_unit.STAKE
    assert tx.events["CourseCreated"]["duration"] == constants_unit.DURATION
    assert tx.events["CourseCreated"]["url"] == constants_unit.URL
    assert tx.events["CourseCreated"]["creator"] == constants_unit.CREATOR

    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants_unit.STAKE,
            sender=deployer
        )
        token.approve(deschool, constants_unit.STAKE, sender=learner)
        before_bal = token.balanceOf(deschool)
        tx = deschool.register(0, sender=learner)

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_unit.STAKE == token.balanceOf(deschool)

    assert deschool.getCurrentBatchTotal() == constants_unit.STAKE * len(learners)
    assert token.balanceOf(deschool) == constants_unit.STAKE * len(learners)

    ape.chain.mine(constants_unit.DURATION)

    assert deschool.verify(learners[0], 0, sender=steward)

    for n, learner in enumerate(learners):
        tx = deschool.mint(0, sender=learner)
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
            sender=learner
            )
        tx = learning_curve.burn(learning_curve.balanceOf(learner), sender=learner)
        print("Learner " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("DAI balance: " + str(token.balanceOf(learner)))
        print("DAI collateral: " + str(token.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
        n += 1