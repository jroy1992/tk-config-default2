# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import copy
import os
import maya.cmds as cmds
import sgtk
from sgtk.platform.qt import QtGui
from sgtk.util import filesystem

# DD imports
import dd.runtime.api
dd.runtime.api.load('wam')
from wam.core import Workflow
from wam.datatypes.element import Element

dd.runtime.api.load('modelpublish')
from modelpublish.lib.introspection import find_model_root_nodes

# for validate workflow
dd.runtime.api.load('indiapipeline')

HookBaseClass = sgtk.get_hook_baseclass()


class MayaPublishSessionRigPlugin(HookBaseClass):
    """
    Inherits from MayaPublishSessionPlugin
    """
    def validate(self, task_settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.
        Additional check for maya scene using validations from Rigpublish.

        :param task_settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """
        if not item.get_property("skip_tide"):
            item.local_properties["skip_tide"] = QtGui.QMessageBox.question(None, 'Skip Tide?',
                                                                            'Would you like to skip Tide validations?',
                                                                            QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        if item.get_property("skip_tide") == QtGui.QMessageBox.Yes:
            skip_message = "Skipping Tide validations!"
            self.logger.warning(skip_message)

            # add to publish comment, if not already added
            if not item.description:
                item.description = skip_message
            elif skip_message not in item.description:
                item.description = "{} {}".format(item.description, skip_message)
            return super(MayaPublishSessionRigPlugin, self).validate(task_settings, item)

        # create list of elements from maya nodes to collect results about
        workflow_data = {"elements": []}
        valid_node_name = item.context.entity['name']
        role = os.environ['DD_ROLE']
        valid_node_name = '{}_{}'.format(valid_node_name, role)

        # assume all children are lod nodes (they should be, if hierarchy is correct)
        for child in cmds.listRelatives(valid_node_name, children=True):
            elem_dict = {
                "name": valid_node_name,
                "selection_node": valid_node_name,
                "lod": child
            }
            workflow_data["elements"].append(Element(**elem_dict))

        workflow = Workflow.loadFromFile("indiapipeline/model_validate.wam", search_contexts=True)
        return_data = workflow.run(workflow_data)
        wam_exception = return_data['wam_exit_reason']

        if wam_exception is not None:
            # something wrong with workflow execution or user clicked cancel
            self.logger.error("User clicked cancel or error in rigpublish "
                              "validations: {}".format(wam_exception.__class__.__name__),
                              extra={
                                  "action_show_more_info": {
                                      "label": "Show Error",
                                      "tooltip": "Show stacktrace from wam",
                                      "text": return_data['wam_exit_stack'] +
                                              "\nCheck terminal/logs for more details."
                                  }
                              }
                              )
            return False

        return super(MayaPublishSessionRigPlugin, self).validate(task_settings, item)