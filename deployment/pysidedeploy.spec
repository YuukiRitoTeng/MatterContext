[app]
title = MatterContext
project_dir = ..
input_file = deployment/MatterContext.py
exec_directory = artifacts/package-smoke
project_file =
icon =

[python]
python_path = python
packages = Nuitka,ordered-set,zstandard

[qt]
qml_files =
excluded_qml_plugins =
modules = Core,Gui,Widgets
plugins =

[nuitka]
macos.permissions =
mode = onefile
extra_args = --quiet --noinclude-qt-translations --assume-yes-for-downloads
