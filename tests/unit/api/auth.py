"""Tests related to the authorization of api calls.

NOTE: while all of these are conceptually authorization related, some illegal
operations will raise exceptions other than AuthorizationError. This usually
happens when the operation is illegal *in principle*, and would not be fixed by
authenticating as someone else. We were already raising exceptions in
these cases before actually adding authentication and authorization to
the mix. They are still tested here, since they are important for security.
"""

import pytest
import unittest
from haas import api, config, model, server, deferred
from haas.network_allocator import get_network_allocator
from haas.rest import RequestContext, local
from haas.auth import get_auth_backend
from haas.errors import AuthorizationError, BadArgumentError, \
    ProjectMismatchError, BlockedError
from haas.test_common import config_testsuite, config_merge, fresh_database

from haas.ext.switches.mock import MockSwitch


def auth_call_test(fn, error, admin, project, args):
    """Test the authorization properties of an api call.

    Parmeters:

        * `fn` - the api function to call
        * `error` - The error that should be raised. None if no error should
                    be raised.
        * `admin` - Whether the request should have admin access.
        * `project` - The name of the project the request should be
                      authenticated as. Can be None if `admin` is True.
        * `args` - the arguments (as a list) to `fn`.
    """
    auth_backend = get_auth_backend()
    auth_backend.set_admin(admin)
    if not admin:
        project = local.db.query(model.Project).filter_by(label=project).one()
        auth_backend.set_project(project)

    if error is None:
        fn(*args)
    else:
        with pytest.raises(error):
            fn(*args)


@pytest.fixture
def configure():
    config_testsuite()
    config_merge({
        'extensions': {
            'haas.ext.auth.mock': '',

            # This extension is enabled by default in the tests, so we need to
            # disable it explicitly:
            'haas.ext.auth.null': None,

            'haas.ext.switches.mock': '',
        },
    })
    config.load_extensions()


@pytest.fixture
def db(request):
    session = fresh_database(request)
    # Create a couple projects:
    runway = model.Project("runway")
    manhattan = model.Project("manhattan")
    for proj in [runway, manhattan]:
        session.add(proj)

    # ...including at least one with nothing in it:
    session.add(model.Project('empty-project'))

    # ...A variety of networks:

    networks = [
        {
            'creator': None,
            'access': None,
            'allocated': True,
            'label': 'stock_int_pub',
        },
        {
            'creator': None,
            'access': None,
            'allocated': False,
            'network_id': 'ext_pub_chan',
            'label': 'stock_ext_pub',
        },
        {
            # For some tests, we want things to initial be attached to a
            # network. This one serves that purpose; using the others would
            # interfere with some of the network_delete tests.
            'creator': None,
            'access': None,
            'allocated': True,
            'label': 'pub_default',
        },
        {
            'creator': runway,
            'access': runway,
            'allocated': True,
            'label': 'runway_pxe'
        },
        {
            'creator': None,
            'access': runway,
            'allocated': False,
            'network_id': 'runway_provider_chan',
            'label': 'runway_provider',
        },
        {
            'creator': manhattan,
            'access': manhattan,
            'allocated': True,
            'label': 'manhattan_pxe'
        },
        {
            'creator': None,
            'access': manhattan,
            'allocated': False,
            'network_id': 'manhattan_provider_chan',
            'label': 'manhattan_provider',
        },
    ]

    for net in networks:
        if net['allocated']:
            net['network_id'] = \
                get_network_allocator().get_new_network_id(session)
        session.add(model.Network(**net))

    # ... Two switches. One of these is just empty, for testing deletion:
    session.add(MockSwitch(label='empty-switch',
                           type=MockSwitch.api_name))

    # ... The other we'll actually attach stuff to for other tests:
    switch = MockSwitch(label="stock_switch_0",
                        type=MockSwitch.api_name)

    # ... Some free ports:
    session.add(model.Port('free_port_0', switch))
    session.add(model.Port('free_port_1', switch))

    # ... Some nodes (with projets):
    nodes = [
        {'label': 'runway_node_0', 'project': runway},
        {'label': 'runway_node_1', 'project': runway},
        {'label': 'manhattan_node_0', 'project': manhattan},
        {'label': 'manhattan_node_1', 'project': manhattan},
        {'label': 'free_node_0', 'project': None},
        {'label': 'free_node_1', 'project': None},
    ]
    for node_dict in nodes:
        node = model.Node(node_dict['label'], '', '', '')
        node.project = node_dict['project']
        session.add(model.Nic(node, label='boot-nic', mac_addr='Unknown'))

        # give it a nic that's attached to a port:
        port_nic = model.Nic(node, label='nic-with-port', mac_addr='Unknown')
        port = model.Port(node_dict['label'] + '_port', switch)
        port.nic = port_nic

    # ... Some headnodes:
    headnodes = [
        {'label': 'runway_headnode_on', 'project': runway, 'on': True},
        {'label': 'runway_headnode_off', 'project': runway, 'on': False},
        {'label': 'runway_manhattan_on', 'project': manhattan, 'on': True},
        {'label': 'runway_manhattan_off', 'project': manhattan, 'on': False},
    ]
    for hn_dict in headnodes:
        headnode = model.Headnode(hn_dict['project'],
                                  hn_dict['label'],
                                  'base-headnode')
        headnode.dirty = not hn_dict['on']
        hnic = model.Hnic(headnode, 'pxe')
        session.add(hnic)

        # Connect them to a network, so we can test detaching.
        hnic = model.Hnic(headnode, 'public')
        hnic.network = session.query(model.Network)\
            .filter_by(label='pub_default').one()


    # ... and at least one node with no nics (useful for testing delete):
    session.add(model.Node('no_nic_node', '', '', ''))

    session.commit()
    return session


