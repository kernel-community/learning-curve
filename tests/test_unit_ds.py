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
    token.transfer(holder, constants_unit.STAKE, {"from": deployer})
    assert token.balanceOf(holder) == constants_unit.STAKE
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
            constants_unit.STAKE,
            constants_unit.DURATION,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": steward}
        )

        assert "CourseCreated" in tx.events
        assert tx.events["CourseCreated"]["courseId"] == n
        assert tx.events["CourseCreated"]["stake"] == constants_unit.STAKE
        assert tx.events["CourseCreated"]["duration"] == constants_unit.DURATION
        assert tx.events["CourseCreated"]["url"] == constants_unit.URL
        assert tx.events["CourseCreated"]["creator"] == constants_unit.CREATOR


def test_create_malicious_courses(contracts, hackerman):
    deschool, learning_curve = contracts
    with brownie.reverts("createCourse: stake must be greater than 0"):
        deschool.createCourse(
            0,
            constants_unit.DURATION,
            constants_unit.URL,
            constants_unit.CREATOR,
            {"from": hackerman}
        )
    with brownie.reverts("createCourse: duration must be greater than 0"):
        deschool.createCourse(
            constants_unit.STAKE,
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
            constants_unit.STAKE,
            {"from": deployer}
        )
        token.approve(deschool, constants_unit.STAKE, {"from": learner})
        before_bal = token.balanceOf(deschool)
        tx = deschool.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_unit.STAKE == token.balanceOf(deschool)

    assert deschool.getCurrentBatchTotal() == constants_unit.STAKE * len(learners)
    assert token.balanceOf(deschool) == constants_unit.STAKE * len(learners)


def test_register_malicious(contracts_with_courses, token, deployer, hackerman):
    deschool, learning_curve = contracts_with_courses
    with brownie.reverts():
        deschool.register(0, {"from": hackerman})

    token.transfer(hackerman, constants_unit.STAKE, {"from": deployer})
    token.approve(deschool, constants_unit.STAKE, {"from": hackerman})
    with brownie.reverts("register: courseId does not exist"):
        deschool.register(999, {"from": hackerman})

    with brownie.reverts("register: courseId does not exist"):
        deschool.register(deschool.getNextCourseId(), {"from": hackerman})

    deschool.register(0, {"from": hackerman})
    token.transfer(hackerman, constants_unit.STAKE, {"from": deployer})
    token.approve(deschool, constants_unit.STAKE, {"from": hackerman})
    with brownie.reverts("register: already registered"):
        deschool.register(0, {"from": hackerman})


def test_mint(contracts_with_learners, learners, token, deployer):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.DURATION)
    for n, learner in enumerate(learners):
        assert deschool.verify(learner, 0)
        mintable_balance = learning_curve.getMintableForReserveAmount(constants_unit.STAKE)
        lc_dai_balance = token.balanceOf(learning_curve)
        ds_dai_balance = token.balanceOf(deschool)
        learner_lc_balance = learning_curve.balanceOf(learner)
        tx = deschool.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        assert tx.events["LearnMintedFromCourse"]["learnMinted"] == mintable_balance
        assert tx.events["LearnMintedFromCourse"]["stableConverted"] == constants_unit.STAKE
        assert token.balanceOf(learning_curve) == lc_dai_balance + constants_unit.STAKE
        assert token.balanceOf(deschool) == ds_dai_balance - constants_unit.STAKE
        assert learning_curve.balanceOf(learner) == learner_lc_balance + mintable_balance


def test_mint_malicious(contracts_with_learners, hackerman, learners):
    deschool, learning_curve = contracts_with_learners
    with brownie.reverts("mint: not a learner on this course"):
        deschool.mint(0, {"from": hackerman})
    brownie.chain.mine(constants_unit.COURSE_RUNNING)
    with brownie.reverts("mint: not yet eligible - wait for the full course duration to pass"):
        deschool.mint(0, {"from": learners[0]})


def test_redeem(contracts_with_learners, learners, token, kernelTreasury):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_unit.DURATION)
    for n, learner in enumerate(learners):
        kt_dai_balance = token.balanceOf(kernelTreasury)
        ds_dai_balance = token.balanceOf(deschool)
        tx = deschool.redeem(0, {"from": learner})
        assert "StakeRedeemed" in tx.events
        assert tx.events["StakeRedeemed"]["amount"] == constants_unit.STAKE
        assert deschool.verify(learner, 0)
        assert kt_dai_balance == token.balanceOf(kernelTreasury)
        assert token.balanceOf(deschool) == ds_dai_balance - constants_unit.STAKE
        assert token.balanceOf(learner) == constants_unit.STAKE


def test_redeem_malicious(hackerman, contracts_with_learners, learners):
    deschool, learning_curve = contracts_with_learners
    with brownie.reverts("redeem: not a learner on this course"):
        deschool.redeem(0, {"from": hackerman})
    brownie.chain.mine(constants_unit.COURSE_RUNNING)
    with brownie.reverts("redeem: not yet eligible - wait for the full course duration to pass"):
        deschool.redeem(0, {"from": learners[0]})


def test_verify(contracts_with_learners, learners):
    deschool, learning_curve = contracts_with_learners
    learner = learners[0]
    assert not(deschool.verify(learner, 0, {"from": learner}))
    brownie.chain.mine(constants_unit.DURATION)
    assert deschool.verify(learner, 0, {"from": learner})


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
        constants_unit.STAKE,
        constants_unit.DURATION,
        constants_unit.URL,
        constants_unit.CREATOR,
        {"from": steward}
    )
    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants_unit.STAKE,
            {"from": deployer}
        )
        token.approve(deschool, constants_unit.STAKE, {"from": learner})
        deschool.register(0, {"from": learner})
        brownie.chain.mine(constants_unit.DURATION)
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