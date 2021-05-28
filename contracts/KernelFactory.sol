"SPDX-License-Identifier: MPL-2.0"

pragma solidity 0.8.3;

/**
 * @title Kernel Factory
 * @dev deploys new courses
 * 
 * questions: best to use a traditional facotry, or the delegatecall pattern, or the diamond standard?
 */

import "@openzeppelin/contracts/proxy/Clones.sol";

contract KernelFactory {

    Course[] public courseAddresses;
    event CourseCreated();
    
    /**
     * @dev
     * 
     * Creates new course given a fee amount (in DAI) and a number of checkpoints
     * 
     * TODO: refactor this to use the Open Zeppelin Clone library instead.
     * 
     */
    function createCourse(uint256 fee, uint256 checkpoints) external {
        Course course = new Course(fee, checkpoints);

        courseAddresses.push(course);
        emit CourseCreated(course);
    }

    function getCourses() external view returns (Course[] memory) {
        return courseAddresses;
    }
}