"restore autosave version and save as nk file"

import os

try:
    from PySide2.QtWidgets import QMessageBox
except ImportError:
    from PySide6.QtWidgets import QMessageBox

import nuke
import nukescripts


def restore_autosave(recent_file):
    "open autosave folder and save as plain nk file"
    if not nuke.scriptClose():
        return

    autosave_value = nuke.toNode("preferences")["AutoSaveName"].value()

    # use a temporary knob to evaluate autosave expression with correct file path
    # default is [firstof [value root.name] [getenv NUKE_TEMP_DIR]].autosave
    tmp_knob = nuke.EvalString_Knob("tmp_knob")
    tmp_knob.setValue(autosave_value.replace("[value root.name]", recent_file))

    autosave_file = tmp_knob.evaluate()

    # open Nuke's file chooser at the correct path, with autosave and backup set as filter
    # added . for manual line edit, because file chooser doesn't behave as expected
    file_name = nuke.getFilename(
        "Restore Autosave",
        f"*{os.path.splitext(autosave_file)[1]};*~",  # possibilty to have custom file extension
        f"{autosave_file.split('.nk')[0]}.",
        "script",
    )

    # cancelled getFilename action
    if not file_name:
        return

    nuke.scriptOpen(file_name)

    ask = QMessageBox(
        QMessageBox.Question,
        "Save File",
        "Save as New Version?",
    )
    ask.addButton("Save New", QMessageBox.YesRole)
    ask.addButton("Save This", QMessageBox.YesRole)
    ask.addButton("Cancel", QMessageBox.RejectRole)  # leaves autosave file open
    ask.setDefaultButton(ask.buttons()[0])
    ask.setEscapeButton(ask.buttons()[2])

    # set the root name to what it was autosaved from
    idx = file_name.find(".nk")  # .autosave and ~ behave differently
    nuke.root()["name"].setValue(file_name[: idx + 3])

    result = ask.exec()
    if result == 0:  # Save New
        nukescripts.script_version_up()
    elif result == 1:  # Save This
        nuke.scriptSave()


if __name__ == "__main__":
    # add this menu after "Open Recent Comp"
    file_menu = nuke.menu("Nuke").findItem("File")
    i = [e.name() for e in file_menu.items()].index("Open Recent Comp")

    autosave_menu = file_menu.addMenu("Restore Autosave From Recent", index=i + 1)
    autosave_menu.addCommand("@recent_file1", "restore_autosave(nuke.recentFile(1))")
    autosave_menu.addCommand("@recent_file2", "restore_autosave(nuke.recentFile(2))")
    autosave_menu.addCommand("@recent_file3", "restore_autosave(nuke.recentFile(3))")
    autosave_menu.addCommand("@recent_file4", "restore_autosave(nuke.recentFile(4))")
    autosave_menu.addCommand("@recent_file5", "restore_autosave(nuke.recentFile(5))")
    autosave_menu.addCommand("@recent_file6", "restore_autosave(nuke.recentFile(6))")
