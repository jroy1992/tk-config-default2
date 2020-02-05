# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
from sgtk.util import filesystem
import os
import xgenm as xg
import maya.cmds as cmds
import pprint
from maya_xgen_handle import MayaXgenHandle

HookBaseClass = sgtk.get_hook_baseclass()

class MayaPublishSessionGroomPlugin(HookBaseClass):
    """
    Inherits from MayaPublishSessionPlugin
    Modified to export xgen palettes and groom_set if its available in scene.
    """

    def publish_files(self, task_settings, item, publish_path, work_path=None, publish_type=None, palette=None):
        """
        This method publishes (copies) the item's path property to the publish location.

        :param task_settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :param publish_path: The output path to publish files to
        """
        publisher = self.parent
        path = item.properties.get("path")
        if not path:
            raise KeyError("Base class implementation of publish_files() method requires a 'path' property.")

        # Determine if we should seal the copied files or not
        seal_files = item.properties.get("seal_files", True)

        xgen_handle = MayaXgenHandle()

        if publish_type == "Xgen Collection":
            publisher.util.copy_folder([work_path], publish_path, seal_folder=seal_files)
            self.logger.info("Published Xgen Collection: {}".format(publish_path))

        elif publish_type == 'Xgen Patch File':
            publisher.util.copy_files([work_path], publish_path, seal_files=seal_files, is_sequence=False)
            self.logger.info("Published Xgen Patch File: {}".format(publish_path))

        elif publish_type == "Xgen Files":
            # Exporting temporary remapped palettes to publish path
            xg.exportPalette(palette, publish_path)
            self.logger.info("Published Xgen File: {}".format(publish_path))
            if seal_files:
                filesystem.seal_file(publish_path)

        elif publish_type == '3dPaintTextures':
            publisher.util.copy_folder([work_path], publish_path, seal_folder=seal_files)
            self.logger.info("Published 3dPaintTextures: {}".format(publish_path))

        else:
            """
            Proceed and publish Maya session item
            - We also need to remap 3dPaintTexture maps from publish dir. 
            Problem with adding this under 3dPaintTextures publish type is 
            Maya creates default texture directory on server before session item publish.
            - Secondly if xgen dependencies are exist in scene then 
            """
            work_path = path

            self.remap_paint_textures_from_target(item, xgen_handle, target='publish_path')

            if item.get_property("xgen_dependencies"):
                """
                If xgen dependencies are exists in the scene then perform predefine nodes 
                export action instead of coping entire session file.
                """

                # Re-mapping xgen file name from publish path
                xgen_dependencies = item.properties.xgen_dependencies

                for palette in xgen_dependencies.iterkeys():
                    self.logger.info("Mapping Xgen Palettes from Publish Path...")
                    xgen_handle.set_cur_xgen_file(
                        palette, xgen_dependencies[palette]['Xgen Files']['publish_path'], check_existence=False)

                # Get predefined publish objects for grooming team
                cmds.select(self.get_publish_objects(), noExpand=True)
                publish_path = os.path.splitext(publish_path)[0]

                # EXPORT PUBLISH OBJECTS IF XGEN IS AVAILABLE IN SCENE
                self.logger.info("Exporting Session item to Publish Path...")
                published_path = cmds.file(
                    publish_path, exportSelected=True, force=True, options="v=0;", type='mayaAscii')
                cmds.select(clear=True)

                filesystem.seal_file(published_path)
                self.logger.info("Mapping Xgen Palettes from Workspace...")
                xgen_handle.set_palettes_from_workspace()

            else:
                """
                If xgen dependencies doesn't exists in the scene then perform copy session item file.
                """
                publisher.util.copy_files([work_path], publish_path, seal_files=seal_files, is_sequence=False)

            self.remap_paint_textures_from_target(item, xgen_handle, target='work_path')
            
            return publish_path

    @staticmethod
    def remap_paint_textures_from_target(item, xgen_handle, target=None):
        """
        Remap 3dPaintTextures from given target value.
        :param item: session item
        :param target: "publish_path" OR "work_path"
        :return:
        """
        if item.get_property("paint_textures"):
            """
            Re map 3dPaintTextures from target path to avoid map creations in shared location.
            """

            paint_textures = item.properties.paint_textures

            for key in paint_textures.keys():
                xgen_handle.re_map_source_images(str(paint_textures[key][target]))

    def publish(self, task_settings, item):
        """
        Executes the publish logic for the given item and task_settings.

        :param task_settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the task_settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """
        sg_fields = {}
        additional_fields = task_settings.get("additional_publish_fields").value or {}
        for template_key, sg_field in additional_fields.iteritems():
            if template_key in item.get_property("fields"):
                sg_fields[sg_field] = item.get_property("fields")[template_key]

        publish_name = item.get_property("publish_name")
        publish_version = item.get_property("publish_version")
        publish_user = item.get_property("publish_user", default_value=None)

        if item.get_property("xgen_dependencies"):
            item.properties["xgen_publish_ids"] = []

            # Instantiate Maya xgen handle
            xgen_handle = MayaXgenHandle()

            xgen_dependencies = item.properties.xgen_dependencies
            self.logger.info("Processing on xgen dependencies...")

            for palette, values in xgen_dependencies.items():
                publish_xgen_file = xgen_dependencies[palette]['Xgen Files']['publish_path']
                publish_dir = os.path.dirname(publish_xgen_file)
                publish_collection_dir = xgen_dependencies[palette]['Xgen Collection']['publish_path']

                # Parsing xgen file from publish path
                self.logger.info(
                    "Re mapping paths for '{}' from publish path {} ".format(palette, publish_dir))
                xgen_handle.set_palette_from_target(palette, publish_dir, publish_collection_dir, check_existence=False)

                for key in values.iterkeys():
                    publish_type = key
                    work_path = values[key]['work_path']
                    publish_path = values[key]['publish_path']

                    self.publish_files(task_settings, item, publish_path, work_path, publish_type, palette)
                    self._create_published_file_entity(task_settings, item, publish_path, publish_name, publish_user,
                                                       publish_version, publish_type, sg_fields)

        if item.get_property("paint_textures"):
            item.properties["3dPaintTextures_publish_ids"] = []

            paint_textures = item.properties.paint_textures
            self.logger.info("Processing on 3dPaintTextures...")

            for key in paint_textures.keys():
                publish_type = key
                work_path = paint_textures[key]['work_path']
                publish_path = paint_textures[key]['publish_path']

                self.publish_files(task_settings, item, publish_path, work_path, publish_type)
                self._create_published_file_entity(task_settings, item, publish_path, publish_name, publish_user,
                                                   publish_version, publish_type, sg_fields)

        # publish maya file
        super(MayaPublishSessionGroomPlugin, self).publish(task_settings, item)

    def _create_published_file_entity(self, task_settings, item, publish_path, publish_name, publish_user,
                                      publish_version, publish_type, sg_fields):
        publish_data = {
            "tk": self.parent.sgtk,
            "context": item.context,
            "comment": item.description,
            "path": publish_path,
            "name": publish_name,
            "created_by": publish_user,
            "version_number": publish_version,
            "thumbnail_path": item.get_thumbnail_as_path() or "",
            "published_file_type": publish_type,
            "dependency_ids": [],
            "dependency_paths": [],
            "sg_fields": sg_fields
        }

        self.logger.debug(
            "Populated Publish data...",
            extra={
                "action_show_more_info": {
                    "label": "Publish Data",
                    "tooltip": "Show the complete Publish data dictionary",
                    "text": "<pre>%s</pre>" % (pprint.pformat(publish_data),)
                }
            }
        )

        exception = None
        sg_publish_data = None
        # create the publish and stash it in the item properties for other
        # plugins to use.
        try:
            sg_publish_data = sgtk.util.register_publish(**publish_data)
            self.logger.info("Publish registered!")
            self.logger.debug(
                "Shotgun Publish data...",
                extra={
                    "action_show_more_info": {
                        "label": "Shotgun Publish Data",
                        "tooltip": "Show the complete Shotgun Publish Entity dictionary",
                        "text": "<pre>%s</pre>" % (pprint.pformat(sg_publish_data),)
                    }
                }
            )
        except Exception as e:
            import traceback
            exception = e
            self.logger.error(
                "Couldn't register Publish for %s" % item.name,
                extra={
                    "action_show_more_info": {
                        "label": "Show Error Log",
                        "tooltip": "Show the error log",
                        "text": traceback.format_exc()
                    }
                }
            )

        if not sg_publish_data:
            self.undo(task_settings, item)
        else:
            item.properties.xgen_publish_ids.append(sg_publish_data["id"])

            item.properties.setdefault("sg_publish_data_list", [])
            item.local_properties.setdefault("sg_publish_data_list", [])

            # add the publish data to local and global item properties
            item.local_properties.sg_publish_data_list.append(sg_publish_data)
            item.properties.sg_publish_data_list.append(sg_publish_data)

        if exception:
            raise exception

    def _get_dependency_ids(self, task_settings, item):
        """
        Extend dependency ids for additional items that has been added as item properties.
        :param task_settings:
        :param item:
        :return:
        """
        dependency_ids = super(MayaPublishSessionGroomPlugin, self)._get_dependency_ids(task_settings, item)
        if item.get_property("xgen_dependencies"):
            dependency_ids.extend(item.get_property("xgen_publish_ids"))
        if item.get_property("paint_textures"):
            dependency_ids.extend(item.get_property("3dPaintTextures_publish_ids"))
        return dependency_ids

    @staticmethod
    def get_publish_objects():
        """
        To export xgen palettes, groom_set and associated node and pass as publish item file path
        to make sure only required data get published.
        :return: If session has xgen palettes then exported file path else the same input path.
        """
        publish_dependencies = []

        # Select all palettes available in scene.
        publish_dependencies.extend([x for x in xg.palettes()])
        # Select object set with name 'groom_set' to export with publish data.
        if cmds.objExists('groom_set') and cmds.nodeType('groom_set') == 'objectSet':
            publish_dependencies.append('groom_set')

        return publish_dependencies