@pytest.fixture
def server_init():
    server.register_drivers()
    server.validate_state()


@pytest.yield_fixture
def with_request_context():
    with RequestContext():
        yield


pytestmark = pytest.mark.usefixtures('configure',
                                     'db',
                                     'server_init',
                                     'with_request_context')


@pytest.mark.parametrize('fn,error,admin,project,args', [
    # TODO: Find out if there's a way to pass these by kwargs; it would be more
    # readable. For now, we try to make things a little better by formatting
    # each entry as:
    #
    # (fn, error,
    #  admin, project,
    #  args),
    #

    # network_create

    ### Legal cases:

    ### Admin creates a public network internal to HaaS:
    (api.network_create, None,
     True, None,
     ['pub', 'admin', '', '']),

    ### Admin creates a public network with an existing net_id:
    (api.network_create, None,
     True, None,
     ['pub', 'admin', '', 'some-id']),

    ### Admin creates a provider network for some project:
    (api.network_create, None,
     True, None,
     ['pxe', 'admin', 'runway', 'some-id']),

    ### Admin creates an allocated network on behalf of a project. Silly, but
    ### legal.
    (api.network_create, None,
     True, None,
     ['pxe', 'admin', 'runway', '']),

    ### Project creates a private network for themselves:
    (api.network_create, None,
     False, 'runway',
     ['pxe', 'runway', 'runway', '']),

    ## Illegal cases:

    ### Project tries to create a private network for another project.
    (api.network_create, AuthorizationError,
     False, 'runway',
     ['pxe', 'manhattan', 'manhattan', '']),

    ### Project tries to specify a net_id.
    (api.network_create, BadArgumentError,
     False, 'runway',
     ['pxe', 'runway', 'runway', 'some-id']),

    ### Project tries to create a public network:
    (api.network_create, AuthorizationError,
     False, 'runway',
     ['pub', 'admin', '', '']),

    ### Project tries to set creator to 'admin' on its own network:
    (api.network_create, AuthorizationError,
     False, 'runway',
     ['pxe', 'admin', 'runway', '']),

    # network_delete

    ## Legal cases

    ### admin should be able to delete any network:
] +
    [
        (api.network_delete, None,
         True, None,
         [net]) for net in [
            'stock_int_pub',
            'stock_ext_pub',
            'runway_pxe',
            'runway_provider',
            'manhattan_pxe',
            'manhattan_provider',
            ]
    ] + [
    ### project should be able to delete it's own (created) network:
    (api.network_delete, None,
     False, 'runway',
     ['runway_pxe']),

    ## Illegal cases:

] +
    ### Project should not be able to delete admin-created networks.
    [(api.network_delete, AuthorizationError,
      False, 'runway',
      [net]) for net in [
          'stock_int_pub',
          'stock_ext_pub',
          'runway_provider',  # ... including networks created for said project.
          ]
    ] +
    ### Project should not be able to delete networks created by other projects.
    [(api.network_delete, AuthorizationError,
      False, 'runway',
      [net]) for net in [
          'manhattan_pxe',
          'manhattan_provider',
          ]
    ] +

    # show_network

    ## Legal cases

    ### Public networks should be accessible by anyone:
    [(api.show_network, None,
      admin, project,
      [net]) for net in [
          'stock_int_pub',
          'stock_ext_pub',
      ] for project in [
          'runway',
          'manhattan',
      ] for admin in (True, False)] +

    ### Projects should be able to view networks they have access to:
    [(api.show_network, None,
      False, project,
      [net]) for (project, net) in [
          ('runway', 'runway_pxe'),
          ('runway', 'runway_provider'),
          ('manhattan', 'manhattan_pxe'),
          ('manhattan', 'manhattan_provider'),
      ]] +

    ## Illegal cases

    ### Projects should not be able to access each other's networks:
    [(api.show_network, AuthorizationError,
      False, project,
      [net]) for (project, net) in [
          ('runway', 'manhattan_pxe'),
          ('runway', 'manhattan_provider'),
          ('manhattan', 'runway_pxe'),
          ('manhattan', 'runway_provider'),
      ]] +

    # node_connect_network

    ## Legal cases

    ### Projects should be able to connect their own nodes to their own networks.
    [(api.node_connect_network, None,
      False, project,
      [node, 'boot-nic', net]) for (project, node, net) in [
          ('runway', 'runway_node_0', 'runway_pxe'),
          ('runway', 'runway_node_1', 'runway_provider'),
          ('manhattan', 'manhattan_node_0', 'manhattan_pxe'),
          ('manhattan', 'manhattan_node_1', 'manhattan_provider'),
      ]] +

    ### Projects should be able to connect their nodes to public networks.
    [(api.node_connect_network, None,
      False, project,
      [node, 'boot-nic', net]) for (project, node) in [
          ('runway', 'runway_node_0'),
          ('runway', 'runway_node_1'),
          ('manhattan', 'manhattan_node_0'),
          ('manhattan', 'manhattan_node_1'),
      ] for net in ('stock_int_pub', 'stock_ext_pub')] +

     ## Illegal cases

     ### Projects should not be able to connect their nodes to each other's
     ### networks.
     [(api.node_connect_network, ProjectMismatchError,
       False, 'runway',
       [node, 'boot-nic', net]) for (node, net) in [
           ('runway_node_0', 'manhattan_pxe'),
           ('runway_node_1', 'manhattan_provider'),
       ]] +

[
    ### Projects should not be able to attach each other's nodes to public networks.
    (api.node_connect_network, AuthorizationError,
       False, 'runway',
       ['manhattan_node_0', 'boot-nic', 'stock_int_pub']),

    ### Projects should not be able to attach free nodes to networks.
    ### The same node about the exception as above applies.
    (api.node_connect_network, ProjectMismatchError,
     False, 'runway',
     ['free_node_0', 'boot-nic', 'stock_int_pub']),

    # list_project_nodes

    ## Legal: admin lists a project's nodes.
    (api.list_project_nodes, None,
     True, None,
     ['runway']),

    ## Legal: project lists its own nodes.
    (api.list_project_nodes, None,
     False, 'runway',
     ['runway']),

    ## Illegal: project lists another project's nodes.
    (api.list_project_nodes, AuthorizationError,
     False, 'runway',
     ['manhattan']),

    # show_node

    ## Legal: project shows a free node
    (api.show_node, None,
     False, 'runway',
     ['free_node_0']),

    ## Legal: project shows its own node.
    (api.show_node, None,
     False, 'runway',
     ['runway_node_0']),

    ## Illegal: project tries to show another project's node.
    (api.show_node, AuthorizationError,
     False, 'runway',
     ['manhattan_node_0']),

    # project_connect_node: Project tries to connect someone else's node
    # to itself. The basic cases of connecting a free node are covered by
    # project_calls, below.
    (api.project_connect_node, BlockedError,
     False, 'runway',
     ['runway', 'manhattan_node_0']),
])
def test_auth_call(fn, error, admin, project, args):
    return auth_call_test(fn, error, admin, project, args)


