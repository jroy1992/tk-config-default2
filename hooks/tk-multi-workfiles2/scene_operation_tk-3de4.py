# Copyright (c) 2015 Shotgun Software Inc.
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
from sgtk.platform.qt import QtGui, QtCore

HookClass = sgtk.get_hook_baseclass()


class SceneOperation(HookClass):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(self, operation, file_path, context, parent_action, file_version, read_only, **kwargs):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """
        if operation == "current_path":
            # return the current project path
            return tde4.getProjectPath()
        elif operation == "open":
            self._set_preferences(context)
            tde4.loadProject(file_path)
        elif operation == "save":
            project_path = tde4.getProjectPath()
            tde4.saveProject(project_path)
        elif operation == "save_as":
            tde4.saveProject(file_path)
        elif operation == "reset":
            """
            Reset the scene to an empty state
            """
            while not tde4.isProjectUpToDate():
                self.logger.debug(file_path)
                # changes have been made to the scene
                res = QtGui.QMessageBox.question(QtGui.QApplication.activeWindow(),
                                                 "Save your scene?",
                                                 "Your scene has unsaved changes. Save before proceeding?",
                                                 QtGui.QMessageBox.Yes|QtGui.QMessageBox.No|QtGui.QMessageBox.Cancel)

                if res == QtGui.QMessageBox.Cancel:
                    return False
                elif res == QtGui.QMessageBox.No:
                    break
                else:
                    project_path = tde4.getProjectPath()
                    if not project_path:
                        # there is no 3de python API to open a save file GUI, so just use sgtk
                        self.parent.engine.commands["File Save..."]["callback"]()
                        return False
                    else:
                        tde4.saveProject(project_path)

            # do new file:
            tde4.newProject()

            if parent_action == "new_file":
                self._set_preferences(context)
            return True

    def _set_preferences(self, context):
        fields = context.as_template_fields()
        project_area_path = self._get_template_path("{engine_name}_{env_name}_work_project_area", fields)
        tde4.setPreferenceValue("PROJECT_DIR", project_area_path)

        export_area_path = self._get_template_path("{engine_name}_{env_name}_work_export_area", fields)
        tde4.setPreferenceValue("OBJ_DIR", export_area_path)

        publish_area_path = self._get_template_path("{env_name}_publish_area", fields)
        tde4.setPreferenceValue("IMAGES_DIR", os.path.join(publish_area_path, "IMG"))

    def _get_template_path(self, template_expression, fields):
        templates = self.parent.sgtk.templates
        template_name = self.parent.resolve_setting_expression(template_expression)
        template = templates.get(template_name)
        template_value = template.apply_fields(fields)
        return template_value
