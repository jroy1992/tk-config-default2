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
# core
import os
import re
import glob
import yaml
# sgtk
import sgtk
from sgtk.platform.qt import QtGui
from sgtk import TankError
# mari
import mari


HookBaseClass = sgtk.get_hook_baseclass()


class CustomMariActions(HookBaseClass):
    ##############################################################################################################
    # public interface - to be overridden by deriving classes

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
        app = self.parent
        mari_engine = app.engine
        app.log_debug("Generate actions called for UI element %s. "
                      "Actions: %s. Publish Data: %s" % (ui_area, actions, sg_publish_data))

        # if there isn't an open project then we can't do anything:
        if not mari.projects.current():
            return []

        # get the existing action instances
        action_instances = super(CustomMariActions, self).generate_actions(sg_publish_data, actions, ui_area)

        existing_action_names = [action_instance["name"] for action_instance in action_instances]

        if "create_layer_with_image" in actions and "create_layer_with_image" not in existing_action_names:
            action_instances.append({"name": "create_layer_with_image",
                                     "params": None,
                                     "caption": "Import Image into Layer",
                                     "description": "This will import the image into a layer on the current channel."})

        if "add_to_image_manager" in actions and "add_to_image_manager" not in existing_action_names:
            action_instances.append({"name": "add_to_image_manager",
                                     "params": None,
                                     "caption": "Add to Image Manager",
                                     "description": "This will add the image to project's image manager."})

        if 'ref_camera_import' in actions and 'ref_camera_import' not in existing_action_names:
            action_instances.append({"name": "ref_camera_import",
                                     "params": None,
                                     "caption": "Import Reference Camera",
                                     "description": "This will import camera as a projector."})
        if 'swap_geometry' in actions:
            action_instances.append({"name": "swap_geometry",
                                     "params": None,
                                     "caption": "Swap Current Geometry",
                                     "description": "This will swap the current geometry with a "
                                                    "Shotgun published geometry."})

        return action_instances

    def execute_action(self, name, params, sg_publish_data):
        """
        Execute a given action. The data sent to this be method will
        represent one of the actions enumerated by the generate_actions method.

        :param name: Action name string representing one of the items returned by generate_actions.
        :param params: Params data, as specified by generate_actions.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :returns: No return value expected.
        """
        app = self.parent
        app.log_debug("Execute action called for action %s. "
                      "Parameters: %s. Publish Data: %s" % (name, params, sg_publish_data))

        # call the actions from super
        super(CustomMariActions, self).execute_action(name, params, sg_publish_data)

        # resolve path
        # toolkit uses utf-8 encoded strings internally and Maya API expects unicode
        # so convert the path to ensure filenames containing complex characters are supported
        path = self.get_publish_path(sg_publish_data).decode("utf-8")

        if name == "create_layer_with_image":
            self._create_layer_with_image(path, sg_publish_data)
        elif name == "add_to_image_manager":
            self._add_to_image_manager(path, sg_publish_data)
        elif name == "ref_camera_import":
            self._import_ref_camera(path, sg_publish_data)
        elif name == "swap_geometry":
            geo = mari.geo.current()
            self._swap_geometry(geo, sg_publish_data)

    ##############################################################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the behaviour of things

    def _swap_geometry(self, geo, sg_publish_data):
        mari_engine = self.parent.engine

        version_list = geo.versionNames()
        if len(version_list) > 1:
            # warn that we are removing all of them
            message = "The geo '{}' has multiple versions attached with it:\n{}\n" \
                      "Are you sure you want to proceed?".format(geo.name(), version_list)
            response = QtGui.QMessageBox.question(None, "Removing multiple geo versions!", message,
                                                  QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
            if response == QtGui.QMessageBox.No:
                return

        mari_engine.swap_geometry(geo, sg_publish_data, options=None)


    def _create_layer_with_image(self, path, sg_publish_data):
        """
        Import the image into a layer on the current channel.

        :param sg_publish_data:     Shotgun data dictionary with all the standard publish fields.
        """
        layer_name = "%s-%s.v%d" % (sg_publish_data.get("entity").get("name"),
                                    sg_publish_data.get("name"),
                                    sg_publish_data.get("version_number"))

        # mari understands this as a template for importing images with UDIMs
        path = path.replace("<UDIM>", "$UDIM")
        active_channel = mari.geo.current().currentChannel()
        available_layers = active_channel.layerList()
        layer_names = [available_layer.name() for available_layer in available_layers]

        if layer_name not in layer_names:
            self.parent.log_info("Creating %s layer on %s channel" % (layer_name, active_channel.name()))
            new_layer = active_channel.createPaintableLayer(layer_name)
            self.parent.log_info("Adding %s image to %s layer" % (path, layer_name))
            new_layer.importImages(path)
        else:
            self.parent.log_error("%s layer already exists!" % layer_name)

    def _add_to_image_manager(self, path, sg_publish_data):
        """
        Import the image to the project's image manager.

        :param sg_publish_data:     Shotgun data dictionary with all the standard publish fields.
        """
        mari_engine = self.parent.engine

        frame_range = self.parent.utils.find_sequence_range(self.sgtk, path)

        if frame_range:
            FRAME_PATTERN_REGEX = re.compile(r"([0-9#]+|[%]0\dd)$")
            root, ext = os.path.splitext(path)
            frame_pattern_match = re.search(FRAME_PATTERN_REGEX, root)
            frame_pattern = frame_pattern_match.groups()[0]

            FRAME_SPEC_REGEX = re.compile("%0(\d+)d")
            frame_spec_pattern_match = re.search(FRAME_SPEC_REGEX, frame_pattern)
            padding = int(frame_spec_pattern_match.groups()[0])

            min_frame, max_frame = frame_range
            if min_frame == max_frame:
                frame_number = min_frame
            else:
                # ask user for frame number
                frame_number, response = QtGui.QInputDialog.getInt(
                    None, "Frame Number", "Enter the frame number ({}-{}) "
                                          "that you want to load: ".format(min_frame, max_frame),
                    minValue=min_frame, maxValue=max_frame
                )
                if not response:
                    self.parent.logger.warning("User pressed Cancel. Not loading image.")
                    return

            path = path.replace(str(frame_pattern), str(frame_number).zfill(padding))

            # add the image to image manager
            mari.images.open(path)
            self.parent.log_info("Added %s to image manager!" % path)
        else:
            self.parent.log_warning("There are no frames in %s image!" % path)

    def _import_ref_camera(self, path, sg_publish_data):
        template = None
        data_loaded = None
        error_msg = ''
        missing_cam = []
        missing_img_path = []
        ref_image_missing = []

        try:
            template = self.parent.sgtk.template_from_path(path)
        except sgtk.TankError:
            pass
        if not template:
            return None

        # get the fields
        fields = template.get_fields(path)

        # get metadata template
        metadata_template_exp = "{env_name}_publish_metadata"
        metadata_template_name = self.parent.resolve_setting_expression(metadata_template_exp)
        metadata_template = self.parent.sgtk.templates.get(metadata_template_name)

        if not metadata_template:
            self.parent.logger.warning("Unable to find metadata template: {}".format(metadata_template_name))
            return None

        try:
            metadata_path = metadata_template.apply_fields(fields)
        except sgtk.TankError:
            self.parent.logger.warning("Unable to apply fields: {}"
                                       "\nto metadata template: {}".format(fields, metadata_template_name))
            return None

        try:
            with open(metadata_path, 'r') as stream:
                data_loaded = yaml.load(stream)
        except:
            self.warning_dialogue('WARNING', 'Unable to load metadata file')

        if data_loaded:
            # Checking for object in Metadata file and removing if object exists in the scene
            for cam, img in data_loaded.iteritems():
                if mari.projectors.find(cam):
                    mari.projectors.remove(cam)
            # Loading Projectors(camera)
            projectors = mari.projectors.load(path)
            for cam in projectors:
                cam_name = cam.name()
                camera = data_loaded.get(cam_name, None)
                if camera:
                    ref_image_attribute = camera.get('ref_image', None)
                    if ref_image_attribute:
                        image_path = ref_image_attribute.get('file_path', None)
                        if image_path and os.path.exists(image_path):
                            cam.setImportPath(image_path)
                            cam.project()
                        else:
                            missing_img_path.append(cam_name)
                    else:
                        ref_image_missing.append(cam_name)

                else:
                    missing_cam.append(cam_name)
        else:
            self.warning_dialogue('WARNING', 'Metadata file is empty')

        if ref_image_missing:
            error_msg += 'Reference image not found in metadata for camera - {}\n'.format(str(ref_image_missing))
        if missing_cam:
            error_msg += 'Camera not found in metadata - {}\n'.format(str(missing_cam))

        if missing_img_path:
            error_msg += 'Image path for camera does not exist - {}\n'.format(str(missing_img_path))
        if error_msg:
            self.warning_dialogue('Object Missing', error_msg)

    def warning_dialogue(self, title, msg):
        QtGui.QMessageBox.warning(None, title, msg)
