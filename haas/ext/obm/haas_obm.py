# Copyright 2013-2015 Massachusetts Open Cloud Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language
# governing permissions and limitations under the License.

""" An obm driver for recursive HaaS.
It invokes Base HaaS to execute various OBM actions on nodes 
"""

from sqlalchemy import Column, String, Integer, ForeignKey
import schema
import requests
import logging


from haas.model import Obm
from haas.errors import OBMError
from haas.dev_support import no_dry_run
from haas.config import cfg


class Haas_obm(Obm):
    id = Column(Integer, ForeignKey('obm.id'), primary_key=True)
    bhaas_nodename = Column(String, nullable=False)

    api_name = 'http://schema.massopencloud.org/haas/v0/obm/haas_obm'
    __mapper_args__ = {
        'polymorphic_identity': api_name,
        }

    @staticmethod
    def validate(kwargs):
        schema.Schema({
            'type': Haas_obm.api_name,
            'bhaas_nodename': basestring,
            }).validate(kwargs)

    @no_dry_run
    def power_cycle(self):
        bhaas = cfg.get('client', 'endpoint')

        url = bhaas+"/node/"+self.bhaas_nodename+"/power_cycle"
        requests.post(url)


    @no_dry_run
    def start_console(self):
        """ API call for this is being refactored."""
        return

    @no_dry_run
    def stop_console(self):
        """ API call for this is being refactored."""
        return

    @no_dry_run
    def delete_console(self):
        """ API call for this is being refactored."""
        return

    @no_dry_run
    def get_console(self):
        """ API call for this is being refactored."""
        return
    @no_dry_run
    def get_console_log_filename(self):
        """ API call for this is being refactored."""
        return

