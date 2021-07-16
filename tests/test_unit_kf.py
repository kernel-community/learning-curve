import brownie
from brownie import LearningCurve, KernelFactory
import constants_unit


def test_create_courses(contracts, steward):
    kernel, learning_curve = contracts
    for n in range(5):
        tx = kernel.createCourse(
            constants_unit.FEE,
            constants_unit.CHECKPOINTS,
            constants_unit.CHECKPOINT_BLOCK_SPACING,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": steward}
        )

        assert "CourseCreated" in tx.events
        assert tx.events["CourseCreated"]["courseId"] == n
        assert tx.events["CourseCreated"]["checkpoints"] == constants_unit.CHECKPOINTS
        assert tx.events["CourseCreated"]["fee"] == constants_unit.FEE
        assert tx.events["CourseCreated"]["checkpointBlockSpacing"] == constants_unit.CHECKPOINT_BLOCK_SPACING
        assert tx.events["CourseCreated"]["url"] == constants_unit.URL
        assert tx.events["CourseCreated"]["creator"] == constants_unit.CREATOR


def test_create_malicious_courses(contracts, hackerman):
    kernel, learning_curve = contracts
    with brownie.reverts("createCourse: fee must be greater than 0"):
        kernel.createCourse(
            0,
            constants_unit.CHECKPOINTS,
            constants_unit.CHECKPOINT_BLOCK_SPACING,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": hackerman}
        )
    with brownie.reverts("createCourse: checkpoint must be greater than 0"):
        kernel.createCourse(
            constants_unit.FEE,
            0,
            constants_unit.CHECKPOINT_BLOCK_SPACING,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": hackerman}
        )
    with brownie.reverts("createCourse: checkpointBlockSpacing must be greater than 0"):
        kernel.createCourse(
            constants_unit.FEE,
            constants_unit.CHECKPOINTS,
            0,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": hackerman}
        )


def test_register(contracts_with_courses, learners, token, deployer):
    kernel, learning_curve = contracts_with_courses

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


def test_register_malicious(contracts_with_courses, token, deployer, hackerman):
    kernel, learning_curve = contracts_with_courses
    with brownie.reverts('ERC20: transfer amount exceeds balance'):
        kernel.register(0, {"from": hackerman})

    token.transfer(hackerman, constants_unit.FEE, {"from": deployer})
    token.approve(kernel, constants_unit.FEE, {"from": hackerman})
    with brownie.reverts("register: courseId does not exist"):
        kernel.register(999, {"from": hackerman})

    with brownie.reverts("register: courseId does not exist"):
        kernel.register(kernel.getNextCourseId(), {"from": hackerman})

    kernel.register(0, {"from": hackerman})
    token.transfer(hackerman, constants_unit.FEE, {"from": deployer})
    token.approve(kernel, constants_unit.FEE, {"from": hackerman})
    with brownie.reverts("register: already registered"):
        kernel.register(0, {"from": hackerman})


def test_mint(contracts_with_learners, learners, token, deployer):
    kernel, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
    for n, learner in enumerate(learners):
        dai_balance = kernel.getLearnerCourseEligibleFunds(learner, 0)
        mintable_balance = learning_curve.getMintableForReserveAmount(dai_balance)
        lc_dai_balance = token.balanceOf(learning_curve)
        kf_dai_balance = token.balanceOf(kernel)
        learner_lc_balance = learning_curve.balanceOf(learner)
        tx = kernel.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        assert tx.events["LearnMintedFromCourse"]["learnMinted"] == mintable_balance
        assert tx.events["LearnMintedFromCourse"]["stableConverted"] == dai_balance
        assert kernel.verify(learner, 0) == constants_unit.CHECKPOINTS
        assert kernel.getLearnerCourseEligibleFunds(learner, 0) == 0
        assert token.balanceOf(learning_curve) == lc_dai_balance + dai_balance
        assert token.balanceOf(kernel) == kf_dai_balance - dai_balance
        assert learning_curve.balanceOf(learner) == learner_lc_balance + mintable_balance


def test_mint_malicious(contracts_with_learners, hackerman, learners):
    kernel, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
    with brownie.reverts("mint: not a learner on this course"):
        kernel.mint(0, {"from": hackerman})
    kernel.mint(0, {"from": learners[0]})
    with brownie.reverts("no fee to redeem"):
        kernel.mint(0, {"from": learners[0]})


def test_mint_diff_checkpoints(contracts_with_learners, learners, token):
    kernel, learning_curve = contracts_with_learners

    for m in range(constants_unit.CHECKPOINTS):
        brownie.chain.mine(constants_unit.CHECKPOINT_BLOCK_SPACING)
        for n, learner in enumerate(learners):
            dai_balance = kernel.getLearnerCourseEligibleFunds(learner, 0)
            mintable_balance = learning_curve.getMintableForReserveAmount(dai_balance)
            lc_dai_balance = token.balanceOf(learning_curve)
            kf_dai_balance = token.balanceOf(kernel)
            learner_lc_balance = learning_curve.balanceOf(learner)
            tx = kernel.mint(0, {"from": learner})
            assert "LearnMintedFromCourse" in tx.events
            assert tx.events["LearnMintedFromCourse"]["learnMinted"] == mintable_balance
            assert tx.events["LearnMintedFromCourse"]["stableConverted"] == dai_balance
            assert kernel.verify(learner, 0) == m + 1
            assert kernel.getLearnerCourseFundsRemaining(learner, 0) == constants_unit.FEE - (
                    constants_unit.FEE / constants_unit.CHECKPOINTS) * (m + 1)
            assert kernel.getLearnerCourseEligibleFunds(learner, 0) == 0
            assert token.balanceOf(learning_curve) == lc_dai_balance + dai_balance
            assert token.balanceOf(kernel) == kf_dai_balance - dai_balance
            assert learning_curve.balanceOf(learner) == learner_lc_balance + mintable_balance
            if m < constants_unit.CHECKPOINTS - 1:
                with brownie.reverts("fee redeemed at this checkpoint"):
                    kernel.mint(0, {"from": learner})
            else:
                with brownie.reverts("no fee to redeem"):
                    kernel.mint(0, {"from": learner})
    assert token.balanceOf(kernel) == 0


