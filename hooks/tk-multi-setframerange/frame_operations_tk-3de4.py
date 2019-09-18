# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import tde4

import sgtk
from sgtk import TankError

HookBaseClass = sgtk.get_hook_baseclass()


class FrameOperation(HookBaseClass):
    """
    Hook called to perform a frame operation with the
    current scene
    """

    def execute(self, operation, in_frame=None, out_frame=None, **kwargs):
        """
        Main hook entry point

        :operation: String
                    Frame operation to perform

        :in_frame: int
                    in_frame for the current context (e.g. the current shot,
                                                      current asset etc)

        :out_frame: int
                    out_frame for the current context (e.g. the current shot,
                                                      current asset etc)

        :returns:   Depends on operation:
                    'set_frame_range' - Returns if the operation was successful
                    'get_frame_range' - Returns the frame range in the form (in_frame, out_frame)
        """

        if operation == "get_frame_range":
            # since 3de doesn't have a concept of scene frame range,
            # return the first camera's frame range
            camera_id = tde4.getFirstCamera()
            (current_in, current_out, step) = tde4.getCameraSequenceAttr(camera_id)
            return (current_in, current_out)

        elif operation == "set_frame_range":
            for camera_id in tde4.getCameraList():
                # set file frame range
                tde4.setCameraSequenceAttr(camera_id, in_frame, out_frame, 1)
                tde4.setCameraFrameOffset(camera_id, in_frame)

                no_of_frames = out_frame - in_frame + 1
                # set calculation range
                tde4.setCameraCalculationRange(camera_id, 1, no_of_frames)
                # set playback range
                tde4.setCameraPlaybackRange(camera_id, 1, no_of_frames)

            return True
