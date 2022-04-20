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
    deschool, learning_curve = contracts

    tx = deschool.createCourse(
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
    assert deschool.getNextCourseId() == 1

    for n, learner in enumerate(learners):
        dai.transfer(
            learner,
            constants_mainnet.FEE,
            {"from": deployer}
        )
        dai.approve(deschool, constants_mainnet.FEE, {"from": learner})
        before_bal = dai.balanceOf(deschool)
        tx = deschool.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_mainnet.FEE == dai.balanceOf(deschool)

    assert deschool.getCurrentBatchTotal() == constants_mainnet.FEE * len(learners)
    assert dai.balanceOf(deschool) == constants_mainnet.FEE * len(learners)
    tx = deschool.batchDeposit({"from": kernelTreasury})
    brownie.chain.mine(constants_mainnet.CHECKPOINT_BLOCK_SPACING * 5)
    gen_lev_strat.harvest({"from": keeper})
    assert dai.balanceOf(deschool) == 0
    assert deschool.getCurrentBatchId() == 1
    assert ydai.balanceOf(deschool) > 0
    assert deschool.verify(learners[0], 0, {"from": steward}) == constants_mainnet.CHECKPOINTS
    print("----- MINT -----")
    for n, learner in enumerate(learners):
        tx = deschool.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        print("Learner " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("YDAI Balance: " + str(ydai.balanceOf(deschool)))
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
    deschool, learning_curve = contracts

    tx = deschool.createCourse(
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
    assert deschool.getNextCourseId() == 1

    for n, learner in enumerate(learners):
        dai.transfer(
            learner,
            constants_mainnet.FEE,
            {"from": deployer}
        )
        dai.approve(deschool, constants_mainnet.FEE, {"from": learner})
        before_bal = dai.balanceOf(deschool)
        tx = deschool.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_mainnet.FEE == dai.balanceOf(deschool)

    assert deschool.getCurrentBatchTotal() == constants_mainnet.FEE * len(learners)
    assert dai.balanceOf(deschool) == constants_mainnet.FEE * len(learners)
    tx = deschool.batchDeposit({"from": kernelTreasury})
    assert dai.balanceOf(deschool) == 0
    assert deschool.getCurrentBatchId() == 1
    assert ydai.balanceOf(deschool) > 0
    brownie.chain.mine(constants_mainnet.CHECKPOINT_BLOCK_SPACING * 2)
    gen_lev_strat.harvest({"from": keeper})
    brownie.chain.mine(constants_mainnet.CHECKPOINT_BLOCK_SPACING * 3)

    assert deschool.verify(learners[0], 0, {"from": steward}) == constants_mainnet.CHECKPOINTS
    print("----- REDEEM -----")
    for n, learner in enumerate(learners):
        tx = deschool.redeem(0, {"from": learner})
        print("Learner " + str(n) + " balance: " + str(learning_curve.balanceOf(learner)))
        print("Learner " + str(n) + " dai balance: " + str(dai.balanceOf(learner)))
        print("YDAI Balance: " + str(ydai.balanceOf(deschool)))
        print("redeemable DAI Balance of Creator: " +
              str(deschool.getYieldRewards(kernelTreasury, {"from": kernelTreasury}))
              )
        print("DAI collateral: " + str(dai.balanceOf(learning_curve)))
        print("Total Supply: " + str(learning_curve.totalSupply()))
        print('\n')
