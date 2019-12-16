# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import glob
import copy
import traceback

import maya.cmds as cmds
import sgtk
from sgtk import TankError

import dd.runtime.api
dd.runtime.api.load('modelpublish')
from modelpublish.lib.introspection import find_model_root_nodes

HookBaseClass = sgtk.get_hook_baseclass()


# This is a dictionary of file type info that allows the basic collector to
# identify common production file types and associate them with a display name,
# item type, and config icon.
MAYA_SESSION_ITEM_TYPES = {
    "maya.session": {
        "icon_path": "{self}/hooks/icons/maya.png",
        "type_display": "Maya Session"
    },
    "maya.geometry": {
        "icon_path": "{self}/hooks/icons/geometry.png",
        "type_display": "Geometry"
    }
}


class MayaSessionCollector(HookBaseClass):

    def collect_session_geometry(self, settings, parent_item):
        """
        Creates items for each lod geometry to be exported.
        Relies on structure <assetname> -> <lod> (as enforced in modelpublish)

        :param dict settings: Configured settings for this collector
        :param parent_item: Parent Item instance
        """
        geo_items = []

        lod_nodes = self._get_lod_nodes(parent_item)
        for lod_node in lod_nodes:
            # Copy the parent session's properties
            properties = copy.deepcopy(parent_item.properties)
            properties["fields"].update({"extension": "abc"})

            properties["fields"].update({"node": lod_node})
            geo_item = self._add_item(settings,
                                      parent_item,
                                      "Geometry: {}".format(lod_node),
                                      "maya.geometry",
                                      properties=properties)
            self.logger.info("Collected item: %s" % geo_item.name)

            geo_items.append(geo_item)

        return geo_items

    def _get_lod_nodes(self, parent_item):
        valid_node_name = parent_item.context.entity['name']
        toplevel_objects = find_model_root_nodes()

        # validate only assetname object
        if valid_node_name not in toplevel_objects:
            if not cmds.objExists("|{}".format(valid_node_name)):
                self.logger.error(
                    "Top-level object with name `{}` not found. Not collecting lod to export.".format(valid_node_name),
                    extra={
                        "action_show_more_info": {
                            "label": "Show Objects",
                            "tooltip": "Show found top-level objects",
                            "text": "Toplevel objects found: {}".format(toplevel_objects)
                        }
                    }
                )
            else:
                self.logger.error(
                    "Top-level object with name `{}` not valid. Not collecting lod to export.".format(valid_node_name),
                    extra={
                        "action_show_more_info": {
                            "label": "Show Error",
                            "tooltip": "Show error details",
                            "text": "Object may not have an lod transform as child. "
                                    "Please check terminal for details."
                        }
                    }
                )
            return []
        else:
            # all children are lod nodes; this is verified in find_model_root_nodes()
            return cmds.listRelatives(valid_node_name, children=True)
