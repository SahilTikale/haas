# Copyright 2013-2014 Massachusetts Open Cloud Contributors
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

"""This module implements the HaaS command line tool."""
from haas import config, server
from haas.config import cfg
from haas.client import Haas
from haas.error_clientlib import *

import inspect
import json
import os
import requests
import sys
import urllib
import schema

from functools import wraps

command_dict = {}
usage_dict = {}
MIN_PORT_NUMBER = 1
MAX_PORT_NUMBER = 2**16 - 1

# Handle to the client library
h = Haas()

def cmd(f):
    """A decorator for CLI commands.

    This decorator firstly adds the function to a dictionary of valid CLI
    commands, secondly adds exception handling for when the user passes the
    wrong number of arguments, and thirdly generates a 'usage' description and
    puts it in the usage dictionary.
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except TypeError:
            # TODO TypeError is probably too broad here.
            sys.stderr.write('Invalid arguements.  Usage:\n')
            help(f.__name__)
    command_dict[f.__name__] = wrapped
    def get_usage(f):
        args, varargs, _, _ = inspect.getargspec(f)
        showee = [f.__name__] + ['<%s>' % name for name in args]
        args = ' '.join(['<%s>' % name for name in args])
        if varargs:
            showee += ['<%s...>' % varargs]
        return ' '.join(showee)
    usage_dict[f.__name__] = get_usage(f)
    return wrapped


def check_status_code(response):
    if response.status_code < 200 or response.status_code >= 300:
        sys.stderr.write('Unexpected status code: %d\n' % response.status_code)
        sys.stderr.write('Response text:\n')
        sys.stderr.write(response.text + "\n")
    else:
        sys.stdout.write(response.text + "\n")

# TODO: This function's name is no longer very accurate.  As soon as it is
# safe, we should change it to something more generic.
def object_url(*args):
    # Prefer an environmental variable for getting the endpoint if available.
    url = os.environ.get('HAAS_ENDPOINT')
    if url is None:
        url = cfg.get('client', 'endpoint')

    for arg in args:
        url += '/' + urllib.quote(arg,'')
    return url

def do_request(fn, url, data={}):
    """Helper function for making HTTP requests against the API.

    Arguments:

        `fn` - a function from the requests library, one of requests.put,
               requests.get...
        `url` - The url to make the request to
        `data` - the body of the request.

    If the environment variables HAAS_USERNAME and HAAS_PASSWORD are
    defined, The request will use HTTP basic auth to authenticate, with
    the given username and password.
    """
    kwargs = {}
    username = os.getenv('HAAS_USERNAME')
    password = os.getenv('HAAS_PASSWORD')
    if username is not None and password is not None:
        kwargs['auth'] = (username, password)
    return check_status_code(fn(url, data=data, **kwargs))

def do_put(url, data={}):
    return do_request(requests.put, url, data=json.dumps(data))

def do_post(url, data={}):
    return do_request(requests.post, url, data=json.dumps(data))

def do_get(url):
    return do_request(requests.get, url)

def do_delete(url):
    return do_request(requests.delete, url)

@cmd
def serve(port):
    try:
        port = schema.And(schema.Use(int), lambda n: MIN_PORT_NUMBER <= n <= MAX_PORT_NUMBER).validate(port)
    except schema.SchemaError:
	sys.exit('Error: Invaid port. Must be in the range 1-65535.')
    except Exception as e:
	sys.exit('Unxpected Error!!! \n %s' % e)

    """Start the HaaS API server"""
    if cfg.has_option('devel', 'debug'):
        debug = cfg.getboolean('devel', 'debug')
    else:
        debug = False
    # We need to import api here so that the functions within it get registered
    # (via `rest_call`), though we don't use it directly:
    from haas import model, api, rest
#    server.api_server_init() # Copied from b4cli.py
    server.init(stop_consoles=True)
    rest.serve(port, debug=debug)


@cmd
def serve_networks():
    """Start the HaaS networking server"""
    from haas import model, deferred
    from time import sleep
#    server.init()
    server.register_drivers()
    server.validate_state()
    model.init_db()
    while True:
        # Empty the journal until it's empty; then delay so we don't tight
        # loop.
        while deferred.apply_networking():
            pass
        sleep(2)

@cmd
def user_create(username, password, is_admin):
    """Create a user <username> with password <password>.

    <is_admin> may be either "admin" or "regular", and determines whether
    the user has administrative priveledges.
    """
    url = object_url('/auth/basic/user', username)
    if is_admin not in ('admin', 'regular'):
        raise TypeError("is_admin must be either 'admin' or 'regular'")
    do_put(url, data={
        'password': password,
        'is_admin': is_admin == 'admin',
    })

@cmd
def network_create(network, creator, access, net_id):
    """Create a link-layer <network>.  See docs/networks.md for details
            --          --              --              --
        network: Any string to name the network
        creator: Either Project name, or  string "admin"
         access : Either Project name, or  null (eg. "")
         net-id : Either a vlan-id, or let HaaS assign one (eg. "")

         Eg: haas network_create prod-network01 admin "" "" [or]
             haas network_create prod-network02 admin proj-01 ""
    """
    try: 
        ret = h.network_create(network, creator, access, net_id)
        print "    SUCCESS: Network %s created " % network
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message



@cmd
def network_create_simple(network, project):
    """Create <network> owned by project.  Specific case of network_create"""

    try:
        ret = h.network_create_simple(network, project) 
        print "    SUCCESS: Network %s created " % network
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message



@cmd
def network_delete(network):
    """Delete a <network>"""

    try:
        ret = h.network_delete(network)
        print "Success: network %s deleted. " % network
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

#    url = object_url('network', network)
#    do_delete(url)

@cmd
def user_delete(username):
    """Delete the user <username>"""
    url = object_url('/auth/basic/user', username)
    do_delete(url)

@cmd
def list_projects():
    """List all projects"""
    try:
        ret = h.list_projects()
        print "Success: Total %d projects found: " % len(ret())
#        print type(ret())
        for i in ret():
            print i

    except UnknownError as e:
        print e.message

#    url = object_url('projects')
#    do_get(url)

@cmd
def user_add_project(user, project):
    """Add <user> to <project>"""
    url = object_url('/auth/basic/user', user, 'add_project')
    do_post(url, data={'project': project})

@cmd
def user_remove_project(user, project):
    """Remove <user> from <project>"""
    url = object_url('/auth/basic/user', user, 'remove_project')
    do_post(url, data={'project': project})

@cmd
def project_create(project):
    """Create a <project>"""
    try:
        ret = h.project_create(project)
        print "    SUCCESS: Project %s created " % project
    except DuplicateName as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def project_delete(project):
    """Delete <project>"""
    try:
        ret = h.project_delete(project)
        print "Success: project %s deleted. " % project
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

#    url = object_url('project', project)
#    do_delete(url)

@cmd
def headnode_create(headnode, project, base_img):
    """Create a <headnode> in a <project> with <base_img>"""

    try:
        ret = h.headnode_create(headnode, project, base_img)
        print "Success: Headnode Created for project  %s " % project
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message


@cmd
def headnode_delete(headnode):
    """Delete <headnode>"""

    try:
        ret = h.headnode_delete(headnode)
        print "Success: Headnode %s deleted." % project
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def project_connect_node(project, node):
    """Connect <node> to <project>"""

    try:
        ret = h.project_connect_node(project, node)
        print "Success: Node %s connected to project %s " % (node, project)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def project_detach_node(project, node):
    """Detach <node> from <project>"""

    try:
        ret = h.project_detach_node(project, node)
        print "Success: Node %s detached from  project %s " % (node, project)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def headnode_start(headnode):
    """Start <headnode>"""

    try:
        ret = h.headnode_start(headnode)
        print "Success: Headnode %s started" % (headnode)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def headnode_stop(headnode):
    """Stop <headnode>"""

    try:
        ret = h.headnode_stop(headnode)
        print "Success: Headnode %s stopped " % (headnode)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message
    url = object_url('headnode', headnode, 'stop')
    do_post(url)

@cmd
def node_register(node, subtype, *args):
    """Register a node named <node>, with the given type
	if obm is of type: ipmi then provide arguments
	"ipmi", <hostname>, <ipmi-username>, <ipmi-password>
    """
    obm_api = "http://schema.massopencloud.org/haas/v0/obm/"
    obm_types = [ "ipmi", "mock" ]
    #Currently the classes are hardcoded
    #In principle this should come from api.py
    #In future an api call to list which plugins are active will be added.


    if subtype in obm_types:
	if len(args) == 3:
	    obminfo = {"type": obm_api+subtype, "host": args[0],
	    		"user": args[1], "password": args[2]
	    	      }
	else:
	    sys.stderr.write('ERROR: subtype '+subtype+' requires exactly 3 arguments\n')
	    sys.stderr.write('<hostname> <ipmi-username> <ipmi-password>\n')
	    return
    else:
	sys.stderr.write('ERROR: Wrong OBM subtype supplied\n')
	sys.stderr.write('Supported OBM sub-types: ipmi, mock\n')
	return

    url = object_url('node', node)
    do_put(url, data={"obm": obminfo})

@cmd
def node_delete(node):
    """Delete <node>"""

    try:
        ret = h.node_delete(node)
        print "Success: Node %s detached from  project %s " % (node)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def node_power_cycle(node):
    """Power cycle <node>"""

    try:
        ret = h.node_power_cycle(node)
        print "Success: Node %s " % (node)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def node_power_off(node):
    """Power off <node>"""
    url = object_url('node', node, 'power_off')
    do_post(url)

@cmd
def node_register_nic(node, nic, macaddr):
    """Register existence of a <nic> with the given <macaddr> on the given <node>"""

    try:
        ret = h.node_register_nic(node, nic, macaddr)
        print "Success: Nic %s registerd with node %s " % (nic, node)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def node_delete_nic(node, nic):
    """Delete a <nic> on a <node>"""

    try:
        ret = h.node_delete_nic(node, nic)
        print "Success: Nic deleted from node %s" % (node)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def headnode_create_hnic(headnode, nic):
    """Create a <nic> on the given <headnode>"""

    try:
        ret = h.headnode_create_hnic(headnode, nic)
        print "Success: Nic created for Headnode %s" % (headnode)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def headnode_delete_hnic(headnode, nic):
    """Delete a <nic> on a <headnode>"""

    try:
        ret = h.headnode_delete_hnic(headnode, nic)
        print "Success: Nic deleted from headnode %s " % (headnode)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def node_connect_network(node, nic, network, channel):
    """Connect <node> to <network> on given <nic> and <channel>"""

    try:
        ret = h.node_connect_network(node, nic, network, channel)
        print "Success: Node %s connected to network %s via %s nic " % (node,network, nic)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def node_detach_network(node, nic, network):
    """Detach <node> from the given <network> on the given <nic>"""

    try:
        ret = h.node_detach_network(node, nic, network)
        print "Success: Node %s detached from  network %s " % (node, network)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def headnode_connect_network(headnode, nic, network):
    """Connect <headnode> to <network> on given <nic>"""

    try:
        ret = h.headnode_connect_network(headnode, nic, network)
        print "Success: Headnode %s connected to network %s " % (headnode,network)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def headnode_detach_network(headnode, hnic):
    """Detach <headnode> from the network on given <nic>"""

    try:
        ret = h.headnode_detach_network(headnode, hnic)
        print "Success: Headnode %s detached from  network %s " % (headnode,network)
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def switch_register(switch, subtype, *args):
    """Register a switch with name <switch> and
    <subtype>, <hostname>, <username>,  <password>
    eg. haas switch_register mock03 mock mockhost01 mockuser01 mockpass01
    """
    switch_api = "http://schema.massopencloud.org/haas/v0/switches/"

@cmd
def switch_register(switch, subtype, *args):
    """Register a switch with name <switch> and
    <subtype>, <hostname>, <username>,  <password>
    eg. haas switch_register mock03 mock mockhost01 mockuser01 mockpass01

    FIXME: current design needs to change. CLI should not know about every backend.
    ideally, this should be taken care of in the driver itself or 
    client library (work-in-progress) should manage it.
    """
    switch_api = "http://schema.massopencloud.org/haas/v0/switches/"
    if subtype == "nexus":
        if len(args) == 4:
            switchinfo = { "type": switch_api+subtype, "hostname": args[0],
                        "username": args[1], "password": args[2], "dummy_vlan": args[3] }
        else:
            sys.stderr.write('ERROR: subtype '+subtype+' requires exactly 4 arguments\n')
            sys.stderr.write('<hostname> <username> <password> <dummy_vlan_no>\n')
            return
    elif subtype == "mock":
        if len(args) == 3:
            switchinfo = { "type": switch_api+subtype, "hostname": args[0],
                        "username": args[1], "password": args[2] }
        else:
            sys.stderr.write('ERROR: subtype '+subtype+' requires exactly 3 arguments\n')
            sys.stderr.write('<hostname> <username> <password>\n')
            return
    elif subtype == "powerconnect55xx":
        if len(args) == 3:
            switchinfo = { "type": switch_api+subtype, "hostname": args[0],
                        "username": args[1], "password": args[2] }
        else:
            sys.stderr.write('ERROR: subtype '+subtype+' requires exactly 3 arguments\n')
            sys.stderr.write('<hostname> <username> <password>\n')
            return
    else:
        sys.stderr.write('ERROR: Invalid subtype supplied\n')
        return
    url = object_url('switch', switch)
    do_put(url, data=switchinfo)

@cmd
def switch_delete(switch):
    """Delete a <switch> """
    url = object_url('switch', switch)
    do_delete(url)


@cmd
def port_register(switch, port):
    """Register a <port> with <switch> """
    url = object_url('switch', switch, 'port', port)
    do_put(url)

@cmd
def port_delete(switch, port):
    """Delete a <port> from a <switch>"""
    url = object_url('switch', switch, 'port', port)
    do_delete(url)

@cmd
def port_connect_nic(switch, port, node, nic):
    """Connect a <port> on a <switch> to a <nic> on a <node>"""
    url = object_url('switch', switch, 'port', port, 'connect_nic')
    do_post(url, data={'node': node, 'nic': nic})

@cmd
def port_detach_nic(switch, port):
    """Detach a <port> on a <switch> from whatever's connected to it"""
    url = object_url('switch', switch, 'port', port, 'detach_nic')
    do_post(url)

