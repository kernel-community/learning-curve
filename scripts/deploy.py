from ape import *
from ape import Contract, accounts, BasicERC20


def main():
    deployer = accounts.load('dep')
    token = BasicERC20.at("0x5592EC0cfb4dbc12D3aB100b257153436a1f0FEa")
    lc = Contract.from_explorer("0x26A1EcDeCBeeE657e9C21273544e555F74b11d54")
    token.approve(lc, 1e18, sender=deployer)
    lc.initialise(sender=deployer)