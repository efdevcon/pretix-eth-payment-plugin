"""
Create a dictionary `networks_dict` with 
key= network name (e.g. ZkSync, Loopring) and 
value= object of the class implemented in networks.py
"""
import sys, importlib

NETWORKS = ["ZkSync", "Rinkeby"]
networks_dict = {}
networks_module = importlib.import_module("pretix_eth.network.networks")

for class_name in NETWORKS:
    network_class_instance = getattr(networks_module, class_name)()
    networks_dict[class_name] = network_class_instance