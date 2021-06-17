# The Kernel Learning Curve

Smart contracts for free and continuous online learning environments, which nevertheless ensure that course designers are properly rewarded for their work.

## Testing and Development
Note: Test suite is WIP, the current tests only do a full flow success test and does not currently go for full coverage or run scenarios.

This repository uses brownie for testing.
### Dependencies

* [python3](https://www.python.org/downloads/release/python-368/) version 3.6 or greater, python3-dev
* [brownie](https://github.com/iamdefinitelyahuman/brownie) - tested with version [1.14.6](https://github.com/eth-brownie/brownie/releases/tag/v1.14.6)
* [ganache-cli](https://github.com/trufflesuite/ganache-cli) - tested with version [6.12.2](https://github.com/trufflesuite/ganache-cli/releases/tag/v6.12.2)

To run the non-mainnet test suite (no yield functionality)

```
cd learning-curve
brownie test tests -s
```

To run the mainnet test suite (yield functionality):
1. Add a WEB3_INFURA_PROJECT_ID as an [environmental variable](https://eth-brownie.readthedocs.io/en/stable/network-management.html#using-infura)
2. Add an ETHERSCAN_TOKEN as an environmental variable
3. Run the following
```
cd learning-curve
brownie test tests-mainnet --network=mainnet-fork -s
```

## Current gas report
```
KernelFactory <Contract>
   ├─ constructor  -  avg: 1231891  avg (confirmed): 1231891  low: 1231891  high: 1231891
   ├─ mint         -  avg:  102775  avg (confirmed):  102775  low:  102225  high:  103353
   ├─ redeem       -  avg:   87439  avg (confirmed):   87439  low:   87112  high:   87989
   ├─ batchDeposit -  avg:   65530  avg (confirmed):   65530  low:   65530  high:   65530
   ├─ createCourse -  avg:   45858  avg (confirmed):   45858  low:   45858  high:   45858
   └─ register     -  avg:   38673  avg (confirmed):   38673  low:   38673  high:   38673
LearningCurve <Contract>
   ├─ constructor  -  avg: 1321662  avg (confirmed): 1321662  low: 1321662  high: 1321662
   ├─ burn         -  avg:   70047  avg (confirmed):   70047  low:   69838  high:   70198
   ├─ initialise   -  avg:   45179  avg (confirmed):   45179  low:   45179  high:   45179
   └─ approve      -  avg:   29295  avg (confirmed):   29295  low:   29285  high:   29309
```