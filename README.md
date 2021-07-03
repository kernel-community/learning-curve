# The Kernel Learning Curve

Smart contracts for free and continuous online learning environments, which nevertheless ensure that course designers are properly rewarded for their work.

## Testing and Development
Note: Test suite is WIP, the current tests only do a full flow success test and does not currently go for full coverage or run scenarios.

This repository uses brownie for testing.
### Dependencies

* [python3](https://www.python.org/downloads/release/python-368/) version 3.6 or greater, python3-dev
* [brownie](https://github.com/iamdefinitelyahuman/brownie) - tested with version [1.14.6](https://github.com/eth-brownie/brownie/releases/tag/v1.14.6)
* [ganache-cli](https://github.com/trufflesuite/ganache-cli) - tested with version [6.12.2](https://github.com/trufflesuite/ganache-cli/releases/tag/v6.12.2)
* [numpy](https://pypi.org/project/numpy/) - used for testing purposes


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
   ├─ constructor                 -  avg: 1518979  avg (confirmed): 1518979  low: 1518979  high: 1518979
   ├─ redeem                      -  avg:   58728  avg (confirmed):   60658  low:   22563  high:   92004
   ├─ mint                        -  avg:   57180  avg (confirmed):   98215  low:   22548  high:  129048
   ├─ createCourse                -  avg:   44654  avg (confirmed):   45858  low:   21981  high:   45858
   ├─ register                    -  avg:   37747  avg (confirmed):   38531  low:   22515  high:   38531
   ├─ getUserCourseFundsRemaining -  avg:   32302  avg (confirmed):   32302  low:   32302  high:   32314
   ├─ getUserCourseEligibleFunds  -  avg:   29595  avg (confirmed):   29595  low:   27765  high:   31489
   ├─ verify                      -  avg:   26572  avg (confirmed):   26701  low:   22852  high:   26713
   ├─ batchDeposit                -  avg:   63394  avg (confirmed):   66838  low:   28978  high:   66838
   ├─ getCurrentBatchTotal        -  avg:   23050  avg (confirmed):   23050  low:   23050  high:   23050
   └─ getNextCourseId             -  avg:   22172  avg (confirmed):   22172  low:   22172  high:   22172
LearningCurve <Contract>
   ├─ constructor                 -  avg: 1315019  avg (confirmed): 1315019  low: 1315019  high: 1315019
   ├─ initialise                  -  avg:   55660  avg (confirmed):   59445  low:   22257  high:   59445
   ├─ burn                        -  avg:   53597  avg (confirmed):   53597  low:   48292  high:   54291
   ├─ mint                        -  avg:   46669  avg (confirmed):   46669  low:   46500  high:   46871
   ├─ getMintableForReserveAmount -  avg:   30090  avg (confirmed):   30090  low:   24477  high:   30476
   ├─ getBurnableForReserveAmount -  avg:   29568  avg (confirmed):   29568  low:   24430  high:   30429
   ├─ approve                     -  avg:   29299  avg (confirmed):   29299  low:   29297  high:   29309
   ├─ balanceOf                   -  avg:   22725  avg (confirmed):   22725  low:   22725  high:   22737
   ├─ reserveBalance              -  avg:   22181  avg (confirmed):   22181  low:   22181  high:   22181
   └─ totalSupply                 -  avg:   22160  avg (confirmed):   22160  low:   22160  high:   22160
```