"""
This is a CSV File exporter for Hiero from within ShotgridDesktop
It sets up the csv file with basic information on the shot, values specific to one shot still need to be added manually
it exports in a structure where each shot is listed 3x for 3 different versions (for example qc, grading etc.)
"""

import re
import os
import csv
import traceback

import hiero.core

from hiero.ui import TaskUIBase, FnTaskUIFormLayout

from hiero.core import FnResolveTable
from hiero.core.FnExporterBase import mediaSourceExportReadPath, mediaSourceExportFileHead
from hiero.exporters.FnExportKeywords import kFileBaseKeyword, kFileHeadKeyword, KeywordTooltips

from tank.platform.qt import QtGui, QtCore

from tk_hiero_export import ShotgunHieroObjectBase


class CSVExportTrackTask:
    def __init__(self, parent, track, trackItems):
        self._parent = parent
        self._track = track
        self._trackItems = trackItems
        self._trackItemIndex = 0
        self._fps = parent._fps
        self._edits = []

    def edits(self):
        return self._edits

    def createRow(self, trackItem):
        edit = []
        versionNames = []
        start = int(trackItem.handleInLength()) + int(trackItem.source().sourceIn())
        duration = int(trackItem.sourceDuration())
        slate = self._parent._preset.properties()["slate"]

        start -= self._parent._preset.properties()["handleLength"]
        duration += 2 * self._parent._preset.properties()["handleLength"]

        if start < 0:
            duration += start
            start = 0

        if self._parent.resolveFromTrackItem(trackItem, "versionName"):
            name = self._parent.resolveFromTrackItem(trackItem, "versionName")
        else:
            name = trackItem.source().name()

        if self._parent.resolveFromTrackItem(trackItem, "linkName"):
            link = self._parent.resolveFromTrackItem(trackItem, "linkName")
        else:
            link = trackItem.name()

        if self._parent.resolveFromTrackItem(trackItem, "scopeWork"):
            work = self._parent.resolveFromTrackItem(trackItem, "scopeWork")
        else:
            work = ""

        if self._parent.resolveFromTrackItem(trackItem, "shotType"):
            shot = self._parent.resolveFromTrackItem(trackItem, "shotType")
        else:
            shot = ""

        if self._parent.resolveFromTrackItem(trackItem, "vendor"):
            vendor = self._parent.resolveFromTrackItem(trackItem, "vendor")
        else:
            vendor = ""

        if self._parent.resolveFromTrackItem(trackItem, "submitFor"):
            sub = self._parent.resolveFromTrackItem(trackItem, "submitFor")
        else:
            sub = "WIP"

        if self._parent.resolveFromTrackItem(trackItem, "submitNote"):
            subN = self._parent.resolveFromTrackItem(trackItem, "submitNote")
        else:
            subN = "WIP"

        versionNames.append(name + ".mov")
        versionNames.append(name + ".[{}-{}].exr".format(start - slate, start + duration - 1))
        versionNames.append(
            name + "_{}.mov".format(self._parent._preset.properties().get("versionSuffix", "h264"))
        )

        cutIn = int(trackItem.handleInLength()) + int(trackItem.source().sourceIn())
        cutOut = (
            int(trackItem.handleInLength())
            + int(trackItem.source().sourceIn())
            + int(trackItem.sourceDuration())
            - 1
        )

        exportPath = os.path.dirname(self._parent.resolvedExportPath())
        basePath = os.path.basename(exportPath)

        for item in versionNames:
            entry = [basePath]  # Delivery
            entry.append(item)  # Version Name
            entry.append(link)  # Link
            entry.append(work)  # VFX Scope of Work
            entry.append(shot)  # Primary Shot Type
            entry.append(vendor)  # Vendor
            entry.append(sub)  # Submitting For
            entry.append(subN)  # Submission Note
            entry.append(str(cutIn))  # Cut In
            entry.append(str(cutOut))  # Cut Out

            edit.append(entry)

        self._edits.append(edit)

    def taskStep(self):
        if len(self._trackItems) == 0:
            return False

        trackItem = self._trackItems[self._trackItemIndex]
        self.createRow(trackItem)

        self._trackItemIndex += 1

        return self._trackItemIndex < len(self._trackItems)