# There are a whole bunch of api calls that just unconditionally require admin
# access. This is  a list of (function, args) pairs, each of which should
# succed as admin and fail as a regular project. The actual test functions for
# these are below.
admin_calls = [
    (api.node_register, ['new_node', '', '', '']),
    (api.node_delete, ['no_nic_node']),
    (api.node_register_nic, ['free_node_0', 'extra-nic', 'de:ad:be:ef:20:16']),
    (api.node_delete_nic, ['free_node_0', 'boot-nic']),
    (api.project_create, ['anvil-nextgen']),
    (api.list_projects, []),

    # node_power_cycle, on free nodes only. Nodes assigned to a project are
    # tested in project_calls, below.
    (api.node_power_cycle, ['free_node_0']),

    (api.project_delete, ['empty-project']),

    (api.switch_register, ['new-switch', MockSwitch.api_name]),
    (api.switch_delete, ['empty-switch']),
    (api.switch_register_port, ['stock_switch_0', 'new_port']),
    (api.switch_delete_port, ['stock_switch_0', 'free_port_0']),
    (api.port_connect_nic, ['stock_switch_0', 'free_port_0',
                            'free_node_0', 'boot-nic']),
    (api.port_detach_nic, ['stock_switch_0', 'free_node_0_port']),
]


