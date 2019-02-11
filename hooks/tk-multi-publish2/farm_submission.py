# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This hook will submit the publish tree to the "farm".
"""

import os
import getpass
import datetime
import pprint
import urllib

import sgtk
from sgtk.util import filesystem

from dd.runtime import api

api.load('submission')
from submission.types.jobs.job import Job

api.load('frangetools')
from frangetools.frameRangeTools import FrameRange

api.load('jstools')
import jstools

api.load('dd_disk', minimum_version='0.27.0')
from dd_disk.temp import getSharedTemporaryDirectory

api.load("wam")
import wam

api.load('farm') # loads the FARM_TYPE environment variable

DEFAULT_CPUS = 5
DEFAULT_CORES = 2
DEFAULT_RAM = 2048
DEFAULT_PRIORITY = 950 # Magic (race) default priority.

class DDFarmSubmission(sgtk.get_hook_baseclass()):

    def submit_to_farm(self, app_state, tree):
        """
        Submits the job to the render farm.

        :param dict app_state: State information about the :class:`Sgtk.Platform.Application`.
        :param tree: The tree of items and tasks that has just been published.
        :type tree: :ref:`publish-api-tree`
        """

        # Provision the top-level shared tmp location.
        # This lives on the network at SHARED/tmp/tk-multi-publish2
        output_dir_base = getSharedTemporaryDirectory(self.parent.name, create=True)

        # Use user+timestamp to distinguish this submission since we can't provision job_ids
        # before submission.
        current_user = getpass.getuser()
        unique_id = datetime.datetime.now().strftime("%d%b%Y_%H:%M:%S")

        # Create a shared tmp dir to put the shared data for all jobs in this submission.
        output_dir = os.path.join(output_dir_base, current_user, unique_id)
        filesystem.ensure_folder_exists(output_dir)

        # Generate the publish tree file
        tree_file = self._generate_tree_file(output_dir, tree)

        # Make a local copy of the publish workflow
        workflow_path = self._generate_workflow_xml(output_dir)

        # Generate the job's execution action
        actions_path = self._generate_publish_actions(output_dir)

        # Generate the job's execution environment
        job_env = self._generate_submission_env(output_dir, workflow_path, actions_path)

        jobs = []
        for item in tree:

            # Tasks need to be run serially, so just run as a single job
            farm_tasks = [task for task in item.tasks \
                if task.plugin._hook_instance.has_steps_on_farm(task.settings, item)]

            # Generate the submission job
            if len(farm_tasks):

                # Create a job-specific subdir for things that shouldn't be shared between jobs
                job_dir_name = urllib.quote(item.name.replace(" ", "_").lower(), safe='')
                job_output_dir = os.path.join(output_dir, job_dir_name)
                filesystem.ensure_folder_exists(job_output_dir)

                # Generate the workflow input data block
                data_path = self._generate_workflow_data(
                    item,
                    farm_tasks,
                    tree_file,
                    job_output_dir
                )

                job = self._generate_submission_job(
                    item,
                    data_path,
                    workflow_path,
                    job_output_dir,
                    job_env
                )
                jobs.append(job)

                # Submit to the farm.
                try:
                    submitted, msg = job.submit()
                except RuntimeError, e:
                    submitted = False
                    msg = e

                if not submitted:
                    self.logger.error(
                        "Job for item '%s' failed to submit." % (item.name,),
                        extra={
                            "action_show_more_info": {
                                "label": "Show Info",
                                "tooltip": "Show more info",
                                "text": msg
                            }
                        }
                    )
                    continue

                # Add the job_id to this item's properties
                if "job_ids" not in item.properties:
                    item.properties.job_ids = []
                item.properties.job_ids.append(job.job_id)

        # Return the list of job_ids
        return [job.job_id for job in jobs if job.job_id is not None]

    def _generate_tree_file(self, output_dir, tree):
        """
        Generate the publish tree file
        """
        tree_file = os.path.join(output_dir, "publish2_tree.json")
        tree.save_file(tree_file)
        self.logger.info(
            "Wrote publish tree file: %r", tree_file,
            extra={
                "action_show_folder": {
                    "path": output_dir
                }
            }
        )
        return tree_file

    def _generate_workflow_xml(self, output_dir):
        """
        Make a copy of the specified workflow file
        """
        workflow_name = "sgtk/RunPublish.wam"
        src_workflow_path = wam.utils.workflow_resolve.locateWorkflow(workflow_name, True)

        workflow_path = os.path.join(output_dir, workflow_name)
        filesystem.ensure_folder_exists(os.path.dirname(workflow_path))
        filesystem.copy_file(src_workflow_path, workflow_path)
        self.logger.info(
            "Wrote workflow xml: %r", workflow_path,
            extra={
                "action_show_folder": {
                    "path": output_dir
                }
            }
        )
        return workflow_path

    def _generate_publish_actions(self, output_dir):
        """
        Dump the WAM Action to run publisher in batch mode.
        """
        # Create python module hierarchy
        python_dir = os.path.join(output_dir, "python")
        filesystem.ensure_folder_exists(python_dir)

        sgtk_dir = os.path.join(python_dir, "sgtk")
        filesystem.ensure_folder_exists(sgtk_dir)
        open(os.path.join(sgtk_dir, "__init__.py"), 'w').close()

        actions_dir = os.path.join(sgtk_dir, "actions")
        filesystem.ensure_folder_exists(actions_dir)
        open(os.path.join(actions_dir, "__init__.py"), 'w').close()

        publish_action = os.path.join(actions_dir, "RunPublishAction.py")
        with open(publish_action, 'w') as of:
            lines = [
                'import sgtk',
                '',
                'from dd.runtime import api',
                'api.load("wam")',
                'from wam.core import Action',
                'from wam.utils import parameters',
                '',
                '__all__ = ["RunPublishAction"]',
                '',
                'class RunPublishAction(Action):',
                '    def run(self, data):',
                '        engine = sgtk.platform.current_engine()',
                '        app = engine.apps.get("tk-multi-publish2")',
                '',
                '        manager = app.create_publish_manager()',
                '        manager.load(self.parameters["publish_tree_file"].value)',
                '',
                '        task_generator = app.execute_hook(',
                '            "task_generator",',
                '            publish_tree=manager.tree,',
                '            publish_logger=manager.logger,',
                '            item_filters=self.parameters["item_filters"].value,',
                '            task_filters=self.parameters["task_filters"].value,',
                '        )',
                '',
                '        manager.run(task_generator)',
                '',
                '        # Store the modified publish tree for downstream actions',
                '        manager.save(self.parameters["publish_tree_file"].value)',
                '',
                '        return data',
                '',
                'RunPublishAction.addParameter("publish_tree_file", value_type=parameters.VT_FILE)',
                'RunPublishAction.addParameter("item_filters", value_type=parameters.VT_LIST)',
                'RunPublishAction.addParameter("task_filters", value_type=parameters.VT_LIST)',
            ]
            of.write('\n'.join(lines) + '\n')

        self.logger.info(
            "Wrote publish action: %r" % publish_action,
            extra={
                "action_show_folder": {
                    "path": actions_dir
                }
            }
        )

        return python_dir

    def _generate_submission_env(self, output_dir, workflow_path, actions_path):
        """
        """
        # Start with a cleaned environment
        new_env = jstools.buildEnvironment(
            show = os.environ.get('DD_SHOW'),
            sequence = os.environ.get('DD_SEQ'),
            shot = os.environ.get('DD_SHOT'),
            workarea = os.environ.get('DD_WORKAREA'),
            role = os.environ.get('DD_ROLE')
        )

        # Add the SGTK context
        new_env["TANK_CONTEXT"] = self.parent.context.serialize()

        # Setup a proper shared path cache for sgtk
        new_env["SHOTGUN_HOME"] = os.path.join(output_dir, "shotgun")

        # Set the serialized workflow that will be used by the subprocess.
        new_env["WORKFLOW"] = workflow_path

        # Prepend PYTHONPATH with the actions path
        new_env["PYTHONPATH"] = os.path.expandvars("%s:$PYTHONPATH" % actions_path)

        self.logger.info(
            "Generated submission env",
            extra={
                "action_show_more_info": {
                    "label": "Show Info",
                    "tooltip": "Show more info",
                    "text": pprint.pformat(new_env)
                }
            }
        )
        return new_env

    def _generate_workflow_data(self, item, tasks, tree_file, output_dir):
        """
        Generate the workflow input data block
        """
        data = wam.datatypes.Collection()
        data.parameters = dict()
        data.parameters["host_app"] = _get_host_application()
        data.parameters["scene_file"] = _get_session_path()
        data.parameters["publish_tree_file"] = tree_file
        data.parameters["item_filters"] = [item.name]
        data.parameters["task_filters"] = [task.name for task in tasks]

        data_path = os.path.join(output_dir, "wam_data.yml")
        data.stash(data_path)
        self.logger.info(
            "Wrote serialized WAM data block: %r", data_path,
            extra={
                "action_show_folder": {
                    "path": output_dir
                }
            }
        )
        return data_path

    def _generate_submission_job(self, item, data_path, workflow_path, output_dir, env):
        """
        """
        # Generate the job object
        job = Job(job_name=item.name, env=env)
        job.software = [_get_host_application()]
        job.activity = "publish"
        job.notes = "SGTK Batch Publisher"
        job.log_dir = os.path.join(output_dir, "logs")

        # Make sure we are just running for 1 frame
        job.frame_range = FrameRange('1-1')
        job.batch_size = 1

        # Default job execution attributes
        job.cpus = DEFAULT_CPUS
        job.cores = DEFAULT_CORES
        job.ram = DEFAULT_RAM
        job.priority = DEFAULT_PRIORITY

        # Sadly these are needed for submission
        job.submitFile = _get_session_path()
        job.outputFile = os.path.join(output_dir, "output.txt")

        current_user = getpass.getuser()
        job.mail_to = '{0}@d2.com'.format(current_user)

        # generate the actual execution command
        job.command = ['/tools/bin/wam', 'run', workflow_path, '-i', data_path]

        # Add any upstream dependencies
        if not item.is_root:
            for parent_job_id in item.parent.properties.get("job_ids", []):
                job.depend_on.append(parent_job_id, False)

        return job

    @classmethod
    def is_on_farm_machine(cls):
        """
        :returns: ``True`` if on the render farm, ``False`` otherwise.
        """
        return os.environ.get("RACE_HOSTNAME", False)


def _get_session_path():
    """
    :returns: Path to the current session.
    """
    try:
        import maya.cmds as cmds
    except ImportError:
        pass
    else:
        path = cmds.file(query=True, sn=True)
        if isinstance(path, unicode):
            path = path.encode("utf-8")

        return path

    try:
        import nuke
    except ImportError:
        pass
    else:
        root_name = nuke.root().name()
        return None if root_name == "Root" else root_name

    try:
        import hou
    except ImportError:
        pass
    else:
        if hou.hipFile.name() == "untitled.hip":
            return None

        return hou.hipFile.path()

    raise NotImplementedError("%s is not supported." % sgtk.platform.current_engine().name)

def _get_host_application():
    """
    """
    return os.environ.get("DD_HOST_APPS", "").split(",")[0]
