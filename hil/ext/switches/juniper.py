
# Copyright 2013-2017 Massachusetts Open Cloud Contributors
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
"""A switch driver for the juniper QFX series.

But in theory can work for any Juniper switch that supports NETCONF.
Driver uses the python library PyEZ made available by Juniper.
By default it sets NETCONF session over ssh, i.e. make RPC calls over ssh.
For this to work, make sure that the Juniper switch is configured
appropriately to recieve NETCONF connections. Its default port is 830.
"""

import re
import logging
import schema
import json
import sys
import os

from jnpr.junos import Device
from jnpr.junos.exception import ConnectError
from jnpr.junos.utils.config import Config
from jnpr.junos.utils.config import ConfigLoadError


from hil.model import db, Switch
from hil.migrations import paths
from os.path import dirname, join
from hil.migrations import paths
from hil.ext.switches.junos.config_tables.ConfigTables import InterfaceConfigTable
logger = logging.getLogger(__name__)
paths[__name__] = join(dirname(__file__), 'migrations', 'juniper')

class VlanAddError(Exception):
    pass

class Juniper(Switch):
    api_name = 'http://schema.massopencloud.org/haas/v0/switches/juniper'
    dir_name = os.path.dirname(__file__)


    __mapper_args__ = {
        'polymorphic_identity': api_name,
    }

    id = db.Column(db.Integer, db.ForeignKey('switch.id'), primary_key=True)
    hostname = db.Column(db.String, nullable=False)
    username = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)

    @staticmethod
    def validate(kwargs):
        schema.Schema({
            'username': basestring,
            'hostname': basestring,
            'password': basestring,
        }).validate(kwargs)

    def session(self):
        return self

    def disconnect(self):
        pass

    def _create_session(self):
        dev = Device(host=self.hostname, user=self.username, passwd=self.password)
        dev.bind(cfg=Config)
        return dev

    def _set_load_config(self, o_session, set_command):
        """ Load configuration changes using the 'set' method.
        `o_session`: session object with connection to switch already open.
        `set_command`: Multi-line `set` method based command string.
        """
        jun = o_session
        try:
            jun.cfg.load(set_command, format="set")
        except ConfigLoadError as e:
            if e.message == "warning: statement not found":
                pass
            else:
                return e

    def _jinja_load_config(self, o_session, j_template, var_dict):
        """ Load configuration changes using the 'jinja_template' method.
        `o_session`: session object with connection to switch already open.
       `j_template`: jinja2 compliant configuration template. Samples is
       available at `junos/jinja_templates/`.
       `var_dict`: Dictionary of variables to be used in the jinja template
       passed with `j_template`, that will load the specific configuration
       change in the switch.
       """
        jun = o_session
        jun.cfg.load(
               template_path=j_template, template_vars=var_dict,
               format='text'
               )

    def _commit_config(self, loaded_session):
        """ Takes an open session that has loaded configuration change.
        Commits it if it is correct, otherwise rollback
        to recent commited state.
        `loaded_session`: session object after new configuration is loaded.
        """
        jun = loaded_session
        if jun.cfg.commit_check:
            jun.cfg.commit()
        else:
            jun.cfg.rollback()

    def _set_commit_config(self, set_command):
        """ Changes the switch config by using only 'set' method.
        `set_command`: 'set' method based command string.
        Note: Some configurations changes require both 'set'
        and 'jinja_template' method. In those cases use combination of functions
        `_set_load_config`, `_jinja_load_config` as needed finally commit using
        `_commit_config`.
        """

        jun = self._create_session()
        try:
            with jun:
                self._set_load_config(jun, set_command)
                self._commit_config(jun)
        except ConnectError as err:
            message = ("cannot connect to device: {0}".format(err))
            return message

    def revert_port(self, port):
        """Resets the port to the factory default.
        Running this function will replace the port settings
        with the ones stored in the jinja template `jinja_templates/`
        It reset any port to default port config as defined in 
        `default_port_config.j2`.
        """
        port_name = { 'port_name': port } # make sure the key here matches 
                # variable names used in the corresponding jinja templates.
        jun = self._create_session()
        err_list = [] # To avoid the issue of referencing before assigment.
                      # in case where only one of cfg.load fails.
        rm_curr_port_config = """
        delete interfaces {iface}
        """.format(iface=port_name['port_name'])

        base_config = self.dir_name+'/junos/jinja_templates/default_port_config.j2'
        
        try:
            with jun:
                try:
                    jun.cfg.load(rm_curr_port_config, format="set")
                except ConfigLoadError as e1:
                    err_list.append(e1)
                try:
                    jun.cfg.load( 
                            template_path = base_config, 
                            template_vars=port_name,
                            format='text'
                            )
                except ConfigLoadError as e2:
                    err_list.append(e2)
                    return err_list


                if jun.cfg.commit_check():
                    jun.cfg.commit()
                    print "configuration committed successfully"
                else:
                    jun.cfg.rollback()
                    print "Committed rolledback."
                
        except ConnectError as err:
            print ("Cannot connect to device: {0}".format(err))
            sys.exit(1)
        except Exception as err:
            print (err)

    def modify_port(self, port, channel, network_id):
        """ Changes vlan assignment to the port. 
        `node_connect_network` with 'vlan/native' flag: 
            enable port; set port to trunk mode; assign native_vlan; 
            remove default vlan
        """

        import pdb; pdb.set_trace()
        (port,) = filter(lambda p: p.label == port, self.ports)
        interface = port.label

        if channel == 'vlan/native':
            if network_id is None:
                self._remove_native_vlan(interface)
            else:
                self._set_native_vlan(interface, network_id)
        else:
            match = re.match(re.compile(r'vlan/(\d+)'), channel)
            assert match is not None, "HIL passed an invalid channel to the" \
                    " switch!"
             #Discuss this with Kristi
            vlan_id = match.groups()[0]

            if network_id is None:
                self._remove_vlan_from_port(interface, vlan_id)
            else:
                assert network_id == vlan_id
