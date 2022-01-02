# SGTK_maya_publish_hooks
An Maya custom publisher hooks for mesh and camera. The publisher sucsess only after all the validations passes in a Shot level.

A maya string attribute created into the root of group node and assigned the start frame of the maya playblack to that attribute. 
publishmesh.py and publishcamera.py automatically convert the alembic of the root group node into the published path and made a entry in the Shotgrid.


If suppose Matchmove alembic tk-maya-loader2.py parse the alembic file startframe and set it into the maya playblack start frame 

