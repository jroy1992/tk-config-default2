import sys
import sgtk
from sgtk.dd_utils import dd_jstools_utils

HookBaseClass = sgtk.get_hook_baseclass()


class ExternalScreenshot(HookBaseClass):
    def capture_screenshot(self, path):
        if sys.platform == "linux2":
            # use image magick in sgtk clean env
            context = self.parent.context
            print context
            ret_code, error_msg = dd_jstools_utils.run_in_clean_env(["import", path], context)
            if ret_code != 0:
                raise sgtk.TankError("Screen capture tool returned error code: %s, message: `%s`."
                                     "For screen capture to work on Linux, you need to have "
                                     "the imagemagick 'import' executable installed and "
                                     "in your PATH." % (ret_code, error_msg))
        else:
            super(ExternalScreenshot, self).capture_screenshot(path)