#                import pdb; pdb.set_trace()
                try:
                    self._add_vlan_to_trunk(interface, vlan_id)
                except VlanAddError as e:
                    return e

    def _set_native_vlan(self, port, network_id):
       """Sets native vlan for a trunked port. """
#       import pdb; pdb.set_trace()
       port_info = self._interface_info(port)
       port_set = "set interfaces {port}".format(port=port)
       port_del = "delete interfaces {port}".format(port=port)
                #To make set commands fit into 79 char limit.
       enable_interface = """
       {port_del} disable""".format(port_del=port_del)

       set_native_vlan = """
       {port_set} native-vlan-id {network_id}
       {port_set} unit 0 family ethernet-switching vlan members {network_id}
       """.format(port_set=port_set, network_id=network_id)
       
       remove_default_vlan = """
       {port_del} unit 0 family ethernet-switching vlan members default
       """.format(port_del=port_del)
       
       if port_info[port]['trunk_mode']:
           pass
       else:
           self._set_mode(port, 'trunk')

       if port_info[port]['disabled']:
           set_native_vlan = enable_interface + set_native_vlan

       if port_info[port]['vlans'] == 'default':
           set_native_vlan = set_native_vlan + remove_default_vlan

       set_native_vlan = set_native_vlan + remove_default_vlan
       self._set_commit_config(set_native_vlan)
       


    def _remove_native_vlan(self, port):
        """Removes native_vlan tag from port. """

        remove_native_vlan = """
        delete interfaces {port} native-vlan-id
        """.format(port=port)
        self._set_commit_config(remove_native_vlan)

    def _get_mode(self, port):
        """Returns True if the port is in trunk mode else returns False. """
        port_info = self._interface_info(port)
        return port_info[port]['trunk_mode']

    def _set_mode(self, port, mode):
        """ Will set a given port to
        trunk mode or access mode based on the `mode` flag.
        """
        if mode == "trunk":
            set_mode = """
            set interfaces {port} unit 0 family ethernet-switching interface-mode trunk
        """.format(port=port)
            self._set_commit_config(set_mode)
        else:
            self._remove_all_vlans_port(port)

        #x = "set interfaces et-0/0/08:0 unit 0 family ethernet-switching interface-mode trunk"

    def _interface_info(self, port):
        """Fetches latest committed configuration information about `port`"""
        jun = self._create_session()
        try:
            with jun:
                interface_config = InterfaceConfigTable(jun)
                interface_config.get(interface= port, options = {'database':'committed'})
                ic_dict = json.loads(interface_config.to_json())
        except ConnectError as err:
                print("connat connect to device: {0}".format(err))
                sys.exit(1)

        return ic_dict

    def _get_port_networks(self, port):
        """ Returns list of all the vlans shared with the port. """
        port_info = self._interface_info(port)
        return port_info[port]['vlans']

    def _add_vlan_to_trunk(self, port, vlan_id):
        """ Adds vlans to a trunk port. """
        #eg: set interfaces et-0/0/08:0 unit 0 family ethernet-switching vlan members 200
        port_set = "set interfaces {port}".format(port=port)
        port_del = "delete interfaces {port}".format(port=port)
                #To make set commands fit into 79 char limit.

        add_vlan = """
        set interfaces {port} unit 0 family ethernet-switching vlan members {vlan_id}
        """.format(port=port, vlan_id=vlan_id)
        enable_interface = """
        {port_del} disable""".format(port_del=port_del)

        remove_default_vlan = """
        {port_del} unit 0 family ethernet-switching vlan members default
        """.format(port_del=port_del)

        port_info = self._interface_info(port)

        if port_info[port]['disabled']:
           add_vlan = enable_interface + add_vlan

        if not port_info[port]['trunk_mode']:
            self._set_mode(port, 'trunk')

        if 'default' in port_info[port]['vlans']:
            add_vlan = add_vlan + remove_default_vlan 
        
        self._set_commit_config(add_vlan)

    def _remove_vlan_from_port(self, port, vlan_id):
        """ removes a single vlan specified by `vlan_id` """
        import pdb; pdb.set_trace()

        remove_vlan = """
            delete interfaces {port} unit 0 family ethernet-switching vlan members {vlan_id}
            """.format(port=port, vlan_id=vlan_id)
        
        port_info = self._interface_info(port)


        if isinstance(port_info[port]['vlans'], (str, unicode)):
            self.revert_port(port)
        else:
            self._set_commit_config(remove_vlan)


