"SPDX-License-Identifier: MPL-2.0"

pragma solidity 0.8.3;

/**
 * @title LearningCurve
 * @dev A simple constant product curve that mints LEARN tokens whenever
 * anyone sends it DAI, or burns LEARN tokens and returns DAI.
 */

import "@open-zeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * Consider adding this trick to prevent transfers without socializing gas costs
 * https://github.com/BellwoodStudios/optimism-dai-bridge/blob/master/contracts/l2/dai.sol#L76-L77
 * from https://twitter.com/godsflaw/status/1379101053766017029
 */

contract LearningCurve is ERC20 {

    /**@dev the constant product used in the curve */
    uint product public constant = 10000; 

    /**
    * @dev this method allows anyone to mint LEARN tokens dependent on the
    * amount of DAI they send. 
    *
    * The amount minted depends on the amount of collateral already locked in
    * the curve. The more DAI is locked, the less LEARN gets minted, ensuring 
    * that the price of LEARN increases linearly.
    *
    * Please see: https://docs.google.com/spreadsheets/d/1hjWFGPC_B9D7b6iI00DTVVLrqRFv3G5zFNiCBS7y_V8/edit?usp=sharing
    */
    function mint() public {

    }

    /**
    * @dev same story here, except that an address is passed in which the minted 
    * LEARN is sent to. Necessary to allow for mints directly from a Course, where
    * we want to learner to receive LEARN, not the course contract.
    *
    * Can be used to send DAI from one address and have LEARN returned to another.
    * Is this a problem? I think not...
    */
    function mint(address learner) public {

    }

    /**
    * @dev used to burn LEARN and return DAI to the sender. Uses the same simple
    * curve to calculate the correct amounts.
    */
    function burn() public {

    }

    /**
    * @dev calculates the amount of LEARN to mint or burn given the amount of DAI
    * or LEARN sent to the curve contract.
    *
    * Not internal because anyone should be able to call it to get the price of 
    * LEARN according to the contract. Could be split into 2 different functions
    * though, one internal, one which just returns price for convenience on any FE.
    */
    function calcPrice(uint256 received) view returns(uint256 price) {
        return uint256 price = received / product;
    }
    
}