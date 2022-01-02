# Namespace manager controls manipulating naming inside maya 

from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QFile
from PySide2 import QtWidgets
from PySide2.QtCore import Qt
import maya.cmds as cmds
import os


class NamespaceManager(QtWidgets.QMainWindow):
    
    
    def __init__(self):
        
        
        super(NamespaceManager,self).__init__()
        embedded_path_file_path = os.path.dirname(__file__)
        file = QFile(os.path.join(
                    embedded_path_file_path,
                    "namespace_manger_UI.ui"
                    ))
        loader = QUiLoader()
        self.window=loader.load(file)
        file.close()
        
        self.initiate_gui()
        self.__naming_convention = ''
        self.__apply_option = ''

    def initiate_gui(self):
        
        ''' Collect GUI elements from the UI file and apply in instance variables'''
        
        self.namespace_user_text = self.window.findChild(
                        QtWidgets.QLineEdit, 
                        "qlineedit_input_text"
                        )
        
        self.naming_convention_options = self.window.findChild(
                    QtWidgets.QGroupBox, 
                    "qgrpbox_select_naming"
                    )
        
        for naming_convention_option in \
                self.naming_convention_options.findChildren(QtWidgets.QRadioButton):
            naming_convention_option.toggled.connect(self.get_naming_convention)
        
        self.apply_naming_conventions = self.window.findChild(
                    QtWidgets.QGroupBox, 
                    "qgrpbox_apply"
                    )
        
        for apply_naming_convention in \
                    self.apply_naming_conventions.findChildren(QtWidgets.QRadioButton):
            apply_naming_convention.toggled.connect(self.get_apply_options)
        
        self.process_btn = self.window.findChild(QtWidgets.QPushButton, "qbtn_proceed")
        self.process_btn.clicked.connect(self.process_naming_convention)
    
    def get_naming_convention(self):

        ''' Get the text of the user selcted radio button text'''

        r = self.sender()
        if r.isChecked():
            self.__naming_convention = r.text()

    
    def get_apply_options(self):

        ''' Get the text of the user selcted radio button text'''

        r = self.sender()
        if r.isChecked():
            self.__apply_option = r.text()
            
    
    def validate(self):

        ''' Check all the fields and entries are made .
        If not raise Qmessagebox dialog to alert user'''
        
        if not self.__naming_convention or not self.__apply_option:
            QtWidgets.QMessageBox.warning(
                        self,
                        'FWX Warning',
                        'Please Select Given Options'
            )
            return False
        
        elif not self.namespace_user_text.text():
            QtWidgets.QMessageBox.warning(
                        self,
                        'FWX Warning',
                        'Please Enter Namespace'
            )
            return False

        else:      
            return True
            
        pass

    def process_naming_convention(self):
        
        ''' Gather all the user selection and input make the namespace'''
        
        
        if self.validate():
            
            name = self.__naming_convention + '_' + self.namespace_user_text.text()
            
            if self.__apply_option == 'Only Selected Nodes':
                
                get_nodes = cmds.ls( sl=True ) 
                for node in get_nodes:
                    file_reference = cmds.referenceQuery(node, filename=True)
                    cmds.file(file_reference, edit=True, namespace= name)
                
                self.window.close()
            
            elif self.__apply_option == 'All nodes':
                
                get_all_namespace_filepath= cmds.file(query=True, l=True)
                for namespace_filepath in get_all_namespace_filepath:
                    if not namespace_filepath.endswith('.ma'):
                        cmds.file(namespace_filepath, edit=True, namespace=name)

                self.window.close()
            
win = NamespaceManager()
win.window.show()