@cmd
def list_free_nodes():
    """List all free nodes"""

    try:
        ret = h.list_free_nodes()
        print "SUCCESS: Total free nodes available with HaaS: %s " % len(ret())
        for i in ret():
            print " %s" % i

    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def list_project_nodes(project):
    """List all nodes attached to a <project>"""

    try:
        ret = h.list_project_nodes(project)
        print "SUCCESS: Total nodes allocated to Project %s : %s " % (project,len(ret()))
        for i in ret():
            print " %s" % i
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def list_project_networks(project):
    """List all networks attached to a <project>"""

    try:
        ret = h.list_project_networks(project)
        print "SUCCESS: Total networks with Project %s: %s " % (project,len(ret()))
        for i in ret():
            print " %s" % i
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def show_network(network):
    """Display information about <network>"""

    try:
        ret = h.show_network(network)
        print "SUCCESS: Total networks: %s " % (network)
        for i in ret():
            print " %s" % i
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def show_node(node):
    """Display information about a <node>"""

    try:
        ret = h.show_node(node)
        print ret()
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def list_project_headnodes(project):
    """List all headnodes attached to a <project>"""

    try:
        ret = h.list_project_headnodes(project)
        print "Success: Total headnodes listed with Project %s: %s " % (project, len(ret()))
        for i in ret():
            print " %s" % i
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def show_headnode(headnode):
    """Display information about a <headnode>"""

    try:
        ret = h.show_headnode(headnode)
        print ret()
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def list_headnode_images():
    """Display registered headnode images"""

    try:
        ret = h.list_headnode_images()
        print "Success: Headnode images avaialable with HaaS: %s " % (ret())
        for i in ret():
            print " %s" % i
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def show_console(node):
    """Display console log for <node>"""

    try:
        ret = h.show_console(node)
