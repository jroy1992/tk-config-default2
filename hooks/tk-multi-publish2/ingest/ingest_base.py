# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


import pprint

import sgtk

from sgtk.platform.qt import QtCore, QtGui
from sgtk import TankError, TankMissingTemplateError, TankMissingTemplateKeysError

HookBaseClass = sgtk.get_hook_baseclass()


class FieldWidgetHandler(object):
    """
    Shows the editor widget with a label or checkbox depending on whether
    the widget is in multi-edit mode or not.

    When multiple values are available for this widget, the widget will by
    default be disabled and a checkbox will appear unchecked. By checking the
    checkbox, the user indicates they want to override the value with a specific
    one that will apply to all items.
    """

    def __init__(self, qtwidgets, item, parent, field, value, editable, color):
        """
        :param layout: Layout to add the widget into.
        :param text: Text on the left of the editor widget.
        :param editor: Widget used to edit the value.
        """
        # import the shotgun_fields module from the qtwidgets framework
        shotgun_fields = qtwidgets.import_module("shotgun_fields")

        self._field = field
        self._value = value
        self._item = item
        self._layout = QtGui.QHBoxLayout()
        self._field_label = shotgun_fields.text_widget.TextWidget(parent)  # QtGui.QLabel(field)
        if color:
            self._field_label.set_value("<b><font color='%s'>%s</font></b>" % (color, field))
        else:
            self._field_label.set_value("<b>%s</b>" % field)

        self._editor = None
        self._display = None

        if isinstance(value, bool):
            self._display = shotgun_fields.checkbox_widget.CheckBoxWidget(parent)
            if editable:
                self._editor = self._display
        elif isinstance(value, float):
            self._display = shotgun_fields.float_widget.FloatWidget(parent)
            if editable:
                self._editor = shotgun_fields.float_widget.FloatEditorWidget(parent)
        elif isinstance(value, int) or isinstance(value, long):
            self._display = shotgun_fields.number_widget.NumberWidget(parent)
            if editable:
                self._editor = shotgun_fields.number_widget.NumberEditorWidget(parent)
        elif isinstance(value, list):
            self._display = shotgun_fields.list_widget.ListWidget(parent)
            if editable:
                self._editor = shotgun_fields.list_widget.ListEditorWidget(parent)
        elif isinstance(value, str):
            self._display = shotgun_fields.text_widget.TextWidget(parent)
            if editable:
                self._editor = shotgun_fields.text_widget.TextEditorWidget(parent)
        else:
            self._display = shotgun_fields.text_widget.TextWidget(parent)

        if editable and self._editor:
            self._widget = shotgun_fields.shotgun_field_editable.ShotgunFieldEditable(self._display, self._editor,
                                                                                      parent)
            self._widget.enable_editing(editable)
        else:
            self._widget = shotgun_fields.shotgun_field_editable.ShotgunFieldNotEditable(self._display, parent)

        # set the default value before connecting the signal
        self._widget.set_value(value)
        self._widget.value_changed.connect(lambda: self._value_changed())

        # self._field_label.setMinimumWidth(50)

        self._layout.addWidget(self._field_label)
        self._layout.addWidget(self._widget)

        parent.layout.addRow(self._layout)

    def _value_changed(self):
        self._item.properties.fields.update({self._field: self.widget.get_value()})

    @property
    def widget(self):
        return self._widget

    @property
    def field(self):
        return self._field

    @property
    def value(self):
        return self._value


class ItemFieldWidgetController(QtGui.QWidget):
    """
    This is the plugin's custom UI.
    """

    def __init__(self, parent, item, qtwidgets, description_widget=None):
        QtGui.QWidget.__init__(self, parent)

        self.qtwidgets = qtwidgets

        self.layout = QtGui.QFormLayout(self)
        self.setLayout(self.layout)

        for key, value in item.properties.fields.iteritems():
            if key in item.properties.non_editable_fields or key in item.properties.context_fields:
                editable = False
                color = None
            else:
                editable = True
                color = sgtk.platform.constants.SG_STYLESHEET_CONSTANTS["SG_HIGHLIGHT_COLOR"]

            FieldWidgetHandler(qtwidgets, item, self, key, value, editable, color)

        for key in item.properties.missing_keys:
            # make sure we are not adding this again
            if key not in item.properties.fields:
                FieldWidgetHandler(qtwidgets, item, self, key, "", editable=True,
                                   color=sgtk.platform.constants.SG_STYLESHEET_CONSTANTS["SG_ALERT_COLOR"])

        if description_widget:
            self.layout.addRow(description_widget)


