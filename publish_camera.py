# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import fnmatch
import os

import maya.cmds as cmds
import maya.mel as mel
import re
import sgtk
from sgtk.platform.qt5 import QtWidgets
#from PySide2  import QtWidgets

GEO_CONSTANT_ENTITIES = [ '_MMtrackalembic_', '_MMtrackfbx_', 
                          '_fxgeo_', '_lgtgeo_', '_RAtrackalembic_',
                          '_animgeo_', '_layoutgeo_']

namings = [ 'MMtrackalembic_', 
            'MMtrackfbx_', 
            'fxgeo_', 'lgtgeo_',
            'RAtrackalembic_', 'animgeo_', 
            'layoutgeo_']

grp_name = [ 'group' ]
# this method returns the evaluated hook base class. This could be the Hook
# class defined in Toolkit core or it could be the publisher app's base publish
# plugin class as defined in the configuration.
HookBaseClass = sgtk.get_hook_baseclass()
aa = True
class MayaCameraPublishPlugin(HookBaseClass):
    """
    This class defines the required interface for a publish plugin. Publish
    plugins are responsible for operating on items collected by the collector
    plugin. Publish plugins define which items they will operate on as well as
    the execution logic for each phase of the publish process.
    """

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does (:class:`str`).

        The string can contain html for formatting for display in the UI (any
        html tags supported by Qt's rich text engine).
        """
        return """
        <p>This plugin handles publishing of cameras from maya.
        A publish template is required to define the destination of the output
        file.
        </p>
        """

    @property
    def settings(self):
        """
        A :class:`dict` defining the configuration interface for this plugin.

        The dictionary can include any number of settings required by the
        plugin, and takes the form::

            {
                <setting_name>: {
                    "type": <type>,
                    "default": <default>,
                    "description": <description>
                },
                <setting_name>: {
                    "type": <type>,
                    "default": <default>,
                    "description": <description>
                },
                ...
            }

        The keys in the dictionary represent the names of the settings. The
        values are a dictionary comprised of 3 additional key/value pairs.

        * ``type``: The type of the setting. This should correspond to one of
          the data types that toolkit accepts for app and engine settings such
          as ``hook``, ``template``, ``string``, etc.
        * ``default``: The default value for the settings. This can be ``None``.
        * ``description``: A description of the setting as a string.

        The values configured for the plugin will be supplied via settings
        parameter in the :meth:`accept`, :meth:`validate`, :meth:`publish`, and
        :meth:`finalize` methods.

        The values also drive the custom UI defined by the plugin whick allows
        artists to manipulate the settings at runtime. See the
        :meth:`create_settings_widget`, :meth:`set_ui_settings`, and
        :meth:`get_ui_settings` for additional information.

        .. note:: See the hooks defined in the publisher app's ``hooks/`` folder
           for additional example implementations.
        """
        # inherit the settings from the base publish plugin
        plugin_settings = super(MayaCameraPublishPlugin, self).settings or {}

        # settings specific to this class
        maya_camera_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published camera. Should"
                               "correspond to a template defined in "
                               "templates.yml.",
            },
            "Cameras": {
                "type": "list",
                "default": ["camera*"],
                "description": "Glob-style list of camera names to publish. "
                               "Example: ['camMain', 'camAux*']."
            }
        }

        # update the base settings
        plugin_settings.update(maya_camera_publish_settings)

        return plugin_settings

    @property
    def item_filters(self):
        """
        A :class:`list` of item type wildcard :class:`str` objects that this
        plugin is interested in.

        As items are collected by the collector hook, they are given an item
        type string (see :meth:`~.processing.Item.create_item`). The strings
        provided by this property will be compared to each collected item's
        type.

        Only items with types matching entries in this list will be considered
        by the :meth:`accept` method. As such, this method makes it possible to
        quickly identify which items the plugin may be interested in. Any
        sophisticated acceptance logic is deferred to the :meth:`accept` method.

        Strings can contain glob patters such as ``*``, for example ``["maya.*",
        "file.maya"]``.
        """
        return ["maya.session.camera"]

    def accept(self, settings, item):
        """
        This method is called by the publisher to see if the plugin accepts the
        supplied item for processing.

        Only items matching the filters defined via the :data:`item_filters`
        property will be presented to this method.

        A publish task will be generated for each item accepted here.

        This method returns a :class:`dict` of the following form::

            {
                "accepted": <bool>,
                "enabled": <bool>,
                "visible": <bool>,
                "checked": <bool>,
            }

        The keys correspond to the acceptance state of the supplied item. Not
        all keys are required. The keys are defined as follows:

        * ``accepted``: Indicates if the plugin is interested in this value at all.
          If ``False``, no task will be created for this plugin. Required.
        * ``enabled``: If ``True``, the created task will be enabled in the UI,
          otherwise it will be disabled (no interaction allowed). Optional,
          ``True`` by default.
        * ``visible``: If ``True``, the created task will be visible in the UI,
          otherwise it will be hidden. Optional, ``True`` by default.
        * ``checked``: If ``True``, the created task will be checked in the UI,
          otherwise it will be unchecked. Optional, ``True`` by default.

        In addition to the item, the configured settings for this plugin are
        supplied. The information provided by each of these arguments can be
        used to decide whether to accept the item.

        For example, the item's ``properties`` :class:`dict` may house meta data
        about the item, populated during collection. This data can be used to
        inform the acceptance logic.

        :param dict settings: The keys are strings, matching the keys returned
            in the :data:`settings` property. The values are
            :class:`~.processing.Setting` instances.
        :param item: The :class:`~.processing.Item` instance to process for
            acceptance.

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        publisher = self.parent
        template_name = settings["Publish Template"].value

        # validate the camera name first
        cam_name = item.properties.get("camera_name")
        cam_shape = item.properties.get("camera_shape")


        # ensure a camera file template is available on the parent item
        work_template = item.parent.properties.get("work_template")
        if not work_template:
            self.logger.debug(
                "A work template is required for the session item in order to "
                "publish a camera. Not accepting session camera item."
            )
            return {"accepted": False}

        # ensure the publish template is defined and valid and that we also have
        publish_template = publisher.get_template_by_name(template_name)
        if publish_template:
            item.properties["publish_template"] = publish_template
            # because a publish template is configured, disable context change.
            # This is a temporary measure until the publisher handles context
            # switching natively.
            item.context_change_allowed = False
        else:
            self.logger.debug(
                "The valid publish template could not be determined for the "
                "session camera item. Not accepting the item."
            )
            return {"accepted": False}

        # check that the FBXExport command is available!
        if not mel.eval("exists \"AbcExport\""):
            self.logger.debug(
                "Item not accepted because fbx export command 'FBXExport' "
                "is not available. Perhaps the plugin is not enabled?"
            )
            return {"accepted": False}

        # all good!
        return {
            "accepted": True,
            "checked": True
        }
        
    def set_version(self, publish_name, settings, item):
        
        """
        Check whether the alembic files published or not
        
        If similar naming alembic files found then it versionup
        """
        import sgtk
        
        # Loop throught the publish name and extract name entity 
        # if pub1_MMtrackalembic_boulder_v001 is our publish_name
        # then the below loop wxtract boulder and attach with
        # MMtrackalembic and make it MMtrackalembic_bpulder_
        extracted_name = str
        for entities in GEO_CONSTANT_ENTITIES:
            if entities in publish_name:
                split_entity = entities[1:]
                split_name_with_version = publish_name.split(entities)[-1]

                extracted_name = ''
                if re.search('_v\d{3}', split_name_with_version) is not None:
                    extract_version = re.search('_v\d{3}', split_name_with_version).group(0)
                    extract_name = split_name_with_version.split(extract_version)[0]
                    extracted_name = split_entity + extract_name + '_'
                else:
                    self.logger.error("Naming Convention error")
                
        engine = sgtk.platform.current_engine()
        task = [[ 'task', 'is', item.context.task ]] 
        versions = []
        get_publish_list = engine.shotgun.find('PublishedFile', task, ['code', 'entity', 'version_number'])
        if get_publish_list != []:
            for publishes in get_publish_list:
                try:
                    if re.search(extracted_name, publishes['code']).group(0):
                       version_str = re.search('_v\d+', publishes['code']).group(0)
                       version = int(re.search('\d+', version_str).group(0))
                       versions.append(version)
                except: pass
                
        if get_publish_list != []:
            for publishes in get_publish_list:
                if versions != []:
                    publishes['version_number'] = max(versions) + 1 or 1
                    return publishes['version_number']
                else:
                    publishes['version_number'] = 1
                    return publishes['version_number']
        else:
            return 1

    def validate(self, settings, item):
        """
        Validates the given item, ensuring it is ok to publish.

        Returns a boolean to indicate whether the item is ready to publish.
        Returning ``True`` will indicate that the item is ready to publish. If
        ``False`` is returned, the publisher will disallow publishing of the
        item.

        An exception can also be raised to indicate validation failed.
        When an exception is raised, the error message will be displayed as a
        tooltip on the task as well as in the logging view of the publisher.

        :param dict settings: The keys are strings, matching the keys returned
            in the :data:`settings` property. The values are
            :class:`~.processing.Setting` instances.
        :param item: The :class:`~.processing.Item` instance to validate.

        :returns: True if item is valid, False otherwise.
        """

        path = _session_path()

        # ---- ensure the session has been saved

        if not path:
            # the session still requires saving. provide a save button.
            # validation fails.
            error_msg = "The Maya session has not been saved."
            self.logger.error(error_msg, extra=_get_save_as_action())
            raise Exception(error_msg)

        # get the normalized path
        path = sgtk.util.ShotgunPath.normalize(path)
        
        cam_name = item.properties["camera_name"]
        error_msg = {}
        
        for native_names in grp_name:
            if re.search('^%s' %native_names, cam_name) is not None:
                cmds.select(cam_name, add=True)
                txt = "Maya native geometry name exists <font color='red'>%s</font> " %cam_name
                error_msg[txt] = u"\u274c"
                break
            
        if any( cam_name.startswith(name) for name in namings) == False:
                cmds.select(cam_name, add=True)
                txt = "Node name <font color='red'>%s</font> not starting with any naming conventions " %cam_name
                error_msg[txt] = u"\u274c"
        
        if cam_name.startswith('_') or cam_name.endswith('_'):
            cmds.select(cam_name, add=True)
            txt = "Camera Name starts or ends with underscore for <font color='red'>%s</font> " %cam_name
            error_msg[txt] = u"\u274c"
        
        if not cmds.listRelatives(cam_name , shapes=1):
            check_entity = any( entities in cam_name for entities in namings )
        
            if not check_entity:
                cmds.select(cam_name, add=True)
                txt = "Naming convetion not found for node  <font color='red'>%s</font>" %cam_name
                error_msg[txt] = u"\u274c"
        
        for names in cmds.listRelatives(cam_name, ad=True):
            if names.startswith('_') or names.endswith('_'):
                cmds.select(names, add=True)
                txt = "Camera Name starts or ends with underscore for <font color='red'>%s</font> " %names
                error_msg[txt] = u"\u274c"

        
        if error_msg != {}:

            app = QtWidgets.QApplication.instance()
            gui = validationCheck_UI(error_msg, cam_name)
            gui.show()
            app.exec_()
                

        # check that the camera still exists in the file
        if not cmds.ls(cam_name):
            error_msg = (
                "Validation failed because the collected camera (%s) is no "
                "longer in the scene. You can uncheck this plugin or create "
                "a camera with this name to export to avoid this error." %
                (cam_name,)
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # get the configured work file template
        work_template = item.parent.properties.get("work_template")
        publish_template = item.properties.get("publish_template")

        # get the current scene path and extract fields from it using the work
        # template:
        work_fields = work_template.get_fields(path)
        
        # include the camera name in the fields
        cam_name = cam_name.split(":")[0]
        cam_name_display = re.sub(r'[\W_]+', '', cam_name)
        work_fields["name"] = cam_name_display

        # ensure the fields work for the publish template
        missing_keys = publish_template.missing_keys(work_fields)
        if missing_keys:
            error_msg = "Work file '%s' missing keys required for the " \
                        "publish template: %s" % (path, missing_keys)
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # create the publish path by applying the fields. store it in the item's
        # properties. This is the path we'll create and then publish in the base
        # publish plugin. Also set the publish_path to be explicit.
        publish_path = publish_template.apply_fields(work_fields)
        item.properties["path"] = publish_path
        item.properties["publish_path"] = publish_path
        
        #item.properties["path"] = item.properties["path"].replace(object_display, object_name)
        item.properties["publish_path"] = item.properties["publish_path"].replace(cam_name_display, cam_name)
        item.properties["publish_name"] =  os.path.basename(item.properties["publish_path"])

        # let consider pub_dev7_Tracking_MMtrackalembic_boulder_v001.abc is published 
        # Maya artist loading this abc. it loading and have namespace of MMtrackalembic_boulder:DE_scene_node
        # Once modification done on the abc MM artist try to publish again with same naming.
        # now maya take the current 'version_number' sg field to update the alembic. 
        # if it is first time then it publish again with pub_dev7_Tracking_MMtrackalembic_boulder_v001.abc
        # so below script send the basename of the publish path to set_version
        # It checks whether this is a 1st time publish or alread with similar naming other ublishes were there
        # If there then it version up otherwise it kept 1 
        # we repling the publish_template.apply_fields due to take this incremented version into account

        work_fields["version"] = self.set_version(item.properties["publish_name"], settings, item)
        item.properties["path"] = publish_template.apply_fields(work_fields)
        item.properties["publish_path"] = item.properties["path"]
        
        item.properties["path"] = item.properties["path"].replace(cam_name_display, cam_name)
        item.properties["publish_path"] = item.properties["publish_path"].replace(cam_name_display, cam_name)
        item.properties["publish_name"] =  os.path.basename(item.properties["publish_path"])

        # use the work file's version number when publishing
        if "version" in work_fields:
            item.properties["publish_version"] = work_fields["version"]
        
        # run the base class validation
        return super(MayaCameraPublishPlugin, self).validate(settings, item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        Any raised exceptions will indicate that the publish pass has failed and
        the publisher will stop execution.

        :param dict settings: The keys are strings, matching the keys returned
            in the :data:`settings` property. The values are
            :class:`~.processing.Setting` instances.
        :param item: The :class:`~.processing.Item` instance to validate.
        """

        # keep track of everything currently selected. we will restore at the
        # end of the publish metho  
        cur_selection = cmds.ls(selection=True)

        current_camera = item.properties["camera_name"]
        
        # get the path to create and publish
        publish_path = item.properties["publish_path"]

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)
        
        #get fram range
        start_frame = cmds.playbackOptions(q=True, min=True)
        end_frame = cmds.playbackOptions(q=True, max=True)
        
        if not cmds.attributeQuery('abc_start_frame', node=current_camera, exists=True):
            cmds.addAttr(current_camera, longName='abc_start_frame', attributeType='float')
            cmds.setAttr(current_camera+'.abc_start_frame', start_frame)
        
        #abc_export_cmd = 'FBXExport -f "%s" -s' % (publish_path.replace(os.path.sep, "/"),)
        if not cmds.referenceQuery(current_camera, isNodeReferenced=True):
            
            get_nameing_convention = [name for name in namings if name in current_camera]
            remove_naming_convension = current_camera.split(get_nameing_convention[0])
            try:
                
                cmds.rename(current_camera, remove_naming_convension[-1])
                abc_export_cmd = 'AbcExport -j "-frameRange %s %s -attr abc_start_frame -root %s -writeVisibility -file %s"' \
                            %(start_frame, end_frame, remove_naming_convension[-1], publish_path.replace(os.path.sep, "/"))
                self.logger.info("Executing command: %s" % abc_export_cmd)
                mel.eval(abc_export_cmd)
                cmds.rename(remove_naming_convension[-1], current_camera)
                
            except Exception as e:
                
                self.logger.error("Failed to export camera: %s" % e)
                return
            
        else:
            try:
                
                abc_export_cmd = 'AbcExport -j "-frameRange %s %s -attr abc_start_frame -root %s -writeVisibility -file %s"' \
                            %(start_frame, end_frame, current_camera, publish_path.replace(os.path.sep, "/"))
                self.logger.info("Executing command: %s" % abc_export_cmd)
                mel.eval(abc_export_cmd)
                
            except Exception as e:
                
                self.logger.error("Failed to export camera: %s" % e)
                return
            
        # set the publish type in the item's properties. the base plugin will
        # use this when registering the file with Shotgun
        item.properties["publish_type"] = "Alembic Cache"

        # Now that the path has been generated, hand it off to the
        super(MayaCameraPublishPlugin, self).publish(settings, item)

        # restore selection
        cmds.select(cur_selection)


def _session_path():
    """
    Return the path to the current session
    :return:
    """
    path = cmds.file(query=True, sn=True)

    if isinstance(path, unicode):
        path = path.encode("utf-8")

    return path


def _get_save_as_action():
    """
    Simple helper for returning a log action dict for saving the session
    """

    engine = sgtk.platform.current_engine()

    # default save callback
    callback = cmds.SaveScene

    # if workfiles2 is configured, use that for file save
    if "tk-multi-workfiles2" in engine.apps:
        app = engine.apps["tk-multi-workfiles2"]
        if hasattr(app, "show_file_save_dlg"):
            callback = app.show_file_save_dlg

    return {
        "action_button": {
            "label": "Save As...",
            "tooltip": "Save the current session",
            "callback": callback
        }
    }

class validationCheck_UI(QtWidgets.QMainWindow):
    
    def __init__(self, msg, camera):
       super(validationCheck_UI,self).__init__()
       self.msg = msg
       self.camera = camera
       self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle('FWX Publisher Warning: %s' %self.camera)
        self.setGeometry(400,1200, 820, 150)
        
        self.scroll = QtWidgets.QScrollArea()
        self.widget = QtWidgets.QWidget()
        self.vertical_layout = QtWidgets.QVBoxLayout()
        
        count = 0
        for msg, symbol in self.msg.iteritems():
            self.namingconvention_lbl_label_count = QtWidgets.QLabel(self)
            self.namingconvention_lbl_label_count.move(80, 5+ count)
            self.namingconvention_lbl_label_count.resize(500, 150)
            self.namingconvention_lbl_label_count.setStyleSheet("font-size: 15px")
            self.namingconvention_lbl_label_count.setText(symbol + "  " + msg)
            self.vertical_layout.addWidget(self.namingconvention_lbl_label_count)
            count = count + 20

        self.widget.setLayout(self.vertical_layout)
        self.scroll.setWidget(self.widget)
        self.scroll.setWidgetResizable(True)
        self.setCentralWidget(self.scroll)
        
        # This make window to appear   center
        frame = self.frameGeometry()
        centerpoint = QtWidgets.QDesktopWidget().availableGeometry().center()
        frame.moveCenter(centerpoint)
        self.move(frame.topLeft())
        
    
        
        