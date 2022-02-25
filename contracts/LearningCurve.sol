//SPDX-License-Identifier: MPL-2.0
pragma solidity 0.8.0;

import "./ERC20.sol";
import "./PRBMath.sol";
import "./PRBMathUD60x18.sol";
import "./SafeTransferLib.sol";
interface DaiPermit {

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

/**
 * @title  LearningCurve
 * @notice A simple constant product curve that mints LEARN tokens whenever
 *         anyone sends it DAI, or burns LEARN tokens and returns DAI.
 */
contract LearningCurve is ERC20 {

    // the constant product used in the curve
    uint256 public constant k = 10000;
    ERC20 public reserve;
    uint256 public reserveBalance;
    bool initialised;

    event LearnMinted(
        address indexed learner,
        uint256 amountMinted,
        uint256 daiDeposited
    );
    event LearnBurned(
        address indexed learner,
        uint256 amountBurned,
        uint256 daiReturned,
        uint256 e
    );

    constructor(address _reserve) ERC20("Learning Curve", "LEARN", 18) {
        reserve = ERC20(_reserve);
    }

    /**
     * @notice initialise the contract, mainly for maths purposes, requires the transfer of 1 DAI.
     * @dev    only callable once
     */
    function initialise() external {
        require(!initialised, "initialised");
        initialised = true;
        SafeTransferLib.safeTransferFrom(reserve, msg.sender, address(this), 1e18);
        reserveBalance += 1e18;
        _mint(address(this), 10001e18);
    }

    /**
     * @notice handles LEARN mint with an approval for DAI
     */
    function permitAndMint(uint256 _amount, uint256 nonce, uint256 expiry, uint8 v, bytes32 r, bytes32 s) external {
        DaiPermit(address(reserve)).permit(msg.sender, address(this), nonce, expiry, true, v, r, s);
        mint(_amount);
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
        SafeTransferLib.safeTransferFrom(reserve, msg.sender, address(this), _wad);
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
        SafeTransferLib.safeTransferFrom(reserve, msg.sender, address(this), _wad);
        uint256 ln = doLn((((reserveBalance + _wad) * 1e18)) / reserveBalance);
        uint256 learnMagic = k * ln;
        reserveBalance += _wad;
        _mint(learner, learnMagic);
        emit LearnMinted(learner, learnMagic, _wad);
    }

    /**
     * @notice used to burn LEARN and return DAI to the sender.
     * @param  _burnAmount amount of LEARN to burn
     */
    function burn(uint256 _burnAmount) public {
        require(initialised, "!initialised");
        uint256 e = e_calc(_burnAmount);
        uint256 learnMagic = reserveBalance - (reserveBalance * 1e18) / e;
        _burn(msg.sender, _burnAmount);
        reserveBalance -= learnMagic;
        SafeTransferLib.safeTransfer(reserve, msg.sender, learnMagic);
        emit LearnBurned(msg.sender, _burnAmount, learnMagic, e);
    }

    /**
     * @notice Calculates the natural exponent of the inputted value
     * @param  x the number to be used in the natural log calc
     */
    function e_calc(uint256 x) internal pure returns (uint256 result) {
        PRBMath.UD60x18 memory xud = PRBMath.UD60x18({value: x / k});
        result = PRBMathUD60x18.exp(xud).value;
    }

    /**
     * @notice Calculates the natural logarithm of x.
     * @param  x      the number to be used in the natural log calc
     * @return result the natural log of the inputted value
     */
    function doLn(uint256 x) internal pure returns (uint256 result) {
        PRBMath.UD60x18 memory xud = PRBMath.UD60x18({value: x});
        result = PRBMathUD60x18.ln(xud).value;
    }

    /**
     * @notice calculates the amount of reserve received for a burn amount
     * @param  _burnAmount   the amount of LEARN to burn
     * @return learnMagic    the dai receivable for a certain amount of burnt LEARN
     */
    function getPredictedBurn(uint256 _burnAmount)
        external
        view
        returns (uint256 learnMagic)
    {
        uint256 e = e_calc(_burnAmount);
        learnMagic = reserveBalance - (reserveBalance * 1e18) / e;
    }

    /**
     * @notice calculates the amount of LEARN to mint given the amount of DAI requested.
     * @param  reserveAmount the amount of DAI to lock
     * @return learnMagic    the LEARN mintable for a certain amount of dai
     */
    function getMintableForReserveAmount(uint256 reserveAmount)
        external
        view
        returns (uint256 learnMagic)
    {
        uint256 ln = doLn(
            (((reserveBalance + reserveAmount) * 1e18)) / reserveBalance
        );
        learnMagic = k * ln;
    }
}