class CSVFileWriter:
    def __init__(self, parent):
        self._parent = parent
        self._edits = []

    def addEdits(self, edits):
        self._edits += edits

    def write(self, filePath):
        edits = self._edits
        directory = os.path.dirname(filePath)
        # util.filesystem.makeDirs(directory)
        if not os.path.exists(directory):
            os.makedirs(directory)
        try:
            # check export root exists
            with open(filePath, "w+") as csv_file:
                writer = csv.writer(
                    csv_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
                )
                writer.writerow(
                    [
                        "Delivery",
                        "Version Name",
                        "Link",
                        "VFX Scope of Work",
                        "Primary Shot Type",
                        "Vendor",
                        "Submitting For",
                        "Submission Note",
                        "Cut In",
                        "Cut Out",
                    ]
                )
                for edit in edits:
                    writer.writerows(edit)
        except IOError:
            self._parent.setError(traceback.format_exc())


# Some helpers for the per-shot token resolution.
def _filenameFromTrackItem(trackItem):
    filename = mediaSourceExportReadPath(trackItem.source().mediaSource(), False)
    return os.path.basename(filename)


def _filebaseFromTrackItem(trackItem):
    filename = _filenameFromTrackItem(trackItem)
    return os.path.splitext(filename)[0]


def _fileheadFromTrackItem(trackItem):
    source = trackItem.source().mediaSource()
    return mediaSourceExportFileHead(source)


def _fileextFromTrackItem(trackItem):
    filename = _filenameFromTrackItem(trackItem)
    return os.path.splitext(filename)[1]


