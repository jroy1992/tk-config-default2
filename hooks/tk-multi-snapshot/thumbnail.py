# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import tempfile
import uuid
import re

import tank
from tank import Hook


class ThumbnailHook(Hook):
    """
    Hook that can be used to provide a pre-defined thumbnail
    for the snapshot
    """

    def execute(self, **kwargs):
        """
        Main hook entry point

        :return:        String
                        Hook should return a file path pointing to the location of
                        a thumbnail file on disk that will be used for the snapshot.
                        If the hook returns None then the screenshot functionality
                        will be enabled in the UI.
        """

        # get the engine name from the parent object (app/engine/etc.)
        engine_name = self.parent.engine.name

        # depending on engine:
        if engine_name == "tk-3de4":
            return self._extract_3de4_thumbnail()

        return super(ThumbnailHook, self).execute(kwargs)

    def _extract_3de4_thumbnail(self):
        import tde4
        SIZE = 600

        mw_width, mw_height = tde4.getMainWindowResolution()
        png_pub_path = os.path.join(tempfile.gettempdir(), "%s_sgtk.png" % uuid.uuid4().hex)

        # find the approx middle
        offset_x = (mw_width - SIZE)/2
        offset_y = (mw_height - SIZE)/2

        # screenshot it
        if tde4.saveMainWindowScreenShot(png_pub_path, "IMAGE_PNG", offset_x, offset_y, SIZE, SIZE):
            return png_pub_path

        return None
