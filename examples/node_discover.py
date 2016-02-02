"""Node Discover: This script will fetch the nodes allocated

to the parent project in Base Haas and populate it into
recursive haas using the node_register call.

The script can fetch the endpoint to base haas from the
enviornment variables.

The script takes as an argument relative path to the haas.cfg
that contains the endpoint to recursive haas.
"""

import argparse
import requests
import json
import sys

from haas.config import cfg, load


parser = argparse.ArgumentParser()
parser.add_argument( "-r","--rhaascfg", action='store',\
        dest='rel_path2cfg', help="give relaive path to the haas.cfg\
        pointing to recursive haas server")



#print args.rel_path2cfg
if len(sys.argv)<2:
    parser.print_usage()
    sys.exit(1)

args = parser.parse_args()

#Importing the base haas endpoint
load(filename=args.rel_path2cfg)
bhaas = cfg.get('client', 'endpoint')
base_proj = cfg.get('recursive', 'project')

#Importing the recursive haas endpoint
load(filename='haas.cfg')
rhaas = cfg.get('client', 'endpoint')

#Fetching nodes assigned to the project at base haas.
url= bhaas+"/project/"+base_proj+"/nodes"
resp = requests.get(url)
stat = resp.status_code

print ("Following Nodes are available with %s" %base_proj)
print resp.text


print ("Populating recursive HaaS")
for bnode in resp.json():
    url2 = rhaas+"/node/rhaas_"+bnode
    payload = {"obm": {"type": "http://schema.massopencloud.org/haas/v0/obm/haas_obm",
            "bhaas_nodename": bnode }
            }
    populate = requests.put(url2, data=json.dumps(payload))
    if ( populate.status_code != 200 ):
        print ("Error: Failed to add %s" % bnode)
        print ("Make sure it was not already added ")
        print (" ")
    else:
        print ("Successfully added node %s as rhaas_%s" % (bnode, bnode))
        print (" ")

