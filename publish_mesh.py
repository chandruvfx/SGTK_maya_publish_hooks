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
import re
import maya.cmds as cmds
import maya.mel as mel
import sgtk
from sgtk.platform.qt5 import QtWidgets

GEO_CONSTANT_ENTITIES = [ '_MMtrackalembic_', '_MMtrackfbx_', 
                          '_fxgeo_', '_lgtgeo_', '_RAtrackalembic_',
                          '_animgeo_', '_layoutgeo_' ]

namings = [ 'MMtrackalembic_', 
            'MMtrackfbx_', 
            'fxgeo_', 'lgtgeo_',
            'RAtrackalembic_', 'animgeo_', 
            'layoutgeo_']
        
maya_native_geo_names = [ 'pSphere', 'pCube', 'pCylinder', 'pCone',
                          'pTorus', 'pPlane', 'pDisc', 'pPlatonic',
                          'pPyramid', 'pPrism', 'pPipe', 'pHelix',
                          'pGear', 'pSolid', 'pSuperShape'
                        ]
                            
grp_name = [ 'group' ]
# this method returns the evaluated hook base class. This could be the Hook
# class defined in Toolkit core or it could be the publisher app's base publish
# plugin class as defined in the configuration.
HookBaseClass = sgtk.get_hook_baseclass()


