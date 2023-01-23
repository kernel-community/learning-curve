# The Kernel Learning Curve

Smart contracts for free and continuous online learning environments, which nevertheless ensure that course designers are properly rewarded for their work.

## Testing and Development

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
DeSchool <Contract>
   ├─ constructor       -  avg: 2722866  avg (confirmed): 2722866  low: 2722866  high: 2722866
   ├─ permitAndRegister -  avg:  146645  avg (confirmed):  146645  low:  146645  high:  146645
   ├─ createCourse      -  avg:  119368  avg (confirmed):  123066  low:   23221  high:  134617
   ├─ mint              -  avg:   90247  avg (confirmed):  113111  low:   22621  high:  116626
   ├─ register          -  avg:   59684  avg (confirmed):   62112  low:   22511  high:   86669
   └─ redeem            -  avg:   57139  avg (confirmed):   68031  low:   22564  high:   70531
LearningCurve <Contract>
   ├─ constructor       -  avg: 1866796  avg (confirmed): 1866796  low: 1866796  high: 1866796
   ├─ permitAndMint     -  avg:  122563  avg (confirmed):  122563  low:  122563  high:  122563
   ├─ initialise        -  avg:  119427  avg (confirmed):  132872  low:   22214  high:  132872
   ├─ burn              -  avg:   65850  avg (confirmed):   65850  low:   65642  high:   66346
   ├─ mint              -  avg:   61697  avg (confirmed):   61697  low:   61356  high:   62166
   └─ approve           -  avg:   44103  avg (confirmed):   44103  low:   44101  high:   44113
```
