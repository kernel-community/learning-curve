//SPDX-License-Identifier: MPL-2.0
pragma solidity 0.8.13;

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