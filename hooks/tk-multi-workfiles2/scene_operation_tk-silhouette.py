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
import shutil
import tempfile
import fx

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
        active_project = fx.activeProject()
        temp_dir = os.path.realpath(tempfile.gettempdir())

        if operation == "current_path":
            # return the current project path
            if active_project:
                return active_project.path
            else:
                return None

        elif operation == "open":
            fx.loadProject(file_path)

        elif operation == "save":
            active_project.save()

        elif operation == "save_as":
            initial_project_path = os.path.realpath(active_project.path)

            save_path = self.parent.engine.utils.get_stripped_project_path(file_path)
            active_project.save(save_path)

            # delete earlier project directory if it was a temporary path
            if initial_project_path.startswith(temp_dir):
                shutil.rmtree(os.path.dirname(os.path.dirname(initial_project_path)))

        elif operation == "reset":
            """
            Reset the scene to an empty state
            """
            # save activeProject
            exit_and_call_save = False
            if active_project:
                if active_project.path:
                    project_dir = os.path.realpath(os.path.dirname(active_project.path))
                    if not project_dir.startswith(temp_dir):
                        active_project.save()
                    else:
                        exit_and_call_save = True
                else:
                    exit_and_call_save = True

            if exit_and_call_save:
                res = QtGui.QMessageBox.question(QtGui.QApplication.activeWindow(),
                                                 "Save your scene?",
                                                 "Your scene has unsaved changes. Save before proceeding?",
                                                 QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel)

                if res == QtGui.QMessageBox.Cancel:
                    return False
                elif res == QtGui.QMessageBox.No:
                    pass
                else:
                    # there is an active project with no path or temp path - save it
                    # there is no silhouette python API to open a save file GUI, so just use sgtk
                    self.parent.engine.commands["File Save..."]["callback"]()
                    return False

            if parent_action == "new_file":
                # do new file. silhouette doesn't do unnamed projects well
                new_project_name = os.path.join(tempfile.mkdtemp(), "tk_silhouette_project")
                new_project = fx.Project(new_project_name)

                # silhouette 7 has method setActiveProject(), which can take None
                fx.activate(new_project)
                new_project.save()

                # make the user save the file immediately,
                # so that we can avoid using the temp location
                self.parent.engine.commands["File Save..."]["callback"]()

        return True
