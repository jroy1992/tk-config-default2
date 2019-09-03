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
import tde4

import sgtk
from sgtk.platform.qt import QtGui


HookBaseClass = sgtk.get_hook_baseclass()


class TDE4Actions(HookBaseClass):
    
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
        app.log_debug("Generate actions called for UI element %s. "
                      "Actions: %s. Publish Data: %s" % (ui_area, actions, sg_publish_data))
        
        action_instances = []

        if "import_img_to_cam" in actions:
            action_instances.append({
                "name": "import_img_to_cam",
                "params": None,
                "caption": "Import Image as Camera Footage",
                "description": "Imports image sequence into currently selected camera, "
                               "or new camera, if none is selected."
            })

        if "import_obj" in actions:
            action_instances.append({
                "name": "import_obj",
                "params": None,
                "caption": "Import OBJ file to 3D Model",
                "description": "Imports obj file into currently selected point group, "
                               "or new point group, if none is selected."
            })

        return action_instances

    def execute_multiple_actions(self, actions):
        """
        Executes the specified action on a list of items.

        The default implementation dispatches each item from ``actions`` to
        the ``execute_action`` method.

        The ``actions`` is a list of dictionaries holding all the actions to execute.
        Each entry will have the following values:

            name: Name of the action to execute
            sg_publish_data: Publish information coming from Shotgun
            params: Parameters passed down from the generate_actions hook.

        .. note::
            This is the default entry point for the hook. It reuses the ``execute_action``
            method for backward compatibility with hooks written for the previous
            version of the loader.

        .. note::
            The hook will stop applying the actions on the selection if an error
            is raised midway through.

        :param list actions: Action dictionaries.
        """
        for single_action in actions:
            name = single_action["name"]
            sg_publish_data = single_action["sg_publish_data"]
            params = single_action["params"]
            self.execute_action(name, params, sg_publish_data)

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

        path = self.get_publish_path(sg_publish_data)

        if name == "import_img_to_cam":
            self._import_img_seq_to_cam(path, sg_publish_data)

        if name == "import_obj":
            self._import_obj(path, sg_publish_data)


    ##############################################################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the behavior of things

    def _import_img_seq_to_cam(self, path, sg_publish_data):
        camera_id = None
        selected_cameras = tde4.getCameraList(True)

        if len(selected_cameras) == 0:
            camera_id = tde4.createCamera("SEQUENCE")
        elif len(selected_cameras) == 1:
            camera_id = selected_cameras[0]
        else:
            raise Exception("Multiple cameras selected.")

        # replace SEQ key with # format
        path_template = self.sgtk.template_from_path(path)
        if path_template:
            seq_keys = [key.name for key in path_template.keys.values()
                        if isinstance(key, sgtk.templatekey.SequenceKey)]
            if seq_keys:
                path_fields = path_template.get_fields(path)
                for key_name in seq_keys:
                    path_fields[key_name] = 'FORMAT: #'
                path = path_template.apply_fields(path_fields)

        tde4.setCameraPath(camera_id, path)

        # by default, use display window
        tde4.setCameraImportEXRDisplayWindowFlag(camera_id, True)

        # set frame range
        in_field, out_field = self.parent.utils.find_sequence_range(self.sgtk, path)
        tde4.setCameraSequenceAttr(camera_id, in_field, out_field, 1)
        tde4.setCameraFrameOffset(camera_id, in_field)

        no_of_frames = out_field - in_field + 1
        # set calculation range
        tde4.setCameraCalculationRange(camera_id, 1, no_of_frames)
        # set playback range
        tde4.setCameraPlaybackRange(camera_id, 1, no_of_frames)

        # TODO: set fps

    def _import_obj(self, path, sg_publish_data):
        if os.path.exists(path):
            point_group_id = tde4.getCurrentPGroup()
            if not point_group_id:
                point_group_id = tde4.createPGroup("OBJECT")
            model_id = tde4.create3DModel(point_group_id, 10000)
            imported = tde4.importOBJ3DModel(point_group_id, model_id, path)

            if not imported:
                raise Exception("Unable to import OBJ from {}. "
                                "Something went wrong in 3dequalizer.".format(path))
            else:
                # set model properties
                model_name, _ = os.path.splitext(os.path.basename(path))
                tde4.set3DModelName(point_group_id, model_id, model_name)
                tde4.set3DModelReferenceFlag(point_group_id, model_id, True)
                tde4.set3DModelSurveyFlag(point_group_id, model_id, True)
                # set3DModelRenderingFlags(<pgroup_id>, <model_id>, <show_points>, <show_lines>, <show_polygons>)
                tde4.set3DModelRenderingFlags(point_group_id, model_id, False, True, False)

        else:
            # TODO: either obj sequence or something wrong
            pass

    # TODO: alembic import