class MayaShaderPublishPlugin(HookBaseClass):
    """
    This class defines the required interface for a publish plugin. Publish
    plugins are responsible for operating on items collected by the collector
    plugin. Publish plugins define which items they will operate on as well as
    the execution logic for each phase of the publish process.
    """

    ############################################################################
    # Plugin properties

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does (:class:`str`).

        The string can contain html for formatting for display in the UI (any
        html tags supported by Qt's rich text engine).
        """
        return """
        <p>
        This plugin handles exporting and publishing Maya shader networks.
        Collected mesh shaders are exported to disk as .ma files that can
        be loaded by artists downstream. This is a simple, example
        implementation and not meant to be a robust, battle-tested solution for
        shader or texture management on production.
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
        plugin_settings = super(MayaShaderPublishPlugin, self).settings or {}

        # settings specific to this class
        shader_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published shader networks. "
                               "Should correspond to a template defined in "
                               "templates.yml.",
            }
        }

        # update the base settings
        plugin_settings.update(shader_publish_settings)

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
        # NOTE: this matches the item type defined in the collector.
        return ["maya.session.mesh"]

    ############################################################################
    # Publish processing methods

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

        # by default we will accept the item. if any of the checks below fail,
        # we'll set this to False.
        accepted = True

        # a handle on the instance of the publisher app
        publisher = self.parent

        # extract the value of the template configured for this instance
        template_name = settings["Publish Template"].value

        # ensure a work file template is available on the parent maya session
        # item.
        work_template = item.parent.properties.get("work_template")
        if not work_template:
            self.logger.debug(
                "A work template is required for the session item in order to "
                "publish session geometry. Not accepting session geom item."
            )
            accepted = False

        # ensure the publish template is defined and valid
        publish_template = publisher.get_template_by_name(template_name)
        self.logger.debug("TEMPLATE NAME: " + str(template_name))
        if not publish_template:
            self.logger.debug(
                "A valid publish template could not be determined for the "
                "session geometry item. Not accepting the item."
            )
            accepted = False

        # we've validated the publish template. add it to the item properties
        # for use in subsequent methods
        item.properties["publish_template"] = publish_template

        # because a publish template is configured, disable context change. This
        # is a temporary measure until the publisher handles context switching
        # natively.
        item.context_change_allowed = False

        return {
            "accepted": accepted,
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
            self.logger.error(
                error_msg,
                extra=_get_save_as_action()
            )
            raise Exception(error_msg)

        # get the normalized path. checks that separators are matching the
        # current operating system, removal of trailing separators and removal
        # of double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(path)

        object_name = item.properties["object"]
        
        error_msg = {}
                
        if any( native_names in object_name for native_names in maya_native_geo_names):
            cmds.select(object_name, add=True)
            txt = "Maya native geometry name exists <font color='red'>%s</font> " %object_name
            error_msg[txt] = u"\u274c"
        
        
        if any( object_name.startswith(name) for name in namings) == False:
                cmds.select(object_name, add=True)
                txt = "Geometry name <font color='red'>%s</font> not starting with any naming conventions " %object_name
                error_msg[txt] = u"\u274c"

        #for nodes in cmds.ls(assemblies=True):
        nodes = object_name
        if cmds.listRelatives(nodes , shapes=1, type='mesh'):
            cmds.select(nodes, add=True)
            txt = "Add <font color='red'>%s</font> in naming convension based group node" %nodes
            error_msg[txt] = u"\u274c"
        
        for native_names in grp_name:
            if re.search('^%s' %native_names, object_name) is not None:
                cmds.select(object_name, add=True)
                txt = "Maya native geometry name exists <font color='red'>%s</font> " %object_name
                error_msg[txt] = u"\u274c"
                break
            
        if not cmds.listRelatives(nodes , shapes=1):
            check_entity = any( entities in nodes for entities in namings )
        
            if not check_entity:
                cmds.select(nodes, add=True)
                txt = "Naming convetion not found for node  <font color='red'>%s</font>" %nodes
                error_msg[txt] = u"\u274c"

        if any( native_names == object_name for native_names in namings):
            cmds.select(object_name, add=True)
            txt = "Only naming convention notation specified. Provide extended naming for <font color='red'>%s</font> " %object_name
            error_msg[txt] = u"\u274c"
        
        if object_name.startswith('_') or object_name.endswith('_'):
            cmds.select(object_name, add=True)
            txt = "Node Name starts or ends with underscore for <font color='red'>%s</font> " %object_name
            error_msg[txt] = u"\u274c"
        
        for names in cmds.listRelatives(object_name, ad=True):
            for name in maya_native_geo_names:
                if re.search('^%s' %name, names) is not None:
                    txt = "Maya native geometry name exists <font color='red'>%s</font> inside <font color='red'>%s</font>" %(names, object_name)
                    error_msg[txt] = u"\u274c"
                    objects = cmds.listRelatives(object_name, ad=True, fullPath= True)
                    for obj in objects:
                        parent_node = cmds.listRelatives(obj, p=True, fullPath= True)
                        cmds.select(parent_node, add=True)
                        
            if names.startswith('_') or names.endswith('_'):
                cmds.select(names, add=True)
                txt = "Node Name starts or ends with underscore for <font color='red'>%s</font> " %names
                error_msg[txt] = u"\u274c"

        if error_msg != {}:
            app = QtWidgets.QApplication.instance()
            gui = validationCheck_UI(error_msg)
            gui.show()
            app.exec_()

        object_name = object_name.split(":")[0]

        # check that there is still geometry in the scene:
        if (not cmds.ls(assemblies=True) or
            not cmds.ls(object_name, dag=True, type="mesh")):
            '''error_msg = (
                "Validation failed because there are no meshes in the scene "
                "to export shaders for. You can uncheck this plugin or create "
                "meshes with shaders to export to avoid this error."
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)'''

        # get the configured work file template
        work_template = item.parent.properties.get("work_template")
        publish_template = item.properties.get("publish_template")

        # get the current scene path and extract fields from it using the work
        # template:
        work_fields = work_template.get_fields(path)
        
        # we want to override the {name} token of the publish path with the
        # name of the object being exported. get the name stored by the
        # collector and remove any non-alphanumeric characters
        object_display = re.sub(r'[\W_]+', '', object_name)
        work_fields["name"] = object_display
    
        # set the display name as the name to use in SG to represent the publish
        #item.properties["publish_name"] = object_display

        # ensure the fields work for the publish template
        missing_keys = publish_template.missing_keys(work_fields)
        if missing_keys:
            error_msg = "Work file '%s' missing keys required for the " \
                        "publish template: %s" % (path, missing_keys)
            self.logger.error(error_msg)
            raise Exception(error_msg)

        # create the publish path by applying the fields. store it in the item's
        # properties. Also set the publish_path to be explicit.
        item.properties["path"] = publish_template.apply_fields(work_fields)
        item.properties["publish_path"] = item.properties["path"]
        
        #item.properties["path"] = item.properties["path"].replace(object_display, object_name)
        item.properties["publish_path"] = item.properties["publish_path"].replace(object_display, object_name)
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
        
        item.properties["path"] = item.properties["path"].replace(object_display, object_name)
        item.properties["publish_path"] = item.properties["publish_path"].replace(object_display, object_name)
        item.properties["publish_name"] =  os.path.basename(item.properties["publish_path"])
                  
        if "version" in work_fields:
            item.properties["publish_version"] = work_fields["version"]
             
        # run the base class validation
        return super(MayaShaderPublishPlugin, self).validate(
            settings, item)


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

        publisher = self.parent

        # get the path to create and publish
        publish_path = item.properties["path"]

        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        publisher.ensure_folder_exists(publish_folder)

        mesh_object = item.properties["object"]
        
        alembic_args = ''
        for meshes in cmds.ls(assemblies=True):

            if not cmds.ls(meshes, dag=True, type="mesh"):
                # ignore non-meshes
                continue
            
            if mesh_object == meshes:
                
                # find the animated frame range to use:
                start_frame = int(cmds.playbackOptions(q=True, min=True))
                end_frame = int(cmds.playbackOptions(q=True, max=True))
                
                
                if not cmds.attributeQuery('abc_start_frame', node=meshes, exists=True):
                        cmds.addAttr(meshes, longName='abc_start_frame', attributeType='float')
                        cmds.setAttr(meshes+'.abc_start_frame', start_frame)
                
                if not cmds.referenceQuery(meshes, isNodeReferenced=True):
                    
                    get_nameing_convention = [name for name in namings if name in meshes]
                    remove_naming_convension = meshes.split(get_nameing_convention[0])

                    cmds.rename(meshes, remove_naming_convension[-1])
                    try:
                        alembic_args = 'AbcExport -j "-renderableOnly -writeFaceSets -uvWrite -fr %d %d -attr abc_start_frame -root %s -file %s"' \
                                    %(start_frame, end_frame, remove_naming_convension[-1], publish_path.replace("\\", "/"))
                        self.logger.info("Executing command: %s" % alembic_args)
                        mel.eval(alembic_args)
                        cmds.rename(remove_naming_convension[-1], meshes)
                        
                    except Exception as e:
                        
                        self.logger.error("Failed to export Geometry: %s" % e)
                        return
                
                else:
                    
                    try:
                        alembic_args = 'AbcExport -j "-renderableOnly -writeFaceSets -uvWrite -fr %d %d -attr abc_start_frame -root %s -file %s"' \
                                    %(start_frame, end_frame, meshes, publish_path.replace("\\", "/"))
                        self.logger.info("Executing command: %s" % alembic_args)
                        mel.eval(alembic_args)
                        
                    except Exception as e:
                        
                        self.logger.error("Failed to export Geometry: %s" % e)
                        return


        # set the publish type in the item's properties. the base plugin will
        # use this when registering the file with Shotgun
        item.properties["publish_type"] = "Alembic Cache"

        # Now that the path has been generated, hand it off to the base publish
        # plugin to do all the work to register the file with SG
        super(MayaShaderPublishPlugin, self).publish(settings, item)

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
    
    def __init__(self, msg):
       super(validationCheck_UI,self).__init__()
       self.msg = msg
       self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle('FWX Publisher Warning ')
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