# Similarly, there are a large number of calls that require access to a
# particular project. This is a list of (function, args) pairs that should
# succeed as project 'runway', and fail as project 'manhattan'.
project_calls = [
    # node_power_cycle, on allocated nodes only. Free nodes are testsed in
    # admin_calls, above.
    (api.node_power_cycle, ['runway_node_0']),

    (api.project_connect_node, ['runway', 'free_node_0']),
    (api.project_detach_node, ['runway', 'runway_node_0']),

    (api.headnode_create, ['new-headnode', 'runway', 'base-headnode']),
    (api.headnode_delete, ['runway_headnode_off']),
    (api.headnode_start, ['runway_headnode_off']),
    (api.headnode_stop, ['runway_headnode_on']),
    (api.headnode_create_hnic, ['runway_headnode_off', 'extra-hnic']),
    (api.headnode_delete_hnic, ['runway_headnode_off', 'pxe']),

    (api.headnode_connect_network, ['runway_headnode_off', 'pxe', 'stock_int_pub']),
    (api.headnode_connect_network, ['runway_headnode_off', 'pxe', 'runway_pxe']),
    (api.headnode_detach_network, ['runway_headnode_off', 'public']),

    (api.list_project_headnodes, ['runway']),
    (api.show_headnode, ['runway_headnode_on']),
]


@pytest.mark.parametrize('fn,args', admin_calls)
def test_admin_succeed(fn, args):
    auth_call_test(fn, None,
                   True, None,
                   args)


@pytest.mark.parametrize('fn,args', admin_calls)
def test_admin_fail(fn, args):
    auth_call_test(fn, AuthorizationError,
                   False, 'runway',
                   args)


@pytest.mark.parametrize('fn,args', project_calls)
def test_runway_succeed(fn, args):
    auth_call_test(fn, None,
                   False, 'runway',
                   args)


@pytest.mark.parametrize('fn,args', project_calls)
def test_manhattan_fail(fn, args):
    auth_call_test(fn, AuthorizationError,
                   False, 'manhattan',
                   args)



class Test_node_detach_network(unittest.TestCase):

    def setUp(self):
        self.auth_backend = get_auth_backend()
        self.runway = local.db.query(model.Project).filter_by(label='runway').one()
        self.manhattan = local.db.query(model.Project).filter_by(label='manhattan').one()
        self.auth_backend.set_project(self.manhattan)
        api.node_connect_network('manhattan_node_0', 'boot-nic', 'stock_int_pub')
        deferred.apply_networking()

    def test_success(self):
        self.auth_backend.set_project(self.manhattan)
        api.node_detach_network('manhattan_node_0', 'boot-nic', 'stock_int_pub')

    def test_wrong_project(self):
        self.auth_backend.set_project(self.runway)
        with pytest.raises(AuthorizationError):
            api.node_detach_network('manhattan_node_0', 'boot-nic', 'stock_int_pub')