# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that loads defines all the available actions, broken down by publish type. 
"""
import os
import re
import sgtk
import sys
import hou

from dd.runtime import api
api.load('qt_py')
from Qt import QtWidgets, QtGui, QtCore

HookBaseClass = sgtk.get_hook_baseclass()

class CustomHoudiniActions(HookBaseClass):

    def generate_actions(self, sg_publish_data, actions, ui_area):
        """
        Returns a list of action instances for a particular publish.
        This method is called each time a user clicks a publish somewhere in the UI.
        The data returned from this hook will be used to populate the actions menu for a publish.

        The mapping between Publish types and actions are kept in a different place
        (in the configuration) so at the point when this hook is called, the loader app
        has already established *which* actions are appropriate for this object.

        The hook should return at least one action for each item passed in via the
        actions parameter.

        This method needs to return detailed data for those actions, in the form of a list
        of dictionaries, each with name, params, caption and description keys.

        Because you are operating on a particular publish, you may tailor the output
        (caption, tooltip etc) to contain custom information suitable for this publish.

        The ui_area parameter is a string and indicates where the publish is to be shown.
        - If it will be shown in the main browsing area, "main" is passed.
        - If it will be shown in the details area, "details" is passed.
        - If it will be shown in the history area, "history" is passed.

        Please note that it is perfectly possible to create more than one action "instance" for
        an action! You can for example do scene introspection - if the action passed in
        is "character_attachment" you may for example scan the scene, figure out all the nodes
        where this object can be attached and return a list of action instances:
        "attach to left hand", "attach to right hand" etc. In this case, when more than
        one object is returned for an action, use the params key to pass additional
        data into the run_action hook.

        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :param actions: List of action strings which have been defined in the app configuration.
        :param ui_area: String denoting the UI Area (see above).
        :returns List of dictionaries, each with keys name, params, caption and description
        """

        # get the existing action instances
        action_instances = super(CustomHoudiniActions, self).generate_actions(sg_publish_data, actions, ui_area)

        if "image_plane" in actions:
            action_instances.append({
                "name": "image_plane",
                "params": None,
                "caption": "Create Camera Image Plane",
                "description": "Creates image plane for the selected camera or adds a new camera node with image plane set."
            })

        if "import_geometry" in actions:
            action_instances.append({
                "name": "import_geometry",
                "params": None,
                "caption": "Import Geometry",
                "description": "Imports model geometry"
            })

        if "import_animation" in actions:
            action_instances.append({
                "name": "import_animation",
                "params": None,
                "caption": "Import Animation",
                "description": "Imports animation for a particular action eg. walk cycle"
            })

        return action_instances

    ##############################################################################################################

    def execute_action(self, name, params, sg_publish_data):
        """
        Execute a given action. The data sent to this be method will
        represent one of the actions enumerated by the generate_actions method.

        :param name: Action name string representing one of the items returned by generate_actions.
        :param params: Params data, as specified by generate_actions.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :returns: No return value expected.
        """

        # call the actions from super
        super(CustomHoudiniActions, self).execute_action(name, params, sg_publish_data)

        if name == "image_plane":
            self._create_image_plane(sg_publish_data)
        elif name == "import_geometry":
            self._import_geometry(sg_publish_data)
        elif name == "import_animation":
            self._import_animation(sg_publish_data)

    ##############################################################################################################
    def _import(self, path, sg_publish_data):
        """Import the supplied path as a geo/alembic sop.

        :param str path: The path to the file to import.
        :param dict sg_publish_data: The publish data for the supplied path.

        """

        app = self.parent

        name = sg_publish_data.get("name")
        path = self.get_publish_path(sg_publish_data)
        parent_module = sys.modules[HookBaseClass.__module__]

        # houdini doesn't like UNC paths.
        path = path.replace("\\", "/")

        obj_context = parent_module._get_current_context("/obj")

        published_file_type = sg_publish_data["published_file_type"].get("name")
        if published_file_type == "Model File" or published_file_type == "Model Sequence":
            try:
                geo_node = obj_context.createNode("geo", name)
            except hou.OperationFailed:
                # failed to create the node in this context, create at top-level
                obj_context = hou.node("/obj")
                geo_node = obj_context.createNode("geo", name)
            app.log_debug("Created geo node: %s" % (geo_node.path(),))
            # delete the default nodes created in the geo
            for child in geo_node.children():
                child.destroy()

            file_sop = geo_node.createNode("file", name)
            # replace any %0#d format string with the corresponding houdini frame
            # env variable. example %04d => $F4
            frame_pattern = re.compile("(%0(\d)d)")
            frame_match = re.search(frame_pattern, path)
            if frame_match:
                full_frame_spec = frame_match.group(1)
                padding = frame_match.group(2)
                path = path.replace(full_frame_spec, "$F%s" % (padding,))
            file_sop.parm("file").set(path)
            node = file_sop
        else:
            try:
                alembic_node = obj_context.createNode("alembicarchive", name)
            except hou.OperationFailed:
                # failed to create the node in this context, create at top-level
                obj_context = hou.node("/obj")
                alembic_node = obj_context.createNode("alembicarchive", name)
            alembic_node.parm("fileName").set(path)
            alembic_node.parm("buildHierarchy").pressButton()
            node = alembic_node

        node_name = hou.nodeType(node.path()).name()
        app.log_debug(
            "Creating %s node: %s\n  path: '%s' " %
            (node_name, node.path(), path)
        )

        parent_module._show_node(node)

    ##############################################################################################################

    def _create_image_plane(self, sg_publish_data):
        """
        Adds an image plane for the selected camera or create a new camera node

        :param sg_publish_data: Shotgun data dictionary with all the standard
            publish fields.
        """

        app = self.parent

        name = sg_publish_data.get("name")
        path = self.get_publish_path(sg_publish_data)
        parent_module = sys.modules[HookBaseClass.__module__]

        # houdini doesn't like UNC paths.
        path = path.replace("\\", "/")
        # replace any %0#d format string with the corresponding houdini frame
        # env variable. example %04d => $F4
        frame_pattern = re.compile("(%0(\d)d)")
        frame_match = re.search(frame_pattern, path)
        if frame_match:
            full_frame_spec = frame_match.group(1)
            padding = frame_match.group(2)
            path = path.replace(full_frame_spec, "$F%s" % (padding,))

        obj_context = parent_module._get_current_context("/obj")

        selected_nodes = hou.selectedNodes()
        if selected_nodes:
            node_type = hou.nodeType(selected_nodes[0].path()).name()
            if len(selected_nodes) > 1:
                hou.ui.displayMessage("Please select only one camera node.")
            elif node_type != "cam":
                hou.ui.displayMessage("Please select a camera node.")
            else:
                camera_node = selected_nodes[0]
                camera_node.parm("vm_background").set(path)
                node_name = hou.nodeType(camera_node.path()).name()
                app.log_debug(
                    "Adding background image to %s node: %s\n  path: '%s' " %
                    (node_name, camera_node.path(), path)
                )
        else:
            try:
                camera_node = obj_context.createNode("cam", name)
            except hou.OperationFailed:
                obj_context = hou.node("/obj")
                camera_node = obj_context.createNode("cam", name)
            camera_node.parm("vm_background").set(path)

            node_name = hou.nodeType(camera_node.path()).name()
            app.log_debug(
                "Creating %s node: %s\n  path: '%s' " %
                (node_name, camera_node.path(), path)
            )

            parent_module._show_node(camera_node)

    def _create_geo_and_ropnet_nodes(self, node_nm):
        """
        Create geo and ropnet nodes or return if already present.

        :node_nm: name to bet set on geo node

        :return geo and ropnet node
        """
        geo_node = hou.node('/obj/' + node_nm)
        ropnet_node = hou.node('/obj/' + node_nm + '/ropnet1')
        # Check if already present
        if not geo_node:
            # Create geo node
            geo_node = hou.node('/obj').createNode('geo', node_name=node_nm)
            # Delete file node inside geo node
            for child in geo_node.children(): child.destroy()
            # Create ropnet node
            ropnet_node = hou.node('/obj/' + node_nm).createNode('ropnet')
        return (geo_node, ropnet_node)

    def _create_geo_ropnet_agent_nodes(self, path, name, geo_node, ropnet_node):
        """
        Create agent nodes inside geo and ropnet nodes

        :file_path: all the files selected from the particular path
        :files: separated file names from their respective paths
        :geo_node: geo node
        :ropnet_node: ropnet node

        :return agent nodes inside ropnet node
        """
        geo_agent_node = hou.node(geo_node.path()).createNode('agent', node_name=name)
        geo_agent_node.parm('input').set(2)
        geo_agent_node.parm('fbxfile').set(path[0])
        geo_agent_node.moveToGoodPosition()
        ropnet_agent_node = hou.node(ropnet_node.path()).createNode('agent', node_name=name)
        ropnet_agent_node.parm('source').set(2)
        ropnet_agent_node.parm('soppath').set(geo_node.path())
        ropnet_agent_node.moveToGoodPosition()
        return ropnet_agent_node, geo_agent_node

    def _set_parms(self, ropnet_agent_node, folder_name, option):
        """
        Setting parameter on agent nodes inside ropnet node based on user choice

        :ropnet_agent_nodes: agent nodes inside ropnet node
        :folder_name: name of folder from where files are imported
        :option: user option of animation or geometry
        """
        ropnet_agent_node.parm('source').set(1)
        ropnet_agent_node.parm('agentname').set(folder_name)
        ropnet_agent_node.parm('soppath').set(ropnet_agent_node.path())
        if option == "animation":
            ropnet_agent_node.parm('bakerig').set(0)
            ropnet_agent_node.parm('bakelayers').set(0)
            ropnet_agent_node.parm('bakeshapes').set(0)
            clip_parm_value = ropnet_agent_node.parm('clips').rawValue()
            ropnet_agent_node.parm('clips').set(clip_parm_value.replace('{CLIP}', 'OS'))
        elif option == "geometry":
            ropnet_agent_node.parm('bakeclip').set(0)

    def _merge_nodes(self, ropnet_node, agent_nodes):
        """
        Connect all the agent nodes to a merge node

        :ropnet_node: ropnet node
        :agent_nodes: agent nodes within a ropnet node
        """
        merge_node = hou.node(ropnet_node.path() + '/merge1')
        if not merge_node:
            merge_node = hou.node(ropnet_node.path()).createNode('merge')
        inputs = len(merge_node.inputs())
        # for node in agent_nodes:
        merge_node.setInput(inputs, agent_nodes)
        inputs += 1
        merge_node.moveToGoodPosition()

    def _import_geometry(self, sg_publish_data):
        name = sg_publish_data.get("name")
        path = self.get_publish_path(sg_publish_data)
        print "import geo path", path
        # get the name of the geo node from the user
        geo_node, ropnet_node = self._create_geo_and_ropnet_nodes("geometry_node")
        ropnet_agent_node, geo_agent_node = self._create_geo_ropnet_agent_nodes(path, name, geo_node, ropnet_node)
        self._set_parms(ropnet_agent_node, "geometry_node", option="geometry")
        self._merge_nodes(ropnet_node, ropnet_agent_node)

    def _import_animation(self, sg_publish_data):
        name = sg_publish_data.get("name")
        path = self.get_publish_path(sg_publish_data)
        # get the name of the geo node from the user
        geo_node, ropnet_node = self._create_geo_and_ropnet_nodes("geometry_node")
        ropnet_agent_node, geo_agent_node = self._create_geo_ropnet_agent_nodes(path, name, geo_node, ropnet_node)
        self._set_parms(ropnet_agent_node, "geometry_node", option="animation")
        self._merge_nodes(ropnet_node, ropnet_agent_node)


class ImportFBXUI(QtWidgets.QDialog):
    def __init__(self, render=None, parent=None):
        super(ImportFBXUI, self).__init__(parent)
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.render_obj = render
        self.mantra_option = None
        self.frange_option = None
        self.custom_frame_range = None
        self.chunk_size = None
        self.mem = None
        self.submit_button = None
        self.raceview_button = None

    def create_ui(self):
        self.use_existing_geo_node = QtWidgets.QCheckBox("Add to existing geo node")
        self.use_existing_geo_node.stateChanged.connect(lambda: self.disable_unused_option(self.use_existing_geo_node))
        self.layout.addWidget(self.use_existing_geo_node, 0, 0)
        self.existing_geo_nodes = QtWidgets.QComboBox()
        node_type = hou.nodeType(hou.objNodeTypeCategory(), "geo")
        geo_nodes = node_type.instances()
        self.existing_geo_nodes.insertItems(0, [node.name() for node in geo_nodes])
        self.existing_nodes_paths_dict = {node.name():{'name':node.name(), 'path':node.path()} for node in geo_nodes}
        self.layout.addWidget(self.existing_geo_nodes, 0, 1)

        self.use_new_geo_node = QtWidgets.QCheckBox("Add to new geo node (/obj)")
        self.use_new_geo_node.stateChanged.connect(lambda: self.disable_unused_option(self.use_new_geo_node))
        self.layout.addWidget(self.use_new_geo_node, 1, 0)
        self.new_geo_node = QtWidgets.QLineEdit()
        self.new_geo_node.textChanged.connect(self.enable_ok_button)
        self.new_geo_node.setStyleSheet("border: 1px solid black;")
        self.layout.addWidget(self.new_geo_node, 1, 1)

        sublayout = QtWidgets.QGridLayout()
        self.ok_button = QtWidgets.QPushButton("Ok")
        self.ok_button.setEnabled(False)
        sublayout.addWidget(self.ok_button, 0, 0)
        self.ok_button.clicked.connect(self.submit)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        sublayout.addWidget(self.cancel_button, 0, 1)
        self.cancel_button.clicked.connect(self.close)
        self.layout.addLayout(sublayout, 4, 1)
        self.setWindowTitle("Import Agent FBX")
        self.show()

    def enable_ok_button(self):
        if self.new_geo_node.text():
            self.ok_button.setEnabled(True)
        else:
            self.ok_button.setEnabled(False)

    def disable_unused_option(self, current_option):
        if current_option.text() == "Add to existing geo node":
            if current_option.isChecked():
                self.ok_button.setEnabled(True)
                self.use_new_geo_node.setEnabled(False)
                self.new_geo_node.setEnabled(False)
                self.new_geo_node.setStyleSheet("border: 0px solid black;")
            else:
                self.ok_button.setEnabled(False)
                self.use_new_geo_node.setEnabled(True)
                self.new_geo_node.setEnabled(True)
                self.new_geo_node.setStyleSheet("border: 1px solid black;")
        elif current_option.text() == "Add to new geo node (/obj)":
            if current_option.isChecked():
                self.use_existing_geo_node.setEnabled(False)
                self.existing_geo_nodes.setEnabled(False)
            else:
                self.use_existing_geo_node.setEnabled(True)
                self.existing_geo_nodes.setEnabled(True)

    def submit(self):
        if self.use_existing_geo_node.isChecked():
            return self.existing_nodes_paths_dict[self.existing_geo_nodes.currentText()]
        elif self.use_new_geo_node.isChecked():
            return {'name': self.new_geo_node.text(), 'path': '/obj'}
