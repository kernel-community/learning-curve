import brownie
import constants_mainnet


def test_full_mint(
        deployer,
        learners,
        steward,
        contracts,
        kernelTreasury,
        keeper,
        dai,
        ydai,
        gen_lev_strat
):
    unschool, learning_curve = contracts

    tx = unschool.createCourse(
        constants_mainnet.FEE,
        constants_mainnet.CHECKPOINTS,
        constants_mainnet.CHECKPOINT_BLOCK_SPACING,
        constants_mainnet.URL,
        constants_mainnet.CREATOR,
        {"from": steward}
    )

    assert "CourseCreated" in tx.events
    assert tx.events["CourseCreated"]["courseId"] == 0
    assert tx.events["CourseCreated"]["checkpoints"] == constants_mainnet.CHECKPOINTS
    assert tx.events["CourseCreated"]["fee"] == constants_mainnet.FEE
    assert tx.events["CourseCreated"]["checkpointBlockSpacing"] == constants_mainnet.CHECKPOINT_BLOCK_SPACING
    assert tx.events["CourseCreated"]["url"] == constants_mainnet.URL
    assert tx.events["CourseCreated"]["creator"] == constants_mainnet.CREATOR
    assert unschool.getNextCourseId() == 1

    for n, learner in enumerate(learners):
        dai.transfer(
            learner,
            constants_mainnet.FEE,
            {"from": deployer}
        )
        dai.approve(unschool, constants_mainnet.FEE, {"from": learner})
        before_bal = dai.balanceOf(unschool)
        tx = unschool.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_mainnet.FEE == dai.balanceOf(unschool)

    assert unschool.getCurrentBatchTotal() == constants_mainnet.FEE * len(learners)
    assert dai.balanceOf(unschool) == constants_mainnet.FEE * len(learners)
    tx = unschool.batchDeposit({"from": kernelTreasury})
    brownie.chain.mine(constants_mainnet.CHECKPOINT_BLOCK_SPACING * 5)
    gen_lev_strat.harvest({"from": keeper})
    assert dai.balanceOf(unschool) == 0
    assert unschool.getCurrentBatchId() == 1
    assert ydai.balanceOf(unschool) > 0
    assert unschool.verify(learners[0], 0, {"from": steward}) == constants_mainnet.CHECKPOINTS
    print("----- MINT -----")
    for n, learner in enumerate(learners):
        tx = unschool.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        print("Learner " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("YDAI Balance: " + str(ydai.balanceOf(unschool)))
        print("DAI collateral: " + str(dai.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')

    n = 0
    print("----- BURN -----")
    for learner in reversed(learners):
        lc_balance_before = learning_curve.balanceOf(learner)
        print("Learner " + str(n) + " balance before: " + str(lc_balance_before))
        learning_curve.approve(
            learning_curve,
            lc_balance_before,
            {"from": learner})
        tx = learning_curve.burn(lc_balance_before, {"from": learner})
        assert learning_curve.balanceOf(learner) < lc_balance_before
        assert dai.balanceOf(learner) - constants_mainnet.FEE < constants_mainnet.ACCURACY
        print("Learner " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
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
        gen_lev_strat
):
    unschool, learning_curve = contracts

    tx = unschool.createCourse(
        constants_mainnet.FEE,
        constants_mainnet.CHECKPOINTS,
        constants_mainnet.CHECKPOINT_BLOCK_SPACING,
        constants_mainnet.URL,
        constants_mainnet.CREATOR,
        {"from": steward}
    )

    assert "CourseCreated" in tx.events
    assert tx.events["CourseCreated"]["courseId"] == 0
    assert tx.events["CourseCreated"]["checkpoints"] == constants_mainnet.CHECKPOINTS
    assert tx.events["CourseCreated"]["fee"] == constants_mainnet.FEE
    assert tx.events["CourseCreated"]["checkpointBlockSpacing"] == constants_mainnet.CHECKPOINT_BLOCK_SPACING
    assert unschool.getNextCourseId() == 1

    for n, learner in enumerate(learners):
        dai.transfer(
            learner,
            constants_mainnet.FEE,
            {"from": deployer}
        )
        dai.approve(unschool, constants_mainnet.FEE, {"from": learner})
        before_bal = dai.balanceOf(unschool)
        tx = unschool.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_mainnet.FEE == dai.balanceOf(unschool)

    assert unschool.getCurrentBatchTotal() == constants_mainnet.FEE * len(learners)
    assert dai.balanceOf(unschool) == constants_mainnet.FEE * len(learners)
    tx = unschool.batchDeposit({"from": kernelTreasury})
    assert dai.balanceOf(unschool) == 0
    assert unschool.getCurrentBatchId() == 1
    assert ydai.balanceOf(unschool) > 0
    brownie.chain.mine(constants_mainnet.CHECKPOINT_BLOCK_SPACING * 2)
    gen_lev_strat.harvest({"from": keeper})
    brownie.chain.mine(constants_mainnet.CHECKPOINT_BLOCK_SPACING * 3)

    assert unschool.verify(learners[0], 0, {"from": steward}) == constants_mainnet.CHECKPOINTS
    print("----- REDEEM -----")
    for n, learner in enumerate(learners):
        tx = unschool.redeem(0, {"from": learner})
        print("Learner " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("Learner " + str(n) + " dai balance: " + str(dai.balanceOf(learner)))
        print("YDAI Balance: " + str(ydai.balanceOf(unschool)))
        print("redeemable DAI Balance of Creator: " +
              str(unschool.getYieldRewards(kernelTreasury, {"from": kernelTreasury}))
              )
        print("DAI collateral: " + str(dai.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
