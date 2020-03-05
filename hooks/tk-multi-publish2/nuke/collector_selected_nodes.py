import nuke
import sgtk
from sgtk import TankError
from sgtk.templatekey import SequenceKey
from sgtk.platform.qt import QtGui

HookBaseClass = sgtk.get_hook_baseclass()

# A look up of node types to parameters for finding outputs to publish
_NUKE_OUTPUTS = {
    "WriteTank": "file",
    "DeepWriteTank": "file",
    "DeepWrite": "file",
}

# TODO: define commonly for other plugins, writenode app?
SG_WRITE_NODE_CLASSES = {"WriteTank", "DeepWriteTank"}


class NukeSessionCollector(HookBaseClass):
    """
    Collector that operates on the current nuke/nukestudio session
    and picks up only selected nodes. Should inherit from
    the nuke collector hook.
    """
    def collect_node_outputs(self, settings, parent_item):
        """
        Scan known output node types in the selected nodes in the session
        and see if they reference files that have been written to disk.

        :param dict settings: Configured settings for this collector
        :param parent_item: The parent item for any write geo nodes collected
        """
        items = []

        # iterate over all the known output types
        for node_type in _NUKE_OUTPUTS:

            # get all the instances of the node type
            selected_nodes_of_type = [n for n in nuke.selectedNodes()
                if n.Class() == node_type]

            items.extend(self.collect_node_outputs_from_list(settings, parent_item,
                                                             selected_nodes_of_type, node_type))

        return items
