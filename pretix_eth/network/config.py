"""
Create a dictionary `networks_dict` with 
key= network name (e.g. ZkSync, Loopring) and 
value= object of the class implemented in networks.py
"""
from .networks import L1, Rinkeby, ZkSync

networks_dict = {
    "L1" : L1(),
    "ZkSync" : ZkSync(),
    "Rinkeby" : Rinkeby() 
}