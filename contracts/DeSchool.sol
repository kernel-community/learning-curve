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
 * @author kjr217
 * @notice Deploys new courses and interacts with the learning curve directly to mint LEARN.
 */

contract DeSchool {
    using SafeERC20 for IERC20;
    using Counters for Counters.Counter;

    struct Course {
        uint256 beginBlock;
        uint256 fee; // the fee for entering the course
        uint256 duration; // the duration of the course, in number of blocks
        uint256 scholars; // the number of scholarships the amount creates for this course
        string url; // url containing course data
        address creator; // address to receive any yield from a redeem call
    }

    struct Provider {
        uint256 amount; // the amount provided for scholarships for this particular course
    }

    struct Scholar {
        address scholar; // used to decide when a new scholarship can be made available
        bool completed; //used to ensure same address cannot claim scholarship twice
    }

    struct Learner {
        uint256 blockRegistered; // used to decide when a learner can claim their registration fee back
        uint256 yieldBatchId; // the batch id for this learner's Yield bearing deposit
    }

    // containing course data mapped by a courseId
    mapping(uint256 => Course) public courses;
    // containing scholarship provider data mapped by a courseId
    mapping(uint256 => Provider) public providers;

    // containing learner data mapped by a courseId and address
    mapping(uint256 => mapping(address => Learner)) learnerData;
    // containing scholar data mapped by a courseId and blockRegistered
    mapping(uint256 => mapping(uint256 => Scholar)) scholarData;
    // containing scholarship provider data mapped by courseId and address
    mapping(uint256 => mapping(address => Provider)) providerData;
    // containg previousScholar data mapped by a courseId and address
    mapping(uint256 => mapping(address => Scholar)) previousScholar;
    

    // containing the total underlying amount for a yield batch mapped by batchId
    mapping(uint256 => uint256) batchTotal;
    // containing the total amount of yield token for a yield batch mapped by batchId
    mapping(uint256 => uint256) batchYieldTotal;
    // containing the vault address of the the yield token for a yield batch mapped by batchId
    mapping(uint256 => address) batchYieldAddress;

    // containing the total amount of yield token for a yield scholarship mapped by scholarshipId
    mapping(uint256 => uint256) scholarshipYieldTotal;
    // containing the vault address of the the yield token for a yield scholarship mapped by scholarshipId
    mapping(uint256 => address) scholarshipYieldAddress;

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
        uint256 beginBlock,
        uint256 fee,
        uint256 duration,
        string url,
        address creator
    );
    event ScholarshipCreated(
        uint256 indexed courseId,
        uint256 scholarshipAmount,
        uint256 numScholars,
        address scholarshipProvider
    );
    event ScholarRegistered(
        uint256 indexed courseId, 
        address scholar
    );
    event ScholarshipWithdrawn(
        uint256 scholarshipId,
        uint256 scholarshipAmount,
        uint256 numScholars
    );
    event LearnerRegistered(
        uint256 indexed courseId, 
        address learner
    );
    event FeeRedeemed(
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
     * @notice                         create a course
     * @param  _fee                    fee for a learner to register
     * @param  _duration               the duration of the course, in number of blocks
     * @param  _url                    url leading to course details
     * @param  _creator                the address that excess yield will be sent to on a redeem
     */
    function createCourse(
        uint256 _fee,
        uint256 _duration,
        string calldata _url,
        address _creator
    ) external {
        require(_fee > 0, "createCourse: fee must be greater than 0");
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
            block.number,
            _fee,
            _duration,
            0,
            _url,
            _creator
        );
        emit CourseCreated(
            courseId_,
            block.number,
            _fee,
            _duration,
            _url,
            _creator
        );
    }

    /**
     * @notice this method allows anyone to create perpetual scholarships by staking
     *         capital for learners to use. The can claim it back at any time.
     * @param  _courseId courseId the donor would like to fund
     * @param  _amount the amount in DAI that the donor wishes to give
     */
    function createScholarships(uint256 _courseId, uint256 _amount) external {
        require(
            _amount >= 1000, 
            "createScholarships: must seed scholarship with enough funds to justify gas costs"
        );
        require(
            _courseId < courseIdTracker.current(),
            "createScholarships: courseId does not exist"
        );

        // get the address of the vault from the yRegistry
        I_Vault vault = I_Vault(registry.latestVault(address(stable)));
        // approve the vault
        stable.approve(address(vault), _amount);
        // // transfer the amount directly into a vault in order to save gas fees and mint y from the vault
        uint256 yTokens = vault.deposit(_amount);

        // TODO: how to ensure that the courseCreator can claim the yield? 

        // set providerData to ensure withdrawals are possible
        providerData[_courseId][msg.sender].amount = _amount;

        // calculate how many scholarships can be awarded based on amount provided
        Course memory course = courses[_courseId];
        uint256 newScholars = _amount / course.fee;
        course.scholars += newScholars;

        emit ScholarshipCreated(
            _courseId,
            _amount,
            newScholars,
            msg.sender
        );
    }

    /**
     * @notice deposit the current batch of DAI in the contract to yearn.
     *         the batching mechanism is used to reduce gas for each learner,
     *         so at any point someone can call this function and deploy all
     *         funds in a specific "batch" to yearn, allowing the funds to gain
     *         interest.
     */
    function batchDeposit() external {
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
     * @notice called by anyone to refresh scholar numbers if previous scholars have completed the course
     * @param  _courseId courseId to be checked for possible new scholarship slots. Used here because we don't expect UIs to store scholarshipIds,
     *                   only courseIds.
     */
    function checkScholarships(uint256 _courseId) external returns (uint256 scholars) {
        Course memory course = courses[_courseId]; 
        uint256 finishedBlock = block.number - course.duration;

        for (uint256 i; i < course.scholars; i++) {
            for (uint256 j = course.beginBlock; j < finishedBlock; j++) {
                if (scholarData[_courseId][j].scholar != address(0)) {
                    scholarData[_courseId][j].completed = true;
                    course.scholars ++;
                }
            }
        }
        return course.scholars;
    }

    /**
     * @notice handles scholar registration if there are scholarship available
     * @param  _courseId courseId the scholar would like to register to
     */
    function registerScholar(uint256 _courseId) public {
        require(
            _courseId < courseIdTracker.current(),
            "registerScholar: courseId does not exist"
        );
        require(
            !previousScholar[_courseId][msg.sender].completed,
            "registerScholar: already registered previously"
        );
        Course storage course = courses[_courseId];
        require(
            course.scholars > 0, 
            "registerScholar: no scholarships available for this course"
        );
        course.scholars -= 1;

        scholarData[_courseId][block.number].scholar = msg.sender;
        
        emit ScholarRegistered(
            _courseId, 
            msg.sender
        );
    }

    /**
     * @notice allows donor to withdraw their scholarship donation, or a portion thereof, at any point
     *         Q: what happens if there are still learners registered for the course and the scholarship is withdrawn from under them?
     *         A: allow them to complete the course, but allow no new scholars after withdraw takes place.       
     * @param _courseId the id of the course from which the scholarship is to be withdrawn.
     */
    function withdrawScholarship(uint256 _courseId, uint256 _amount) public {
        require(
            providerData[_courseId][msg.sender].amount <= _amount,
            "withdrawScholarship: can only withdraw up to the amount initally provided for scholarships"
        );
        Course memory course =  courses[_courseId];
        uint256 scholarsRemoved = course.fee / _amount;
        // check, as provider could withdraw full amount while scholars are still registered, potentially causing solidity weirdness.
        if (scholarsRemoved > course.scholars) {
            course.scholars = 0;
        } else {
            course.scholars -= scholarsRemoved;
        }
        emit ScholarshipWithdrawn(
            _courseId,
            _amount,
            scholarsRemoved
        );
        // TODO: make this actually work by withdrawing from the vault first, then sending to the scholarship provider
        stable.safeTransfer(msg.sender, _amount);
    }

    /**
     * @notice handles learner registration
     * @param  _courseId course id the learner would like to register to
     */
    function register(uint256 _courseId) public {
        require(
            _courseId < courseIdTracker.current(),
            "register: courseId does not exist"
        );
        uint256 batchId_ = batchIdTracker.current();
        require(
            learnerData[_courseId][msg.sender].blockRegistered == 0,
            "register: already registered"
        );
        Course storage course = courses[_courseId];

        stable.safeTransferFrom(msg.sender, address(this), course.fee);

        learnerData[_courseId][msg.sender].blockRegistered = block.number;
        learnerData[_courseId][msg.sender].yieldBatchId = batchId_;
        batchTotal[batchId_] += course.fee;

        emit LearnerRegistered(
            _courseId, 
            msg.sender
        );
    }
    /**
     * @notice handles learner registration with permit for approval
     */
    function permitAndRegister(uint256 _courseId, uint256 nonce, uint256 expiry, uint8 v, bytes32 r, bytes32 s) external {
        IERC20Permit(address(stable)).permit(msg.sender, address(this), nonce, expiry, true, v, r, s);
        register(_courseId);
    }

    /**
     * @notice           handles checkpoint verification
     *                   All course are deployed with a duration in blocks, after which learners
     *                   can either claim their fee back, or use it to mint LEARN
     *
     *                   This is a helper function that checks where a learner is
     *                   in a course and is used by both redeem() and mint().
     *
     * @param  _learner  address of the learner to verify
     * @param  _courseId course id to verify for the learner
     * @return completed if the full course duration has passed and the learner can redeem their fee or mint LEARN
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
     * @notice           handles fee redemption into stable
     *                   if a learner is redeeming rather than minting, it means
     *                   they are simply requesting their initial fee back.
     *                   In this case, we check that the course duration has passed and,
     *                   if so, send the full fee back to the learner.
     *
     *                   Whatever yield was earned is sent to the course creator address.
     *
     * @param  _courseId course id to redeem the fee from
     */
    function redeem(uint256 _courseId) external {
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
            uint256 temp = (courses[_courseId].fee * 1e18) / batchTotal[batchId_];
            learnerShares = (temp * batchYieldTotal[batchId_]) / 1e18;
            shares = vault.withdraw(learnerShares);
            if (courses[_courseId].fee < shares) {
                yieldRewards[courses[_courseId].creator] += shares - courses[_courseId].fee;
                emit FeeRedeemed(_courseId, msg.sender, courses[_courseId].fee);
                stable.safeTransfer(msg.sender, courses[_courseId].fee);
            } else {
                emit FeeRedeemed(_courseId, msg.sender, shares);
                stable.safeTransfer(msg.sender, shares);
            }
        } else {
            emit FeeRedeemed(_courseId, msg.sender, courses[_courseId].fee);
            stable.safeTransfer(msg.sender, courses[_courseId].fee);
        }
    }

    /**
     * @notice           handles learner minting new LEARN
     *                   checks via verify() what proportion of the fee to send to the
     *                   Learning Curve, any yield earned on the original fee is sent to
     *                   the creator's designated address, and returns all
     *                   the resulting LEARN tokens to the learner.
     * @param  _courseId course id to mint LEARN from
     */
    function mint(uint256 _courseId) external {
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
            uint256 temp = (courses[_courseId].fee * 1e18) / batchTotal[batchId_];
            learnerShares = (temp * batchYieldTotal[batchId_]) / 1e18;
            shares = vault.withdraw(learnerShares);
        }
        if (courses[_courseId].fee < shares) {
            yieldRewards[courses[_courseId].creator] += shares - courses[_courseId].fee;
            stable.approve(address(learningCurve), courses[_courseId].fee);
            uint256 balanceBefore = learningCurve.balanceOf(msg.sender);
            learningCurve.mintForAddress(msg.sender, courses[_courseId].fee);
            emit LearnMintedFromCourse(
                _courseId,
                msg.sender,
                courses[_courseId].fee,
                learningCurve.balanceOf(msg.sender) - balanceBefore
            );
        } else {
            stable.approve(address(learningCurve), courses[_courseId].fee);
            uint256 balanceBefore = learningCurve.balanceOf(msg.sender);
            learningCurve.mintForAddress(msg.sender, courses[_courseId].fee);
            emit LearnMintedFromCourse(
                _courseId,
                msg.sender,
                courses[_courseId].fee,
                learningCurve.balanceOf(msg.sender) - balanceBefore
            );
        }
    }

    /**
     * @notice Gets the amount of dai that an address is eligible, addresses become eligible if
     *         they are the designated reward receiver for a specific course and a learner on that
     *         course decided to redeem, meaning yield was reserved for the reward receiver
     */
    function withdrawYieldRewards() external {
        uint256 withdrawableReward = getYieldRewards(msg.sender);
        yieldRewards[msg.sender] = 0;
        emit YieldRewardRedeemed(msg.sender, withdrawableReward);
        stable.safeTransfer(msg.sender, withdrawableReward);
    }

    /**
     * @notice                check whether the fee a learner staked has been deployed to a Yearn vault
     * @param  _courseId      course id to redeem fee or mint LEARN from
     * @return deployed       whether the funds to be redeemed were deployed to yearn
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

    function getScholars(uint256 _courseId) external view returns (uint256) {
        Course memory course = courses[_courseId];
        return course.scholars;
    }

    function getCurrentBatchTotal() external view returns (uint256) {
        return batchTotal[batchIdTracker.current()];
    }

    function getBlockRegistered(address learner, uint256 courseId)
        external
        view
        returns (uint256)
    {
        return learnerData[courseId][learner].blockRegistered;
    }

    function getCurrentBatchId() external view returns (uint256) {
        return batchIdTracker.current();
    }

    function getNextCourseId() external view returns (uint256) {
        return courseIdTracker.current();
    }

    function getCourseUrl(uint256 _courseId)
        external
        view
        returns (string memory)
    {
        return courses[_courseId].url;
    }

    function getYieldRewards(address redeemer) public view returns (uint256) {
        return yieldRewards[redeemer];
    }
}
