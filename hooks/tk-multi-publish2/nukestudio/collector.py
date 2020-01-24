# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import hiero
import sgtk


HookBaseClass = sgtk.get_hook_baseclass()


class NukeSessionCollector(HookBaseClass):
    """
    Collector that operates on the current nuke/nukestudio session. Should
    inherit from the basic collector hook.
    """
    def __init__(self, parent, **kwargs):
        """
        Construction
        """
        # call base init
        super(NukeSessionCollector, self).__init__(parent, **kwargs)

        # cache the write node and workfiles apps
        self.__write_node_app = self.parent.engine.apps.get("tk-nuke-writenode")
        self.__workfiles_app = self.parent.engine.apps.get("tk-multi-workfiles2")

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current session open in Nuke/NukeStudio and parents a
        subtree of items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """
        items = []

        publisher = self.parent
        engine = publisher.engine

        if hasattr(engine, "studio_enabled") and engine.studio_enabled:
            # running nuke studio.
            project_list = self.collect_current_nukestudio_session(settings, parent_item)
            for e_project in project_list:
                items.append(e_project)
                # since we're in NS, any additional collected outputs will be
                # parented under the root item
                session_item = e_project

                # Also collect any output node items
                items.extend(self.collect_node_outputs(settings, session_item))

                # if we have work path templates, collect matching files to publish
                for work_template in settings["Work File Templates"].value:
                    items.extend(self.collect_work_files(settings, session_item, work_template))
        else:
            # running nuke. ensure additional collected outputs are parented
            # under the session
            session_item = self.collect_current_nuke_session(settings, parent_item)

            # Add session_item to the list
            items.append(session_item)

            # Also collect any output node items
            items.extend(self.collect_node_outputs(settings, session_item))

            # if we have work path templates, collect matching files to publish
            for work_template in settings["Work File Templates"].value:
                items.extend(self.collect_work_files(settings, session_item, work_template))

        # Return the list of items
        return items

    def collect_current_nukestudio_session(self, settings, parent_item):
        """
        Analyzes the current session open in NukeStudio and parents a subtree of
        items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """

        # import here since the hooks are imported into nuke and nukestudio.
        # hiero module is only available in later versions of nuke

        active_project = hiero.ui.activeSequence().project()

        items = []
        for project in hiero.core.projects():

            # get the current path
            file_path = project.path()
            if not file_path:
                # the project has not been saved before (no path determined).
                # provide a save button. the project will need to be saved before
                # validation will succeed.
                self.logger.warning(
                    "The Nuke Studio project '%s' has not been saved." %
                    (project.name()),
                    extra=self._get_save_as_action(project)
                )

            # Define the item's properties
            properties = {}

            # add the project object to the properties so that the publish
            # plugins know which open project to associate with this item
            properties["project"] = project

            # create the session item for the publish hierarchy
            # get item context based on project
            work_path_template = str(settings['Item Types']['file.nukestudio']['work_path_template'])
            item_context = self._get_item_context_from_path(work_path_template, file_path, parent_item, [])

            project_item = self._add_file_item(settings,
                                               parent_item,
                                               project.path(),
                                               False,
                                               None,
                                               project.name(),
                                               "nukestudio.project",
                                               item_context,
                                               properties)

            self.logger.info(
                "Collected Nuke Studio project: %s" % (project_item.name,))
            items.append(project_item)

            # enable the active project and expand it. other projects are
            # collapsed and disabled.
            if active_project and active_project.guid() == project.guid():
                project_item.expanded = True
                project_item.checked = True
                project_item.properties.active = True
            elif active_project:
                # there is an active project, but this isn't it. collapse and
                # disable this item
                project_item.expanded = False
                project_item.checked = False
        return items
