//SPDX-License-Identifier: MPL-2.0
pragma solidity 0.8.13;

interface I_Registry {
    function latestVault(address) external view returns (address);
}