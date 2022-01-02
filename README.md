# SGTK_maya_publish_hooks

An Maya custom publisher hooks for mesh and camera. The publisher sucsess only after all the validations passes in a Shot level.

<ins>publishmesh.py and publishcamera.py </ins>
 
Collects all the cameras and meshes in the maya files and automatically convert the alembic of the root group node into the published path and made a entry in the Shotgrid.
This scripts also includes a maya string attribute in the root of group node and assigns the starting frame of the maya playblack to that attribute. 

<ins>tk-maya-loader2.py</ins>

3dequalizer and maya exported alembic datas may have different starting frame of each shots.  This custom hook parse the alembic file startframe , check the maya playback startframe with the parsed alembic frame value. if not matches, the hook just replaces the alembic node offset value with the parsed value.

## SGTK Hooks In Action

[![IMAGE ALT TEXT HERE](https://img.youtube.com/vi/g71p3cnA8gc/0.jpg)](https://www.youtube.com/watch?v=g71p3cnA8gc)