def test_redeem(contracts_with_learners, learners, token, kernelTreasury):
    kernel, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
    for n, learner in enumerate(learners):
        dai_balance = kernel.getLearnerCourseEligibleFunds(learner, 0)
        kt_dai_balance = token.balanceOf(kernelTreasury)
        kf_dai_balance = token.balanceOf(kernel)
        tx = kernel.redeem(0, {"from": learner})
        assert "FeeRedeemed" in tx.events
        assert tx.events["FeeRedeemed"]["amount"] == dai_balance
        assert kernel.verify(learner, 0) == constants_unit.CHECKPOINTS
        assert kernel.getLearnerCourseEligibleFunds(learner, 0) == 0
        assert kt_dai_balance == token.balanceOf(kernelTreasury)
        assert token.balanceOf(kernel) == kf_dai_balance - dai_balance
        assert token.balanceOf(learner) == dai_balance


def test_redeem_malicious(hackerman, contracts_with_learners, learners):
    kernel, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
    with brownie.reverts("redeem: not a learner on this course"):
        kernel.redeem(0, {"from": hackerman})
    kernel.redeem(0, {"from": learners[0]})
    with brownie.reverts("no fee to redeem"):
        kernel.redeem(0, {"from": learners[0]})


def test_redeem_diff_checkpoints(contracts_with_learners, learners, token, kernelTreasury):
    kernel, learning_curve = contracts_with_learners

    for m in range(constants_unit.CHECKPOINTS):
        brownie.chain.mine(constants_unit.CHECKPOINT_BLOCK_SPACING)
        for n, learner in enumerate(learners):
            dai_balance = kernel.getLearnerCourseEligibleFunds(learner, 0)
            kt_dai_balance = token.balanceOf(kernelTreasury)
            kf_dai_balance = token.balanceOf(kernel)
            learner_dai_balance = token.balanceOf(learner)
            tx = kernel.redeem(0, {"from": learner})
            assert "FeeRedeemed" in tx.events
            assert tx.events["FeeRedeemed"]["amount"] == dai_balance
            assert kernel.verify(learner, 0) == m + 1
            assert kernel.getLearnerCourseFundsRemaining(learner, 0) == constants_unit.FEE - (
                    constants_unit.FEE / constants_unit.CHECKPOINTS) * (m + 1)
            assert kernel.getLearnerCourseEligibleFunds(learner, 0) == 0
            assert kt_dai_balance == token.balanceOf(kernelTreasury)
            assert token.balanceOf(kernel) == kf_dai_balance - dai_balance
            assert token.balanceOf(learner) == learner_dai_balance + dai_balance
            if m < constants_unit.CHECKPOINTS - 1:
                with brownie.reverts("fee redeemed at this checkpoint"):
                    kernel.mint(0, {"from": learner})
            else:
                with brownie.reverts("no fee to redeem"):
                    kernel.mint(0, {"from": learner})
    assert token.balanceOf(kernel) == 0


def test_verify(contracts_with_learners, learners):
    kernel, learning_curve = contracts_with_learners
    learner = learners[0]
    for n in range(constants_unit.CHECKPOINTS + 1):
        assert kernel.verify(learner, 0, {"from": learner}) == n
        brownie.chain.mine(constants_unit.CHECKPOINT_BLOCK_SPACING)


def test_verify_malicious(contracts_with_learners, hackerman, learners):
    kernel, learning_curve = contracts_with_learners
    learner = learners[0]
    with brownie.reverts("verify: courseId does not exist"):
        kernel.verify(learner, 999, {"from": hackerman})
    with brownie.reverts("verify: courseId does not exist"):
        kernel.verify(learner, kernel.getNextCourseId(), {"from": hackerman})
    with brownie.reverts("verify: not registered to this course"):
        kernel.verify(hackerman, 0, {"from": hackerman})


def test_mint_lc_not_initialised(token, deployer, steward, learners):
    learning_curve = LearningCurve.deploy(token.address, {"from": deployer})
    kernel = KernelFactory.deploy(
        token.address,
        learning_curve.address,
        constants_unit.VAULT,
        {"from": deployer}
    )
    kernel.createCourse(
        constants_unit.FEE,
        constants_unit.CHECKPOINTS,
        constants_unit.CHECKPOINT_BLOCK_SPACING,
        constants_unit.URL,
        constants_unit.CREATOR,
        {"from": steward}
    )
    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants_unit.FEE,
            {"from": deployer}
        )
        token.approve(kernel, constants_unit.FEE, {"from": learner})
        kernel.register(0, {"from": learner})
        brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
        with brownie.reverts("!initialised"):
            kernel.mint(0, {"from": learner})