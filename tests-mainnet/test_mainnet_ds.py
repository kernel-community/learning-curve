import brownie
import constants_mainnet
from eth_account import Account
from eth_account._utils.structured_data.hashing import hash_domain
from eth_account.messages import encode_structured_data
from eth_utils import encode_hex


def test_create_scholarships(contracts_with_scholarships, token, deployer):
    deschool, learning_curve = contracts_with_scholarships
    # provide another scholarship, from a separate account, to the first course
    token.approve(deschool, (constants_mainnet.SCHOLARSHIP_AMOUNT), {"from": deployer})
    tx = deschool.createScholarships(
        0,
        constants_mainnet.SCHOLARSHIP_AMOUNT,
        {"from": deployer}
    )
    assert "ScholarshipCreated" in tx.events
    assert tx.events["ScholarshipCreated"]["courseId"] == 0
    assert tx.events["ScholarshipCreated"]["scholarshipsAvailable"] == (constants_mainnet.SCHOLARSHIP_AMOUNT / constants_mainnet.STAKE) * 2
    assert tx.events["ScholarshipCreated"]["scholarshipTotal"] == (constants_mainnet.SCHOLARSHIP_AMOUNT * 2)
    assert tx.events["ScholarshipCreated"]["scholarshipProvider"] == deployer
    # double check the "scholarshipsAvailable" field in the course struct and ensure it reflects the number of scholars added by both scholarships
    assert deschool.courses(0)[5] == tx.events["ScholarshipCreated"]["scholarshipsAvailable"]


def test_scholarship_reverts(contracts_with_scholarships, token, deployer, provider):
    deschool, learning_curve = contracts_with_scholarships
    token.transfer(provider, (constants_mainnet.SCHOLARSHIP_AMOUNT), {"from": deployer})
    assert token.balanceOf(provider) == (constants_mainnet.SCHOLARSHIP_AMOUNT)
    token.approve(deschool, (constants_mainnet.SCHOLARSHIP_AMOUNT), {"from": provider})
    with brownie.reverts("createScholarships: must seed scholarship with enough funds to justify gas costs"):
        deschool.createScholarships(
            0,
            constants_mainnet.SCHOLARSHIP_AMOUNT / 3,
            {"from": provider}
        )
    with brownie.reverts("createScholarships: courseId does not exist"):
        deschool.createScholarships(
            6,
            constants_mainnet.SCHOLARSHIP_AMOUNT,
            {"from": provider}
        )

def test_register_scholar(contracts_with_scholarships, learners):
    deschool, learning_curve = contracts_with_scholarships
    for n, learner in enumerate(learners):
        tx = deschool.registerScholar(
            n,
            {"from": learner}
        )
        assert "ScholarRegistered" in tx.events
        assert tx.events["ScholarRegistered"]["courseId"] == n
        assert tx.events["ScholarRegistered"]["scholar"] == learner


def test_register_scholar_reverts(contracts_with_scholarships, learners):
    deschool, learning_curve = contracts_with_scholarships
    with brownie.reverts("registerScholar: courseId does not exist"):
        deschool.registerScholar(
            6,
            {"from": learners[0]}
        )
    tx = deschool.registerScholar(
        0,
        {"from": learners[0]}
    )
    with brownie.reverts("registerScholar: already registered"):
        tx = deschool.registerScholar(
            0,
            {"from": learners[0]}
        )
    tx = deschool.registerScholar(
        0,
        {"from": learners[1]}
    )
    with brownie.reverts("registerScholar: no scholarships available for this course"):
        tx = deschool.registerScholar(
            0,
            {"from": learners[2]}
        )


