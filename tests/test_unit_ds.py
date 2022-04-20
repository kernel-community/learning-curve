import brownie
from brownie import LearningCurve, DeSchool
import constants_unit

from eth_account import Account
from eth_account._utils.structured_data.hashing import hash_domain
from eth_account.messages import encode_structured_data
from eth_utils import encode_hex


def test_register_permit(contracts_with_courses, learners, token, deployer):
    deschool, learning_curve = contracts_with_courses
    signer = Account.create()
    holder = signer.address
    token.transfer(holder, constants_unit.FEE, {"from": deployer})
    assert token.balanceOf(holder) == constants_unit.FEE
    permit = build_permit(holder, str(deschool), token, 3600)
    signed = signer.sign_message(permit)
    print(token.balanceOf(deschool.address))
    tx = deschool.permitAndRegister(0, 0, 0, signed.v, signed.r, signed.s, {"from": holder})
    print(token.balanceOf(deschool.address))
    assert "LearnerRegistered" in tx.events
    assert tx.events["LearnerRegistered"]["courseId"] == 0


def test_create_courses(contracts, steward):
    deschool, learning_curve = contracts
    for n in range(5):
        tx = deschool.createCourse(
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
    deschool, learning_curve = contracts
    with brownie.reverts("createCourse: fee must be greater than 0"):
        deschool.createCourse(
            0,
            constants_unit.CHECKPOINTS,
            constants_unit.CHECKPOINT_BLOCK_SPACING,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": hackerman}
        )
    with brownie.reverts("createCourse: checkpoint must be greater than 0"):
        deschool.createCourse(
            constants_unit.FEE,
            0,
            constants_unit.CHECKPOINT_BLOCK_SPACING,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": hackerman}
        )
    with brownie.reverts("createCourse: checkpointBlockSpacing must be greater than 0"):
        deschool.createCourse(
            constants_unit.FEE,
            constants_unit.CHECKPOINTS,
            0,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": hackerman}
        )


def test_register(contracts_with_courses, learners, token, deployer):
    deschool, learning_curve = contracts_with_courses

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


def test_register_malicious(contracts_with_courses, token, deployer, hackerman):
    deschool, learning_curve = contracts_with_courses
    with brownie.reverts():
        deschool.register(0, {"from": hackerman})

    token.transfer(hackerman, constants_unit.FEE, {"from": deployer})
    token.approve(deschool, constants_unit.FEE, {"from": hackerman})
    with brownie.reverts("register: courseId does not exist"):
        deschool.register(999, {"from": hackerman})

    with brownie.reverts("register: courseId does not exist"):
        deschool.register(deschool.getNextCourseId(), {"from": hackerman})

    deschool.register(0, {"from": hackerman})
    token.transfer(hackerman, constants_unit.FEE, {"from": deployer})
    token.approve(deschool, constants_unit.FEE, {"from": hackerman})
    with brownie.reverts("register: already registered"):
        deschool.register(0, {"from": hackerman})


def test_mint(contracts_with_learners, learners, token, deployer):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
    for n, learner in enumerate(learners):
        dai_balance = deschool.getLearnerCourseEligibleFunds(learner, 0)
        mintable_balance = learning_curve.getMintableForReserveAmount(dai_balance)
        lc_dai_balance = token.balanceOf(learning_curve)
        kf_dai_balance = token.balanceOf(deschool)
        learner_lc_balance = learning_curve.balanceOf(learner)
        tx = deschool.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        assert tx.events["LearnMintedFromCourse"]["learnMinted"] == mintable_balance
        assert tx.events["LearnMintedFromCourse"]["stableConverted"] == dai_balance
        assert deschool.verify(learner, 0) == constants_unit.CHECKPOINTS
        assert deschool.getLearnerCourseEligibleFunds(learner, 0) == 0
        assert token.balanceOf(learning_curve) == lc_dai_balance + dai_balance
        assert token.balanceOf(deschool) == kf_dai_balance - dai_balance
        assert learning_curve.balanceOf(learner) == learner_lc_balance + mintable_balance


def test_mint_malicious(contracts_with_learners, hackerman, learners):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
    with brownie.reverts("mint: not a learner on this course"):
        deschool.mint(0, {"from": hackerman})
    deschool.mint(0, {"from": learners[0]})
    with brownie.reverts("no fee to redeem"):
        deschool.mint(0, {"from": learners[0]})


def test_mint_diff_checkpoints(contracts_with_learners, learners, token):
    deschool, learning_curve = contracts_with_learners

    for m in range(constants_unit.CHECKPOINTS):
        brownie.chain.mine(constants_unit.CHECKPOINT_BLOCK_SPACING)
        for n, learner in enumerate(learners):
            dai_balance = deschool.getLearnerCourseEligibleFunds(learner, 0)
            mintable_balance = learning_curve.getMintableForReserveAmount(dai_balance)
            lc_dai_balance = token.balanceOf(learning_curve)
            kf_dai_balance = token.balanceOf(deschool)
            learner_lc_balance = learning_curve.balanceOf(learner)
            tx = deschool.mint(0, {"from": learner})
            assert "LearnMintedFromCourse" in tx.events
            assert tx.events["LearnMintedFromCourse"]["learnMinted"] == mintable_balance
            assert tx.events["LearnMintedFromCourse"]["stableConverted"] == dai_balance
            assert deschool.verify(learner, 0) == m + 1
            assert deschool.getLearnerCourseFundsRemaining(learner, 0) == constants_unit.FEE - (
                    constants_unit.FEE / constants_unit.CHECKPOINTS) * (m + 1)
            assert deschool.getLearnerCourseEligibleFunds(learner, 0) == 0
            assert token.balanceOf(learning_curve) == lc_dai_balance + dai_balance
            assert token.balanceOf(deschool) == kf_dai_balance - dai_balance
            assert learning_curve.balanceOf(learner) == learner_lc_balance + mintable_balance
            if m < constants_unit.CHECKPOINTS - 1:
                with brownie.reverts("fee redeemed at this checkpoint"):
                    deschool.mint(0, {"from": learner})
            else:
                with brownie.reverts("no fee to redeem"):
                    deschool.mint(0, {"from": learner})
    assert token.balanceOf(deschool) == 0


def test_redeem(contracts_with_learners, learners, token, kernelTreasury):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
    for n, learner in enumerate(learners):
        dai_balance = deschool.getLearnerCourseEligibleFunds(learner, 0)
        kt_dai_balance = token.balanceOf(kernelTreasury)
        kf_dai_balance = token.balanceOf(deschool)
        tx = deschool.redeem(0, {"from": learner})
        assert "FeeRedeemed" in tx.events
        assert tx.events["FeeRedeemed"]["amount"] == dai_balance
        assert deschool.verify(learner, 0) == constants_unit.CHECKPOINTS
        assert deschool.getLearnerCourseEligibleFunds(learner, 0) == 0
        assert kt_dai_balance == token.balanceOf(kernelTreasury)
        assert token.balanceOf(deschool) == kf_dai_balance - dai_balance
        assert token.balanceOf(learner) == dai_balance


def test_redeem_malicious(hackerman, contracts_with_learners, learners):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
    with brownie.reverts("redeem: not a learner on this course"):
        deschool.redeem(0, {"from": hackerman})
    deschool.redeem(0, {"from": learners[0]})
    with brownie.reverts("no fee to redeem"):
        deschool.redeem(0, {"from": learners[0]})


def test_redeem_diff_checkpoints(contracts_with_learners, learners, token, kernelTreasury):
    deschool, learning_curve = contracts_with_learners

    for m in range(constants_unit.CHECKPOINTS):
        brownie.chain.mine(constants_unit.CHECKPOINT_BLOCK_SPACING)
        for n, learner in enumerate(learners):
            dai_balance = deschool.getLearnerCourseEligibleFunds(learner, 0)
            kt_dai_balance = token.balanceOf(kernelTreasury)
            kf_dai_balance = token.balanceOf(deschool)
            learner_dai_balance = token.balanceOf(learner)
            tx = deschool.redeem(0, {"from": learner})
            assert "FeeRedeemed" in tx.events
            assert tx.events["FeeRedeemed"]["amount"] == dai_balance
            assert deschool.verify(learner, 0) == m + 1
            assert deschool.getLearnerCourseFundsRemaining(learner, 0) == constants_unit.FEE - (
                    constants_unit.FEE / constants_unit.CHECKPOINTS) * (m + 1)
            assert deschool.getLearnerCourseEligibleFunds(learner, 0) == 0
            assert kt_dai_balance == token.balanceOf(kernelTreasury)
            assert token.balanceOf(deschool) == kf_dai_balance - dai_balance
            assert token.balanceOf(learner) == learner_dai_balance + dai_balance
            if m < constants_unit.CHECKPOINTS - 1:
                with brownie.reverts("fee redeemed at this checkpoint"):
                    deschool.mint(0, {"from": learner})
            else:
                with brownie.reverts("no fee to redeem"):
                    deschool.mint(0, {"from": learner})
    assert token.balanceOf(deschool) == 0


def test_verify(contracts_with_learners, learners):
    deschool, learning_curve = contracts_with_learners
    learner = learners[0]
    for n in range(constants_unit.CHECKPOINTS + 1):
        assert deschool.verify(learner, 0, {"from": learner}) == n
        brownie.chain.mine(constants_unit.CHECKPOINT_BLOCK_SPACING)


def test_verify_malicious(contracts_with_learners, hackerman, learners):
    deschool, learning_curve = contracts_with_learners
    learner = learners[0]
    with brownie.reverts("verify: courseId does not exist"):
        deschool.verify(learner, 999, {"from": hackerman})
    with brownie.reverts("verify: courseId does not exist"):
        deschool.verify(learner, deschool.getNextCourseId(), {"from": hackerman})
    with brownie.reverts("verify: not registered to this course"):
        deschool.verify(hackerman, 0, {"from": hackerman})


def test_mint_lc_not_initialised(token, deployer, steward, learners):
    learning_curve = LearningCurve.deploy(token.address, {"from": deployer})
    deschool = DeSchool.deploy(
        token.address,
        learning_curve.address,
        constants_unit.VAULT,
        {"from": deployer}
    )
    deschool.createCourse(
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
        token.approve(deschool, constants_unit.FEE, {"from": learner})
        deschool.register(0, {"from": learner})
        brownie.chain.mine(constants_unit.CHECKPOINTS * constants_unit.CHECKPOINT_BLOCK_SPACING)
        with brownie.reverts("!initialised"):
            deschool.mint(0, {"from": learner})


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