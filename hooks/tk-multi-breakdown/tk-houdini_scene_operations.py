# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from tank import Hook

import hou
import re

class BreakdownSceneOperations(Hook):
    """
    Breakdown operations for Houdini.

    This implementation handles detection of alembic node paths.
    """

    def scan_scene(self):
        """
        The scan scene method is executed once at startup and its purpose is
        to analyze the current scene and return a list of references that are
        to be potentially operated on.

        The return data structure is a list of dictionaries. Each scene reference
        that is returned should be represented by a dictionary with three keys:

        - "node": The name of the 'node' that is to be operated on. Most DCCs have
          a concept of a node, path or some other way to address a particular
          object in the scene.
        - "type": The object type that this is. This is later passed to the
          update method so that it knows how to handle the object.
        - "path": Path on disk to the referenced object.

        Toolkit will scan the list of items, see if any of the objects matches
        any templates and try to determine if there is a more recent version
        available. Any such versions are then displayed in the UI as out of date.
        """

        items = []

        # get a list of all regular alembic nodes in the file
        alembic_nodes = hou.nodeType(hou.objNodeTypeCategory(),
            "alembicarchive").instances()

        # return an item for each alembic node found. the breakdown app will check
        # the paths of each looking for a template match and a newer version.
        for alembic_node in alembic_nodes:

            file_parm = alembic_node.parm("fileName")
            file_path = os.path.normpath(file_parm.eval())

            items.append({
                "node": alembic_node.path(),
                "type": "alembic",
                "path": file_path,
            })

        # get a list of all regular file nodes in the file
        file_nodes = hou.nodeType(hou.sopNodeTypeCategory(),
            "file").instances()

        for file_node in file_nodes:
            file_parm = file_node.parm("file")
            file_path = os.path.normpath(file_parm.eval())

            items.append({
                "node": file_node.path(),
                "type": "file",
                "path": file_path,
            })

        cam_nodes = hou.nodeType(hou.objNodeTypeCategory(),
                                  "cam").instances()

        for cam_node in cam_nodes:
            file_parm = cam_node.parm("vm_background")
            file_path = os.path.normpath(file_parm.eval())

            items.append({
                "node": cam_node.path(),
                "type": "cam",
                "path": file_path,
            })

        return items

    def update(self, items):
        """
        Perform replacements given a number of scene items passed from the app.

        Once a selection has been performed in the main UI and the user clicks
        the update button, this method is called.

        The items parameter is a list of dictionaries on the same form as was
        generated by the scan_scene hook above. The path key now holds
        the that each node should be updated *to* rather than the current path.
        """

        engine = self.parent.engine

        # these items are to be updated. swap out the fileName parm value with the
        # new path as supplied by the breakdown app.
        for item in items:

            node_path = item["node"]
            node_type = item["type"]
            file_path = item["path"]

            file_path = file_path.replace("\\", "/")

            # update the alembic archive fileName parm to the new path
            if node_type == "alembic":

                alembic_node = hou.node(node_path)
                engine.log_debug(
                    "Updating alembic archive node '%s' to: %s" % (node_path, file_path))
                alembic_node.parm("fileName").set(file_path)
                alembic_node.parm("buildHierarchy").pressButton()
            elif node_type == "file":
                file_node = hou.node(node_path)
                engine.log_debug(
                    "Updating file node '%s' to: %s" % (node_path, file_path))
                file_node.parm("file").set(file_path)
            elif node_type == "cam":
                cam_node = hou.node(node_path)
                # replace any %0#d format string with the corresponding houdini frame
                # env variable. example %04d => $F4
                frame_pattern = re.compile("(%0(\d)d)")
                frame_match = re.search(frame_pattern, file_path)
                if frame_match:
                    full_frame_spec = frame_match.group(1)
                    padding = frame_match.group(2)
                    file_path = file_path.replace(full_frame_spec, "$F%s" % (padding,))
                engine.log_debug(
                    "Updating camera node '%s' to: %s" % (node_path, file_path))
                cam_node.parm("vm_background").set(file_path)

