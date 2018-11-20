# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import ast
import sgtk
HookBaseClass = sgtk.get_hook_baseclass()


class HieroTranslateTemplate(HookBaseClass):
    """
    This class implements a hook that's responsible for translating a Toolkit
    template object into a Hiero export string.
    """
    def execute(self, template, output_type, **kwargs):
        """
        Takes a Toolkit template object as input and returns a string
        representation which is suitable for Hiero exports. The Hiero export
        templates contain tokens, such as {shot} or {clip}, which are replaced
        by the exporter. This hook should convert a template object with its
        special custom fields into such a string. Depending on your template
        setup, you may have to do different steps here in order to fully
        convert your template. The path returned will be validated to check
        that no leftover template fields are present, and that the returned
        path is fully understood by Hiero.

        :param template: The Toolkit template object to be translated.
        :param str output_type: The output type associated with the template.

        :returns: A Hiero-compatible path.
        :rtype: str
        """
        # First add in any relevant fields from the context
        fields = self.parent.context.as_template_fields(template)
        # Substitute the variables that Hiero will inject during export
        hiero_fields = {
            "Sequence": "{sequence}",
            "Shot": "{shot}",
            "name": "{project}",
            "output": "{clip}",
            "width": "{width}",
            "height": "{height}",
            "version": "{tk_version}",
            "extension": "{ext}"
        }
        fields.update(hiero_fields)

        for name, key in template.keys.iteritems():
            if isinstance(key, sgtk.templatekey.SequenceKey):
                fields.update({name: "FORMAT:#"})

        # simple string to string replacement
        # the nuke script name is hard coded to ensure a valid template
        if output_type == 'script':
            fields.update({"output": "scene"})

        # Nuke Studio project string has version number which is an issue when we have to resolve template by path
        # so replacing {name} with 'plate' string
        # and stripping {output} to simplify template to {Sequence}_{Shot}_{Step}_{name}.v{tk_version}.mov
        # engine specific template would have been useful here (as could update only for nuke studio)
        if output_type == "plate":
            fields.update({"name": "plate"})
            del fields['output']

        template_str = template._apply_fields(fields, hiero_fields.keys())

        return template_str