class CSVExportTask(ShotgunHieroObjectBase, hiero.core.TaskBase):
    def __init__(self, initDict):
        """Initialize"""
        self._currentTrack = None
        hiero.core.TaskBase.__init__(self, initDict)
        self._fps = self._sequence.framerate().toInt()
        self._trackTasks = []
        self._trackTaskIndex = 0

        self._stepTotal = 0
        self._stepCount = 0

    def currentTrackName(self):
        if self._currentTrack:
            return self._currentTrack.name()
        else:
            return self._sequence.videoTracks()[0].name()

    def resolveFromTrackItem(self, trackItem, presetName):
        resolvedString = None
        propertyString = self._preset.properties()[presetName]
        resolver = CSVExportTask.ShotResolveTable(trackItem)
        try:
            resolvedString = resolver.resolve(propertyString)
        except NotImplementedError:
            self.setWarning(traceback.format_exc())
        except Exception as e:
            error = "CSVExportTask failed to resolve '{0}' value: '{1}'\n".format(
                presetName, propertyString
            )
            error = error + "\nValid tokens are: " + str(resolver.entries()) + "\n"
            error = error + str(e)
            self.setError(error)
            raise
        return resolvedString

    def trackItemEditName(self, trackItem):
        editName = self.resolveFromTrackItem(trackItem, "versionName")
        if not editName:
            clip = trackItem.source()
            if clip:
                source = clip.mediaSource()
                if source and hiero.core.Keys.kSourceReelId in source.metadata():
                    editName = source.metadata()[hiero.core.Keys.kSourceReelId]
        if not editName:
            editName = trackItem.name()
        editName = re.sub(r"[\W_]+", "", editName)  # make it legal
        if self._preset.properties()["truncate"]:
            editName = editName[:8]
        return editName

    def startTask(self):
        try:
            for track in self._sequence.videoTracks():
                trackItems = []
                for trackitem in track:
                    trackItems.append(trackitem)
                    self._stepTotal += 1

                # We shouldn't get passed any empty tracks but if we do, don't create a task for them
                if trackItems:
                    task = CSVExportTrackTask(self, track, trackItems)
                    self._trackTasks.append(task)
        except Exception:
            self.setError(traceback.format_exc())

    def exportFilePath(self):
        exportPath = self.resolvedExportPath()
        # Check file extension
        if not exportPath.lower().endswith(".csv"):
            exportPath += ".csv"
        return exportPath

    def taskStep(self):
        try:
            trackTask = self._trackTasks[self._trackTaskIndex]
            self._currentTrack = trackTask._track

            if not trackTask.taskStep():
                path = self.exportFilePath()

                fileWriter = CSVFileWriter(self)
                fileWriter.addEdits(trackTask.edits())
                fileWriter.write(path)
                self._trackTaskIndex += 1

            self._stepCount += 1
            return self._stepCount < self._stepTotal
        except NotImplementedError:
            self.setWarning(traceback.format_exc())
            return False
        except Exception:
            self.setError(traceback.format_exc())
            return False

    def progress(self):
        if self._stepTotal == 0:
            return 0.0
        else:
            return float(self._stepCount / self._stepTotal)

    # Keyword resolver for tokens relevant to shots.
    # This is a bit of a hack, using the genericness of the ResolveTable to eval using functions on TrackItems.
    # Keep this in the CSVExportTask for now but it might be good to move to FnResolveTable for general use.
    # but keeping it for now for backwards compatibility with pre-existing CSVExportTask presets.
    class ShotResolveTable(FnResolveTable.ResolveTable):
        def __init__(self, trackItem):
            FnResolveTable.ResolveTable.__init__(self)
            self._trackItem = trackItem

            # Some shots may not have a Clip, so just return None to let the resolver base handle it as it does with any other.
            # If this list is changed, be sure to update the text for the tooltips on the QLineEdit widgets in FnCSVExportUI.py.
            self.addResolver(
                "{shot}",
                "Name of the TrackItem being processed",
                lambda keyword, trackItem: trackItem.name(),
            )
            self.addResolver(
                "{shotCode}",
                "Shot as in Shotgun",
                lambda keyword, trackItem: self.__getShotCode(trackItem.source().name()),
            )
            self.addResolver(
                "{clip}",
                "Name of the source Media clip being processed",
                lambda keyword, trackItem: trackItem.source().name()
                if trackItem.source()
                else None,
            )
            self.addResolver(
                "{track}",
                "Name of the track being processed",
                lambda keyword, trackItem: trackItem.parent().name()
                if trackItem.parent()
                else None,
            )
            self.addResolver(
                "{sequence}",
                "Name of the Sequence being processed",
                lambda keyword, trackItem: trackItem.parent().parent().name()
                if trackItem.parent().parent()
                else None,
            )
            self.addResolver(
                "{fps}",
                "Frame rate of the Sequence",
                lambda keyword, trackItem: str(trackItem.parent().parent().framerate())
                if trackItem.parent().parent()
                else None,
            )
            self.addResolver(
                "{filename}",
                "File name part of the TrackItem's Source file.",
                lambda keyword, trackItem: _filenameFromTrackItem(trackItem),
            )
            self.addResolver(
                kFileBaseKeyword,
                KeywordTooltips[kFileBaseKeyword],
                lambda keyword, trackItem: _filebaseFromTrackItem(trackItem),
            )
            self.addResolver(
                "{fileext}",
                "File name extension of the TrackItem's Source file.",
                lambda keyword, trackItem: _fileextFromTrackItem(trackItem),
            )
            self.addResolver(
                kFileHeadKeyword,
                KeywordTooltips[kFileHeadKeyword],
                lambda keyword, trackItem: _fileheadFromTrackItem(trackItem),
            )

        def __getShotCode(self, name):
            parts = name.split("_")
            if len(parts) > 3:
                return "_".join(parts[1:4])
            else:
                return name

        def resolve(self, value):
            return FnResolveTable.ResolveTable.resolve(self, self._trackItem, value)


