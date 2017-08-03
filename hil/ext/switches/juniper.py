
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

import pexpect
import re
import logging
import schema

from jnpr.junos import Device
from jnpr.junos.exception import ConnectError

from hil.model import db, Switch
from hil.migrations import paths
from hil.ext.switches import _console
from hil.ext.switches._dell_base import _BaseSession
from os.path import dirname, join
from hil.migrations import paths

logger = logging.getLogger(__name__)
paths[__name__] = join(dirname(__file__), 'migrations', 'n3000')


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
        return _JuniperSession.connect(self)


class _JuniperSession(_BaseSession):
    """session object for the N3000 series"""

    def __init__(self, config_prompt, if_prompt, main_prompt, switch, console,
                 dummy_vlan):
        self.config_prompt = config_prompt
        self.if_prompt = if_prompt
        self.main_prompt = main_prompt
        self.switch = switch
        self.console = console
        self.dummy_vlan = dummy_vlan

    def _sendline(self, line):
        logger.debug('Sending to switch` switch %r: %r',
                     self.switch, line)
        self.console.sendline(line)

    @staticmethod
    def connect(switch):
        # connect to the switch, and log in:
        console = pexpect.spawn('telnet ' + switch.hostname)
        console.expect('User:')
        console.sendline(switch.username)
        console.expect('Password:')
        console.sendline(switch.password)
        console.expect('>')
        console.sendline('en')

        logger.debug('Logged in to switch %r', switch)

        prompts = _console.get_prompts(console)
        # create the dummy vlan for port_revert
        # this is a one time thing though; maybe we could remove this and let
        # the admin create the dummy vlan on the switch
        console.sendline('config')
        console.expect(prompts['config_prompt'])
        console.sendline('vlan ' + switch.dummy_vlan)
        console.sendline('exit')
        console.sendline('exit')
        console.expect(prompts['main_prompt'])

        return _DellN3000Session(switch=switch,
                                 dummy_vlan=switch.dummy_vlan,
                                 console=console,
                                 **prompts)

    def disable_port(self):
        self._sendline('sw trunk allowed vlan add ' + self.dummy_vlan)
        self._sendline('sw trunk native vlan ' + self.dummy_vlan)
        self._sendline('sw trunk allowed vlan remove 1-4093')

    def disable_native(self, vlan_id):
        self.disable_vlan(vlan_id)
        # first set the dummy vlan as trunking vlan, then set that as it's
        # native, then remove that vlan from trunking vlans. otherwise the
        # switch won't let you set a native vlan that isn't added.
        self._sendline('sw trunk allowed vlan add ' + self.dummy_vlan)
        self._sendline('sw trunk native vlan ' + self.dummy_vlan)
        self._sendline('sw trunk allowed vlan remove ' + self.dummy_vlan)

    def _int_config(self, interface):
        """Collect information about the specified interface

        Returns a dictionary from the output of ``show int sw <interfaces>``.
        """

        self._sendline('show int sw %s' % interface)
        self.console.expect('Port: .*')
        k, v = 'key', 'value'
        result = {k: v}
        key_lines = self.console.after.splitlines()
        del key_lines[-3:]
        for line in key_lines:
            k, v = line.split(':', 1)
            result[k] = v
        # expecting main_prompt here fails, because it appears that the
        # main_prompt is a part of the interface configuration (console.after)
        # sending a new line clears things up here.
        self._sendline('\n')
        self.console.expect(self.main_prompt)
        return result

    def get_port_networks(self, ports):
        num_re = re.compile(r'(\d+)')
        port_configs = self._port_configs(ports)
        result = {}
        for k, v in port_configs.iteritems():
            native = v['Trunking Mode Native VLAN'].strip()
            match = re.match(num_re, native)
            if match:
                # We need to call groups to get the part of the string that
                # actually matched, because it could include some junk on the
                # end, e.g. "100 (Inactive)".
                num_str = match.groups()[0]
                native = int(num_str)
                if native == int(self.switch.dummy_vlan):
                    native = None
            else:
                native = None
            networks = []
            for range_str in v['Trunking Mode VLANs Enabled'].split(','):
                for num_str in range_str.split('-'):
                    num_str = num_str.strip()
                    match = re.match(num_re, num_str)
                    if match:
                        # There may be other tokens in the output, e.g.
                        # the string "(Inactive)" somteimtes appears.
                        # We should only use the value if it's an actual number
                        num_str = match.groups()[0]
                        networks.append(('vlan/%s' % num_str, int(num_str)))
            if native is not None:
                networks.append(('vlan/native', native))
            result[k] = networks
        return result
