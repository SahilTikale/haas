#Populating and using Recursive HaaS

Base Haas henceforth known as bHaaS
Recursive Haas henceforth known as rHaaS

## Node registration:

Example: 
node name under rHaaS: dummyNode_rHaaS-01
node name under bHaaS: dummyNode-01
Using curl utility:

curl -X PUT http://127.0.0.1:5001/node/dummyNode_rHaaS-01 -d\
	'{ "obm": { "type": "http://schema.massopencloud.org/haas/v0/obm/haas_obm",\
		"bhaas_nodename": "dummyNode-01" }}'

## Node discover:
Location: `haas/examples/node_discover.py`

This script queries the nodes allocated to the project in the base haas.
Then registers those nodes as the free pool of recursive haas.


## Node Power_Cycle:

Example:
node name under rHaaS: dummyNode_rHaaS-01

curl -X POST http://127.0.0.1:5001/node/dummyNode_rHaaS-01/power_cycle/


