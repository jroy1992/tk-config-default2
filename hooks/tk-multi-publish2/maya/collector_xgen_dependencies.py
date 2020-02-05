# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import glob
import copy
import traceback
import os

import maya.cmds as cmds
import sgtk
from sgtk import TankError
from sgtk.templatekey import SequenceKey
from maya_xgen_handle import MayaXgenHandle

HookBaseClass = sgtk.get_hook_baseclass()


# This is a dictionary of file type info that allows the basic collector to
# identify common production file types and associate them with a display name,
# item type, and config icon.
MAYA_SESSION_ITEM_TYPES = {
    "maya.session": {
        "icon_path": "{self}/hooks/icons/maya.png",
        "type_display": "Maya Session"
    },
    "maya.geometry": {
        "icon_path": "{self}/hooks/icons/geometry.png",
        "type_display": "Geometry"
    }
}


class MayaSessionCollector(HookBaseClass):
    """
    Collector that operates on the current maya session. Should
    inherit from the basic collector hook.
    """
    def __init__(self, parent, **kwargs):
        """
        Construction
        """
        # call base init
        super(MayaSessionCollector, self).__init__(parent, **kwargs)

        # cache the workfiles app
        self.__workfiles_app = self.parent.engine.apps.get("tk-multi-workfiles2")

    @property
    def settings_schema(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default_value": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """
        schema = super(MayaSessionCollector, self).settings_schema
        schema["Item Types"]["default_value"].update(MAYA_SESSION_ITEM_TYPES)
        schema["Work File Templates"] = {
            "type": "list",
            "values": {
                "type": "template",
                "description": "",
                "fields": "context, *"
            },
            "default_value": [],
            "allows_empty": True,
            "description": "A list of templates to use to search for work files."
        }

        # Schema for Xgen file
        schema["file.xgen"] = {
            "type": "list",
            "description": "List of xgen file publish settings.",
            "skip_validation": "True",
            "values": {
                "type": "dict",
                "description": "",
                "items": {
                    "extensions": {
                        "type": "str"
                    },
                    "publish_type": {
                        "type": "str"
                    },
                    "publish_path_template": {
                        "type": "template",
                        "default": {},
                        "description": "Xgen file publish path template"
                    }
                }
            },
        }

        # Schema for Xgen patch cache
        schema["file.xgen.patch"] = {
            "type": "list",
            "description": "List of xgen file patch publish settings.",
            "skip_validation": "True",
            "values": {
                "type": "dict",
                "description": "",
                "items": {
                    "extensions": {
                        "type": "str"
                    },
                    "publish_type": {
                        "type": "str"
                    },
                    "publish_path_template": {
                        "type": "template",
                        "default": {},
                        "description": "Xgen file patch publish path template"
                    }
                }
            },
        }
        # Schema for Xgen collection folder
        schema["file.xgen.collection"] = {
            "type": "list",
            "description": "List of xgen collection publish settings.",
            "skip_validation": "True",
            "values": {
                "type": "dict",
                "description": "",
                "items": {
                    "extensions": {
                        "type": "str"
                    },
                    "publish_type": {
                        "type": "str"
                    },
                    "publish_path_template": {
                        "type": "template",
                        "default": {},
                        "description": "Xgen collection publish path template"
                    }
                }
            },
        }
        # Schema for 3dPaintTextures
        schema["file.3dPaintTextures"] = {
            "type": "list",
            "description": "List of 3dPaintTextures publish settings.",
            "skip_validation": "True",
            "values": {
                "type": "dict",
                "description": "",
                "items": {
                    "extensions": {
                        "type": "str"
                    },
                    "publish_type": {
                        "type": "str"
                    },
                    "publish_path_template": {
                        "type": "template",
                        "default": {},
                        "description": "3dPaintTextures publish path template"
                    }
                }
            },
        }
        return schema

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current session open in Maya and parents a
        subtree of items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance
        """
        items = super(MayaSessionCollector, self).process_current_session(settings, parent_item)

        # items = []

        # # create an item representing the current maya session
        # session_item = self.collect_current_maya_session(settings, parent_item)
        # items.append(session_item)
        #
        # # look at the render layers to find rendered images on disk
        # items.extend(self.collect_rendered_images(settings, session_item))

        session_item = None
        for item in items:
            if item.type_spec == "maya.session":
                session_item = item
                break
        # Adding xgen dependencies as session item properties
        self.collect_xgen_dependencies(settings, session_item)
        # print 'session_item.properties.xgen_dependencies: ', session_item.properties.xgen_dependencies

        # Collecting 3dPainteTextures
        self.collect_paint_textures(settings, session_item)
        # print 'parent_item.properties.paint_textures: ', session_item.properties.paint_textures

        # # collect any scene geometry
        # if cmds.ls(geometry=True, noIntermediate=True):
        #     items.extend(self.collect_session_geometry(settings, session_item))
        #
        # # if we have work path templates, collect matching files to publish
        # for work_template in settings["Work File Templates"].value:
        #     items.extend(self.collect_work_files(settings, session_item, work_template))

        # Return the list of items
        return items

    def collect_paint_textures(self, settings, parent_item):
        """
        Collect 3dPainteTextures as session item
        properties attribute with name "paint_textures"

        The reason for collecting entire folder instated
        of individual files is then we need to crate really
        long dictionary of work_files and publish_files and run
        a long loop. Unless there is a way to publish dir
        could  be same for multiple dependency files.

        :param settings:
        :param parent_item:
        :return:
        """
        # Get maya scene name
        scene_name = os.path.basename(cmds.file(q=True, sceneName=True))
        # Removing scene name extension
        scene_name = os.path.splitext(scene_name)[0]

        workspace_path = cmds.workspace(q=True, rootDirectory=True)

        paintTextures_dir = os.path.join(workspace_path, 'sourceimages', '3dPaintTextures', scene_name)

        # Adding 3dPaintTextures folder in collector
        if os.path.isdir(paintTextures_dir):
            dict_values = dict()
            dict_values.update(self.resolve_custom_path_template(
                settings, parent_item, 'file.3dPaintTextures', paintTextures_dir))
            self.logger.info(" Collected file.3dPaintTextures: '%s'" % (paintTextures_dir))

            parent_item.properties.paint_textures = dict_values

        return None

    def collect_xgen_dependencies(self, settings, parent_item):
        """
        Collect live palettes dependencies as session item
        properties attribute with name "xgen_dependencies"

        :param settings:
        :param parent_item: session item
        :return:
        """

        # Instance of maya xgen handle
        xgen_handle = MayaXgenHandle()

        # Collecting all available live palettes information
        palette_info = xgen_handle.get_live_palette_info()

        if palette_info:
            xgen_dependencies = dict()
            for palette in palette_info.iterkeys():

                dict_values = dict()

                # Adding xgen file in collector
                xgFileName = palette_info[palette]['xgFileName']
                if os.path.isfile(xgFileName):
                    dict_values.update(
                        self.resolve_custom_path_template(
                            settings, parent_item, 'file.xgen', str(xgFileName)))
                    self.logger.info(" Collected file.xgen: '%s'" % (os.path.basename(xgFileName)))
                else:
                    error_msg = "Collect Xgen Dependencies failed. " \
                                "Missing xgen file: '{}'".format(xgFileName)
                    self.logger.error(error_msg)
                    raise Exception(error_msg)

                # Adding xgen data path in collector
                xgDataPath = palette_info[palette]['xgDataPath']
                if os.path.isdir(xgDataPath):
                    dict_values.update(self.resolve_custom_path_template(
                        settings, parent_item, 'file.xgen.collection', xgDataPath))
                    self.logger.info(" Collected file.xgen.collection: '%s'" % (xgDataPath))
                else:
                    error_msg = "Collect Xgen Dependencies failed. " \
                                "Missing xgen data path: '{}'".format(xgDataPath)
                    self.logger.error(error_msg)
                    raise Exception(error_msg)

                # Adding xgen data path in collector
                xgPatchCache = palette_info[palette]['xgPatchCache']
                if os.path.isfile(xgPatchCache):
                    dict_values.update(self.resolve_custom_path_template(
                        settings, parent_item, 'file.xgen.patch', xgPatchCache))
                    self.logger.info(" Collected file.xgen.patch: '%s'" % (os.path.basename(xgPatchCache)))
                else:
                    error_msg = "Collect Xgen Dependencies failed. " \
                                "Missing xgen patch caches: '{}'".format(xgPatchCache)
                    self.logger.error(error_msg)
                    raise Exception(error_msg)

                xgen_dependencies[str(palette)] = dict_values
            parent_item.properties.xgen_dependencies = xgen_dependencies
        return None

    def resolve_custom_path_template(self, settings, parent_item, item_key, work_path):
        """
        Resolve custom work and publish path_template from the given work_path for the
        specified item.

        :param settings: collector settings
        :param parent_item: parent item
        :param item_key: valid settings item key
        :param work_path: source work path to resolve publish type and publish path
        :return: Resolved values in dict format: {publish_type:{work_path:, publish_path:}}
        """

        resolved_values = dict()

        work_tmpl = self.sgtk.template_from_path(work_path)
        fields = work_tmpl.get_fields(work_path)

        if item_key == 'file.xgen.collection':
            """
            By default xgen collection doesn't maintain versions 
            and link with source maya file. So to resolve this issue, 
            We are collecting session item fields and passing the 
            missing values to xgen collections publish template 
            fields which creates the folder with session file name 
            and publishes collections inside.
            """
            # Resolve session work path template
            session_work_path = parent_item.properties.path
            session_work_template = self.sgtk.template_from_path(session_work_path)
            session_item_fields = session_work_template.get_fields(session_work_path)

            # Adding required session name fields
            fields['Step'] = session_item_fields['Step']
            fields['name'] = session_item_fields['name']
            fields['version'] = session_item_fields['version']

        publish_tmp_name = settings[item_key]['publish_path_template'].value
        publish_tmp_obj = self.sgtk.templates[publish_tmp_name]
        publish_path = publish_tmp_obj.apply_fields(fields)
        publish_type = settings[item_key]['publish_type'].value

        resolved_values[publish_type] = {'work_path': str(work_path), 'publish_path': str(publish_path)}

        return resolved_values

