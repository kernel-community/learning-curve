//SPDX-License-Identifier: MPL-2.0
pragma solidity 0.8.13;

import "./ERC20.sol";
import "./SafeTransferLib.sol";
import "./interfaces/I_Vault.sol";
import "./interfaces/I_Registry.sol";
import "./interfaces/IERC20Permit.sol";
import "./interfaces/I_LearningCurve.sol";

/**
 * @title DeSchool
 * @author kjr217, cryptowanderer
 * @notice Deploys new courses and interacts with the learning curve directly to mint LEARN.
 */

contract DeSchool {

    struct Course {
        uint256 stake; // an amount in DAI to be staked for the duration course
        uint256 duration; // the duration of the course, in number of blocks
        string url; // url containing course data
        address creator; // address to receive any yield from a redeem call
        uint256 scholars; // keep track of how many scholars are registered so we can deregister them later
        uint256 completedScholars; // keep track of how many scholars have completed the course
        uint256 scholarshipTotal; // the total amount of DAI provided for scholarships for this course
        address scholarshipVault; // one scholarship vault per course, any new scholarships are simply added to it
        uint256 scholarshipYTokens; // the yTokens, earned by the course creator from scholarships
    }

    struct Scholar {
        uint256 blockRegistered; // used to create perpetual scholarships as needed
    }

    struct Learner {
        uint256 blockRegistered; // used to decide when a learner can claim their stake back
        uint256 yieldBatchId; // the batch id for this learner's Yield bearing deposit
    }

    // containing course data mapped by a courseId
    mapping(uint256 => Course) public courses;

    // containing learner data mapped by a courseId and address
    mapping(uint256 => mapping(address => Learner)) learnerData;
    // containing scholar data mapped by a courseId and the number of "completed" scholars.
    // We keep track of this separately from the number of scholars in order to lookup the "active" scholar
    // who registered most long ago, check if the course duration has passed has passed since they registered 
    // and, if it has, we replace them with a new scholar
    mapping(uint256 => mapping(uint256 => Scholar)) scholarData;
    // containing scholarship provider amount mapped by courseId and address
    mapping(uint256 => mapping(address => uint256)) providerAmount;
    // containg currentScholar data mapped by a courseId and address for the require in registerScholar()
    mapping(uint256 => mapping(address => Scholar)) registered;

    // containing the total underlying amount for a yield batch mapped by batchId
    mapping(uint256 => uint256) batchTotal;
    // containing the total amount of yield token for a yield batch mapped by batchId
    mapping(uint256 => uint256) batchYieldTotal;
    // containing the vault address of the the yield token for a yield batch mapped by batchId
    mapping(uint256 => address) batchYieldAddress;

    // yield rewards for an eligible address
    mapping(address => uint256) yieldRewards;

    // tracker for the courseId, current represents the id of the next course
    uint256 private courseIdTracker;
    // tracker for the batchId, current represents the current batch
    uint256 private batchIdTracker;

    // the stablecoin used by the contract, DAI
    ERC20 public immutable stable;
    // the yearn registry used by the contract, to determine what the yDai address is.
    I_Registry public immutable registry;
    // interface for the learning curve
    I_LearningCurve public immutable learningCurve;

    event CourseCreated(
        uint256 indexed courseId,
        uint256 stake,
        uint256 duration,
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
    event ScholarshipWithdrawn(
        uint256 indexed courseId,
        uint256 amountWithdrawn
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
        stable = ERC20(_stable);
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
        uint256 courseId_ = courseIdTracker;
        courseIdTracker++;
        courses[courseId_] = Course(
            _stake,
            _duration,
            _url,
            _creator,
            0, // no scholars when a course is first created
            0, // scholarshipAmount is similarly 0.
            0, // no completed scholars yet 
            address(0), // scholarshipVault address unset at course creation
            0 // scholarshipYield also 0
        );
        emit CourseCreated(
            courseId_,
            _stake,
            _duration,
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
        public 
    {
        require(
            _amount >= courses[_courseId].stake, 
            "createScholarships: must seed scholarship with enough funds to justify gas costs"
        );
        require(
            _courseId < courseIdTracker,
            "createScholarships: courseId does not exist"
        );
        Course storage course = courses[_courseId];
        
        SafeTransferLib.safeTransferFrom(stable, msg.sender, address(this), _amount);

        // get the address of the scholarshipVault if it exists, otherwise get the latest vault from the yRegistry
        if (course.scholarshipVault != address(0)) {
            I_Vault vault = I_Vault(course.scholarshipVault);
            stable.approve(course.scholarshipVault, _amount);
            course.scholarshipYTokens += vault.deposit(_amount);
        } else {
            I_Vault newVault = I_Vault(registry.latestVault(address(stable)));
            course.scholarshipVault = address(newVault);
            stable.approve(course.scholarshipVault, _amount);
            course.scholarshipYTokens = newVault.deposit(_amount);
        }

        // set providerData to ensure withdrawals are possible
        providerAmount[_courseId][msg.sender] += _amount;

        // add this scholarship provided to any pre-existing amount
        course.scholarshipTotal += _amount;

        emit ScholarshipCreated(
            _courseId,
            _amount,
            _amount / course.stake, // amount scholars this specific scholarship creates
            course.scholarshipTotal,
            msg.sender,
            course.scholarshipVault,
            course.scholarshipYTokens
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
    function permitCreateScholarships(
        uint256 _courseId, 
        uint256 _amount,
        uint256 nonce, 
        uint256 expiry, 
        uint8 v, 
        bytes32 r, 
        bytes32 s
    ) external {
        IERC20Permit(address(stable)).permit(msg.sender, address(this), nonce, expiry, true, v, r, s);
        createScholarships(_courseId, _amount);
    }

    /**
     * @notice           handles scholar registration if there are scholarship available
     * @param  _courseId course id the scholar would like to register to
     */
    function registerScholar(uint256 _courseId) 
        public 
    {
        require(
            _courseId < courseIdTracker,
            "registerScholar: courseId does not exist"
        );
        Course storage course = courses[_courseId];
        if (registered[_courseId][msg.sender].blockRegistered != 0) {
            revert("registerScholar: already registered");
        }
        // Perpetual scholarships are enabled on an as needed basis - it is most gas efficient
        if ((course.scholarshipTotal / course.stake) <= course.scholars) {
            if (scholarData[_courseId][course.completedScholars].blockRegistered + course.duration <= block.number) {
                scholarData[_courseId][course.scholars].blockRegistered = block.number;
                registered[_courseId][msg.sender].blockRegistered = block.number;
                course.completedScholars++;
                course.scholars++;
            } else {
                revert("registerScholar: no scholarships available for this course");
            }
        } else {
            scholarData[_courseId][course.scholars].blockRegistered = block.number;
            registered[_courseId][msg.sender].blockRegistered = block.number;
            course.scholars++;
        }
        
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
            providerAmount[_courseId][msg.sender] >= _amount,
            "withdrawScholarship: can only withdraw up to the amount initally provided for scholarships"
        );
        Course storage course =  courses[_courseId];
        I_Vault vault = I_Vault(course.scholarshipVault);
        // get the proportional amount of shares the user owns
        uint256 providerShares = (((_amount * 1e18) / course.scholarshipTotal) * (course.scholarshipYTokens)) / 1e18;
        // in case of rounding errors we want to cap provider shares at the total number of ytokens on the scholarship
        if (providerShares > course.scholarshipYTokens) {
            providerShares = course.scholarshipYTokens;
        }
        // reduce the number of ytokens
        course.scholarshipYTokens -= providerShares;
        // first, mark down the amount provided
        providerAmount[_courseId][msg.sender] -= _amount;
        // we only need to subtract from the total scholarship for this course, as that is what is used to
        // check when registering new scholars.
        course.scholarshipTotal -= _amount;

        emit ScholarshipWithdrawn(
            _courseId,
            _amount
        );
        // withdraw amount from scholarshipVault for this course and return to provider
        uint256 collateral = vault.withdraw(providerShares);
        // check if the collateral returned is greater than the amount passed in
        // if it is then we take away the excess and allocate it to the course creator
        // as yield rewards and send the original amount back to the scholarship provider
        if (collateral > _amount) {
            yieldRewards[course.creator] = collateral - _amount;
            collateral = _amount;
        }
        SafeTransferLib.safeTransfer(stable, msg.sender, collateral);
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
        uint256 batchId_ = batchIdTracker;
        // initiate the next batch
        uint256 batchAmount_ = batchTotal[batchId_];
        batchIdTracker++;
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
            _courseId < courseIdTracker,
            "register: courseId does not exist"
        );
        uint256 batchId_ = batchIdTracker;
        require(
            learnerData[_courseId][msg.sender].blockRegistered == 0,
            "register: already registered"
        );
        Course memory course = courses[_courseId];

        SafeTransferLib.safeTransferFrom(stable, msg.sender, address(this), course.stake);

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
            _courseId < courseIdTracker,
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
        uint256 collateral;
        uint256 learnerShares;
        require(
            learnerData[_courseId][msg.sender].blockRegistered != 0,
            "redeem: not a learner on this course"
        );
        require(
            verify(msg.sender, _courseId), 
            "redeem: not yet eligible - wait for the full course duration to pass"
        );
        Course memory course = courses[_courseId];
        if (isDeployed(_courseId)) {
            I_Vault vault = I_Vault(
                batchYieldAddress[
                    learnerData[_courseId][msg.sender].yieldBatchId
                ]
            );
            uint256 batchId_ = learnerData[_courseId][msg.sender].yieldBatchId;
            uint256 temp = (course.stake * 1e18) / batchTotal[batchId_];
            learnerShares = (temp * batchYieldTotal[batchId_]) / 1e18;
            collateral = vault.withdraw(learnerShares);
            if (course.stake < collateral) {
                yieldRewards[course.creator] += collateral - course.stake;
                emit StakeRedeemed(_courseId, msg.sender, course.stake);
                SafeTransferLib.safeTransfer(stable, msg.sender, course.stake);
            } else {
                emit StakeRedeemed(
                    _courseId, 
                    msg.sender, 
                    collateral
                );
                SafeTransferLib.safeTransfer(stable, msg.sender, collateral);
            }
        } else {
            emit StakeRedeemed(
                _courseId, 
                msg.sender, 
                course.stake
            );
            SafeTransferLib.safeTransfer(stable, msg.sender, course.stake);
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
        uint256 collateral;
        uint256 learnerShares;
        require(
            learnerData[_courseId][msg.sender].blockRegistered != 0,
            "mint: not a learner on this course"
        );
        require(
            verify(msg.sender, _courseId), 
            "mint: not yet eligible - wait for the full course duration to pass"
        );
        Course memory course = courses[_courseId];
        if (isDeployed(_courseId)) {
            I_Vault vault = I_Vault(
                batchYieldAddress[
                    learnerData[_courseId][msg.sender].yieldBatchId
                ]
            );
            uint256 batchId_ = learnerData[_courseId][msg.sender].yieldBatchId;
            uint256 temp = (course.stake * 1e18) / batchTotal[batchId_];
            learnerShares = (temp * batchYieldTotal[batchId_]) / 1e18;
            collateral = vault.withdraw(learnerShares);
        }
        if (course.stake < collateral) {
            yieldRewards[course.creator] += collateral - course.stake;
            stable.approve(address(learningCurve), course.stake);
            uint256 balanceBefore = learningCurve.balanceOf(msg.sender);
            learningCurve.mintForAddress(msg.sender, course.stake);
            emit LearnMintedFromCourse(
                _courseId,
                msg.sender,
                course.stake,
                learningCurve.balanceOf(msg.sender) - balanceBefore
            );
        } else {
            stable.approve(address(learningCurve), course.stake);
            uint256 balanceBefore = learningCurve.balanceOf(msg.sender);
            learningCurve.mintForAddress(msg.sender, course.stake);
            emit LearnMintedFromCourse(
                _courseId,
                msg.sender,
                course.stake,
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
     */
    function withdrawYieldRewards() 
        external 
    {
        uint256 withdrawableReward;
        // add to the withdrawableRewards any yield from learner deposits who are not scholars
        withdrawableReward = yieldRewards[msg.sender];
        yieldRewards[msg.sender] = 0;
        emit YieldRewardRedeemed(msg.sender, withdrawableReward);
        SafeTransferLib.safeTransfer(stable, msg.sender, withdrawableReward);
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
        if (batchId_ == batchIdTracker) {
            return false;
        } else {
            return true;
        }
    }

    function scholarshipAvailable(uint256 _courseId) 
        external 
        view 
        returns (bool) 
    {
        Course memory course = courses[_courseId];
        return (course.scholarshipTotal / course.stake) > course.scholars || 
        scholarData[_courseId][course.completedScholars].blockRegistered + course.duration <= block.number;
    }

    function getCurrentBatchTotal() 
        external 
        view 
        returns (uint256) 
    {
        return batchTotal[batchIdTracker];
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
        return batchIdTracker;
    }

    function getNextCourseId() 
        external 
        view 
        returns (uint256)
    {
        return courseIdTracker;
    }

    function getCourseUrl(uint256 _courseId)
        external
        view
        returns (string memory)
    {
        return courses[_courseId].url;
    }
}
