//SPDX-License-Identifier: MPL-2.0
pragma solidity 0.8.13;

import "@openzeppelin/contracts/utils/Counters.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

interface I_Vault {
    function token() external view returns (address);

    function underlying() external view returns (address);

    function pricePerShare() external view returns (uint256);

    function deposit(uint256) external returns (uint256);

    function depositAll() external;

    function withdraw(uint256) external returns (uint256);

    function withdraw() external returns (uint256);

    function balanceOf(address) external returns (uint256);
}

interface I_LearningCurve {
    function mintForAddress(address, uint256) external;

    function balanceOf(address) external view returns (uint256);
}

interface I_Registry {
    function latestVault(address) external view returns (address);
}

interface IERC20Permit {

    function permit(
        address holder,
        address spender,
        uint256 nonce,
        uint256 expiry,
        bool allowed,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external;

    //EIP2612 implementation
    function permit(
        address holder,
        address spender,
        uint256 amount,
        uint256 expiry,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external;

    function nonces(address holder) external view returns(uint);

    function pull(address usr, uint256 wad) external;

    function approve(address usr, uint256 wad) external returns (bool);
}
/**
 * @title DeSchool
 * @author kjr217, cryptowanderer
 * @notice Deploys new courses and interacts with the learning curve directly to mint LEARN.
 */

contract DeSchool {
    using SafeERC20 for IERC20;
    using Counters for Counters.Counter;

    struct Course {
        uint256 stake; // an amount in DAI to be staked for the duration course
        uint256 duration; // the duration of the course, in number of blocks
        uint256 checkpoint; // a block number we use to enable perpetual scholarships
        string url; // url containing course data
        address creator; // address to receive any yield from a redeem call
        uint256 scholars; // keep track of how many scholars are registered so we can deregister them later
        uint256 scholarshipTotal; // the total amount of DAI provided for scholarships for this course
        address scholarshipVault; // one scholarship vault per course, any new scholarships are simply added to it
        uint256 scholarshipYield; // the yield, in yTokens, earned by the course creator from scholarships
    }

    struct Provider {
        uint256 amount; // the amount provided for scholarships for this particular course 
    }

    struct Scholar {
        address scholar; // used to decide when a new scholarship can be made available
        uint256 blockRegistered; // used to ensure same address cannot register for a scholarship when already registered
    }

    struct Learner {
        uint256 blockRegistered; // used to decide when a learner can claim their stake back
        uint256 yieldBatchId; // the batch id for this learner's Yield bearing deposit
    }

    // containing course data mapped by a courseId
    mapping(uint256 => Course) public courses;

    // containing learner data mapped by a courseId and address
    mapping(uint256 => mapping(address => Learner)) learnerData;
    // containing scholar data mapped by a courseId and scholarId for perpetualScholarships() loop
    mapping(uint256 => mapping(uint256 => Scholar)) scholarData;
    // containing scholarship provider data mapped by courseId and address
    mapping(uint256 => mapping(address => Provider)) providerData;
    // containg currentScholar data mapped by a courseId and address for register() check
    mapping(uint256 => mapping(address => Scholar)) currentScholar;

    // containing the total underlying amount for a yield batch mapped by batchId
    mapping(uint256 => uint256) batchTotal;
    // containing the total amount of yield token for a yield batch mapped by batchId
    mapping(uint256 => uint256) batchYieldTotal;
    // containing the vault address of the the yield token for a yield batch mapped by batchId
    mapping(uint256 => address) batchYieldAddress;

    // yield rewards for an eligible address
    mapping(address => uint256) yieldRewards;

    // tracker for the courseId, current represents the id of the next course
    Counters.Counter private courseIdTracker;
    // tracker for the batchId, current represents the current batch
    Counters.Counter private batchIdTracker;

    // the stablecoin used by the contract, DAI
    IERC20 public stable;
    // the yearn resgistry used by the contract, to determine what the yDai address is.
    I_Registry public registry;
    // interface for the learning curve
    I_LearningCurve public learningCurve;

    event CourseCreated(
        uint256 indexed courseId,
        uint256 stake,
        uint256 duration,
        uint256 checkpoint,
        string url,
        address creator
    );
    event ScholarshipCreated(
        uint256 indexed courseId,
        uint256 scholarshipAmount,
        uint256 newScholars,
        uint256 scholarshipTotal,
        address scholarshipProvider,
        address scholarshipVault,
        uint256 scholarshipYield
    );
    event ScholarRegistered(
        uint256 indexed courseId, 
        address scholar
    );
    event PerpetualScholarships (
        uint256 indexed courseId,
        uint256 newScholars
    );
    event ScholarshipWithdrawn(
        uint256 indexed courseId,
        uint256 amountWithdrawn,
        uint256 scholarsRemoved
    );
    event LearnerRegistered(
        uint256 indexed courseId, 
        address learner
    );
    event StakeRedeemed(
        uint256 courseId, 
        address learner, 
        uint256 amount
    );
    event LearnMintedFromCourse(
        uint256 courseId,
        address learner,
        uint256 stableConverted,
        uint256 learnMinted
    );
    event BatchDeposited(
        uint256 batchId,
        uint256 batchAmount,
        uint256 batchYieldAmount
    );
    event YieldRewardRedeemed(
        address redeemer, 
        uint256 yieldRewarded
    );

    constructor(
        address _stable,
        address _learningCurve,
        address _registry
    ) {
        stable = IERC20(_stable);
        learningCurve = I_LearningCurve(_learningCurve);
        registry = I_Registry(_registry);
    }

    /**
     * @notice            create a course
     * @param  _stake     stake required to register
     * @param  _duration  the duration of the course, in number of blocks
     * @param  _url       url leading to course details
     * @param  _creator   the address that excess yield will be sent to on a redeem
     */
    function createCourse(
        uint256 _stake,
        uint256 _duration,
        string calldata _url,
        address _creator
    ) external {
        require(
            _stake > 0, 
            "createCourse: stake must be greater than 0"
        );
        require(
            _duration > 0,
            "createCourse: duration must be greater than 0"
        );
        require(
            _creator != address(0),
            "createCourse: creator cannot be 0 address"
        );
        uint256 courseId_ = courseIdTracker.current();
        courseIdTracker.increment();
        courses[courseId_] = Course(
            _stake,
            _duration,
            block.number,
            _url,
            _creator,
            0, // no scholars when a course is first created
            0, // scholarshipAmount is similarly 0.
            address(0), // scholarshipVault address unset at coures creation
            0 // scholarshipYield also 0
        );
        emit CourseCreated(
            courseId_,
            _stake,
            _duration,
            block.number,
            _url,
            _creator
        );
    }

    /**
     * @notice           this method allows anyone to create perpetual scholarships by staking
     *                   capital for learners to use. The can claim it back at any time.
     * @param  _courseId course id the donor would like to fund
     * @param  _amount   the amount in DAI that the donor wishes to give
     */
    function createScholarships(uint256 _courseId, uint256 _amount) 
        external 
    {
        require(
            _amount >= 1 * 1e21, 
            "createScholarships: must seed scholarship with enough funds to justify gas costs"
        );
        require(
            _courseId < courseIdTracker.current(),
            "createScholarships: courseId does not exist"
        );
        Course storage course = courses[_courseId];
        // TODO: can we transfer the amount directly into the relevant vault via permit() in order to save gas fees?
        stable.safeTransferFrom(msg.sender, address(this), _amount);

        // get the address of the scholarshipVault if it exists, otherwise get the latest vault from the yRegistry
        if (course.scholarshipVault != address(0)) {
            I_Vault vault = I_Vault(course.scholarshipVault);
            stable.approve(course.scholarshipVault, _amount);
            course.scholarshipYield += vault.deposit(_amount);
        } else {
            I_Vault newVault = I_Vault(registry.latestVault(address(stable)));
            course.scholarshipVault = address(newVault);
            stable.approve(course.scholarshipVault, _amount);
            uint256 yTokens = newVault.deposit(_amount);
            course.scholarshipYield = yTokens;
        }

        // set providerData to ensure withdrawals are possible
        providerData[_courseId][msg.sender].amount = _amount;

        // add this scholarship provided to any pre-existing amount
        course.scholarshipTotal += _amount;

        emit ScholarshipCreated(
            _courseId,
            _amount,
            _amount / course.stake, // amount scholars this specific scholarship creates
            course.scholarshipTotal,
            msg.sender,
            course.scholarshipVault,
            course.scholarshipYield
        );
    }

    /**
     * @notice           called by anyone to ensure perpetual scholarships are possible as previous scholars are deregistered from the course.
     *                   The core concept here is that, with perpetual scholarships, we need not assess outcomes or merit, because we are
     *                   not consuming the money, just leveraging its presence in a shared vault to enable perpetual, collective learning.
     * @param  _courseId course id to be checked for possible new scholarship slots.
     */
    function perpetualScholars(uint256 _courseId) 
        external
    {
        Course storage course = courses[_courseId];
        uint256 currentScholars = course.scholars;
        uint256 totalScholars = course.scholarshipTotal / course.stake; 

        // For courses with large numbers of scholars, we have to deregister scholars in batches
        // as loops in solidity are not cool for gas costs.
        // 
        // We begin after the first batch rather than 0 so as to avoid counting the first scholar as a whole batch.
        //  
        // It's not 100% accurate: there could be uncompleted scholars in a batch who first member is completed,
        // which therefore triggers the if statement. We feel OK about optimistcally increasing scholarships
        // for such cases.
        if (totalScholars > 10) {
            for (uint256 i = (totalScholars / 10); i <= currentScholars; i += (totalScholars / 10)) {
                if (
                    scholarData[_courseId][i].blockRegistered != 0 &&
                    scholarData[_courseId][i].blockRegistered + course.duration <= block.number
                ) {
                    course.scholars -= (totalScholars / 10);
                }
            }
        } else {
            for (uint256 j = 0; j <= currentScholars; j++) {
                if (
                    scholarData[_courseId][j].blockRegistered != 0 &&
                    scholarData[_courseId][j].blockRegistered + course.duration <= block.number
                ) {
                    course.scholars --;
                }
            }
        }

        uint256 newScholars = currentScholars - course.scholars;

        emit PerpetualScholarships(
            _courseId,
            newScholars
        );
    }

    /**
     * @notice           handles scholar registration if there are scholarship available
     * @param  _courseId course id the scholar would like to register to
     */
    function registerScholar(uint256 _courseId) 
        public 
    {
        require(
            _courseId < courseIdTracker.current(),
            "registerScholar: courseId does not exist"
        );
        Course storage course = courses[_courseId];
        require(
            (course.scholarshipTotal / course.stake) - course.scholars > 0, 
            "registerScholar: no scholarships available for this course"
        );
        if (currentScholar[_courseId][msg.sender].blockRegistered != 0) {
            revert("registerScholar: already registered");
        }
        currentScholar[_courseId][msg.sender].blockRegistered = block.number;
        // we assign a "scholarId" here to make the loop in perpetualScholars possible
        scholarData[_courseId][course.scholars].scholar = msg.sender;
        // it seems silly, but we need this for perpetualScholarships()
        scholarData[_courseId][course.scholars].blockRegistered = block.number;
        course.scholars++;
        
        emit ScholarRegistered(
            _courseId, 
            msg.sender
        );
    }

    /**
     * @notice          allows donor to withdraw their scholarship donation, or a portion thereof, at any point
     *                  Q: what happens if there are still learners registered for the course and the scholarship is withdrawn from under them?
     *                  A: allow them to complete the course, but allow no new scholars after withdraw takes place.       
     * @param _courseId course id from which the scholarship is to be withdrawn.
     * @param _amount   the amount that the scholarship provider wishes to withdraw
     */
    function withdrawScholarship(uint256 _courseId, uint256 _amount) 
        public 
    {
        require(
            providerData[_courseId][msg.sender].amount >= _amount,
            "withdrawScholarship: can only withdraw up to the amount initally provided for scholarships"
        );
        Course storage course =  courses[_courseId];
        I_Vault vault = I_Vault(course.scholarshipVault);
        uint256 scholarsRemoved = _amount / course.stake;

        // first, mark down the amount provided
        providerData[_courseId][msg.sender].amount -= _amount;
        // we only need to subtract from the total scholarship for this course, as that is what is used to
        // check when registering new scholars.
        course.scholarshipTotal -= _amount;

        emit ScholarshipWithdrawn(
            _courseId,
            _amount,
            scholarsRemoved
        );
        // withdraw amount from scholarshipVault for this course and return to provider
        vault.withdraw(_amount);
        stable.safeTransfer(msg.sender, _amount);
    }

    /**
     * @notice deposit the current batch of DAI in the contract to yearn.
     *         the batching mechanism is used to reduce gas for each learner,
     *         so at any point someone can call this function and deploy all
     *         funds in a specific "batch" to yearn, allowing the funds to gain
     *         interest.
     */
    function batchDeposit() 
        external 
    {
        uint256 batchId_ = batchIdTracker.current();
        // initiate the next batch
        uint256 batchAmount_ = batchTotal[batchId_];
        batchIdTracker.increment();
        require(batchAmount_ > 0, "batchDeposit: no funds to deposit");
        // get the address of the vault from the yRegistry
        I_Vault vault = I_Vault(registry.latestVault(address(stable)));
        // approve the vault
        stable.approve(address(vault), batchAmount_);
        // mint y from the vault
        uint256 yTokens = vault.deposit(batchAmount_);
        batchYieldTotal[batchId_] = yTokens;
        batchYieldAddress[batchId_] = address(vault);
        emit BatchDeposited(batchId_, batchAmount_, yTokens);
    }

    /**
     * @notice           handles learner registration in the case that no scholarships are available
     * @param  _courseId course id the learner would like to register to
     */
    function register(uint256 _courseId) 
        public 
    {
        require(
            _courseId < courseIdTracker.current(),
            "register: courseId does not exist"
        );
        uint256 batchId_ = batchIdTracker.current();
        require(
            learnerData[_courseId][msg.sender].blockRegistered == 0,
            "register: already registered"
        );
        Course memory course = courses[_courseId];

        stable.safeTransferFrom(msg.sender, address(this), course.stake);

        learnerData[_courseId][msg.sender].blockRegistered = block.number;
        learnerData[_courseId][msg.sender].yieldBatchId = batchId_;
        batchTotal[batchId_] += course.stake;

        emit LearnerRegistered(
            _courseId, 
            msg.sender
        );
    }

    /**
     * @notice          handles learner registration with permit. This enable learners to register with only one transaction,
     *                  rather than two, i.e. approve DeSchool to spend your DAI, and only then register. This saves gas for
     *                  learners and improves the UX.
     * @param _courseId course id for which the learner wishes to register
     * @param nonce     provided in the 2616 standard for replay protection.
     * @param expiry    the current blocktime must be less than or equal to this for a valid transaction
     * @param v         a recovery identity variable included in Ethereum, in addition to the r and s below which are standard ECDSA parameters
     * @param r         standard ECDSA parameter
     * @param s         standard ECDSA parameter
     */
    function permitAndRegister(
        uint256 _courseId, 
        uint256 nonce, 
        uint256 expiry, 
        uint8 v, 
        bytes32 r, 
        bytes32 s
    ) external {
        IERC20Permit(address(stable)).permit(msg.sender, address(this), nonce, expiry, true, v, r, s);
        register(_courseId);
    }

    /**
     * @notice           All courses are deployed with a duration in blocks, after which learners
     *                   can either claim their stake back, or use it to mint LEARN
     * @param  _learner  address of the learner to verify
     * @param  _courseId course id to verify for the learner
     * @return completed if the full course duration has passed and the learner can redeem their stake or mint LEARN
     */
    function verify(address _learner, uint256 _courseId)
        public
        view
        returns (bool completed)
    {
        require(
            _courseId < courseIdTracker.current(),
            "verify: courseId does not exist"
        );
        require(
            learnerData[_courseId][_learner].blockRegistered != 0,
            "verify: not registered to this course"
        );
        if (courses[_courseId].duration < block.number - learnerData[_courseId][_learner].blockRegistered) {
            return true;
        }
    }

    /**
     * @notice           handles stake redemption in DAI
     *                   if a learner is redeeming rather than minting, it means
     *                   they are simply requesting their initial stake back.
     *                   In this case, we check that the course duration has passed and,
     *                   if so, send the full stake back to the learner.
     *
     *                   Whatever yield was earned is sent to the course creator address.
     *
     * @param  _courseId course id to redeem the stake from
     */
    function redeem(uint256 _courseId) 
        external 
    {
        uint256 shares;
        uint256 learnerShares;
        require(
            learnerData[_courseId][msg.sender].blockRegistered != 0,
            "redeem: not a learner on this course"
        );
        require(
            verify(msg.sender, _courseId), 
            "redeem: not yet eligible - wait for the full course duration to pass"
        );
        if (isDeployed(_courseId)) {
            I_Vault vault = I_Vault(
                batchYieldAddress[
                    learnerData[_courseId][msg.sender].yieldBatchId
                ]
            );
            uint256 batchId_ = learnerData[_courseId][msg.sender].yieldBatchId;
            uint256 temp = (courses[_courseId].stake * 1e18) / batchTotal[batchId_];
            learnerShares = (temp * batchYieldTotal[batchId_]) / 1e18;
            shares = vault.withdraw(learnerShares);
            if (courses[_courseId].stake < shares) {
                yieldRewards[courses[_courseId].creator] += shares - courses[_courseId].stake;
                emit StakeRedeemed(_courseId, msg.sender, courses[_courseId].stake);
                stable.safeTransfer(msg.sender, courses[_courseId].stake);
            } else {
                emit StakeRedeemed(
                    _courseId, 
                    msg.sender, 
                    shares
                );
                stable.safeTransfer(msg.sender, shares);
            }
        } else {
            emit StakeRedeemed(
                _courseId, 
                msg.sender, 
                courses[_courseId].stake
            );
            stable.safeTransfer(msg.sender, courses[_courseId].stake);
        }
    }

    /**
     * @notice           handles learner minting new LEARN
     *                   checks via verify() that the original stake can be redeemed and used
     *                   to mint via the Learning Curve.
     *                   Any yield earned on the original stake is sent to
     *                   the creator's designated address.
     *                   All the resulting LEARN tokens are returned to the learner.
     * @param  _courseId course id to mint LEARN from
     */
    function mint(uint256 _courseId) 
        external 
    {
        uint256 shares;
        uint256 learnerShares;
        require(
            learnerData[_courseId][msg.sender].blockRegistered != 0,
            "mint: not a learner on this course"
        );
        require(
            verify(msg.sender, _courseId), 
            "mint: not yet eligible - wait for the full course duration to pass"
        );
        if (isDeployed(_courseId)) {
            I_Vault vault = I_Vault(
                batchYieldAddress[
                    learnerData[_courseId][msg.sender].yieldBatchId
                ]
            );
            uint256 batchId_ = learnerData[_courseId][msg.sender].yieldBatchId;
            uint256 temp = (courses[_courseId].stake * 1e18) / batchTotal[batchId_];
            learnerShares = (temp * batchYieldTotal[batchId_]) / 1e18;
            shares = vault.withdraw(learnerShares);
        }
        if (courses[_courseId].stake < shares) {
            yieldRewards[courses[_courseId].creator] += shares - courses[_courseId].stake;
            stable.approve(address(learningCurve), courses[_courseId].stake);
            uint256 balanceBefore = learningCurve.balanceOf(msg.sender);
            learningCurve.mintForAddress(msg.sender, courses[_courseId].stake);
            emit LearnMintedFromCourse(
                _courseId,
                msg.sender,
                courses[_courseId].stake,
                learningCurve.balanceOf(msg.sender) - balanceBefore
            );
        } else {
            stable.approve(address(learningCurve), courses[_courseId].stake);
            uint256 balanceBefore = learningCurve.balanceOf(msg.sender);
            learningCurve.mintForAddress(msg.sender, courses[_courseId].stake);
            emit LearnMintedFromCourse(
                _courseId,
                msg.sender,
                courses[_courseId].stake,
                learningCurve.balanceOf(msg.sender) - balanceBefore
            );
        }
    }

    /**
     * @notice          Gets the yield a creator can claim, which comes from two sources.
     *                  There may be yield from scholarships provided for their course, which is assigned as
     *                  the scholarship is created and may be claimed at any time thereafter.
     *                  There may also be yield from any learners who have registered in the case no scholarships are available.
     *                  When the learner decides to redeem or mint their stake, this yield is assigned to the creator.
     * @param _courseId only course creators can claim yield. The information for how much yield they can claim
     *                  is always accessible via the courseId.
     */
    function withdrawYieldRewards(uint256 _courseId) 
        external 
    {
        require(
            msg.sender == courses[_courseId].creator,
            "withdrawYieldRewards: only course creator can withdraw yield"
        );
        uint256 withdrawableReward;
        // if there is yield from scholarships, withdraw it all
        if (courses[_courseId].scholarshipYield != 0) {
            withdrawableReward = courses[_courseId].scholarshipYield;
            courses[_courseId].scholarshipYield = 0;
        }
        // add to the withdrawableRewards any yield from learner deposits who are not scholars
        withdrawableReward += getYieldRewards(_courseId);
        yieldRewards[courses[_courseId].creator] = 0;
        emit YieldRewardRedeemed(courses[_courseId].creator, withdrawableReward);
        stable.safeTransfer(courses[_courseId].creator, withdrawableReward);
    }

    /**
     * @notice           check whether a learner's staked has been deployed to a Yearn vault
     * @param  _courseId course id to redeem stake or mint LEARN from
     * @return deployed  whether the funds to be redeemed were deployed to yearn
     */
    function isDeployed(uint256 _courseId)
        internal
        view
        returns (bool deployed)
    {
        uint256 batchId_ = learnerData[_courseId][msg.sender].yieldBatchId;
        if (batchId_ == batchIdTracker.current()) {
            return false;
        } else {
            return true;
        }
    }

    function getScholars(uint256 _courseId) 
        external 
        view 
        returns (uint256) 
    {
        return courses[_courseId].scholars;
    }

    function getCurrentBatchTotal() 
        external 
        view 
        returns (uint256) 
    {
        return batchTotal[batchIdTracker.current()];
    }

    function getBlockRegistered(address learner, uint256 courseId)
        external
        view
        returns (uint256)
    {
        return learnerData[courseId][learner].blockRegistered;
    }

    function getCurrentBatchId() 
        external 
        view 
        returns (uint256) 
    {
        return batchIdTracker.current();
    }

    function getNextCourseId() 
        external 
        view 
        returns (uint256) 
    {
        return courseIdTracker.current();
    }

    function getCourseUrl(uint256 _courseId)
        external
        view
        returns (string memory)
    {
        return courses[_courseId].url;
    }

    function getYieldRewards(uint256 _courseId) 
        public 
        view 
        returns (uint256) 
    {
        uint256 yield = yieldRewards[courses[_courseId].creator] + courses[_courseId].scholarshipYield;
        return yield;
    }
}
