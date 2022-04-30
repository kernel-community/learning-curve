//SPDX-License-Identifier: MPL-2.0
pragma solidity ^0.8.0;

interface I_Registry {
    function latestVault(address) external view returns (address);
}