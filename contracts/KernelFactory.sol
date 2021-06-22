//SPDX-License-Identifier: MPL-2.0
pragma solidity 0.8.0;
pragma abicoder v2;

import "./LearningCurve.sol";

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
}

/**
 * @title Kernel Factory
 * @author kjr217
 * @notice Deploys new courses and interacts with the learning curve directly to mint LEARN.
 */

contract KernelFactory {
    using SafeERC20 for IERC20;
    using Counters for Counters.Counter;

    struct Course {
        uint256 checkpoints;            // number of checkpoints the course should have
        uint256 fee;                    // the fee for entering the course
        uint256 checkpointBlockSpacing; // the block spacing between checkpoints
    }

    struct Learner {
        uint256 blockRegistered;        // used to decide when a learner can claim their registration fee back
        uint256 yieldBatchId;           // the batch id for this learner's Yield bearing deposit
        uint256 checkpointReached;      // what checkpoint the user has reached
    }

    // containing course data mapped by a courseId
    mapping(uint256 => Course) public courses;
    // containing learner data mapped by a courseId and address
    mapping(uint256 => mapping (address => Learner)) learnerData;

    // containing the total underlying amount for a yield batch mapped by batchId
    mapping(uint256 => uint256) batchTotal;
    // containing the total amount of yield token for a yield batch mapped by batchId
    mapping(uint256 => uint256) batchYieldTotal;
    // containing the underlying amount a user deposited in a specific batchId
    mapping(uint256 => mapping (address => uint256)) userDeposit;
    // tracker for the batchId, current represents the current batch
    Counters.Counter private batchIdTracker;
    // the stablecoin used by the contract, DAI
    IERC20 public stable;
    // the yearn vault used by the contract, yDAI
    I_Vault public vault;

    // tracker for the courseId, current represents the id of the next batch
    Counters.Counter private courseIdTracker;
    // interface for the learning curve
    I_LearningCurve public learningCurve;
    // kernel treasury address
    address public kernelTreasury;


    event CourseCreated(
        uint256 indexed courseId,
        uint256 checkpoints,
        uint256 fee,
        uint256 checkpointBlockSpacing
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
        uint256 amount
    );
    event BatchDeposited(
        uint256 batchId,
        uint256 batchAmount,
        uint256 batchYieldAmount
    );
    event CheckpointUpdated(
        uint256 courseId,
        uint256 checkpointReached,
        address learner
    );

    constructor(
        address _stable,
        address _learningCurve,
        address _vault,
        address _kernelTreasury
    ) {
        stable = IERC20(_stable);
        learningCurve = I_LearningCurve(_learningCurve);
        vault = I_Vault(_vault);
        kernelTreasury = _kernelTreasury;
    }

    /**
     * @notice                         create a course
     * @param  _fee                    fee for a learner to register
     * @param  _checkpoints            number of checkpoints on the course
     * @param  _checkpointBlockSpacing block spacing between subsequent checkpoints
     */
    function createCourse(
        uint256 _fee,
        uint256 _checkpoints,
        uint256 _checkpointBlockSpacing
    ) external {
        require(_fee > 0, "createCourse: fee must be greater than 0");
        require(_checkpointBlockSpacing > 0,
            "createCourse: checkpointBlockSpacing must be greater than 0");
        require(_checkpoints > 0, "createCourse: checkpoint must be greater than 0");
        uint256 courseId_ = courseIdTracker.current();
        courseIdTracker.increment();
        courses[courseId_] = Course(
                                  _checkpoints,
                                  _fee,
                                  _checkpointBlockSpacing
                                 );
        emit CourseCreated(courseId_, _checkpoints, _fee, _checkpointBlockSpacing);
    }

    /**
     * @notice deposit the current batch of DAI in the contract to yearn
     */
    function batchDeposit() external {
        uint256 batchId_ = batchIdTracker.current();
        // initiate the next batch
        uint256 batchAmount_ = batchTotal[batchId_];
        batchIdTracker.increment();
        require(batchAmount_ > 0, "batchDeposit: no funds to deposit");
        // approve the vault
        stable.approve(address(vault), batchAmount_);
        // mint y from the vault
        uint256 yTokens = vault.deposit(batchAmount_);
        batchYieldTotal[batchId_] = yTokens;

        emit BatchDeposited(batchId_, batchAmount_, yTokens);
    }

    /**
     * @notice handles learner registration
     * @param  _courseId course id the learner would like to register to
     */
     function register(uint256 _courseId) public {
         require(_courseId < courseIdTracker.current(), "register: courseId does not exist");
         uint256 batchId_ = batchIdTracker.current();
         require(learnerData[_courseId][msg.sender].blockRegistered == 0, "register: already registered");
         Course storage course = courses[_courseId];

         stable.safeTransferFrom(msg.sender, address(this), course.fee);

         learnerData[_courseId][msg.sender].blockRegistered = block.number;
         learnerData[_courseId][msg.sender].yieldBatchId = batchId_;
         batchTotal[batchId_] += course.fee;
         userDeposit[batchId_][msg.sender] += course.fee;

         emit LearnerRegistered(_courseId, msg.sender);
     }

    /**
     * @notice           handles checkpoint verification
     *                   All course are deployed with a given number of checkpoints
     *                   allowing learners to receive a portion of their fees back
     *                   at various stages in the course.
     *
     *                   This is a helper function that checks where a learner is
     *                   in a course and is used by both redeem() and mint() to figure out
     *                   the proper amount required.
     *
     * @param  learner   address of the learner to verify
     * @param  _courseId course id to verify for the learner
     * @return           the checkpoint that the user has reached
     */
     function verify (address learner, uint256 _courseId) public view returns (uint256) {
         require(_courseId < courseIdTracker.current(), "verify: courseId does not exist");
         require(learnerData[_courseId][learner].blockRegistered != 0, "verify: not registered to this course");
         return _verify(learner, _courseId);
     }

    /**
     * @notice                   handles checkpoint verification
     *                           All course are deployed with a given number of checkpoints
     *                           allowing learners to receive a portion of their fees back
     *                           at various stages in the course.
     *
     *                           This is a helper function that checks where a learner is
     *                           in a course and is used by both redeem() and mint() to figure out
     *                           the proper amount required.
     *
     * @param  learner           address of the learner to verify
     * @param  _courseId         course id to verify for the learner
     * @return checkpointReached the checkpoint that the learner has reached.
     */
     function _verify(address learner, uint256 _courseId) internal view returns (uint256 checkpointReached){
         uint256 blocksSinceRegister = block.number - learnerData[_courseId][learner].blockRegistered;
         checkpointReached = blocksSinceRegister / courses[_courseId].checkpointBlockSpacing;
         if (courses[_courseId].checkpoints < checkpointReached){
             checkpointReached = courses[_courseId].checkpoints;
         }
     }

     /**
     * @notice           handles fee redemption into stable
     *                   if a learner is redeeming rather than minting, it means
     *                   they are simply requesting their initial fee back (whether
     *                   they have completed the course or not).
     *                   In this case, it checks what proportion of `fee` (set when
     *                   the course is deployed) must be returned and sends it back
     *                   to the learner.
     *
     *                   Whatever yield they earned is sent to the Kernel Treasury.
     *
     *                   If the learner has not completed the course, it checks that ~6months
     *                   have elapsed since blockRegistered, at which point the full `fee`
     *                   can be returned and the yield sent to the Kernel Treasury.
     *
     * @param  _courseId course id to redeem the fee from
     */
     function redeem(uint256 _courseId) external {
         uint256 shares;
         uint256 learnerShares;
         bool undeployed;
         require(learnerData[_courseId][msg.sender].blockRegistered != 0, "redeem: not a learner");
         (learnerShares, undeployed) = getEligibleAmount(_courseId);
         if (!undeployed){
             shares = vault.withdraw(learnerShares);
             uint256 fee_ = courses[_courseId].fee;
             if (fee_ < shares){
                 stable.safeTransfer(kernelTreasury, shares - fee_);
                 stable.safeTransfer(msg.sender, fee_);
                 emit FeeRedeemed(_courseId, msg.sender, fee_);
             } else {
                 stable.safeTransfer(msg.sender, shares);
                 emit FeeRedeemed(_courseId, msg.sender, shares);
             }
         } else {
             stable.safeTransfer(msg.sender, learnerShares);
             emit FeeRedeemed(_courseId, msg.sender, learnerShares);
         }


     }

    /**
     * @notice           handles learner minting new LEARN
     *                   checks via verify() what proportion of the fee to send to the
     *                   Learning Curve, adds any yield earned to that, and returns all
     *                   the resulting LEARN tokens to the learner.
     *
     *                   This acts as an effective discount for learners (as they receive more LEARN)
     *                   without us having to maintain a whitelist or the like: great for simplicity,
     *                   security and usability.
     *
     * @param  _courseId course id to mint LEARN from
     */
    function mint(uint256 _courseId) external {
        uint256 shares;
        bool undeployed;
        require(learnerData[_courseId][msg.sender].blockRegistered != 0, "mint: not a learner");
        (shares, undeployed) = getEligibleAmount(_courseId);
        if (!undeployed){
            shares = vault.withdraw(shares);
        }
        stable.approve(address(learningCurve), shares);
        learningCurve.mintForAddress(msg.sender, shares);
        emit LearnMintedFromCourse(_courseId, msg.sender, shares);
     }

    /**
     * @notice                gets the amount of funds that a user is eligible for at this timestamp
     * @param  _courseId      course id to mint LEARN from
     * @return eligibleShares the number of shares the user can withdraw
     *                        (if bool undeployed is true will return dai amount, if it is false it will
     *                        return the yDai amount)
     * @return undeployed     if the funds to be redeemed were deployed to yearn
     */
    function getEligibleAmount(uint256 _courseId) internal returns (uint256 eligibleShares, bool undeployed){
        uint256 fee = userDeposit[_courseId][msg.sender];
        require(fee > 0, "no fee to redeem");
        uint256 checkpointReached = verify(msg.sender, _courseId);
        uint256 eligibleAmount = (checkpointReached
            - learnerData[_courseId][msg.sender].checkpointReached)
            * courses[_courseId].fee;
        learnerData[_courseId][msg.sender].checkpointReached = checkpointReached;
        emit CheckpointUpdated(_courseId, checkpointReached, msg.sender);
        if (eligibleAmount > fee){
            eligibleAmount = fee;
        }
        uint256 batchId_ = learnerData[_courseId][msg.sender].yieldBatchId;
        if (batchId_ == batchIdTracker.current()){
            undeployed = true;
            eligibleShares = eligibleAmount;
        } else {
            uint256 temp =  (eligibleAmount * 1e18) / batchTotal[batchId_];
            eligibleShares = (temp * batchYieldTotal[batchId_]) / 1e18;
        }
        userDeposit[_courseId][msg.sender] -= eligibleAmount;
    }

    function getCurrentBatchTotal() external view returns(uint256){
        return batchTotal[batchIdTracker.current()];
    }

    function getBlockRegistered(address learner, uint256 courseId) external view returns (uint256){
        return learnerData[courseId][learner].blockRegistered;
    }

    function getCurrentBatchId() external view returns (uint256){
        return batchIdTracker.current();
    }

    function getNextCourseId() external view returns (uint256){
        return courseIdTracker.current();
    }
}