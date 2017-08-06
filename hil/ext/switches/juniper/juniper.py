
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
appropriately to recieve NETCONF connections. Default port is 830.
"""

import re
import logging
import schema

from jnpr.junos import Device
from jnpr.junos.exception import ConnectError
from jnpr.junos.utils.config import Config


from hil.model import db, Switch
from hil.migrations import paths
from os.path import dirname, join
from hil.migrations import paths
from hil.ext.switches.juniper.config_tables.ConfigTables import InterfaceConfigTable
logger = logging.getLogger(__name__)
paths[__name__] = join(dirname(__file__), 'migrations', 'juniper')


class juniper(Switch):
    api_name = 'http://schema.massopencloud.org/haas/v0/switches/' \
        'juniper'

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
        """Creates necessary object ready to be used by other functions
        to open a session and manipulate the switch configuration.
        """
        dev = Device(host=hostname, user=username, passwd=password)
        dev.bind(cfg=Config)
        return dev

    def _commit_config(self, loaded_session):
        """ Takes an open session that has loaded configuration change. 
        Commits it if it is correct, otherwise rollback
        to recent commited state. 
        """
        jun = loaded_session
        if jun.cfg.commit_check:
            jun.cfg.commit
        else:
            jun.cfg.rollback

    def _set_load_config(self, o_session, set_command):
        """ Changes the switch config using the 'set' method. 
        'o_session': object with open connection to the switch
        'set_command': `set` method based command string.
        """
        jun = o_session
        jun.cfg.load(set_command, format="set")

    def _set_commit_config(self, set_command):
        """ Changes the switch config by using only 'set' method.
        'set_command': `set` method based command string.
        """

        jun = self.session()
        try:
            with jun:
                self._set_load_config(jun, set_command)
                self._commit_config(jun)
            except ConnectError as err:
                print("connat connect to device: {0}".format(err))
                sys.exit(1)

    def _interface_info(self, port):
        """Fetches latest committed configuration information about `port`"""
        jun = self.session()
        try: 
            with jun:
                interface_config = InterfaceConfigTables(jun)
                interface_config.get(interface= port, options = {'database':'committed'})
                ic_dict = json.loads(interface_config.to_json())

        return ic_dict

    def _trunk_mode(self, port):
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
        else: 
            self._remove_all_vlans_port(port)

        #x = "set interfaces et-0/0/08:0 unit 0 family ethernet-switching interface-mode trunk"
        set_mode = """ 
        set interfaces {port} unit 0 family ethernet-switching interface-mode trunk
        """.format(port=port)

        self._set_commit_config(set_mode)

    def _get_native_vlan(self, port):
        """ Returns the id of the native vlan for the trunked port 
        if it exists returns nothing otherwise.  
        """ 
        port_info = self._interface_info(port)
        return port_info[port]['native_vlan']

    def _set_native_vlan(self, port, network_id):
       """ if `network_id` is provided,, 
       it sets native vlan for a trunked port.
       if `network_id` is None, it will remove the 
       current native vlan id.
       """
       if network_id:
           #x = "set interfaces et-0/0/08:0 native-vlan-id 100"
           set_native_vlan = """
           set interface {port} native-vlan-id {network_id}
           """.format(port=port, network_id=network_id)
       else:
           set_native_vlan = """
           delete interface {port} native-vlan-id {network_id}
           """.format(port=port, network_id=network_id)


        self._set_commit_config(set_native_vlan)
                
#    def _remove_native_vlan(self, port):
#        """ Removes native vlan from a trunked port. """
#
#        delete_native_vlan = """
#        delete interfaces {port} native-vlan-id
#       """.format(port=port)
#
#        self._set_commit_config(delete_native_vlan)
    
    def _add_vlan_from_trunk(self, port, vlan_id):
        """ Adds vlans to a trunk port. """
        
        #eg: set interfaces et-0/0/08:0 unit 0 family ethernet-switching vlan members 200
        add_vlan = """
        set interfaces {port} unit 0 family ethernet-switching vlan members {vlan_id}
        """.format(port=port, vlan_id=vlan_id)

        self._set_commit_config(add_vlan)

    def _remove_vlan_port(self, port, vlan_id):
        """ removes a single vlan specified by `vlan_id` """
        remove_vlan = """
        delete interfaces {port} unit 0 family ethernet-switching vlan members {vlan_id}
        """.format(port=port, vlan_id=vlan_id)
        self._set_commit_config(remove_vlan)
        
    def _remove_all_vlans_port(self, port):
        """ Removes all vlans from the port, including the native vlan.
        Also converts the interface to access mode. 
        """
            remove_all_vlans = """
            delete interfaces {port} unit 0 family ethernet-switching vlan
            delete interfaces {port} unit 0 family ethernet-switching interface-mode
            delete interfaces {port} native-vlan-id
            """.format(port=port)
            self._set_commit_config(remove_all_vlans)

    def _get_port_networks(self, port):
        """ List all the vlans shared with the port. """
        port_info = self._interface_info(port)
        return port_info[port]['vlans'] 

    def revert_port(self, port):
        """Resets the port to the factory default.
        Running this function will replace the port settings
        with the ones stored in the jinja template `jinja_templates/`
        For a physical port, it will use the template `revert_nonchannelized_port.j2`
        For a channelized port ( 4 10G ports made from 1 40G port) it will use
        template `revert_channelized_port.j2`
        """
        port_name = { 'port_name': port }
        jun = self.session()
        rm_curr_port_config = """
        delete interfaces {iface}
        """.format(iface=port_name['port_name'])

        if port[-2] == ":":
            base_config='jinja_templates/revert_channelized_port.j2'
        else:
            base_config='jinja_templates/revert_nonchannelized_port.j2'
        
        try:
            with jun:
                jun.cfg.load(rm_curr_port_config, format="set")
                jun.cfg.load( 
                        template_path = base_config, template_vars=port_name,
                        format='text'
                        )

                if jun.cfg.commit_check:
                    jun.cfg.commit
                else:
                    jun.cfg.rollback
                
        except ConnectError as err:
            print ("Cannot connect to device: {0}".format(err))
            sys.exit(1)
        except Exception as err:
            print (err)


    def _set_port_state(self, port, state):
        """ Disables or enables the `port`. 
        Depending on the value of `state`.
        """

        if state == "enable":
            set_port_state = """
            delete interface {port} disable
            """.format(port=port)
        elif state == "disable":
            set_port_state = """
            set interface {port} disable
            """.format(port=port)
        self._set_commit_config(remove_vlan)



