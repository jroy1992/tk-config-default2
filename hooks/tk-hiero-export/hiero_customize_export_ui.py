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

import hiero.core
import hiero.ui

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

        # from selected project
        view = hiero.ui.activeView()
        if hasattr(view, 'selection'):
            selection = view.selection()

            if isinstance(view, hiero.ui.BinView):
                item = selection[0]

                # iterate until you get project
                while hasattr(item, 'parentBin') and item != isinstance(item.parentBin(), hiero.core.Project):
                    item = item.parentBin()

                project_name = item.name()
                if ".v" in project_name:
                    version = project_name.split(".")[1]
                    version_number = int(version.split("v")[1])
                    print "Selected project: %s, version: %d" % (project_name, version_number)

        return version_number

    def get_default_preset_properties(self):

        properties = {

            'shotgunShotCreateProperties': {
                'sg_cut_type': 'Boards',
                'collateSequence': False,
                'collateShotNames': False,
                'collateTracks': False,
                'collateCustomStart': True,
            },

            'cutLength': True,
            'cutUseHandles': False,
            'cutHandles': 12,
            'includeRetimes': False,
            'startFrameSource': 'Custom',
            'startFrameIndex': 1001,
        }

        return properties

    def get_transcode_exporter_ui_properties(self):

        return [

            dict(
                name="burninDataEnabled",
                value=True,
            ),
            dict(
                name="burninData",
                value={
                    'burnIn_bottomRight': '[frame]',
                    'burnIn_topLeft': '',
                    'burnIn_topMiddle': '',
                    'burnIn_padding': 120,
                    'burnIn_topRight': '',
                    'burnIn_bottomMiddle': '[frames {first}]-[frames {last}]',
                    'burnIn_bottomLeft': '{sequence}_{shot}',
                    'burnIn_textSize': 28,
                    'burnIn_font': "/dd/facility/lib/fonts/Arial Bold.ttf",
                    },
            ),
        ]






