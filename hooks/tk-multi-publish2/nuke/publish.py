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
import nuke
import sgtk
import fnmatch
from dd.runtime import api
api.load("frangetools")
import frangetools

HookBaseClass = sgtk.get_hook_baseclass()


class NukePublishDDValidationPlugin(HookBaseClass):
    """
    Inherits from NukePublishFilesPlugin
    """
    def __init__(self, parent, **kwargs):
        """
        Construction
        """
        # call base init
        super(NukePublishDDValidationPlugin, self).__init__(parent, **kwargs)

    def _build_dict(self, seq, key):
        """
        Creating a dictionary based on a key.

        :param seq: list of dictionaries
        :param key: dictionary key from which to create the dictionary
        :return: dict with information for that particular key
        """
        return dict((d[key], dict(d, index=index)) for (index, d) in enumerate(seq))


    def _framerange_to_be_published(self, item):
        """
        Since users have the option to render only a subset of frames,
        adding validation to check if the full frame range is being published.

        :param item: Item to process
        :return: True if yes false otherwise
        """
        lss_path = item.properties['node']['cached_path'].value()
        lss_data = frangetools.getSequence(lss_path)

        # Since lss_data will be a list of dictionaries,
        # building a dictionary from key value for the ease of fetching data.
        info_by_path = self._build_dict(lss_data, key="path")
        missing_frames = info_by_path.get(lss_path)['missing_frames']
        root = nuke.Root()

        # If there are no missing frames, then checking if the first and last frames match with root first and last
        # Checking with root because _sync_frame_range() will ensure root is up to date with shotgun
        if missing_frames:
            self.logger.warning("Renders Mismatch! Incomplete renders on disk.")
            nuke.message("WARNING!\n"+item.properties['node'].name()+"\nRenders Mismatch! Incomplete renders on disk.")
        else:
            first_rendered_frame = info_by_path.get(lss_path)['frame_range'][0]
            last_rendered_frame = info_by_path.get(lss_path)['frame_range'][1]

            if (first_rendered_frame > root.firstFrame()) or (last_rendered_frame < root.lastFrame()):
                self.logger.warning("Renders Mismatch! Incomplete renders on disk.")
                nuke.message("WARNING!\n"+item.properties['node'].name()+"\nRenders Mismatch! Incomplete renders on disk.")
            elif (first_rendered_frame < root.firstFrame()) or (last_rendered_frame > root.lastFrame()):
                self.logger.warning("Renders Mismatch! Extra renders on disk.")
                nuke.message("WARNING!\n"+item.properties['node'].name()+"\nRenders Mismatch! Extra renders on disk.")
        return True

    def _collect_file_nodes_in_graph(self, node, visited_files):
        """
        Traverses the graph for the write node being validated and collects all the
        nodes with file knobs and their respective file values

        :param node: The node being visited in the graph
        :param visited_files: Dictionary of nodes and associated files
        :return: Dictionary of all the file nodes in the graph and associated files
        """
        if self.visited_dict[node] == 0:
            # get the file path if exists
            if self._contains_active_file_knob(node):
                node_file_path = node['file'].value()
                if node_file_path:
                    visited_files.setdefault(node_file_path, []).append(node.name())
            # set visited to 1 for the node so as not to revisit
            self.visited_dict[node] = 1
            dep = node.dependencies()
            if dep:
                for item in dep:
                    self._collect_file_nodes_in_graph(item, visited_files)

        return visited_files

    @staticmethod
    def _check_file_validity(visited_files, suspicious_paths, valid_paths, show_path):
        """
        Checks for unpublished and invalid paths in files collected after graph traversal
        :param visited_files: File nodes and associated files collected during traversal
        :param suspicious_paths: Dict to capture unpublished/invalid paths
        :param valid_paths: Dict with all the valid paths for a particular show
        :param show_path: Show path i.e /dd/shows/<SHOW>
        :return: Suspicious files found among the visited files
        """
        for file_path in visited_files:
            valid_patterns = [pattern for pattern in valid_paths.itervalues()]
            matches_valid_pattern = any([fnmatch.fnmatch(file_path, pattern) for pattern in valid_patterns])
            if show_path in file_path and not matches_valid_pattern:
                suspicious_paths['unpublished'].append(file_path)
            elif show_path not in file_path and not matches_valid_pattern:
                suspicious_paths['invalid'].append(file_path)
        return suspicious_paths

    def _read_and_camera_file_paths(self, item):
        """
        Checks if the files loaded are published or from valid locations i.e
        /dd/shows/<show>/SHARED, dd/shows/<show>/<seq>/SHARED, dd/shows/<show>/<seq>/<shot>/SHARED
        or
        /dd/shows/<show>, /dd/library

        :param item: Item to process
        :return: True if paths are published or valid false otherwise
        """
        self.visited_dict = item.parent.properties['visited_dict']

        show_path = os.path.join(os.environ['DD_SHOWS_ROOT'], os.environ['DD_SHOW'])
        valid_paths = {
            'dd_library': os.path.join(os.environ['DD_ROOT'], 'library', '**'),  # dd library path
            'show': show_path,
            'show_pub': os.path.join(show_path, '**', 'SHARED', '*'),  # show published glob
        }

        # Collect all the nodes associated with a write node
        # For all the read, readgeo and camera nodes present in the write node graph, check for 'file' knob.
        # If its populated, get the file path.
        suspicious_paths = {
            'unpublished': [],
            'invalid': [],
        }
        visited_files = {}
        self._collect_file_nodes_in_graph(item.properties['node'], visited_files)
        self._check_file_validity(visited_files, suspicious_paths, valid_paths, show_path)
        item.parent.properties['visited_dict'] = self.visited_dict

        if suspicious_paths['unpublished']:
            unpublished = ""
            for path in suspicious_paths['unpublished']:
                unpublished += "\n\n{}: {}".format(visited_files[path], path)
            self.logger.warning(
                "Unpublished files found.",
                extra={
                    "action_show_more_info": {
                        "label": "Show Info",
                        "tooltip": "Show unpublished files",
                        "text": "Unpublished files.\n{}".format(unpublished)
                    }
                }
            )
            nuke.message("WARNING!\n{} node".format(item.properties['node'].name())
                         + "\nUnpublished files found.{}".format(unpublished))

        if suspicious_paths['invalid']:
            paths = ""
            for item in suspicious_paths['invalid']:
                paths += "\n\n{}: {}".format(visited_files[item], item)
            self.logger.error("Invalid paths! Try loading from Shotgun menu -> Load.",
                              extra={
                                  "action_show_more_info": {
                                      "label": "Show Info",
                                      "tooltip": "Show invalid path(s)",
                                      "text": "Paths not in {}: {}".format(valid_paths.values(), paths)
                                  }
                              }
                              )
            return False
        return True


    def _sync_frame_range(self, item):
        """
        Checks whether frame range is in sync with shotgun.

        :param item: Item to process
        :return: True if yes false otherwise
        """
        context = item.context
        entity = context.entity

        # checking entity validity since it can be invalid/empty in case of Project Level item
        if entity:
            frame_range_app = self.parent.engine.apps.get("tk-multi-setframerange")
            if not frame_range_app:
                # return valid for asset/sequence entities
                self.logger.warning("Unable to find tk-multi-setframerange app. "
                                    "Not validating frame range.")
                return True

            sg_entity_type = entity["type"]
            sg_filters = [["id", "is", entity["id"]]]
            in_field = frame_range_app.get_setting("sg_in_frame_field")
            out_field = frame_range_app.get_setting("sg_out_frame_field")
            fields = [in_field, out_field]

            # get the field information from shotgun based on Shot
            # sg_cut_in and sg_cut_out info will be on Shot entity, so skip in case this info is not present
            data = self.sgtk.shotgun.find_one(sg_entity_type, filters=sg_filters, fields=fields)
            if in_field not in data or out_field not in data:
                return True
            elif data[in_field] is None or data[out_field] is None:
                return True

            # compare if the frame range set at root level is same as the shotgun cut_in, cut_out
            root = nuke.Root()
            if root.firstFrame() != data[in_field] or root.lastFrame() != data[out_field]:
                self.logger.warning("Frame range not synced with Shotgun.")
                nuke.message("WARNING! Frame range not synced with Shotgun.")
        return True


    def _non_sgtk_writes(self):
        """
        Checks for non SGTK write nodes present in the scene.

        :return: True if yes false otherwise
        """
        write_nodes = ""
        # get all write and write geo nodes
        write = nuke.allNodes('Write') + nuke.allNodes('WriteGeo')

        if write:
            for item in range(len(write)):
                write_nodes += "\n" + write[item].name()
            self.logger.error("Non SGTK write nodes detected here.",
                              extra={
                                  "action_show_more_info": {
                                      "label": "Show Info",
                                      "tooltip": "Show non sgtk write node(s)",
                                      "text": "Non SGTK write nodes:\n{}".format(write_nodes)
                                  }
                              }
                              )
            return False
        return True

    def _write_node_path_duplicacy(self, item):
        node_path = item.properties['node']['cached_path'].value()
        node_name = item.properties['node'].name()
        all_paths = item.parent.properties['write_node_paths_dict'].values()
        if node_path in all_paths:
            duplicate_path_node = [key for (key, value) in item.parent.properties['write_node_paths_dict'].items()
                                   if value == node_path]
            self.logger.error("Duplicate output path.",
                              extra={
                                  "action_show_more_info": {
                                      "label": "Show Info",
                                      "tooltip": "Show node(s) with identical output path",
                                      "text": "Following node(s) have same output path as {}:\n\n{}".
                                      format(node_name, '\n'.join(duplicate_path_node))
                                  }
                              }
                              )
            return False
        item.parent.properties['write_node_paths_dict'] = {node_name: node_path}
        return True

    @staticmethod
    def _contains_active_file_knob(node):
        if (node.knob('disable')) and (node['disable'].value() == 0):
            if node.knob('file'):
                return True

    def validate(self, task_settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param task_settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """
        status = True
        # Segregating the checks, specifically for general nuke script
        if item.type == 'nuke.session':
            status = self._non_sgtk_writes() and status
            status = self._sync_frame_range(item) and status
            # Properties to be used by child write nodes
            item.properties['visited_dict'] = {node: 0 for node in nuke.allNodes()}
            item.properties['write_node_paths_dict'] = dict()

        # Segregating the checks, specifically for write nodes
        if item.properties.get("node"):
            status = self._read_and_camera_file_paths(item) and status
            status = self._framerange_to_be_published(item) and status
            status = self._write_node_path_duplicacy(item) and status

        if not status:
            return status

        return super(NukePublishDDValidationPlugin, self).validate(task_settings, item)
