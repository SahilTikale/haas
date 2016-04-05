import pytest
import tempfile
import os
import signal
from subprocess import check_call, Popen
from time import sleep

config = """
[headnode]
base_imgs = base-headnode, img1, img2, img3, img4
[database]
uri = sqlite:///haas.db
[extensions]
haas.ext.auth.null =
haas.ext.network_allocators.null =
"""


@pytest.fixture(autouse=True)
def make_config(request):
    tmpdir = tempfile.mkdtemp()
    cwd = os.getcwd()
    os.chdir(tmpdir)
    with open('haas.cfg', 'w') as f:
        f.write(config)

    def cleanup():
        os.remove('haas.cfg')
        os.remove('haas.db')
        os.chdir(cwd)
        os.rmdir(tmpdir)

    request.addfinalizer(cleanup)


def test_init_db():
    check_call(['haas', 'init_db'])


def runs_for_seconds(cmd, seconds=1):
    """Test if the command ``cmd`` runs for at least ``seconds`` seconds.

    ``cmd`` is a list containing the name of a command and its arguments.

    ``seconds`` is a number of seconds (by default 1).

    ``run_for_seconds`` will execute ``cmd``, wait for ``seconds`` seconds,
    send SIGTERM to the process, and then wait() for it. If the exit status
    indicates that it stopped for any reason other than SIGTERM,
    ``run_for_seconds`` returns False, otherwise it returns True.

    This is useful to check that a server process does not immediately die on
    startup, though it's a bit of a hack --- checking rigorously would require
    extra knowledge of the workings of that process (hooray for the halting
    problem).
    """
    proc = Popen(cmd)
    sleep(seconds)
    proc.terminate()
    status = proc.wait()
    return status == -signal.SIGTERM


def test_serve():
    check_call(['haas', 'init_db'])
    assert runs_for_seconds(['haas', 'serve', '5000'], seconds=1)


def test_serve_networks():
    check_call(['haas', 'init_db'])
    assert runs_for_seconds(['haas', 'serve_networks'], seconds=1)