class CSVExportPreset(ShotgunHieroObjectBase, hiero.core.TaskPresetBase):
    def __init__(self, name, properties):
        """Initialise presets to default values"""
        hiero.core.TaskPresetBase.__init__(self, CSVExportTask, name)
        self._properties = {}
        self._name = name

        # Set any preset defaults here
        self.properties()["versionName"] = "{clip}"
        self.properties()["versionSuffix"] = "h264"
        self.properties()["linkName"] = "{shot}"
        self.properties()["scopeWork"] = ""
        self.properties()["shotType"] = ""
        self.properties()["vendor"] = "Celluloid"
        self.properties()["submitFor"] = "WIP"
        self.properties()["submitNote"] = ""
        self.properties()["handleLength"] = 0
        self.properties()["slate"] = 0

        # Update preset with loaded data
        self.properties().update(properties)

    def supportedItems(self):
        return hiero.core.TaskPresetBase.kSequence

    def addCustomResolveEntries(self, resolver):
        resolver.addResolver(
            "{track}",
            "Name of the track being processed",
            lambda keyword, task: task.currentTrackName(),
        )

    def supportsAudio(self):
        return True


class CSVExportUI(ShotgunHieroObjectBase, TaskUIBase):
    def __init__(self, preset):
        """Initialize"""
        TaskUIBase.__init__(self, CSVExportTask, preset, "CSV Exporter")

    def initializeUI(self, widget):
        self.parentType()._allTasks = []
        TaskUIBase.initializeUI(self, widget)

    def propertyChanged(self, key, field):
        self._preset.properties()[key] = field.text()

    def handleLengthChanged(self):
        if self._handleLineEdit.text() == "":
            self._preset.properties()["handleLength"] = 0
        else:
            self._preset.properties()["handleLength"] = int(self._handleLineEdit.text())

    def slateCheckBoxChanged(self, state):
        if state == QtCore.Qt.Checked:
            self._preset.properties()["slate"] = 1
        else:
            self._preset.properties()["slate"] = 0

    def populateUI(self, widget, exportTemplate):
        formLayout = FnTaskUIFormLayout.TaskUIFormLayout()
        widget.layout().addLayout(formLayout)

        kTrackItemTokensToolTip = "Valid tokens are: {shot}, {shotCode}, {clip}, {track}, {sequence}, {fps}, {filename}, {filebase}, {fileext}, {filehead}"
        # generalToolTip = 'Define the {} for all entries.\n' + kTrackItemTokensToolTip
        kVersionNameToolTip = (
            "Define the text for each version name in the CSV. If not set, the name of the clip will be set.\n"
            + kTrackItemTokensToolTip
        )
        kVersionSuffixToolTip = "Define a suffix for one of the mov entries (mp4, h264 etc.)"
        kLinkNameToolTip = (
            "Define the text for each link in the CSV. If not set, the name of the shot will be set.\n"
            + kTrackItemTokensToolTip
        )
        kSubmitForToolTip = (
            "Define the purpose what the CSV is submitted for. If not set, WIP will be set instead.\n"
            + kTrackItemTokensToolTip
        )
        kHandleToolTip = "Define the number of frames that shall be added to the beginning and the end of each clip. (Defaults to 0)"

        # Version Name
        self._versionNameLineEdit = QtGui.QLineEdit()
        self._versionNameLineEdit.setToolTip(kVersionNameToolTip)
        self._versionNameLineEdit.setText(self._preset.properties()["versionName"])
        self._versionNameLineEdit.textChanged.connect(
            lambda: self.propertyChanged("versionName", self._versionNameLineEdit)
        )

        self._versionNameSuffix = QtGui.QLineEdit()
        self._versionNameSuffix.setToolTip(kVersionSuffixToolTip)
        self._versionNameSuffix.setText(self._preset.properties()["versionSuffix"])
        self._versionNameSuffix.textChanged.connect(
            lambda: self.propertyChanged("versionSuffix", self._versionNameSuffix)
        )

        # Link
        self._linkNameLineEdit = QtGui.QLineEdit()
        self._linkNameLineEdit.setToolTip(kLinkNameToolTip)
        self._linkNameLineEdit.setText(self._preset.properties()["linkName"])
        self._linkNameLineEdit.textChanged.connect(
            lambda: self.propertyChanged("linkName", self._linkNameLineEdit)
        )

        # VFX Scope of Work
        self._scopeWorkLineEdit = QtGui.QLineEdit()
        # self._scopeWorkLineEdit.setToolTip(generalToolTip.format('Scope of Work'))
        self._scopeWorkLineEdit.setText(self._preset.properties()["scopeWork"])
        self._scopeWorkLineEdit.textChanged.connect(
            lambda: self.propertyChanged("scopeWork", self._scopeWorkLineEdit)
        )

        # Primary Shot Type
        self._shotTypeLineEdit = QtGui.QLineEdit()
        # self._shotTypeLineEdit.setToolTip(generalToolTip.format('Primary Shot Type'))
        self._shotTypeLineEdit.setText(self._preset.properties()["shotType"])
        self._shotTypeLineEdit.textChanged.connect(
            lambda: self.propertyChanged("shotType", self._shotTypeLineEdit)
        )

        # Vendor
        self._vendorLineEdit = QtGui.QLineEdit()
        # self._vendorLineEdit.setToolTip(generalToolTip.format('Vendor'))
        self._vendorLineEdit.setText(self._preset.properties()["vendor"])
        self._vendorLineEdit.textChanged.connect(
            lambda: self.propertyChanged("vendor", self._vendorLineEdit)
        )

        # Submitting For
        self._submitForLineEdit = QtGui.QLineEdit()
        self._submitForLineEdit.setToolTip(kSubmitForToolTip)
        self._submitForLineEdit.setText(self._preset.properties()["submitFor"])
        self._submitForLineEdit.textChanged.connect(
            lambda: self.propertyChanged("submitFor", self._submitForLineEdit)
        )

        # Submission Note
        self._submitNoteLineEdit = QtGui.QLineEdit()
        # self._submitNoteLineEdit.setToolTip(generalToolTip.format('Submission Note'))
        self._submitNoteLineEdit.setText(self._preset.properties()["submitNote"])
        self._submitNoteLineEdit.textChanged.connect(
            lambda: self.propertyChanged("submitNote", self._submitNoteLineEdit)
        )

        # Handles for Cut In and Cut Out
        self._handleLineEdit = QtGui.QLineEdit()
        self._handleLineEdit.setToolTip(kHandleToolTip)
        self._handleLineEdit.setValidator(QtGui.QIntValidator(self._handleLineEdit))
        self._handleLineEdit.setText(str(self._preset.properties()["handleLength"]))
        self._handleLineEdit.textChanged.connect(self.handleLengthChanged)

        slateCheckBox = QtGui.QCheckBox()
        slateCheckBox.setToolTip("Add a frame at the beginning, used as a slate.")
        if self._preset.properties()["slate"]:
            slateCheckBox.setCheckState(QtCore.Qt.Checked)
        else:
            slateCheckBox.setCheckState(QtCore.Qt.Unchecked)
        slateCheckBox.stateChanged.connect(self.slateCheckBoxChanged)

        _delivery = QtGui.QLineEdit("will be set automatically")
        _delivery.setEnabled(False)

        # Add Checkbox to layout
        formLayout.addRow("Delivery", _delivery)
        formLayout.addRow("Version Name", self._versionNameLineEdit)
        formLayout.addRow("Version Suffix", self._versionNameSuffix)
        formLayout.addRow("Link", self._linkNameLineEdit)
        formLayout.addRow("VFX Scope of Work", self._scopeWorkLineEdit)
        formLayout.addRow("Primary Shot Type", self._shotTypeLineEdit)
        formLayout.addRow("Vendor", self._vendorLineEdit)
        formLayout.addRow("Submitting For", self._submitForLineEdit)
        formLayout.addRow("Submission Note", self._submitNoteLineEdit)
        formLayout.addRow("", QtGui.QLabel(""))
        formLayout.addRow("Handle Length", self._handleLineEdit)
        formLayout.addRow("create Slate", slateCheckBox)

