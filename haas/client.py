# Copyright 2013-2015 Massachusetts Open Cloud Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the
# License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied.  See the License for the specific language
# governing permissions and limitations under the License.

"""This module implements the HaaS client library."""
from haas import config
from haas.config import cfg
from error_clientlib import *

from haas.rest import APIError, ServerError
    # Do we need ServerError ? It is not supposed to know 
    # what happens on the server side
import requests
import os
import urllib
import json


#Return Codes:
""" Following is how return codes should be interpreted:
    -1  :       Operation Failed
    1   :       Operation was successful
    2   :       Duplication error. Entity already exists
    3   :

"""



class Haas:
    """Client class for making Haas API calls.
    Note that this client library is not yet complete and will be added to as
    needed.

    Example:
        h = Haas(endpoint="http://127.0.0.1:5000")
        h.node_connect_network("node-2000", "eth1", "production-network",
        "vlan/native")

    Errors are thrown when receiving HTTP status_codes from the HaaS server
    that are not in the [200,300) range
    """

    def __init__(self, endpoint=None):
        """Initiatlize an instance.

        If endpoint is None, use the endpoint specification from:
            1) The HAAS_ENDPOINT env variable or
            2) Take the endpoint from [client] endpoint

        Exceptions:
            LookupError - no endpoint could be found
        """
        config.load(filename='haas.cfg')
        if endpoint != None:
            self.endpoint = endpoint
        else:
            self.endpoint = os.environ.get('HAAS_ENDPOINT')
            if self.endpoint is None:
                try:
                    self.endpoint = cfg.get('client', 'endpoint')
                except LookupError:
                    print("no endpoint found")

    def object_url(self, *args):
        """Append the arguments to the endpoint URL"""
        url = self.endpoint
        for arg in args:
            url += '/' + urllib.quote(arg,'')
        return url

    def user_create(self, username, password):
        """Create a user <username> with password <password>."""
        url = self.object_url('user', username)
        data = {'password': password}
        r = requests.put(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return                    #Operation successful
        elif (r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )    #Username already exists
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed

    def network_create(self, network, creator, access, net_id):
        """Create a link-layer <network>. See docs/networks.md for details."""
        url = self.object_url('network', network)
        data = {'creator': creator, 'access': access, 'net_id': net_id}
        r = requests.put(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed

    def network_create_simple(self, network, project):
        """Create <network> owned by project.  Specific case of network_create"""
        url = self.object_url('network', network)
        data = {'creator': project, 'access': project, 'net_id': ""}
        r = requests.put(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return                    #Operation successful
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" ) #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed

    def network_delete(self, network):
        url = self.object_url('network', network)
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: Entity does not exist ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! " )     #Operation Failed 

    def user_delete(self, user):
        url = self.object_url('user', user)
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: Entity does not exist ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! " )     #Operation Failed 

    def list_projects(self):
        url = self.object_url('projects')
        r = requests.get(url)

        if(200 <= r.status_code < 300):
            return r.json
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! " )     #Operation Failed 

    def project_add_user(self, project, username):
        """Add <user> to <project>"""
        url = self.object_url('project', project, 'add_user')
        data = {'user': username}
        r = requests.post(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return                    #Operation successful
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" ) #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def project_remove_user(self, project, username):
        """Remove <user> from <project> """
        url = self.object_url('project', project, 'remove_user')
        data ={'user': username}
        r = requests.post(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return                    #Operation successful
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed

    def project_create(self, project):
        """ Create a <project>"""
        url = self.object_url('project', project)
        r = requests.put(url)

        if (200 <= r.status_code < 300):
            return                    #Operation successful
        elif (r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )    #Username already exists
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def project_delete(self,project):
        url = self.object_url('project', project)
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: Entity does not exist ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! " )     #Operation Failed 







#    def node_connect_network(self, node, nic, network, channel="vlan/native"):
#        """Connect <node> to <network> on given <nic> and <channel>.
#        If no channel is specified, the action is applied to the native vlan.
#        Returns text sent from server"""
#
#        url = object_url('node', node, 'nic', nic, 'connect_network')
#        data={'network': network, 'channel': channel}
#        r = requests.post(url, data=json.dumps(data))
#
#        if not (r.status_code >= 200 and r.status_code < 300):
#            # We weren't successful. Throw an exception
#            if r.status_code >= 400 and r.status_code < 500:
#                raise APIError(r.text)
#            elif r.status_code >= 500 and r.status_code < 600:
#                raise ServerError(r.text)
#            else:
#                raise Exception(r.text)
#
#        #TODO: when async statuses are incorporated, we could create a status
#        #      class, or just return this.
#        return r.text

#    def list_free_nodes(self):
#        url = self.object_url('free_nodes')
#        url = "http://127.0.0.1:5000/free_nodes"
#        r = requests.get(url)
#        return r.json



    def headnode_create(self, headnode, project, base_img):
        """Create a <headnode> in a <project> with <base_img>"""
        url = self.object_url('headnode', headnode)
        data={'project': project, 'base_img': base_img}
        r = requests.put(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def headnode_delete(self, headnode):
        """Delete <headnode>"""
        url = self.object_url('headnode', headnode)
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def project_connect_node(self, project, node):
        """Connect <node> to <project>"""
        url = self.object_url('project', project, 'connect_node')
        data = {'node': node}
        r = requests.post(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def project_detach_node(self, project, node):
        """Detach <node> from <project>"""
        url = self.object_url('project', project, 'detach_node')
        data={'node': node}
        r = requests.post(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def headnode_start(self, headnode):
        """Start <headnode>"""
        url = self.object_url('headnode', headnode, 'start')
        r = requests.post(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def headnode_stop(self, headnode):
        """Stop <headnode>"""
        url = self.object_url('headnode', headnode, 'stop')
        r = requests.post(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def node_register(self, node, ipmi_host, ipmi_user, ipmi_pass):
        """Register a node named <node>, with the given ipmi host/user/password"""
        url = self.object_url('node', node)

        data={'ipmi_host': ipmi_host, 'ipmi_user': ipmi_user, 'ipmi_pass': ipmi_pass}
        r = requests.put(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def node_delete(self, node):
        """Delete <node>"""
        url = self.object_url('node', node)
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def node_power_cycle(self, node):
        """Power cycle <node>"""
        url = self.object_url('node', node, 'power_cycle')
        r = requests.post(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def node_register_nic(self, node, nic, macaddr):
        """Register existence of a <nic> with the given <macaddr> on the given <node>"""
        url = self.object_url('node', node, 'nic', nic)
        data={'macaddr':macaddr}
        r = requests.put(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def node_delete_nic(self, node, nic):
        """Delete a <nic> on a <node>"""

        url = self.object_url('node', node, 'nic', nic)
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def headnode_create_hnic(self, headnode, nic):
        """Create a <nic> on the given <headnode>"""

        url = self.object_url('headnode', headnode, 'hnic', nic)
        r = requests.put(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def headnode_delete_hnic(self, headnode, nic):
        """Delete a <nic> on a <headnode>"""

        url = self.object_url('headnode', headnode, 'hnic', nic)
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


#       def node_connect_network(self, node, nic, network, channel):
#        """Connect <node> to <network> on given <nic> and <channel>"""
#        ret = h.node_connect_network(node, nic, network, channel)
#        print(ret)
#        # TODO: do something nice for exceptions. Maybe a wrapper like is used by
#        # r = requests.post()


    def node_detach_network(self, node, nic, network):
        """Detach <node> from the given <network> on the given <nic>"""

        url = self.object_url('node', node, 'nic', nic, 'detach_network')
        data={'network': network}
        r = requests.post(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def headnode_connect_network(self, headnode, nic, network):
        """Connect <headnode> to <network> on given <nic>"""

        url = self.object_url('headnode', headnode, 'hnic', nic, 'connect_network')
        data={'network':network}
        r = requests.post(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed

    def headnode_detach_network(self, headnode, hnic):
        """Detach <headnode> from the network on given <nic>"""

        url = self.object_url('headnode', headnode, 'hnic', hnic, 'detach_network')
        r = requests.post(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def port_register(self, port):
        """Register a <port> on a switch"""

        url = self.object_url('port', port)
        r = requests.put(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def port_delete(self, port):
        """Delete a <port> on a switch"""

        url = self.object_url('port', port)
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def port_connect_nic(self, port, node, nic):
        """Connect a <port> on a switch to a <nic> on a <node>"""

        url = self.object_url('port', port, 'connect_nic')
        data={'node': node, 'nic': nic}
        r = requests.post(url, data=json.dumps(data))

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def port_detach_nic(self, port):
        """Detach a <port> on a switch from whatever's connected to it"""
        url = self.object_url('port', port, 'detach_nic')
        r = requests.post(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def list_free_nodes(self):
        """List all free nodes"""
        url = self.object_url('free_nodes')
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return r.json
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def list_project_nodes(self, project):
        """List all nodes attached to a <project>"""
        url = self.object_url('project', project, 'nodes')
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return r.json
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def list_project_networks(self, project):
        """List all networks attached to a <project>"""
        url = self.object_url('project', project, 'networks')
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return r.json
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def show_network(self, network):
        """Display information about <network>"""
        url = self.object_url('network', network)
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return r.json
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def show_node(self, node):
        """Display information about a <node>"""
        url = self.object_url('node', node)
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return r.json
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def list_project_headnodes(self, project):
        """List all headnodes attached to a <project>"""
        url = self.object_url('project', project, 'headnodes')
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return r.json
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def show_headnode(self, headnode):
        """Display information about a <headnode>"""
        url = self.object_url('headnode', headnode)
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return r.json
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def list_headnode_images(self):
        """Display registered headnode images"""
        url = self.object_url('headnode_images')
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return r.json
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def show_console(self, node):
        """Display console log for <node>"""
        url = self.object_url('node', node, 'console')
        r = requests.get(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def start_console(self, node):
        """Start logging console output from <node>"""
        url = self.object_url('node', node, 'console')
        r = requests.put(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed


    def stop_console(self, node):
        """Stop logging console output from <node> and delete the log"""
        url = self.object_url('node', node, 'console')
        r = requests.delete(url)

        if (200 <= r.status_code < 300):
            return
        elif(r.status_code == 409):
            raise DuplicateName("FAILURE: Name already exists" )      #Network-name already exists
        elif(r.status_code == 404):
            raise IncompleteDependency("FAILURE: does not meet dependency ")
        elif(500 <= r.status_code):
            raise ServersideError("FAILURE: Server failed to process the request ")
        else:
            raise UnknownError("FAILURE: Contact the HaaS Admin. Unknown error occured !!! ")      #Operation failed

