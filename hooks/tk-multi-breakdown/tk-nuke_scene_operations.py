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
import nuke

import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class BreakdownSceneOperations(HookBaseClass):
    """
    Breakdown operations for Nuke.

    This implementation handles detection of Nuke read nodes,
    geometry nodes and camera nodes.
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

        reads = []

        # If we're in Nuke Studio or Hiero, we need to see if there are any
        # clips we need to be aware of that we might want to point to newer
        # publishes.
        if self.parent.engine.studio_enabled or self.parent.engine.hiero_enabled:
            import hiero

            # scan for only valid pipeline steps (shot entity)
            filters = [["entity_type", "is", "Shot"]]
            fields = ["short_name"]
            result = self.parent.sgtk.shotgun.find("Step", filters, fields)
            steps = list(set([step["short_name"] for step in result]))

            for project in hiero.core.projects():
                for bin in project.clipsBin().bins():

                    if bin.name() in steps:

                        for clip in bin.clips():
                            files = clip.activeItem().mediaSource().fileinfos()
                            for file in files:
                                path = file.filename().replace("/", os.path.sep)
                                reads.append(
                                    dict(
                                        node=clip.activeItem(),
                                        type="Clip",
                                        path=path,
                                    )
                                )

        # Hiero doesn't have nodes to check, so just return the clips.
        if self.parent.engine.studio_enabled or self.parent.engine.hiero_enabled:
            return reads

        # first let's look at the read nodes
        for node in nuke.allNodes("Read"):
            node_name = node.name()

            # note! We are getting the "abstract path", so contains
            # %04d and %V rather than actual values.
            path = node.knob('file').value().replace("/", os.path.sep)

            reads.append({"node": node_name, "type": "Read", "path": path})

        # then the read geometry nodes
        for node in nuke.allNodes("ReadGeo2"):
            node_name = node.name()

            path = node.knob('file').value().replace("/", os.path.sep)
            reads.append({"node": node_name, "type": "ReadGeo2", "path": path})

        # then the read camera nodes
        for node in nuke.allNodes("Camera2"):
            node_name = node.name()

            path = node.knob('file').value().replace("/", os.path.sep)
            reads.append({"node": node_name, "type": "Camera2", "path": path})

        return reads

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

        node_type_list = ["Read", "ReadGeo2", "Camera2", "DeepRead"]

        for i in items:
            node_name = i["node"]
            node_type = i["type"]
            new_path = i["path"].replace(os.path.sep, "/")

            if node_type in node_type_list:
                engine.log_debug("Node %s: Updating to version %s" % (node_name, new_path))
                node = nuke.toNode(node_name)
                node.knob("file").setValue(new_path)

                if i.get("sg_data"):
                    self._update_node_metadata(node, new_path, i["sg_data"])

            if node_type == "Clip":
                engine.log_debug("Clip %s: Updating to version %s" % (node_name, new_path))
                clip = node_name
                clip.reconnectMedia(new_path)

    def _update_node_metadata(self, node, path, sg_publish_data):
        """
        Bakes/Updates the additional metadata on the read node creating a SGTK tab on the node.

        This currently only stores fields that are in `additional_publish_fields` setting of our app.

        :param node: Node to store the additional metadata on.
        :param path: Path to file on disk.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """
        additional_publish_fields = self.parent.get_setting("additional_publish_fields")

        if not node.knob("sgtk_tab"):
            sgtk_tab_knob = nuke.Tab_Knob("sgtk_tab", "SGTK")
            node.addKnob(sgtk_tab_knob)

        for publish_field in additional_publish_fields:

            try:
                knob_value = sg_publish_data[publish_field]
                # create the knob if the field has a value now
                if knob_value and not node.knob(publish_field):
                    new_knob = None
                    # create a pretty name for the knob
                    knob_name = publish_field.replace("sg_", "")
                    knob_name = knob_name.replace("_", " ")
                    knob_name = knob_name.title()

                    if isinstance(knob_value, str):
                        new_knob = nuke.String_Knob(publish_field, knob_name)
                    elif isinstance(knob_value, int):
                        new_knob = nuke.Int_Knob(publish_field, knob_name)
                    else:
                        self.parent.logger.warning("Unable to create {} knob for type {}".format(publish_field,
                                                                                                 type(knob_value)))

                    if new_knob:
                        # make the knob read only
                        new_knob.setFlag(nuke.READ_ONLY)
                        new_knob.setValue(knob_value)

                        node.addKnob(new_knob)
                #  else just update it
                elif knob_value and node.knob(publish_field):
                    # make the knob read only
                    node.knob(publish_field).setFlag(nuke.READ_ONLY)
                    node.knob(publish_field).setValue(knob_value)
            except KeyError:
                self.parent.logger.warning("%s not found in PublishedFile. Please check the SG Schema." % publish_field)

