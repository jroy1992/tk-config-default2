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
import glob
import random
import nuke
import sgtk
import fnmatch
from dd.runtime import api
api.load("frangetools")
import frangetools

api.load('qt_py')
from Qt import QtWidgets, QtGui, QtCore

HookBaseClass = sgtk.get_hook_baseclass()

USER_FILE_SETTING_NAME = "Error On User File"


class DisplayUnpublishedFiles(QtWidgets.QWidget):
    def __init__(self, message, unpublished, gif_path):
        self.message = message
        self.message_label = QtWidgets.QLabel(self.message)
        self.unpublished = unpublished
        self.report_unpublished = QtWidgets.QTextEdit()
        self.success_label = QtWidgets.QLabel()
        self.report_replaced = QtWidgets.QLabel()
        self.gif_path = gif_path
        self.progress_note = QtWidgets.QLabel()
        self.mov_label = QtWidgets.QLabel()
        self.mov_layout = QtWidgets.QHBoxLayout()
        self.rewire_nodes_btn = QtWidgets.QPushButton("Replace user files with published versions...")

    def create_ui(self):
        self.main_dialog = QtWidgets.QDialog()
        self.main_dialog.setMinimumSize(1000, 400)
        main_layout = QtWidgets.QVBoxLayout()
        self.main_dialog.setLayout(main_layout)
        self.main_dialog.setWindowTitle(self.message)

        space_left = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        size = QtCore.QSize(256, 256)

        # We introduce the usage of gifs to grab attention in this UI, via which we expect artists' interactions
        # to continue to auto fix unpublished work paths when required
        gifs = glob.glob(os.path.join(self.gif_path, 'choice*.gif'))
        gif = random.choice(gifs)
        mov = QtGui.QMovie(gif)
        mov.setScaledSize(size)
        self.mov_label.setMovie(mov)
        mov.start()
        space_right = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        self.mov_layout.addItem(space_left)
        self.mov_layout.addWidget(self.mov_label)
        self.mov_layout.addItem(space_right)
        main_layout.addLayout(self.mov_layout)

        message_font = QtGui.QFont()
        message_font.setBold(True)
        self.message_label.setFont(message_font)
        main_layout.addWidget(self.message_label)
        self.report_unpublished.setPlainText(self.unpublished)
        self.report_unpublished.setReadOnly(True)
        self.report_unpublished.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        main_layout.addWidget(self.report_unpublished)

        self.progress_note.setFont(message_font)
        self.progress_note.setStyle(QtWidgets.QStyleFactory.create('Plastique'))
        main_layout.addWidget(self.progress_note)
        space = QtWidgets.QLabel()
        main_layout.addWidget(space)

        self.success_label.setFont(message_font)
        main_layout.addWidget(self.success_label)
        self.success_label.hide()
        self.report_replaced.setStyle(QtWidgets.QStyleFactory.create('Plastique'))
        self.report_replaced.setStyleSheet("color: #288f62")
        main_layout.addWidget(self.report_replaced)
        self.report_replaced.hide()

        spacer_1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        spacer_2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addItem(spacer_1)
        btn_layout.addItem(spacer_2)
        btn_layout.addWidget(self.rewire_nodes_btn)
        main_layout.addLayout(btn_layout)
        self.main_dialog.setLayout(main_layout)
        self.main_dialog.adjustSize()

    def display_ui(self):
        self.main_dialog.exec_()


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
        self._breakdown_app = self.parent.engine.apps.get('tk-multi-breakdown')

    @property
    def settings_schema(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default_value": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts
        as part of its environment configuration.
        """

        schema = super(NukePublishDDValidationPlugin, self).settings_schema

        validation_schema = {
            USER_FILE_SETTING_NAME: {
                "type": "bool",
                "default_value": True,
                "description": "Setting to Error the validation that checks for user paths in the nuke script."
            }
        }

        schema.update(validation_schema)

        return schema

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
                    visited_files.setdefault(node_file_path, []).append(nuke.Node.fullName(node))
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

    def _get_published_counterparts(self, unpublished_files):
        """
        Query shotgun and get published counterparts of the unpublished files

        :param unpublished_files: Unpublished files in the nuke script
        :return: Queried sg data for files which have published versions
        """
        filters = [["project.Project.name", "is", os.environ['DD_SHOW']], ['sg_path_to_source', 'in', unpublished_files]]
        fields = ['path', 'entity', 'task'] + self._breakdown_app.get_setting('additional_publish_fields')
        sg_data = self.parent.engine.shotgun.find('PublishedFile', filters, fields)
        sg_data = {entity['sg_path_to_source']: entity for entity in sg_data}
        return sg_data

    def _rewire_script_and_report(self, suspicious_paths, visited_files, sg_data, display_files):
        """
        Replace nodes with unpublished file paths and update to have sgtk metadata

        :param suspicious_paths: Dict with unpublished and invalid paths
        :param visited_files: File nodes and associated files collected during traversal
        :param sg_data: Shotgun data for files which have published versions
        :param display_files: DisplayUnpublishedFiles instance
        """
        self._update_progress_note(display_files.progress_note, "Replacement initiated...")
        items = []
        for key, value in sg_data.iteritems():
            nodes = visited_files[key]
            for node in nodes:
                display_files.progress_note.clear()
                self._update_progress_note(display_files.progress_note,
                                           ("Attempting file replacement on node: {}".format(node)))
                node_data = dict()
                node_data["node"] = node
                node_data["type"] = nuke.toNode(node).Class()
                node_data["path"] = value["path"]["local_path"]
                node_data["sg_data"] = value
                items.append(node_data)
        if items:
            self._breakdown_app.execute_hook_method('hook_scene_operations', 'update', items=items)
            self._report_successful_replacements(sg_data, visited_files, display_files)
        self._report_failed_replacements(sg_data, suspicious_paths, visited_files, display_files)

    def _report_successful_replacements(self, sg_data, visited_files, display_files):
        """
        Report any files on which replace attempt succeeded

        :param sg_data: Shotgun data for files which have published versions
        :param visited_files: File nodes and associated files collected during traversal
        :param display_files: DisplayUnpublishedFiles instance
        """
        display_files.success_label.show()
        display_files.success_label.setText("Files on below nodes were successfully replaced:")
        success_report = ""
        for path in sg_data:
            success_report += "{}: {}\n".format(visited_files[path], sg_data[path]['path']['local_path'])
        self.logger.debug("Successful Replacements: {}".format(success_report))
        display_files.report_replaced.clear()
        display_files.report_replaced.show()
        display_files.report_replaced.setText(success_report)

    def _report_failed_replacements(self, sg_data, suspicious_paths, visited_files, display_files):
        """
        Report any files on which replace attempt failed

        :param sg_data: Shotgun data for files which have published versions
        :param suspicious_paths: Dict with unpublished and invalid paths
        :param visited_files:File nodes and associated files collected during traversal
        :param display_files: DisplayUnpublishedFiles instance
        """
        failure_report = ""
        self.logger.debug("Paths to be replaced: {}".format('\n'.join(suspicious_paths['unpublished'])))
        if sg_data:
            failed_replace = list(set(suspicious_paths['unpublished']) - set(sg_data.keys()))
        else:
            failed_replace = suspicious_paths['unpublished']
        for path in failed_replace:
            failure_report += "{}: {}\n".format(visited_files[path], path)
        self.logger.debug("Failed Replacements: {}".format(failure_report))

        display_files.report_unpublished.clear()
        if failed_replace:
            color = "#e30202"
            display_files.report_unpublished.setPlainText(failure_report)
            display_files.report_unpublished.setStyleSheet("color: {}".format(color))
            message = "The above versions have not been published." \
                      "\nPlease get these versions published if you wish to use them."
            self._update_progress_note(display_files.progress_note, message, color=color)
            display_files.mov_label.hide()
            display_files.mov_layout.setParent(None)
            display_files.main_dialog.adjustSize()
        else:
            display_files.message_label.clear()
            display_files.message_label.setText("Success!\nAll user files replaced with published versions")
            gif = os.path.join(display_files.gif_path, 'approved.gif')
            mov = QtGui.QMovie(gif)
            size = QtCore.QSize(256, 200)
            mov.setScaledSize(size)
            display_files.mov_label.setMovie(mov)
            mov.start()
            display_files.progress_note.hide()
            display_files.report_unpublished.hide()
            display_files.main_dialog.adjustSize()
        display_files.rewire_nodes_btn.setEnabled(False)

    @staticmethod
    def _update_progress_note(progress_note, message, color='white'):
        """
        Update the note which what is going on (eg: file on which node is being replaced)

        :param progress_note: Qt label showing the node wise update
        :param message: Message to be reflected on the note
        :param color: Note color (eg: red for error, green for success, white otherwise)
        """
        progress_note.clear()
        progress_note.setStyleSheet("color: {};".format(color))
        progress_note.setText(message)

    def _read_and_camera_file_paths(self, task_settings, item):
        """
        Checks if the files loaded are published or from valid locations i.e
        /dd/shows/<show>/SHARED, dd/shows/<show>/<seq>/SHARED, dd/shows/<show>/<seq>/<shot>/SHARED
        or
        /dd/shows/<show>, /dd/library

        :param item: Item to process
        :return: True if paths are published or valid false otherwise
        """
        status = True
        logger_method = None
        self.visited_dict = item.parent.properties['visited_dict']

        show_path = os.path.join(os.environ['DD_SHOWS_ROOT'], os.environ['DD_SHOW'])
        valid_paths = {
            'dd_library': os.path.join(os.environ['DD_ROOT'], 'library', '**'),  # dd library path
            'shot_pub': os.path.join(show_path, '**', 'SHARED', '*'),  # shot published glob
            'show_pub': os.path.join(show_path, 'SHARED', '*'),  # show published glob
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
                unpublished += "{}: {}\n".format(visited_files[path], path)
            message = "Unpublished files found for {}:".format(item.properties['node'].name())

            user_file_error = task_settings[USER_FILE_SETTING_NAME].value
            if user_file_error:
                sg_data = self._get_published_counterparts(suspicious_paths['unpublished'])
                gifs_path = self.parent.expand_path("{config}/resources")
                display_files = DisplayUnpublishedFiles(message, unpublished, gifs_path)
                display_files.create_ui()
                display_files.rewire_nodes_btn.clicked.connect(lambda: self._rewire_script_and_report(suspicious_paths,
                                                                                                      visited_files,
                                                                                                      sg_data,
                                                                                                      display_files))
                display_files.display_ui()
                if sg_data:
                    failed_replace = []
                    # This is in case the user closes the UI without running "Replace user files with published files"
                    for path in suspicious_paths['unpublished']:
                        node_name = visited_files[path][0]
                        node = nuke.toNode(node_name)
                        # Check if the file on node now is same as when initially collected during graph traversal
                        if node.knob('file').value() == path:
                            failed_replace.append(path)
                else:
                    failed_replace = suspicious_paths['unpublished']
                if failed_replace:
                    logger_method = self.logger.error
                    status = False
            else:
                nuke.message(message+'\n'+unpublished)
                logger_method = self.logger.warning
                status = not user_file_error

            if logger_method:
                logger_method(
                    "Unpublished files found.",
                    extra={
                        "action_show_more_info": {
                            "label": "Show Info",
                            "tooltip": "Show unpublished files",
                            "text": "Unpublished files.\n{}".format(unpublished)
                        }
                    }
                )

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
            status = False
        return status


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
            item.properties['visited_dict'] = {node: 0 for node in nuke.allNodes(recurseGroups=True)}
            item.properties['write_node_paths_dict'] = dict()

        # Segregating the checks, specifically for write nodes
        if item.properties.get("node"):
            status = self._read_and_camera_file_paths(task_settings, item) and status
            status = self._framerange_to_be_published(item) and status
            status = self._write_node_path_duplicacy(item) and status

        if not status:
            return status

        return super(NukePublishDDValidationPlugin, self).validate(task_settings, item)
