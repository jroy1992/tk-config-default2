
import sgtk

from sgtk.platform.qt import QtGui

HookClass = sgtk.get_hook_baseclass()

class TaskOperations(HookClass):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(self, operation, file_path, context, parent_action, file_version, read_only, **kwargs):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """

        if operation == "open":
            self.update_task_status(context)
            # handle status updates, and show a pop-up for user confirmation to switch the task status.
        elif operation == "reset":
            if parent_action == "new_file":
                return self.update_task_status(context)
            return True
        elif operation == "save":
            self.update_task_status(context)
        elif operation == "save_as":
            self.update_task_status(context)

    def update_task_status(self, context, **kwargs):
        """
        Method to update the task entity status.

        :param context: Source for the task entity.
        """

        sg_filters = [
            ["project", "is", context.project],
            ["id", "is", context.task["id"]]
        ]

        task_status_update_mapping = self.parent.settings["task_status_updates"]

        task_entity = self.parent.shotgun.find_one("Task", sg_filters, fields=["sg_status_list"])
        current_task_status = task_entity["sg_status_list"]
        task_name = context.task["name"]

        new_status_list = list(set([new_status for new_status,
                                                   existing_status_list in task_status_update_mapping.iteritems()
                                    if current_task_status in existing_status_list]))

        if task_entity and len(new_status_list) == 1:
            # we found the new status for the task, confirm with user before updating.
            new_task_status = new_status_list[0]
            res = QtGui.QMessageBox.question(None,
                                             'Update task "%s" Status?' % task_name,
                                             'Do you want to switch the task status '
                                             'from %s to %s?' % (current_task_status, new_task_status),
                                             QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)

            if res == QtGui.QMessageBox.Yes:
                try:
                    self.parent.shotgun.update("Task", context.task["id"], {"sg_status_list": new_task_status})
                    self.parent.logger.info("Updated status for task '%s' from %s to %s.", task_name,
                                            current_task_status, new_task_status)
                except:
                    self.parent.logger.warning("Failed to update status for task '%s' from %s to %s.", task_name,
                                               current_task_status, new_task_status)
            else:
                self.parent.logger.info("User denied to update status for task '%s' from %s to %s.", task_name,
                                        current_task_status, new_task_status)

            return True

        elif task_entity and len(new_status_list) > 1:
            # there is something wrong with the configuration, we shouldn't have two new statuses.
            self.parent.logger.error("Multiple new statuses found: %s. Please contact your TD.", new_status_list)
            return False
        else:
            # there is no status mapping for this status, just ignore.
            return True
