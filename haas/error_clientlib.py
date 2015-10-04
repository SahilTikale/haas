#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module `errorClientLib`  provides exceptions to be used in  module `clientLib` """

class DuplicateName(Exception):
    """ An exception indicating that the name of the entity already exists. """

class IncompleteDependency(Exception):
    """ Some calls require the input argument to be objects that are already.

    present in the database. If the objects used as input are missing in the database, 
    this exception will be raised.
    """


class ServersideError(Exception):
    """ An exception that indicating if something did not work on server side. """

class UnknownError(Exception):
    """ An exception class to handle everything else. """


