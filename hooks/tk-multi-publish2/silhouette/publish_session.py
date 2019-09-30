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
import re
import fx

import sgtk
from sgtk.util.filesystem import ensure_folder_exists

HookBaseClass = sgtk.get_hook_baseclass()

# sources have path format /path/to/file.[start-end].ext
SILHOUETTE_FRAME_REGEX = "\.\[(\d+)-\d+\]\."


class SilhouetteSessionPublishPlugin(HookBaseClass):
    """
    Inherits from SessionPublishPlugin
    """

    SESSION_ITEM_TYPE_FILTERS = ["silhouette.session"]
    SESSION_ITEM_TYPE_SETTINGS = {
        "3de.session": {
            "publish_type": "Silhouette Project",
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
        engine = self.parent.engine

        dependency_paths = set()

        # let's look at sources in the project
        active_project = fx.activeProject()
        for source in active_project.sources:
            source_path = source.property("path").value
            formatted_path, errors = engine.utils.seq_path_from_silhouette_format(self.sgtk,
                                                                                  source_path)
            if errors:
                self.parent.log_error(errors)
            dependency_paths.add(formatted_path)

        return list(dependency_paths)

    def _save_session(self, path, version, item):
        """
        Save the current session to the supplied path.
        """

        ensure_folder_exists(os.path.dirname(path))
        active_project = fx.activeProject()
        if path != active_project.path:
            save_path = self.parent.engine.utils.get_stripped_project_path(path)
            active_project.save(save_path)
        else:
            active_project.save()

        # Save the updated property
        item.properties.path = path
