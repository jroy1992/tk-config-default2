# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import tde4

import sgtk
from sgtk.util.filesystem import ensure_folder_exists

HookBaseClass = sgtk.get_hook_baseclass()


class TDE4SessionPublishPlugin(HookBaseClass):
    """
    Inherits from SessionPublishPlugin
    """

    SESSION_ITEM_TYPE_FILTERS = ["3de.session"]
    SESSION_ITEM_TYPE_SETTINGS = {
        "3de.session": {
            "publish_type": "3dequalizer File",
            "publish_name_template": None,
            "publish_path_template": None
        }
    }

    def _get_dependency_paths(self, node=None):
        """
        Find all dependency paths for the current node. If no node specified,
        will return all dependency paths for the session.

        :param node: Optional node to process
        :return: List of upstream dependency paths
        """

        dependency_paths = set()

        # first let's look at camera footage
        for camera_id in tde4.getCameraList():
            path = tde4.getCameraPath(camera_id)
            dependency_paths.add(path)

        # now look at 3D models
        for pgroup_id in tde4.getPGroupList():
            for model_id in tde4.get3DModelList(pgroup_id):
                path = tde4.get3DModelFilepath(pgroup_id, model_id)
                # internal 3D objects (eg. cube, sphere) will not have a path
                if path:
                    dependency_paths.add(path)

        return list(dependency_paths)

    def _save_session(self, path, version, item):
        """
        Save the current session to the supplied path.
        """
        ensure_folder_exists(os.path.dirname(path))
        tde4.saveProject(path)

        # Save the updated property
        item.properties.path = path
