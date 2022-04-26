//SPDX-License-Identifier: MPL-2.0
pragma solidity ^0.8.0;

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