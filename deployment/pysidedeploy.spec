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
extra_args = --quiet --noinclude-qt-translations --assume-yes-for-downloads --include-package=sqlalchemy.dialects.sqlite --include-package=matter_context.storage.migrations --include-package-data=matter_context.storage.migrations:*.mako --include-data-files=src/matter_context/storage/migrations/env.py=matter_context/storage/migrations/env.py --include-data-files=src/matter_context/storage/migrations/versions/*.py=matter_context/storage/migrations/versions/ --nofollow-import-to=sqlalchemy.dialects.mssql --nofollow-import-to=sqlalchemy.dialects.mysql --nofollow-import-to=sqlalchemy.dialects.oracle
