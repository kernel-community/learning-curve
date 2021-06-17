pragma solidity 0.8.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/*
ERC20 wrapper used for testing. Any account can call mint()
*/

contract BasicERC20 is ERC20 {
    constructor(string memory name_, string memory symbol_)
        public
        ERC20(name_, symbol_)
    {}

    function mint(uint256 amount) public {
        _mint(msg.sender, amount);
    }
}
