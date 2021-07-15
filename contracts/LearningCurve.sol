//SPDX-License-Identifier: MPL-2.0
pragma solidity 0.8.4;

import "./PRBMath.sol";
import "./PRBMathUD60x18.sol";

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title  LearningCurve
 * @author kjr217
 * @notice A simple constant product curve that mints LEARN tokens whenever
 *         anyone sends it DAI, or burns LEARN tokens and returns DAI.
 */
contract LearningCurve is ERC20 {
    using SafeERC20 for IERC20;

    // the constant product used in the curve
    uint public constant k = 10000;
    IERC20 public reserve;
    uint256 public reserveBalance;
    bool initialised;

    event LearnMinted(address indexed learner, uint256 amountMinted, uint256 daiDeposited);
    event LearnBurned(address indexed learner, uint256 amountBurned, uint256 daiReturned);
    constructor (address _reserve) ERC20("Learning Curve", "LEARN"){
        reserve = IERC20(_reserve);
    }

    /**
    * @notice initialise the contract, mainly for maths purposes, requires the transfer of 1 DAI.
    * @dev    only callable once
    */
    function initialise() external {
        require(!initialised, "initialised");
        initialised = true;
        reserve.safeTransferFrom(msg.sender, address(this), 1e18);
        reserveBalance += 1e18;
        _mint(address(this), 10001e18);
    }

    /**
    * @notice This method allows anyone to mint LEARN tokens dependent on the
    *         amount of DAI they send.
    *
    *         The amount minted depends on the amount of collateral already locked in
    *         the curve. The more DAI is locked, the less LEARN gets minted, ensuring
    *         that the price of LEARN increases linearly.
    *
    *         Please see: https://docs.google.com/spreadsheets/d/1hjWFGPC_B9D7b6iI00DTVVLrqRFv3G5zFNiCBS7y_V8/edit?usp=sharing
    * @param  _wad amount of Dai to send to the contract
    */
    function mint(uint256 _wad) public {
        require(initialised, "!initialised");
        reserve.safeTransferFrom(msg.sender, address(this), _wad);
        uint256 ln = doLn((((reserveBalance + _wad) * 1e18)) / reserveBalance);
        uint256 learnMagic = k * ln;
        reserveBalance += _wad;
        _mint(msg.sender, learnMagic);
        emit LearnMinted(msg.sender, learnMagic, _wad);
    }

    /**
    * @notice Same as normal mint, except that an address is passed in which the minted
    *         LEARN is sent to. Necessary to allow for mints directly from a Course, where
    *         we want to learner to receive LEARN, not the course contract.
    *
    *         Can be used to send DAI from one address and have LEARN returned to another.
    * @param  learner address of the learner to mint LEARN to
    * @param  _wad    amount of DAI being sent in.
    */
    function mintForAddress(address learner, uint256 _wad) public {
        require(initialised, "!initialised");
        reserve.safeTransferFrom(msg.sender, address(this), _wad);
        uint256 ln = doLn((((reserveBalance + _wad) * 1e18)) / reserveBalance);
        uint256 learnMagic = k * ln;
        reserveBalance += _wad;
        _mint(learner, learnMagic);
        emit LearnMinted(learner, learnMagic, _wad);
    }

    /**
    * @notice used to burn LEARN and return DAI to the sender. The amount of dai that the burner wants
    *         to be received should be sent in, this is because providing a Learn and converting to DAI
    *         is complex mathematically.
    * @param  _daiToReceive amount of dai the burner would like to receive
    */
    function burn(uint256 _daiToReceive) public {
        require(initialised, "!initialised");
        uint256 ln = doLn((reserveBalance * 1e18) / (reserveBalance - _daiToReceive));
        uint256 learnMagic = k * ln;
        _burn(msg.sender, learnMagic);
        reserveBalance -= _daiToReceive;
        reserve.safeTransfer(msg.sender, _daiToReceive);
        emit LearnBurned(msg.sender, learnMagic, _daiToReceive);
    }

    /**
    * @notice Calculates the natural logarithm of x.
    * @param  x the number to be magic'd
    */
    function doLn(uint256 x) internal pure returns (uint256 result) {
        PRBMath.UD60x18 memory xud = PRBMath.UD60x18({ value: x });
        result = PRBMathUD60x18.ln(xud).value;
    }

    /**
    * @notice calculates the amount of LEARN to burn given the amount of DAI requested.
    * @param  reserveAmount the amount of DAI to receive
    */
    function getBurnableForReserveAmount(uint256 reserveAmount) external view returns (uint256 learnMagic){
        uint256 ln = doLn((reserveBalance * 1e18) / (reserveBalance - reserveAmount));
        learnMagic = k * ln;
    }

    /**
    * @notice calculates the amount of LEARN to mint given the amount of DAI requested.
    * @param  reserveAmount the amount of DAI to lock
    */
    function getMintableForReserveAmount(uint256 reserveAmount) external view returns (uint256 learnMagic){
        uint256 ln = doLn((((reserveBalance + reserveAmount) * 1e18)) / reserveBalance);
        learnMagic = k * ln;
    }

}