def test_perpetual_scholarships(contracts_with_scholarships, learners, provider):
    deschool, learning_curve = contracts_with_scholarships
    assert deschool.courses(0)[5] == 2
    tx = deschool.registerScholar(
        0,
        {"from": learners[0]}
    )
    assert deschool.courses(0)[5] == 1
    brownie.chain.mine(constants_mainnet.COURSE_RUNNING)
    # this will pass, but not affect the scholarshipsAvailable, as it should not pass the if statement yet
    tx = deschool.perpetualScholars(
        0,
        {"from": provider}
    )
    # our contracts_with_scholarships creates 2 scholarships for each course, hence this should still equal 1 at this stage
    assert deschool.courses(0)[5] == 1
    tx = deschool.registerScholar(
        0,
        {"from": learners[1]}
    )
    assert deschool.courses(0)[5] == 0
    brownie.chain.mine(constants_mainnet.DURATION)
    tx = deschool.perpetualScholars(
        0,
        {"from": provider}
    )
    assert "PerpetualScholarships" in tx.events
    assert tx.events["PerpetualScholarships"]["scholarshipsAvailable"] == 2
    assert deschool.courses(0)[5] == 2
    # should be able to register now that scholarships have been perpetuated
    tx = deschool.registerScholar(
        0,
        {"from": learners[2]}
    )
    assert "ScholarRegistered" in tx.events
    assert tx.events["ScholarRegistered"]["courseId"] == 0
    assert tx.events["ScholarRegistered"]["scholar"] == learners[2]


def test_register_permit(contracts_with_courses, learners, token, deployer):
    deschool, learning_curve = contracts_with_courses
    signer = Account.create()
    holder = signer.address
    token.transfer(holder, constants_mainnet.STAKE, {"from": deployer})
    assert token.balanceOf(holder) == constants_mainnet.STAKE
    permit = build_permit(holder, str(deschool), token, 3600)
    signed = signer.sign_message(permit)
    print(token.balanceOf(deschool.address))
    tx = deschool.permitAndRegister(0, 0, 0, signed.v, signed.r, signed.s, {"from": holder})
    print(token.balanceOf(deschool.address))
    assert "LearnerRegistered" in tx.events
    assert tx.events["LearnerRegistered"]["courseId"] == 0


def test_redeem(contracts_with_learners, learners, token, steward, keeper, gen_lev_strat, ydai):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_mainnet.COURSE_RUNNING)
    tx = deschool.batchDeposit({"from": keeper})
    brownie.chain.mine(constants_mainnet.DURATION)
    brownie.chain.sleep(1000)
    gen_lev_strat.harvest({"from": keeper})
    for n, learner in enumerate(learners):
        ds_ydai_balance = ydai.balanceOf(deschool)
        tx = deschool.redeem(0, {"from": learner})
        assert "StakeRedeemed" in tx.events
        assert tx.events["StakeRedeemed"]["amount"] == constants_mainnet.STAKE
        assert deschool.verify(learner, 0)
        assert token.balanceOf(steward) == 0
        assert deschool.getYieldRewards(steward, {"from": steward}) > 0
        assert ydai.balanceOf(deschool) < ds_ydai_balance
        assert token.balanceOf(learner) == constants_mainnet.STAKE
        assert token.balanceOf(learning_curve) == 1e18
        assert ydai.balanceOf(learning_curve) == 0
    kt_redemption = deschool.getYieldRewards(steward, {"from": steward})
    deschool.withdrawYieldRewards({"from": steward})
    assert deschool.getYieldRewards(steward, {"from": steward}) == 0
    assert token.balanceOf(steward) == kt_redemption
    assert token.balanceOf(deschool) == 0
    assert ydai.balanceOf(deschool) < 1000


def test_batch_success(
        contracts_with_learners,
        keeper,
        token,
        ydai,
        learners
):
    deschool, learning_curve = contracts_with_learners
    ds_balance_before = token.balanceOf(deschool)
    batch_id_before = deschool.getCurrentBatchId()
    tx = deschool.batchDeposit({"from": keeper})
    assert "BatchDeposited" in tx.events
    assert batch_id_before == \
           0 == \
           tx.events["BatchDeposited"]["batchId"] == \
           deschool.getCurrentBatchId() - 1
    assert token.balanceOf(deschool) == 0
    assert ds_balance_before == tx.events["BatchDeposited"]["batchAmount"] == constants_mainnet.STAKE * len(learners)
    assert ydai.balanceOf(deschool) > 0
    assert ydai.balanceOf(deschool) == tx.events["BatchDeposited"]["batchYieldAmount"]


