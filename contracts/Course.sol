"SPDX-License-Identifier: MPL-2.0"

pragma solidity 0.8.3;

/** 
 * @title Kernel Course
 * @dev each course instance controls exactly one course.
 * Anyone can deploy a course, though unclaimed yield is always
 * allocated to the Kernel Treasury to prevent misaligned incentives
 * which might make it attractive to design bad course which people
 * don't complete.
 */
contract Course {
   
    struct Learner {
        uint blockRegistered; // used to decide when a learner can claim their registration fee back
        address learner; // person taking a course
    }
    
    /**
     * @dev handles learner registration
     * 
     * receives DAI
     * allocates DAI to Compound (or yEarn)
     * keeps track of yield earned per leaner (?)
     * 
     */
     function register () public {
         
     }
     
     /**
     * @dev handles checkpoint verification
     * 
     * All course are deployed with a given number of checkpoints
     * allowing learners to receive a portion of their fees back
     * at various stages in the course. 
     * 
     * This is a helper function that verifies (?) where a learner is
     * in a course and is used by both redeem() and mint() to figure out
     * the proper amount required.
     * 
     */
     function verify (address learner) public {
         
     }
     
     /**
     * @dev handles learner redeeming their initial fee
     * 
     * if a learner is redeeming rather than minting, it means
     * they are simply requesting their initial fee back (whether
     * they have completed the course or not).
     * 
     * In this case, it checks what proportion of `fee` (set when 
     * the course is deployed) must be returned and sends it back 
     * to the learner.
     * 
     * Whatever yield they earned is sent to the Kernel Treasury.
     * 
     * If the learner has not completed the course, it checks that ~6months
     * have elapsed since blockRegistered, at which point the full `fee`
     * can be returned and the yield sent to the Kernel Treasury.
     * 
     */
     function redeem () public {
         
     }
     
     /**
     * @dev handles learner minting new LEARN
     * 
     * checks via verify() what proportion of the fee to send to the
     * Learning Curve, adds any yield earned to that, and returns all
     * the resulting LEARN tokens to the learner.
     * 
     * This acts as an effective discount for learners (as they receive more LEARN)
     * without us having to maintain a whitelist or the like: great for simplicity,
     * security and usability.
     * 
     */
     function mint () public {
         
     }
}