//SPDX-License-Identifier: MPL-2.0
pragma solidity 0.8.13;

interface I_LearningCurve {
    function mintForAddress(address, uint256) external;

    function balanceOf(address) external view returns (uint256);
}