class IngestBasePlugin(HookBaseClass):
    """
    Base Ingest Plugin
    """

    def create_settings_widget(self, parent, item):
        """
        Creates a Qt widget, for the supplied parent widget (a container widget
        on the right side of the publish UI).

        :param parent: The parent to use for the widget being created
        :param item: Item for the settings widget is being created
        :return: A QtGui.QWidget or subclass that displays information about
            the plugin and/or editable widgets for modifying the plugin's
            settings.
        """

        qtwidgets = self.load_framework("tk-framework-qtwidgets_v2.x.x")

        return ItemFieldWidgetController(
            parent,
            item,
            qtwidgets,
            description_widget=super(IngestBasePlugin, self).create_settings_widget(parent, item)
        )

    def _create_vendor_task(self, item, step_entity):
        """
        Creates a Vendor Task for the Entity represented by the Context.

        :param item: Item to get the context from.
        :param step_entity: Step entity to create Task against.
        """

        # construct the data for the new Task entity
        data = {
            "step": step_entity,
            "project": item.context.project,
            "entity": item.context.entity if item.context.entity else item.context.project,
            "content": "Vendor"
        }

        # create the task
        sg_result = self.sgtk.shotgun.create("Task", data)
        if not sg_result:
            self.logger.error("Failed to create new task - reason unknown!")
        else:
            self.logger.info("Created a Vendor Task.", extra={
                        "action_show_more_info": {
                            "label": "Show Task",
                            "tooltip": "Show the existing Task in Shotgun",
                            "text": "Task Entity: %s" % pprint.pformat(sg_result)
                        }
                    }
                )

    def validate(self, task_settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.

        :param task_settings: Dictionary of settings
        :param item: Item to process

        :returns: True if item is valid, False otherwise.
        """

        # Run the context validations first.
        if not item.context.entity:
            self.logger.error("Ingestion at project level is not allowed! Please Contact TDs.")
            return False
        # context check needs to run before the other validations do.
        if not item.context.step:
            # Item doesn't contain a step entity! Intimate the user to create one, if they want to ingest.
            step_filters = list()
            step_filters.append(['short_name', 'is', "vendor"])

            # make sure we get the correct Step!
            # this should handle whether the Step is from Sequence/Shot/Asset
            step_filters.append(["entity_type", "is", item.context.entity["type"]])

            fields = ['entity_type', 'code', 'id']

            # add a vendor step to all ingested files
            step_entity = self.sgtk.shotgun.find_one(
                entity_type='Step',
                filters=step_filters,
                fields=fields
            )

            if not step_entity:
                self.logger.error("Step Entity doesn't exist. Please contact your TDs.",
                                  extra={
                                        "action_show_more_info": {
                                            "label": "Show Filters",
                                            "tooltip": "Show the filters used to query the Step.",
                                            "text": "SG Filters: %s\n"
                                                    "Fields: %s" % (pprint.pformat(step_filters),
                                                                    pprint.pformat(fields))
                                        }
                                    })

                return False

            task_filters = [
                ['step', 'is', step_entity],
                ['entity', 'is', item.context.entity],
                ['content', 'is', 'Vendor']
            ]

            task_fields = ['content', 'step', 'entity']

            task_entity = self.sgtk.shotgun.find_one(
                entity_type='Task',
                filters=task_filters,
                fields=task_fields
            )

            if task_entity:
                self.logger.warning(
                    "Vendor task already exists! Please select that task.",
                    extra={
                        "action_show_more_info": {
                            "label": "Show Task",
                            "tooltip": "Show the existing Task in Shotgun",
                            "text": "Task Entity: %s" % pprint.pformat(task_entity)
                        }
                    }
                )
            else:
                self.logger.error(
                    "Item doesn't have a valid Step.",
                    extra={
                        "action_button": {
                            "label": "Crt Vendor Task",
                            "tooltip": "Creates a Vendor Task on the Entity represented by the Context.",
                            "callback": lambda: self._create_vendor_task(item, step_entity)
                        }
                    }
                )

            return False

        try:
            # rest of the validations run after the context is verified.
            status = super(IngestBasePlugin, self).validate(task_settings, item)
        except TankMissingTemplateKeysError:
            # we want the user to fill these missing fields!
            self.logger.error(
                "Missing fields in the templates!",
                extra={
                    "action_show_more_info": {
                        "label": "Show Fields",
                        "tooltip": "Shows the missing fields across all templates.",
                        "text": "Missing Fields: %s\nContext Fields: %s" % pprint.pformat
                        (item.properties.missing_keys, item.properties.context_fields)
                    }
                }
            )
            status = False

        return status