def test_batch_malicious(contracts_with_courses, keeper):
    deschool, learning_curve = contracts_with_courses
    with brownie.reverts("batchDeposit: no funds to deposit"):
        deschool.batchDeposit({"from": keeper})


def test_register_diff_batches(contracts_with_courses, keeper, token, learners, deployer, ydai):
    deschool, learning_curve = contracts_with_courses
    for n, learner in enumerate(learners):
        token.transfer(
            learner,
            constants_mainnet.STAKE,
            {"from": deployer}
        )
        token.approve(deschool, constants_mainnet.STAKE, {"from": learner})
        before_bal = token.balanceOf(deschool)
        tx = deschool.register(0, {"from": learner})

        assert "LearnerRegistered" in tx.events
        assert tx.events["LearnerRegistered"]["courseId"] == 0
        assert before_bal + constants_mainnet.STAKE == token.balanceOf(deschool)
        ds_balance_before = token.balanceOf(deschool)
        batch_id_before = deschool.getCurrentBatchId()
        ydai_bal_before = ydai.balanceOf(deschool)
        tx = deschool.batchDeposit({"from": keeper})
        assert "BatchDeposited" in tx.events
        assert batch_id_before == \
               n == \
               tx.events["BatchDeposited"]["batchId"] == \
               deschool.getCurrentBatchId() - 1
        assert token.balanceOf(deschool) == 0
        assert ds_balance_before == tx.events["BatchDeposited"]["batchAmount"] == constants_mainnet.STAKE
        assert ydai.balanceOf(deschool) > ydai_bal_before
        assert ydai.balanceOf(deschool) - ydai_bal_before == tx.events["BatchDeposited"]["batchYieldAmount"]


def test_mint(contracts_with_learners, learners, token, keeper, gen_lev_strat, ydai, steward):
    deschool, learning_curve = contracts_with_learners
    brownie.chain.mine(constants_mainnet.COURSE_RUNNING)
    tx = deschool.batchDeposit({"from": keeper})
    brownie.chain.mine(constants_mainnet.DURATION)
    brownie.chain.sleep(1000)
    gen_lev_strat.harvest({"from": keeper})

    for n, learner in enumerate(learners):
        mintable_balance = learning_curve.getMintableForReserveAmount(constants_mainnet.STAKE)
        lc_dai_balance = token.balanceOf(learning_curve)
        ds_dai_balance = token.balanceOf(deschool)
        learner_lc_balance = learning_curve.balanceOf(learner)
        tx = deschool.mint(0, {"from": learner})
        assert "LearnMintedFromCourse" in tx.events
        assert abs(tx.events["LearnMintedFromCourse"]["learnMinted"] - mintable_balance) < constants_mainnet.ACCURACY_Y
        assert abs(tx.events["LearnMintedFromCourse"]["stableConverted"] - constants_mainnet.STAKE) < constants_mainnet.ACCURACY_Y
        assert deschool.verify(learner, 0)
        assert abs(token.balanceOf(learning_curve) - lc_dai_balance - constants_mainnet.STAKE) < constants_mainnet.ACCURACY_Y
        assert abs(token.balanceOf(deschool) - deschool.getYieldRewards(steward)) < constants_mainnet.ACCURACY
        assert abs(learning_curve.balanceOf(learner) - learner_lc_balance - mintable_balance) < constants_mainnet.ACCURACY_Y
    assert token.balanceOf(deschool) == deschool.getYieldRewards(steward)
    assert ydai.balanceOf(deschool) < 1000


def test_verify(contracts_with_learners, learners, keeper):
    deschool, learning_curve = contracts_with_learners
    learner = learners[0]
    tx = deschool.batchDeposit({"from": keeper})
    assert not(deschool.verify(learner, 0, {"from": learner}))
    brownie.chain.mine(constants_mainnet.DURATION)
    assert deschool.verify(learner, 0, {"from": learner})


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