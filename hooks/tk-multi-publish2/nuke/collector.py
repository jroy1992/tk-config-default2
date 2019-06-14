# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk

HookBaseClass = sgtk.get_hook_baseclass()
print 'Hook base class: ', HookBaseClass

class NukeSessionDDCollector(HookBaseClass):
    """
    Collector that operates on the current nuke/nukestudio session. Should
    inherit from the basic collector hook.
    """
    # def __init__(self, parent, **kwargs):
    #     """
    #     Construction
    #     """
    #     # call base init
    #     super(NukeSessionDDCollector, self).__init__(parent, **kwargs)
    #     print 'resetting'
    #     self.visited_dict = {}
    #     self.write_node_paths_dict = {}

    def process_current_session(self, settings, parent_item):
        print 'new session processor'
        self.visited_dict = {}
        self.write_node_paths_dict = {}
        return super(NukeSessionDDCollector, self).process_current_session(settings, parent_item)