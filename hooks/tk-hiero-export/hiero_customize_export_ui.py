# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk

from hiero.core import projects

HookBaseClass = sgtk.get_hook_baseclass()


class HieroCustomizeExportUI(HookBaseClass):
    """
    This class defines methods that can be used to customize the UI of the various
    Shotgun-related exporters. Each processor has its own set of create/get/set
    methods, allowing for customizable UI elements for each type of export.
    """
    # For detailed documentation of the methods available for this hook, see
    # the documentation at http://developer.shotgunsoftware.com/tk-hiero-export/

    def get_default_version_number(self):

        version_number = 1
        seq_projects = projects()

        # Picks the first valid project (to do for selected project, if multiple projects are applicable)
        for project in seq_projects:
            project_name = project.name()
            if ".v" in project_name:
                version = project_name.split(".")[1]
                version_number = int(version.split("v")[1])
                break
            else:
                self.parent.logger.debug("Unsaved project {%s}. Do a Shotgun File Save." % project)

        return version_number




