# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import mari

import glob
import os
import sgtk
from sgtk import TankError
from sgtk.platform.qt import QtGui

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
        current_project = mari.projects.current()

        if operation == "current_path":
            # return the current scene path
            # used in snapshot only, not required for Mari?
            self.parent.logger.warning("Mari workfile may not be exported yet!")
            return find_msf_file(file_path)
        elif operation == "open":
            engine = sgtk.platform.current_engine()
            templates = self.sgtk.templates

            project_name_tmpl_exp = '{engine_name}_{env_name}_project_name'
            project_name_tmpl_name = engine.resolve_setting_expression(project_name_tmpl_exp)
            project_name_template = templates.get(project_name_tmpl_name)
            fields = context.as_template_fields()

            if file_path:
                file_template = context.sgtk.template_from_path(file_path)
                fields.update(file_template.get_fields(file_path))
            project_name = project_name_template.apply_fields(fields)

            mari_project_info = mari.projects.find(project_name)
            if mari_project_info:
                # if project exists, open it
                current_project = mari_project_info.open()
                # if version incorrect, import session
                # TODO: does this create multiple copies of channels?
                if engine.get_project_version(current_project) != file_version:
                    mari.session.importSession(find_msf_file(file_path))
            else:
                # else create project from session
                engine.create_project_from_msf(find_msf_file(file_path))

        elif operation == "save":
            # save the current scene:
            current_project.save()
            mari.session.exportSession(file_path)
        elif operation == "save_as":
            # reset file version and save:
            engine = sgtk.platform.current_engine()
            if engine.get_project_version(current_project) != file_version:
                engine.set_project_version(current_project, file_version)
            current_project.save()
            mari.session.exportSession(file_path)
        elif operation == "reset":
            """
            Reset the scene to an empty state
            """
            mari.projects.close()
            # TODO: this isn't what other DCCs do (they create a blank scene)
            # but mari cannot have an empty project (needs a geometry)
            if parent_action == "new_file":
                engine = sgtk.platform.current_engine()
                project_manager_app = engine.apps.get("tk-mari-projectmanager")
                project_manager_app.start_new_project_ui()
            return True

    def get_upstream_published_files(self, publish_path, context):
        published_file_type = sgtk.util.get_published_file_entity_type(self.sgtk)
        fields = ["upstream_published_files"]
        publish_filters = [["entity", "is",
                            context.entity or context.project]]
        if context.task:
            publish_filters.append(["task", "is", context.task])
        else:
            publish_filters.append(["task", "is", None])

        publish_path_cache = publish_path.lstrip(os.environ['DD_SHOWS_ROOT'])
        publish_filters.append(["path_cache", "is", publish_path_cache])
        published_file_entity = self.parent.shotgun.find_one(published_file_type,
                                                             publish_filters, fields)
        if not published_file_entity:
            # self.parent.logger.error("No published file found for filters: {}".format(fields))
            return None
        return published_file_entity.get("upstream_published_files")


def find_msf_file(export_directory):
    globbed_msf_files = glob.glob(os.path.join(export_directory, "*", "*.msf"))
    if len(globbed_msf_files) != 1:
        raise TankError("Found 0 or multiple msf files: {} "
                        "in export directory: {}".format(globbed_msf_files, export_directory))
    return globbed_msf_files[0]
