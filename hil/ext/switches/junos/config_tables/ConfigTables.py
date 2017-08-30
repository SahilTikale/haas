from jnpr.junos.factory import loadyaml
from os.path import splitext
_YAML_ = splitext(__file__)[0] + '.yml'
globals().update(loadyaml(_YAML_))

# Reference: "https://www.juniper.net/documentation/en_US/junos-pyez/topics/
# task/program/junos-pyez-tables-views-external-importing.html"
