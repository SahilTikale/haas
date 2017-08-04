
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
from jnpr.junos.op.vlan import VlanTable


from hil.model import db, Switch
from hil.migrations import paths
from os.path import dirname, join
from hil.migrations import paths

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
        """Creates necessary object ready to open session
        and manipulate the switch configuration.
        """
        dev = Device(host=hostname, user=username, passwd=password)
        dev.bind(cfg=Config)
        return dev

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


    def disable_port(self):
        pass

    def get_port_networks(self, ports):
        pass