#       Not sure what sort of feedback is good message here.
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def start_console(node):
    """Start logging console output from <node>"""

    try:
        ret = h.start_console(node)
#       Not sure what sort of feedback is good message here.
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def stop_console(node):
    """Stop logging console output from <node> and delete the log"""

    try:
        ret = h.stop_console(node)
#       Not sure what sort of feedback is good message here.
    except DuplicateName as e:
        print e.message
    except IncompleteDependency as e:
        print e.message
    except UnknownError as e:
        print e.message

@cmd
def create_admin_user(username, password):
    """Create an admin user. Only valid for the database auth backend.

    This must be run on the HaaS API server, with access to haas.cfg and the
    database. It will create an user named <username> with password
    <password>, who will have administrator priviledges.

    This command should only be used for bootstrapping the system; once you
    have an initial admin, you can (and should) create additional users via
    the API.
    """
    if not config.cfg.has_option('extensions', 'haas.ext.auth.database'):
        sys.exit("'make_inital_admin' is only valid with the database auth backend.")
    from haas import model
    from haas.model import db
    from haas.ext.auth.database import User
    model.init_db()
    db.session.add(User(label=username, password=password, is_admin=True))
    db.session.commit()

@cmd
def help(*commands):
    """Display usage of all following <commands>, or of all commands if none are given"""

    if not commands:
        sys.stdout.write('Usage: %s <command> <arguments...> \n' % sys.argv[0])
        sys.stdout.write('Where <command> is one of:\n')
        commands = sorted(command_dict.keys())
    for name in commands:
        # For each command, print out a summary including the name, arguments,
        # and the docstring (as a #comment).
        sys.stdout.write('  %s\n' % usage_dict[name])
        sys.stdout.write('      %s\n' % command_dict[name].__doc__)


def main():
    """Entry point to the CLI.

    There is a script located at ${source_tree}/scripts/haas, which invokes
    this function.
    """
    config.setup()

    if len(sys.argv) < 2 or sys.argv[1] not in command_dict:
        # Display usage for all commands
        help()
    else:
        command_dict[sys.argv[1]](*sys.argv[2:])
